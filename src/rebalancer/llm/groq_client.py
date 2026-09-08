import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    @abstractmethod
    def explain(self, plan_summary: str, impact_summary: str) -> str: ...


@dataclass
class GroqClient(LLMClient):
    api_key: str
    model: str = "openai/gpt-oss-20b"
    max_tokens: int = 512

    def explain(self, plan_summary: str, impact_summary: str) -> str:
        try:
            from groq import Groq

            client = Groq(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a fleet dispatcher assistant. Write concise "
                            "driver work orders based on the rebalancing plan. "
                            "Include: which stations to visit, how many bikes to "
                            "pick up or drop off at each, and the route order. "
                            "Keep it under 200 words."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Plan:\n{plan_summary}\n\n"
                            f"Impact:\n{impact_summary}\n\n"
                            "Write the driver work order."
                        ),
                    },
                ],
                max_tokens=self.max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Groq call failed (%s), using deterministic fallback", exc)
            return deterministic_fallback(plan_summary, impact_summary)


def deterministic_fallback(plan_summary: str, impact_summary: str) -> str:
    return (
        "=== DRIVER WORK ORDER (auto-generated) ===\n\n"
        f"{plan_summary}\n\n"
        f"Expected impact:\n{impact_summary}\n\n"
        "Follow stops in order. Confirm bike counts at each station."
    )
