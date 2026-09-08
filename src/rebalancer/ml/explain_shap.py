import logging
from pathlib import Path

import matplotlib
import pandas as pd
import shap

matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def compute_shap_values(
    model: object, X: pd.DataFrame, max_samples: int = 1000
) -> shap.Explanation:
    sample = X.sample(n=min(max_samples, len(X)), random_state=42)
    explainer = shap.TreeExplainer(model)
    return explainer(sample)


def save_shap_summary(
    shap_values: shap.Explanation,
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure()
    shap.summary_plot(shap_values, show=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Saved SHAP summary plot to %s", output_path)
