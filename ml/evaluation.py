import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score
)


def evaluate_predictions(y_true, y_pred, y_prob=None, average="weighted"):
    """
    Standardized evaluation metrics for classification and recommendation models.
    """
    metrics = {
        "accuracy": float(round(accuracy_score(y_true, y_pred), 4)),
        "precision": float(round(precision_score(y_true, y_pred, average=average, zero_division=0), 4)),
        "recall": float(round(recall_score(y_true, y_pred, average=average, zero_division=0), 4)),
        "f1": float(round(f1_score(y_true, y_pred, average=average, zero_division=0), 4))
    }

    try:
        cm = confusion_matrix(y_true, y_pred)
        metrics["confusion_matrix"] = cm.tolist()
    except Exception:
        metrics["confusion_matrix"] = []

    if y_prob is not None:
        try:
            if len(np.unique(y_true)) == 2:
                # Binary classification
                metrics["roc_auc"] = float(round(roc_auc_score(y_true, y_prob[:, 1] if y_prob.ndim > 1 else y_prob), 4))
            else:
                # Multi-class
                metrics["roc_auc"] = float(round(roc_auc_score(y_true, y_prob, multi_class="ovr", average="weighted"), 4))
        except Exception:
            metrics["roc_auc"] = None
    else:
        metrics["roc_auc"] = None

    return metrics
