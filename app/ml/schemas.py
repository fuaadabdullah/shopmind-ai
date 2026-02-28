"""
Torch V2: Structured output schemas for probability engine.

Defines Pydantic models for type-safe, structured predictions.
Not text. Not vibes. Structured data that LLM can reason with.

Field naming convention matches actual usage across:
  - mock_predictor.py (demo mode)
  - predictor.py (real model inference)
  - ranker.py (_format_torch_context)
  - diagnostic_service.py (score_diagnostics)
"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContradictionFlag(BaseModel):
    """Warning when diagnosis seems contradictory."""

    code: str = Field(..., description="E.g., 'P0171+P0174' or 'rough_idle_with_converter_issue'")
    description: str = Field(..., description="Human-readable contradiction description")
    severity: str = Field(..., description="'high', 'medium', or 'low'")
    recommendation: str = Field(..., description="What to do about this contradiction")


class TorchDiagnosis(BaseModel):
    """Single fault diagnosis from Torch (ONE ranked cause)."""

    rank: int = Field(..., ge=1, le=10, description="Ranking (1 = most likely)")
    code: str = Field(..., description="Diagnostic code (e.g., 'MAF', 'O2', 'spark_plugs')")
    description: str = Field(..., description="Human-readable fault name")
    raw_probability: float = Field(..., ge=0.0, le=1.0, description="Pre-calibration probability")
    calibrated_probability: float = Field(..., ge=0.0, le=1.0, description="Post-Platt-scaling probability")
    estimated_cost: float = Field(..., ge=0.0, description="Estimated repair cost in USD")
    estimated_labor_hours: float = Field(..., ge=0.0, description="Estimated labor time in hours")


class ModelInfo(BaseModel):
    """Torch model metadata."""

    name: str = Field(..., description="Model name, e.g., 'XGBoost Torch V2'")
    version: str = Field(..., description="Model version, e.g., 'v2.0.0'")
    framework: str = Field(..., description="Framework: 'xgboost', 'mock', etc.")
    feature_dim: int = Field(default=798, ge=0, description="Feature vector dimensionality")


class VehicleContext(BaseModel):
    """Decoded vehicle info from VIN."""

    vin: str = Field(..., description="Vehicle Identification Number")
    obd_codes: list[str] = Field(default_factory=list, description="Parsed OBD codes")
    make: str | None = Field(default=None, description="Vehicle make (Honda, Ford, etc.)")
    model: str | None = Field(default=None, description="Vehicle model (Accord, F-150, etc.)")
    year: int | None = Field(default=None, description="Model year")


class DiagnosticsContext(BaseModel):
    """Summary diagnostics statistics."""

    top_cause_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of top diagnosis")
    num_high_confidence: int = Field(..., ge=0, description="Count of high-confidence diagnoses (>=0.70)")
    num_medium_confidence: int = Field(..., ge=0, description="Count of medium-confidence diagnoses (0.35-0.70)")


class SymptomEmbedding(BaseModel):
    """Symptom text vectorization metadata."""

    embedding_model: str = Field(..., description="Model used for embedding")
    embedding_dim: int = Field(default=384, description="Embedding dimension")
    symptom_text: str = Field(..., description="Original symptom text (truncated)")


class UncertaintyFactors(BaseModel):
    """Epistemic + aleatoric uncertainty quantification."""

    epistemic_uncertainty: float = Field(..., ge=0.0, le=1.0, description="Model uncertainty")
    aleatoric_uncertainty: float = Field(..., ge=0.0, le=1.0, description="Data uncertainty")
    total_uncertainty: float = Field(..., ge=0.0, le=1.0, description="Combined uncertainty score")


class ContradictionDetection(BaseModel):
    """Were there impossible or suspicious combos?"""

    has_contradiction: bool = Field(..., description="True if contradictions detected")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Contradiction severity score")
    flags: list[ContradictionFlag] = Field(default_factory=list, description="Detailed contradiction flags")


class CostWeightedRanking(BaseModel):
    """Multiple diagnostic strategies ranked by cost, probability, ROI."""

    by_probability: list[dict[str, Any]] = Field(default_factory=list, description="Ranked by probability")
    by_cost: list[dict[str, Any]] = Field(default_factory=list, description="Ranked by cost (cheapest first)")
    by_roi: list[dict[str, Any]] = Field(default_factory=list, description="Ranked by ROI (best value)")


class InferenceMetadata(BaseModel):
    """Performance and system info about this prediction."""

    latency_ms: float = Field(..., ge=0, description="Total inference time in milliseconds")
    hardware: str = Field(default="cpu", description="'cpu', 'gpu', or 'mock'")
    model_size_mb: float = Field(default=0, ge=0, description="Model size in MB")


class TorchPrediction(BaseModel):
    """
    Complete Torch V2 prediction response.

    This is what Torch returns: NOT text, NOT vibes.
    Structured JSON that LLM can reason with deterministically.
    """

    request_id: str = Field(..., description="UUID for tracing")
    model_info: ModelInfo
    vehicle_context: VehicleContext
    diagnostics: DiagnosticsContext
    symptom_embedding: SymptomEmbedding
    top_diagnoses: list[TorchDiagnosis] = Field(default_factory=list, description="Ranked predictions (1-10)")
    uncertainty_factors: UncertaintyFactors
    contradiction_detection: ContradictionDetection
    cost_weighted_ranking: CostWeightedRanking
    inference_metadata: InferenceMetadata

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "model_info": {
                    "name": "XGBoost Torch V2",
                    "version": "2.0.0",
                    "framework": "xgboost",
                    "feature_dim": 798
                },
                "vehicle_context": {
                    "vin": "1HG991BS3MH509186",
                    "obd_codes": ["P0171", "P0420"]
                },
                "top_diagnoses": [
                    {
                        "rank": 1,
                        "code": "MAF",
                        "description": "Mass Airflow Sensor",
                        "raw_probability": 0.80,
                        "calibrated_probability": 0.75,
                        "estimated_cost": 242.50,
                        "estimated_labor_hours": 0.5
                    }
                ]
            }
        }
    )