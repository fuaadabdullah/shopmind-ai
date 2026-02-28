"""
ML configuration and constants.

Controls ML model behavior, versioning, and feature engineering parameters.
"""

# Model serving
ML_MODEL_ENABLED = True
ML_MODEL_PATH = "data/ml_models/v1.pkl"
ML_ENCODER_PATH = "data/ml_models/v1_encoder.pkl"
ML_REGISTRY_PATH = "data/ml_models/registry.json"

# Training
MAX_CAUSES_PER_PREDICTION = 5
CONFIDENCE_THRESHOLD = 0.10  # Exclude predictions below 10% confidence
MIN_TRAINING_SAMPLES = 100  # Minimum samples before training is worthwhile
OBD_CODE_VOCAB_SIZE = 200  # Max unique OBD codes to encode

# Features
SYMPTOM_EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension
VIN_FEATURE_DIM = 50  # One-hot encoded make/model/year
OBD_FEATURE_DIM = 200  # Multi-hot encoded OBD codes
TOTAL_FEATURE_DIM = SYMPTOM_EMBEDDING_DIM + VIN_FEATURE_DIM + OBD_FEATURE_DIM  # 634

# XGBoost hyperparameters
XGBOOST_PARAMS = {
    "booster": "gbtree",
    "objective": "multi:softprob",  # Multiclass classification
    "max_depth": 6,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 1,
    "n_estimators": 100,
    "random_state": 42,
}

# Test/train split
TEST_SPLIT = 0.2
VALIDATION_SPLIT = 0.1
