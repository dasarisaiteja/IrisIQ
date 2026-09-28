from abc import ABC, abstractmethod
from typing import Any
import os
import json
import joblib


class BasePredictor(ABC):
    """
    Standard interface for all prediction models across personality, cognitive,
    learning styles, leadership, stream selection, and career recommendation.
    Ensures modularity, replaceability, and strict metric tracking.
    """

    def __init__(self, model_name="base_model", version="1.0.0"):
        self.model_name = model_name
        self.version = version
        self.is_trained = False
        self.metadata = {
            "model_name": model_name,
            "version": version,
            "trained_date": None,
            "dataset_info": None,
            "metrics": {}
        }

    @abstractmethod
    def fit(self, X, y, **kwargs) -> Any:
        """Train model on empirical training dataset."""
        return self

    @abstractmethod
    def predict(self, X) -> Any:
        """Generate predictions for feature matrix X."""
        raise NotImplementedError

    @abstractmethod
    def predict_proba(self, X) -> Any:
        """Generate prediction confidence / probability distributions."""
        raise NotImplementedError

    def evaluate(self, X_test, y_test):
        """Evaluate model against test dataset."""
        from ml.evaluation import evaluate_predictions
        y_pred = self.predict(X_test)
        y_prob = self.predict_proba(X_test) if hasattr(self, "predict_proba") else None
        metrics = evaluate_predictions(y_test, y_pred, y_prob)
        self.metadata["metrics"] = metrics
        return metrics

    def save(self, filepath):
        """Serialize model weights and metadata."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump({"model": self, "metadata": self.metadata}, filepath)

    @classmethod
    def load(cls, filepath):
        """Load serialized model."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file {filepath} not found.")
        data = joblib.load(filepath)
        return data["model"]
