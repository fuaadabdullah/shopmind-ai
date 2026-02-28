"""
Mock Torch V2 predictor for demo/testing.

Generates realistic but deterministic TorchPrediction objects.
Useful for testing Week 2 integration before model is trained.

Switch to real predictor.predict_structured() once model available.
"""
import hashlib
from typing import Any

from ..config import settings
from ..logger import setup_logger
from .schemas import (
    ContradictionDetection,
    ContradictionFlag,
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


class MockTorchPredictor:
    """Mock Torch V2 for demo/test mode."""

    # Realistic diagnosis pool with typical probabilities
    DIAGNOSIS_POOL = {
        "MAF": {"prob_base": 0.75, "name": "Mass Airflow Sensor"},
        "O2": {"prob_base": 0.65, "name": "Oxygen Sensor"},
        "spark_plugs": {"prob_base": 0.55, "name": "Spark Plugs"},
        "fuel_filter": {"prob_base": 0.45, "name": "Fuel Filter"},
        "catalytic_converter": {"prob_base": 0.70, "name": "Catalytic Converter"},
        "EGR_valve": {"prob_base": 0.50, "name": "EGR Valve"},
        "timing_belt": {"prob_base": 0.35, "name": "Timing Belt"},
        "transmission": {"prob_base": 0.40, "name": "Transmission Issue"},
    }

    # OBD code to common diagnoses
    OBD_MAPPING = {
        "P0171": ["fuel_filter", "MAF", "O2"],  # Fuel trim
        "P0174": ["fuel_filter", "MAF", "O2"],  # Fuel trim
        "P0420": ["catalytic_converter", "O2"],  # Cat efficiency
        "P0300": ["spark_plugs", "fuel_filter", "timing_belt"],  # Random misfire
        "P0325": ["timing_belt", "spark_plugs"],  # Knock sensor
        "P0440": ["fuel_filter"],  # EVAP system
    }

    # Common contradictions for flagging
    CONTRADICTION_PATTERNS = {
        ("P0171", "P0174"): {"severity": "medium", "desc": "Simultaneous fuel trim faults (unusual)"},
        ("P0300", "P0420"): {"severity": "low", "desc": "Misfire + cat efficiency (possible)"},
    }

    def __init__(self):
        """Initialize mock predictor."""
        logger.info("MockTorchPredictor initialized (demo mode)")

    def predict_structured(
        self,
        vin: str,
        obd_codes: str,
        symptoms: str,
        repair_history: dict | None = None,
    ) -> TorchPrediction:
        """
        Generate a realistic mock TorchPrediction.

        Deterministic seeding ensures same input → same output (good for testing).

        Args:
            vin: Vehicle Identification Number
            obd_codes: Comma-separated OBD codes
            symptoms: Symptom text
            repair_history: Optional repair history context

        Returns:
            TorchPrediction object with mock data
        """
        import time
        from uuid import uuid4

        request_id = str(uuid4())[:8]
        start_time = time.time()

        try:
            # Parse OBD codes
            obd_list = [c.strip().upper() for c in obd_codes.split(",") if c.strip()]

            # Generate seeded diagnoses based on OBD codes
            diagnoses = self._generate_diagnoses(obd_list, symptoms, vin)

            # Detect contradictions (mock detection)
            contradiction_score, contradiction_flags = self._detect_contradictions(obd_list)

            # Build cost rankings (mock)
            cost_ranking = self._build_cost_ranking(diagnoses)

            # Create response
            inference_time = time.time() - start_time
            response = TorchPrediction(
                request_id=request_id,
                model_info=ModelInfo(
                    name="MockTorchV2 (Demo)",
                    version="2.0.0-demo",
                    framework="mock",
                    feature_dim=798
                ),
                vehicle_context=VehicleContext(vin=vin, obd_codes=obd_list),
                diagnostics=DiagnosticsContext(
                    top_cause_confidence=max((d["prob"] for d in diagnoses), default=0.5),
                    num_high_confidence=sum(1 for d in diagnoses if d["prob"] >= 0.70),
                    num_medium_confidence=sum(1 for d in diagnoses if 0.35 <= d["prob"] < 0.70),
                ),
                symptom_embedding=SymptomEmbedding(
                    embedding_model=f"sentence-transformers/{settings.EMBEDDING_MODEL}",
                    embedding_dim=settings.EMBEDDING_DIMENSION,
                    symptom_text=symptoms[:256],
                ),
                top_diagnoses=[
                    TorchDiagnosis(
                        rank=i + 1,
                        code=d["code"],
                        description=d["name"],
                        raw_probability=d["prob"],
                        calibrated_probability=d["prob"] * 0.92,  # Mock calibration
                        estimated_cost=d["cost"],
                        estimated_labor_hours=d["labor"],
                    )
                    for i, d in enumerate(diagnoses[:10])
                ],
                uncertainty_factors=UncertaintyFactors(
                    epistemic_uncertainty=0.15,  # Model uncertainty
                    aleatoric_uncertainty=0.08,  # Data uncertainty
                    total_uncertainty=0.20,
                ),
                contradiction_detection=ContradictionDetection(
                    has_contradiction=contradiction_score > 0.5,
                    overall_score=contradiction_score,
                    flags=contradiction_flags,
                ),
                cost_weighted_ranking=cost_ranking,
                inference_metadata=InferenceMetadata(
                    latency_ms=inference_time * 1000,
                    hardware="mock",
                    model_size_mb=0,
                ),
            )

            logger.info(f"[{request_id}] Mock prediction generated (demo mode)")
            return response

        except Exception as e:
            logger.error(f"Mock prediction failed: {e}", exc_info=True)
            raise

    def _generate_diagnoses(
        self,
        obd_codes: list[str],
        symptoms: str,
        vin: str
    ) -> list[dict[str, Any]]:
        """Generate ranked diagnoses based on OBD codes and symptoms."""
        # Build diagnosis scores
        scores = {}

        # Boost scores based on OBD codes
        for code in obd_codes:
            if code in self.OBD_MAPPING:
                for diag in self.OBD_MAPPING[code]:
                    # Boost probability for mapped diagnoses
                    base_prob = self.DIAGNOSIS_POOL[diag]["prob_base"]
                    scores[diag] = scores.get(diag, 0) + base_prob

        # Add symptom-based boosting
        symptom_lower = symptoms.lower()
        if "rough idle" in symptom_lower or "idle" in symptom_lower:
            scores["MAF"] = scores.get("MAF", 0) + 0.15
            scores["spark_plugs"] = scores.get("spark_plugs", 0) + 0.10

        if "check engine" in symptom_lower or "light" in symptom_lower:
            scores["O2"] = scores.get("O2", 0) + 0.10

        if "hard start" in symptom_lower:
            scores["fuel_filter"] = scores.get("fuel_filter", 0) + 0.15
            scores["spark_plugs"] = scores.get("spark_plugs", 0) + 0.10

        # Normalize scores to probabilities
        max_score = max(scores.values()) if scores else 1.0
        diagnoses = []

        for diag, score in scores.items():
            if diag not in self.DIAGNOSIS_POOL:
                continue

            normalized_prob = min(score / (max_score or 1.0) * 0.95, 0.95)
            diagnoses.append({
                "code": diag,
                "name": self.DIAGNOSIS_POOL[diag]["name"],
                "prob": max(normalized_prob, 0.2),  # Min 20% confidence
                "cost": self._estimate_cost(diag),
                "labor": self._estimate_labor(diag),
            })

        # Sort by probability
        diagnoses.sort(key=lambda x: x["prob"], reverse=True)
        return diagnoses

    def _detect_contradictions(
        self,
        obd_codes: list[str]
    ) -> tuple[float, list[dict]]:
        """Detect contradictory code combinations."""
        flags = []
        max_score = 0.0

        # Check all pairs
        for code1 in obd_codes:
            for code2 in obd_codes:
                if code1 >= code2:
                    continue  # Avoid duplicates
                pair = (code1, code2)
                if pair in self.CONTRADICTION_PATTERNS:
                    pattern = self.CONTRADICTION_PATTERNS[pair]
                    severity_map = {"high": 0.8, "medium": 0.5, "low": 0.2}
                    score = severity_map.get(pattern["severity"], 0.3)
                    max_score = max(max_score, score)
                    flags.append(
                        ContradictionFlag(
                            code=f"{code1}+{code2}",
                            description=pattern["desc"],
                            severity=pattern["severity"],
                            recommendation=f"Verify scanner accuracy for {code1} and {code2}",
                        )
                    )

        return max_score, flags

    def _build_cost_ranking(self, diagnoses: list) -> CostWeightedRanking:
        """Build cost-weighted ranking strategies."""
        # By probability (natural order from _generate_diagnoses)
        by_prob = [
            {
                "rank": i + 1,
                "code": d["code"],
                "description": d["name"],
                "probability": round(d["prob"], 3),
                "estimated_cost_usd": round(d["cost"], 2),
                "estimated_labor_hours": round(d["labor"], 1),
                "roi_score": round(d["prob"] / (d["cost"] + 1), 3),
            }
            for i, d in enumerate(diagnoses)
        ]

        # By cost (sort by cost ascending)
        by_cost = sorted(by_prob, key=lambda x: x["estimated_cost_usd"])
        for i, item in enumerate(by_cost, 1):
            item["rank"] = i

        # By ROI (sort by roi_score descending)
        by_roi = sorted(by_prob, key=lambda x: x["roi_score"], reverse=True)
        for i, item in enumerate(by_roi, 1):
            item["rank"] = i

        return CostWeightedRanking(
            by_probability=by_prob[:5],
            by_cost=by_cost[:5],
            by_roi=by_roi[:5],
        )

    @staticmethod
    def _estimate_cost(diagnosis_code: str) -> float:
        """Estimate repair cost for diagnosis."""
        cost_map = {
            "MAF": 242.50,  # Parts ($180) + labor (0.5h * $125)
            "O2": 245.0,  # (~$120) + labor (1h * $125)
            "spark_plugs": 227.50,  # (~$40) + labor (1.5h * $125)
            "fuel_filter": 223.75,  # (~$30) + labor (0.75h * $125)
            "catalytic_converter": 1050.0,  # (~$800) + labor (2h * $125)
            "EGR_valve": 375.0,  # (~$250) + labor (1h * $125)
            "timing_belt": 1025.0,  # (~$400) + labor (5h * $125)
            "transmission": 2500.0,  # Complex
        }
        return cost_map.get(diagnosis_code, 400.0)

    @staticmethod
    def _estimate_labor(diagnosis_code: str) -> float:
        """Estimate labor hours for diagnosis."""
        labor_map = {
            "MAF": 0.5,
            "O2": 1.0,
            "spark_plugs": 1.5,
            "fuel_filter": 0.75,
            "catalytic_converter": 2.0,
            "EGR_valve": 1.0,
            "timing_belt": 5.0,
            "transmission": 8.0,
        }
        return labor_map.get(diagnosis_code, 2.0)


# Global instance
_mock_predictor = MockTorchPredictor()


def predict_mock(
    vin: str,
    obd_codes: str,
    symptoms: str,
    repair_history: dict | None = None,
) -> TorchPrediction:
    """
    Generate mock Torch prediction.

    Convenience function wrapping MockTorchPredictor.
    """
    return _mock_predictor.predict_structured(
        vin=vin,
        obd_codes=obd_codes,
        symptoms=symptoms,
        repair_history=repair_history,
    )
