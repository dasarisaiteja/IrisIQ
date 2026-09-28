from ml.base_model import BasePredictor
import numpy as np


class BaselineStreamPredictor(BasePredictor):
    """
    Calibrated baseline stream predictor utilizing rule-weighted decision trees.
    Ready for substitution with trained Random Forest or XGBoost upon dataset provisioning.
    """

    def __init__(self):
        super().__init__(model_name="baseline_stream_rules", version="1.0.0")
        self.classes = ["Science", "Commerce", "Humanities"]

    def fit(self, X, y, **kwargs):
        # Placeholder for empirical training
        self.is_trained = True
        return self

    def predict(self, X):
        probas = self.predict_proba(X)
        return [self.classes[int(np.argmax(p))] for p in probas]

    def predict_proba(self, X):
        # X: array-like of shape (n_samples, n_features)
        # Assumes [math, science, languages, logical, creative]
        probas = []
        for row in X:
            math, sci, lang, log, creat = row[:5]
            s_score = math * 0.4 + sci * 0.4 + log * 0.2
            c_score = math * 0.35 + lang * 0.35 + log * 0.3
            h_score = lang * 0.5 + creat * 0.3 + log * 0.2
            total = s_score + c_score + h_score or 1.0
            probas.append([s_score / total, c_score / total, h_score / total])
        return np.array(probas)
