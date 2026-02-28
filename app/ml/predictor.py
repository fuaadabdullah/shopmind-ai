"""ML predictor: model serving and inference.

Lazy-loads trained XGBoost model and runs diagnostics predictions.
Returns structured TorchPrediction objects with confidence calibration,
contradiction detection, and cost-weighted ranking strategies.

Version-Aware Loading:
  - Supports loading specific model versions from registry
  - Defaults to active version if none specified
  - Caches loaded model in memory for performance
"""
import pickle
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from ..embeddings_utils import embed_query
from ..config import settings
from ..logger import setup_logger
from ..metrics import torch_inference_latency_seconds, torch_inference_total, torch_predictions_confidence_distribution
from .calibration import ConfidenceCalibrator
from .config import (
    CONFIDENCE_THRESHOLD,
    MAX_CAUSES_PER_PREDICTION,
)
from .contradiction_detector import ContradictionDetector
from .cost_weighting import CostWeightedRanker
from .registry import get_registry
from .schemas import (
    ContradictionDetection,
    CostWeightedRanking,
    DiagnosticsContext,
    InferenceMetadata,
    ModelInfo,
    SymptomEmbedding,
    TorchDiagnosis,
    TorchPrediction,
    UncertaintyFactors,
    VehicleContext,
)

logger = setup_logger(__name__)

# Global model state
_model: Any = None
_encoder: Any = None
_loaded_version: str | None = None

# Torch V2 intelligence layers (initialized on first use)
_calibrator: ConfidenceCalibrator | None = None
_contradiction_detector: ContradictionDetector | None = None
_cost_ranker: CostWeightedRanker | None = None


def _load_model(version: str | None = None) -> Any:
    """Lazy-load XGBoost model from version-specific pickle file.

    Args:
        version: Specific version to load, or None for active version from registry

    Returns:
        The loaded model, or None if loading failed
    """
    global _model, _loaded_version

    # If no version specified, get active from registry
    if version is None:
        registry = get_registry()
        version = registry.get_active_version()

    # If we already have the right version loaded, return it
    if _model is not None and _loaded_version == version:
        return _model

    if version is None:
        logger.warning("No model version available (registry empty?)")
        return None

    try:
        # Build path from version: data/ml_models/v1.0.pkl
        model_dir = Path("data/ml_models")
        model_path = model_dir / f"{version}.pkl"

        if not model_path.exists():
            logger.warning(f"Model not found at {model_path}")
            return None

        logger.debug(f"Loading model {version} from {model_path}")
        with open(model_path, "rb") as f:
            _model = pickle.load(f)
        _loaded_version = version
        logger.info(f"Model {version} loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model {version}: {e}")
        return None

    return _model


def _load_encoder(version: str | None = None) -> Any:
    """Lazy-load label encoder from version-specific pickle file.

    Args:
        version: Specific version to load, or None for active version from registry

    Returns:
        The loaded encoder, or None if loading failed
    """
    global _encoder, _loaded_version

    # If no version specified, get active from registry
    if version is None:
        registry = get_registry()
        version = registry.get_active_version()

    # If we already have the right version loaded, return it
    if _encoder is not None and _loaded_version == version:
        return _encoder

    if version is None:
        logger.warning("No encoder version available (registry empty?)")
        return None

    try:
        # Build path from version: data/ml_models/v1.0_encoder.pkl
        model_dir = Path("data/ml_models")
        encoder_path = model_dir / f"{version}_encoder.pkl"

        if not encoder_path.exists():
            logger.warning(f"Encoder not found at {encoder_path}")
            return None

        logger.debug(f"Loading encoder {version} from {encoder_path}")
        with open(encoder_path, "rb") as f:
            _encoder = pickle.load(f)
        _loaded_version = version
        logger.info(f"Encoder {version} loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load encoder {version}: {e}")
        return None

    return _encoder


def encode_features(
    vin: str, obd_codes: str, symptoms: str
) -> np.ndarray | None:
    """
    Encode VIN + OBD + symptoms into feature vector (798D).

    Feature breakdown:
    - VIN features: 100D (make, model, year, engine, transmission)
    - OBD codes: 300D (multi-hot + code frequency + severity)
    - Symptoms: 384D (sentence embedding)
    - Temporal: 14D (time of day, seasonality, mileage age)
    Total: 100 + 300 + 384 + 14 = 798D

    Args:
        vin: Vehicle Identification Number (17 chars)
        obd_codes: Comma-separated OBD codes (e.g., "P0420,P0171")
        symptoms: Customer symptom text

    Returns:
        Feature vector (798 dimensions) or None if encoding fails

    Example:
        >>> X = encode_features("1HGBH41JXMN109186", "P0420", "car won't start")
        >>> X.shape
        (1, 798)
    """
    try:
        # 1. VIN features (100D)
        # Parse VIN: make (3), model (5), year (4), body (2), engine (3)...
        vin_vec = np.zeros(100, dtype=np.float32)
        for i, char in enumerate(vin[:17]):
            vin_vec[i] = ord(char) / 256.0

        # 2. OBD features (300D)
        # Multi-hot encode + frequency + severity heuristics
        obd_codes_list = [c.strip().upper() for c in obd_codes.split(",") if c.strip()]
        obd_vec = np.zeros(300, dtype=np.float32)

        for code in obd_codes_list[:20]:  # Max 20 codes
            # Hash OBD code to bucket (200 slots for multi-hot)
            hash_val = hash(code) % 200
            obd_vec[hash_val] += 1.0

            # Severity encoding (P = powertrain, C = chassis, B = body, U = network)
            severity_slot = 200 + "PCBU".find(code[0]) if len(code) > 0 else 200
            obd_vec[severity_slot] += 0.5

        # 3. Symptom embeddings (384D)
        try:
            symptom_emb = embed_query(symptoms)
            symptom_vec = np.array(symptom_emb, dtype=np.float32)
            if len(symptom_vec) != settings.EMBEDDING_DIMENSION:
                # Pad or truncate to expected dimension
                if len(symptom_vec) < settings.EMBEDDING_DIMENSION:
                    symptom_vec = np.pad(symptom_vec, (0, settings.EMBEDDING_DIMENSION - len(symptom_vec)))
                else:
                    symptom_vec = symptom_vec[:settings.EMBEDDING_DIMENSION]
        except Exception as e:
            logger.warning(f"Failed to embed symptoms: {e}, using zeros")
            symptom_vec = np.zeros(settings.EMBEDDING_DIMENSION, dtype=np.float32)

        # 4. Temporal features (14D)
        # Placeholder: timestamp features (hour, day of week, month, etc.)
        # FUTURE: Replace with actual temporal features from request context
        temporal_vec = np.zeros(14, dtype=np.float32)

        # Concatenate: [VIN (100) + OBD (300) + symptom (384) + temporal (14)] = 798D
        X = np.concatenate([vin_vec, obd_vec, symptom_vec, temporal_vec])
        assert len(X) == 798, f"Feature vector size {len(X)} != 798"
        return X.reshape(1, -1)

    except Exception as e:
        logger.error(f"Feature encoding failed: {e}", exc_info=True)
        return None


def predict(vin: str, obd_codes: str, symptoms: str) -> dict[str, float] | None:
    """
    Predict diagnostic causes.

    Args:
        vin: Vehicle Identification Number
        obd_codes: OBD-II codes (comma-separated)
        symptoms: Customer symptoms

    Returns:
        Dict mapping cause → confidence (0-1), or None if prediction fails

    Example:
        >>> predictions = predict("1HGBH41JXMN109186", "P0420", "rough idle")
        >>> predictions
        {'Catalytic Converter': 0.67, 'O2 Sensor': 0.21}
    """
    try:
        model = _load_model()
        if model is None:
            return None

        # Encode features
        X = encode_features(vin, obd_codes, symptoms)
        if X is None:
            return None

        # Predict probabilities
        logger.debug(f"Running inference on features shape {X.shape}")
        probas = model.predict_proba(X)[0]  # [n_classes]

        # Get class labels
        encoder = _load_encoder()
        if encoder is None:
            # Fallback: use numeric class indices
            causes = [f"cause_{i}" for i in range(len(probas))]
        else:
            try:
                causes = encoder.inverse_transform(range(len(probas)))
            except Exception as e:
                logger.warning(f"Failed to inverse transform: {e}")
                causes = [f"cause_{i}" for i in range(len(probas))]

        # Filter by confidence threshold and top-K
        predictions = {}
        for cause, prob in zip(causes, probas, strict=False):
            if prob >= CONFIDENCE_THRESHOLD:
                predictions[str(cause)] = float(prob)

        # Sort by confidence, keep top K
        sorted_preds = sorted(
            predictions.items(), key=lambda x: x[1], reverse=True
        )[:MAX_CAUSES_PER_PREDICTION]

        result = dict(sorted_preds)
        logger.debug(f"Predictions: {result}")
        return result

    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        return None


def is_model_available() -> bool:
    """Check if an active model version is available for inference."""
    registry = get_registry()
    active_version = registry.get_active_version()

    if not active_version:
        logger.warning("No active model version in registry")
        return False

    # Check if the model file exists for this version
    model_dir = Path("data/ml_models")
    model_path = model_dir / f"{active_version}.pkl"

    return model_path.exists()


def predict_structured(
    vin: str,
    obd_codes: str,
    symptoms: str
) -> TorchPrediction | None:
    """
    Run structured Torch inference with full Torch V2 intelligence layers.

    Returns:
        TorchPrediction object with confidences, contradictions, and cost rankings
        or None if inference fails/model unavailable

    Example:
        >>> pred = predict_structured("1HGBH41JXMN109186", "P0420", "rough idle")
        >>> pred.top_diagnoses[0].code
        'Catalytic Converter'
        >>> pred.contradiction_detection.has_contradiction
        False
    """
    import time

    # Get model version for metrics labeling
    registry = get_registry()
    model_version = registry.get_active_version() or "unknown"

    try:
        request_id = str(uuid4())[:8]
        start_time = time.time()

        # Step 1: Encode features (798D)
        logger.debug(f"[{request_id}] Encoding features for prediction")
        X = encode_features(vin, obd_codes, symptoms)
        if X is None:
            logger.error(f"[{request_id}] Feature encoding failed")
            torch_inference_total.labels(model_version=model_version, status="encoding_failed").inc()
            return None

        # Step 2: Load model
        model = _load_model()
        if model is None:
            logger.error(f"[{request_id}] Model not available")
            torch_inference_total.labels(model_version=model_version, status="model_unavailable").inc()
            return None

        # Step 3: Run inference (with timing)
        logger.debug(f"[{request_id}] Running model inference")
        inference_start = time.time()
        probas = model.predict_proba(X)[0]
        inference_elapsed = time.time() - inference_start
        torch_inference_latency_seconds.labels(model_version=model_version, status="success").observe(inference_elapsed)

        # Step 4: Get class labels
        encoder = _load_encoder()
        if encoder is None:
            causes = [f"cause_{i}" for i in range(len(probas))]
        else:
            try:
                causes = encoder.inverse_transform(range(len(probas)))
            except Exception as e:
                logger.warning(f"[{request_id}] Failed inverse transform: {e}")
                causes = [f"cause_{i}" for i in range(len(probas))]

        # Raw predictions dict
        raw_predictions = {}
        for cause, prob in zip(causes, probas, strict=False):
            if prob >= CONFIDENCE_THRESHOLD:
                raw_predictions[str(cause)] = float(prob)

        if not raw_predictions:
            logger.warning(f"[{request_id}] No predictions above threshold")
            torch_inference_total.labels(model_version=model_version, status="below_threshold").inc()
            return None

        # Record confidence distribution for successful predictions
        for confidence in raw_predictions.values():
            torch_predictions_confidence_distribution.labels(model_version=model_version).observe(confidence)

        # Step 5: Calibrate probabilities
        logger.debug(f"[{request_id}] Calibrating confidence scores")
        global _calibrator
        if _calibrator is None:
            _calibrator = ConfidenceCalibrator()
        
        # Apply calibration to all probabilities
        raw_probs = np.array(list(raw_predictions.values()), dtype=np.float32)
        calibrated_probs = _calibrator.calibrate(raw_probs)
        
        calibrated_predictions = dict(
            zip(raw_predictions.keys(), calibrated_probs, strict=True)
        )

        # Step 6: Detect contradictions
        logger.debug(f"[{request_id}] Detecting contradictions")
        global _contradiction_detector
        if _contradiction_detector is None:
            _contradiction_detector = ContradictionDetector()

        obd_codes_list = [c.strip().upper() for c in obd_codes.split(",") if c.strip()]
        contradiction_score, contradiction_flags = _contradiction_detector.detect_contradictions(
            obd_codes=obd_codes_list,
            symptoms=symptoms,
            vin_info={"vin": vin}
        )

        # Step 7: Generate cost-weighted rankings
        logger.debug(f"[{request_id}] Generating cost-weighted rankings")
        global _cost_ranker
        if _cost_ranker is None:
            _cost_ranker = CostWeightedRanker()

        by_prob = _cost_ranker.rank_by_probability(calibrated_predictions)
        by_cost = _cost_ranker.rank_by_cost(calibrated_predictions)
        by_roi = _cost_ranker.rank_by_roi(calibrated_predictions)

        inference_time = time.time() - start_time
        logger.debug(f"[{request_id}] Inference completed in {inference_time:.2f}s")

        # Step 8: Build response schema
        top_diagnoses = [
            TorchDiagnosis(
                rank=opt.rank,
                code=opt.code,
                description=opt.description,
                raw_probability=raw_predictions.get(opt.code, 0.0),
                calibrated_probability=opt.probability,
                estimated_cost=opt.estimated_cost,
                estimated_labor_hours=opt.estimated_labor_hours
            )
            for opt in by_prob[:10]  # Top 10
        ]

        cost_ranking = _cost_ranker.format_ranking_for_response(
            by_probability=by_prob[:5],
            by_cost=by_cost[:5],
            by_roi=by_roi[:5]
        )

        # Create TorchPrediction object
        response = TorchPrediction(
            request_id=request_id,
            model_info=ModelInfo(
                name="XGBoost Torch V2",
                version="2.0.0-alpha",
                framework="xgboost",
                feature_dim=798
            ),
            vehicle_context=VehicleContext(vin=vin, obd_codes=obd_codes_list),
            diagnostics=DiagnosticsContext(
                top_cause_confidence=max(calibrated_predictions.values()) if calibrated_predictions else 0.0,
                num_high_confidence=sum(1 for v in calibrated_predictions.values() if v >= 0.7),
                num_medium_confidence=sum(1 for v in calibrated_predictions.values() if 0.35 <= v < 0.7)
            ),
            symptom_embedding=SymptomEmbedding(
                embedding_model=f"sentence-transformers/{settings.EMBEDDING_MODEL}",
                embedding_dim=settings.EMBEDDING_DIMENSION,
                symptom_text=symptoms[:256]
            ),
            top_diagnoses=top_diagnoses,
            uncertainty_factors=UncertaintyFactors(
                epistemic_uncertainty=1.0 - (max(calibrated_predictions.values()) if calibrated_predictions else 0.0),
                aleatoric_uncertainty=float(np.std(list(calibrated_predictions.values())) if len(calibrated_predictions) > 1 else 0.1),
                total_uncertainty=0.5
            ),
            contradiction_detection=ContradictionDetection(
                has_contradiction=contradiction_score > 0.5,
                overall_score=contradiction_score,
                flags=contradiction_flags
            ),
            cost_weighted_ranking=CostWeightedRanking(
                by_probability=cost_ranking.get("by_probability", []),
                by_cost=cost_ranking.get("by_cost", []),
                by_roi=cost_ranking.get("by_roi", [])
            ),
            inference_metadata=InferenceMetadata(
                latency_ms=inference_time * 1000,
                hardware="cpu",
                model_size_mb=50
            )
        )

        # Record successful inference
        torch_inference_total.labels(model_version=model_version, status="success").inc()
        logger.info(f"[{request_id}] Structured prediction completed")
        return response

    except Exception as e:
        logger.error(f"Structured prediction failed: {e}", exc_info=True)
        torch_inference_total.labels(model_version=model_version, status="error").inc()
        return None
