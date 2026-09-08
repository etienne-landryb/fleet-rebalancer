"""Run one full graph tick for testing.

Usage:
    conda activate rebalancer
    python scripts/run_tick.py
    python scripts/run_tick.py --approve    # auto-approve the plan
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from rebalancer.agents.graph import build_graph

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one rebalancer tick")
    parser.add_argument(
        "--approve", action="store_true", help="Auto-approve the plan"
    )
    args = parser.parse_args()

    graph = build_graph()
    checkpointer = MemorySaver()
    app = graph.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "tick-1"}}

    print("\n--- Running graph tick ---\n")
    result = None
    initial_input = {"decision_trace": [], "llm_calls": 0}
    for event in app.stream(initial_input, config=config):
        for node_name, node_output in event.items():
            logger.info("Node [%s] completed", node_name)
            result = node_output

    # Check if we hit an interrupt (human_approval)
    state = app.get_state(config)
    if state.next:
        print(f"\nGraph paused at: {state.next}")
        if "do_approval" in state.next:
            interrupt_data = state.tasks
            if interrupt_data:
                for task in interrupt_data:
                    if hasattr(task, "interrupts") and task.interrupts:
                        print("\n--- Plan for review ---")
                        for intr in task.interrupts:
                            data = intr.value
                            if isinstance(data, dict):
                                print(data.get("plan", ""))
                                print()
                                print(data.get("impact", ""))
                                print()
                                print(data.get("work_orders", ""))

            if args.approve:
                decision = "approved"
                print(f"\nAuto-approving: {decision}")
            else:
                decision = input("\nApprove or reject? [approved/rejected]: ").strip()

            for event in app.stream(
                Command(resume=decision), config=config
            ):
                for node_name, node_output in event.items():
                    logger.info("Node [%s] completed", node_name)
                    result = node_output

    final_state = app.get_state(config)
    values = final_state.values
    print("\n--- Tick complete ---")
    print(f"LLM calls: {values.get('llm_calls', 0)}")
    print(f"Trigger: {values.get('trigger', False)}")
    print(f"Approval: {values.get('approval', 'n/a')}")
    print(f"Trace: {' -> '.join(values.get('decision_trace', []))}")


if __name__ == "__main__":
    main()
