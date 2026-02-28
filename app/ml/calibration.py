"""
Confidence calibration for Torch V2.

Platt scaling: converts raw probabilities to calibrated probabilities.
Prevents hallucinated certainty.
"""
from functools import lru_cache

import numpy as np

from ..logger import setup_logger

logger = setup_logger(__name__)


class ConfidenceCalibrator:
    """
    Calibrates raw XGBoost probabilities using Platt scaling.

    Problem: ML models often output overconfident probabilities.
    Solution: Train logistic regression on model outputs to calibrate.

    Example:
        Raw XGBoost: "90% sure it's MAF"
        Calibrated: "68% sure it's MAF"
        (Because on validation set, when model said 90%, only 68% were correct)
    """

    def __init__(self):
        """Initialize calibrator with default parameters."""
        # Platt scaling parameters: learned on validation set
        # sigmoid(A * raw_prob + B)
        self.A = None
        self.B = None
        self.is_fitted = False
        logger.debug("ConfidenceCalibrator initialized (unfitted)")

    def fit(
        self,
        raw_probabilities: np.ndarray,
        true_labels: np.ndarray,
        epochs: int = 100
    ) -> dict:
        """
        Fit Platt scaling parameters on validation data.

        Args:
            raw_probabilities: Model outputs from predict_proba (0-1)
            true_labels: True binary labels (0 or 1)
            epochs: Optimization epochs

        Returns:
            Dict with {a, b, training_log_loss, validation_accuracy}
        """
        try:
            if len(raw_probabilities) != len(true_labels):
                raise ValueError("Probability and label arrays must have same length")

            # Initialize parameters
            self.A = 0.0
            self.B = 0.0
            learning_rate = 0.001
            epsilon = 1e-6

            # Clip probabilities to avoid log(0)
            probs = np.clip(raw_probabilities, epsilon, 1 - epsilon)

            # Gradient descent to fit sigmoid(A*p + B) to true labels
            for epoch in range(epochs):
                # Predictions: sigmoid(A*p + B)
                logit = self.A * probs + self.B
                predictions = self._sigmoid(logit)

                # Cross-entropy loss
                loss = -np.mean(
                    true_labels * np.log(predictions + epsilon) +
                    (1 - true_labels) * np.log(1 - predictions + epsilon)
                )

                # Gradients
                error = predictions - true_labels
                d_a = np.mean(error * probs)
                d_b = np.mean(error)

                # Update parameters
                self.A -= learning_rate * d_a
                self.B -= learning_rate * d_b

                if epoch % 20 == 0:
                    logger.debug(f"Calibration epoch {epoch}: loss={loss:.4f}")

            self.is_fitted = True
            logger.info(f"Calibration fitted: A={self.A:.4f}, B={self.B:.4f}")

            # Evaluate calibration quality
            calibrated = self.calibrate(raw_probabilities)
            accuracy = np.mean((calibrated > 0.5) == true_labels)
            brier_score = np.mean((calibrated - true_labels) ** 2)

            return {
                "a": float(self.A),
                "b": float(self.B),
                "accuracy": float(accuracy),
                "brier_score": float(brier_score),
                "fitted": True
            }

        except Exception as e:
            logger.error(f"Calibration fitting failed: {e}")
            self.is_fitted = False
            return {"fitted": False, "error": str(e)}

    def calibrate(self, raw_probabilities: np.ndarray) -> np.ndarray:
        """
        Apply calibration to raw probabilities.

        Args:
            raw_probabilities: Raw model outputs (0-1)

        Returns:
            Calibrated probabilities

        If not fitted, returns raw probabilities unchanged.
        """
        if not self.is_fitted or self.A is None or self.B is None:
            logger.warning("Calibrator not fitted, returning raw probabilities")
            return raw_probabilities

        # Sigmoid: 1 / (1 + exp(-(A*p + B)))
        logit = self.A * raw_probabilities + self.B
        calibrated = self._sigmoid(logit)

        return np.clip(calibrated, 0.0, 1.0)

    def calibrate_with_details(self, raw_prob: float) -> dict:
        """
        Calibrate a single probability with explanation.

        Args:
            raw_prob: Raw model probability (0-1)

        Returns:
            Dict with {raw, calibrated, shift, method}
        """
        if not self.is_fitted or self.A is None or self.B is None:
            return {
                "raw_probability": raw_prob,
                "calibrated_probability": raw_prob,
                "shift": 0.0,
                "method": "not_fitted"
            }

        calibrated = self._sigmoid(self.A * raw_prob + self.B)
        shift = calibrated - raw_prob

        return {
            "raw_probability": float(raw_prob),
            "calibrated_probability": float(calibrated),
            "shift": float(shift),
            "method": "Platt scaling"
        }

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        """Numerically stable sigmoid."""
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

    @staticmethod
    @lru_cache(maxsize=128)
    def get_confidence_band(probability: float) -> str:
        """
        Classify probability into confidence band.

        Args:
            probability: Calibrated probability (0-1)

        Returns:
            'high', 'medium', or 'low'
        """
        if probability >= 0.70:
            return "high"
        elif probability >= 0.35:
            return "medium"
        else:
            return "low"


def expected_calibration_error(
    predictions: np.ndarray,
    true_labels: np.ndarray,
    n_bins: int = 10
) -> float:
    """
    Calculate Expected Calibration Error (ECE).

    Measure of how well calibrated the probabilities are.
    Lower = better calibration. 0 = perfect.

    Args:
        predictions: Model predictions (0-1)
        true_labels: True binary labels (0 or 1)
        n_bins: Number of bins for histogram

    Returns:
        ECE value (0-1)
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        mask = (predictions >= bin_edges[i]) & (predictions < bin_edges[i + 1])
        if mask.sum() == 0:
            continue

        avg_confidence = predictions[mask].mean()
        accuracy = true_labels[mask].mean()
        ece += np.abs(avg_confidence - accuracy) * mask.sum() / len(predictions)

    return ece


def brier_score(predictions: np.ndarray, true_labels: np.ndarray) -> float:
    """
    Calculate Brier Score for probability predictions.

    MSE between predicted probabilities and true labels.
    Lower = better. 0 = perfect.

    Args:
        predictions: Model predictions (0-1)
        true_labels: True binary labels (0 or 1)

    Returns:
        Brier score (0-1)
    """
    return np.mean((predictions - true_labels) ** 2)
