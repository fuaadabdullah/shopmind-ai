"""
Torch model trainer (XGBoost classifier).

Trains multiclass diagnostic classifier offline.
Consumes labeled data from DiagnosticSession DB and exports trained model.
"""
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from ..logger import setup_logger
from .config import ML_ENCODER_PATH, ML_MODEL_PATH, XGBOOST_PARAMS
from .predictor import encode_features
from .registry import get_registry

logger = setup_logger(__name__)


def train_model(
    csv_path: str = "data/training/labeled_data.csv", save_model: bool = True
) -> tuple[Any, Any, dict[str, float]]:
    """
    Train XGBoost diagnostic classifier.

    This trainer is meant to run offline, typically via a cron job or
    manual trigger after collecting sufficient labeled data.

    Args:
        csv_path: Path to CSV file with labeled diagnostic sessions
        save_model: Whether to save trained model to disk

    Returns:
        Tuple of (model, encoder, metrics_dict)

    Raises:
        ImportError: If xgboost not installed
        IOError: If CSV file not found or data cannot be loaded

    Example:
        >>> model, encoder, metrics = train_model("data/training/labeled_data.csv")
        >>> print(f"Accuracy: {metrics['accuracy']:.2%}")
    """
    try:
        import csv

        import xgboost as xgb
        from sklearn.metrics import accuracy_score, precision_score, recall_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder

    except ImportError as e:
        logger.error(f"Missing required package: {e}")
        raise

    try:
        logger.info(f"Loading training data from {csv_path}")

        # Read CSV manually (no pandas dependency)
        records = []
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)

        if not records:
            raise ValueError("No training records found")

        logger.info(f"Loaded {len(records)} training records")

        # Encode features and targets
        X_list = []
        y_list = []

        for i, record in enumerate(records):
            if i % 1000 == 0:
                logger.debug(f"Processing record {i}/{len(records)}")

            try:
                X = encode_features(
                    record["vin"],
                    record["obd_codes"],
                    record["symptoms"],
                )
                if X is not None:
                    X_list.append(X[0])
                    y_list.append(record["confirmed_cause"])
            except Exception as e:
                logger.warning(f"Failed to encode record {i}: {e}")
                continue

        if len(X_list) == 0:
            raise ValueError("No valid records after encoding")

        X = np.array(X_list, dtype=np.float32)
        logger.info(f"Feature matrix shape: {X.shape}")

        # Encode labels (causes → class indices)
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(y_list)

        n_classes = len(label_encoder.classes_)
        logger.info(f"Number of unique causes: {n_classes}")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        logger.info(f"Training set: {len(X_train)}, Test set: {len(X_test)}")

        # Train XGBoost
        logger.info("Training XGBoost classifier...")
        model = xgb.XGBClassifier(
            num_class=n_classes,
            **XGBOOST_PARAMS,
        )
        model.fit(
            X_train,
            y_train,
            verbose=True,
        )

        # Evaluate
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)

        logger.info(
            f"Accuracy: {accuracy:.2%}, Precision: {precision:.2%}, Recall: {recall:.2%}"
        )

        metrics = {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "n_classes": n_classes,
            "n_training_samples": len(X_train),
        }

        # Save model
        if save_model:
            Path(ML_MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)
            with open(ML_MODEL_PATH, "wb") as f:
                pickle.dump(model, f)
            logger.info(f"Saved model to {ML_MODEL_PATH}")

            # Save encoder
            with open(ML_ENCODER_PATH, "wb") as f:
                pickle.dump(label_encoder, f)
            logger.info(f"Saved encoder to {ML_ENCODER_PATH}")

            # Register model
            version = "v1.0"  # TODO: auto-increment from registry
            registry = get_registry()
            registry.register_model(
                version=version,
                accuracy=accuracy,
                precision={str(c): 0.0 for c in label_encoder.classes_},
                recall={str(c): 0.0 for c in label_encoder.classes_},
                samples_used=len(X_train),
            )

        return model, label_encoder, metrics

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise
