"""
Contradiction detection for Torch V2.

Flags when symptoms don't match codes, when scans seem impossible, etc.
Prevents chasing ghost problems.
"""
import logging
from typing import Any

from ..logger import setup_logger

logger = setup_logger(__name__)


class ContradictionDetector:
    """Detects suspicious OBD/symptom/VIN combinations."""

    # Code-symptom relationships: what makes sense together
    CODE_SYMPTOM_MATRIX = {
        "P0171": {
            "expected_symptoms": ["lean mixture", "rough idle", "hard start", "misfires", "sluggish"],
            "unexpected_with": ["full tank", "never idles badly"],
            "severity": "medium"
        },
        "P0100": {
            "expected_symptoms": ["rough idle", "poor fuel economy", "hesitation", "stalling"],
            "unexpected_with": ["perfect idle", "smooth acceleration"],
            "severity": "medium"
        },
        "P0420": {
            "expected_symptoms": ["check light", "reduced power", "failed emission test"],
            "unexpected_with": ["no symptoms", "rough idle", "hard start"],  # Must pair with fuel codes
            "severity": "low"
        },
        "P0300": {
            "expected_symptoms": ["misfire", "rough idle", "check light", "hesitation"],
            "unexpected_with": ["perfect engine operation"],
            "severity": "high"
        },
    }

    # VIN patterns: what faults are common for which vehicles
    VIN_FAULT_PATTERNS = {
        ("Honda", "Accord", "2005-2012"): {
            "common_faults": ["P0171", "P0100", "idle_issues"],
            "rare_faults": ["transmission_failure"],
        },
        ("Honda", "Accord", "2006-2015"): {
            "common_faults": ["P0420", "valve_coil_failure"],
            "rare_faults": ["engine_knocking"],
        },
        ("Toyota", "Camry", "2005-2010"): {
            "common_faults": ["P0171", "knock_sensor"],
            "rare_faults": ["transmission_slipping"],
        },
    }

    # Semantic contradictions
    SEMANTIC_CONTRADICTIONS = {
        "rough_idle_with_converter": {
            "codes": ["P0420"],
            "symptoms": ["rough idle"],
            "contradiction": "Idle issues typically indicate fuel system, not catalyst efficiency",
            "severity": "low",
            "flag": "Consider checking fuel trim first"
        },
        "hard_start_with_catalyst": {
            "codes": ["P0420"],
            "symptoms": ["hard start", "won't start"],
            "contradiction": "P0420 shouldn't cause starting issues",
            "severity": "high",
            "flag": "Look at spark plugs, battery, or fuel pump instead"
        },
        "perfect_running_with_error_codes": {
            "codes": ["*"],  # Any codes
            "symptoms": ["runs great", "no issues", "perfect"],
            "contradiction": "Customer reports no symptoms but has error codes",
            "severity": "medium",
            "flag": "Scan head error or PO codes from previous owner?"
        },
    }

    def __init__(self):
        """Initialize contradiction detector."""
        logger.debug("ContradictionDetector initialized")

    def detect_contradictions(
        self,
        obd_codes: list[str],
        symptoms: str,
        vin_info: dict[str, Any],
        **kwargs
    ) -> tuple[float, list[dict[str, Any]]]:
        """
        Detect contradictions in diagnostic input.

        Args:
            obd_codes: List of OBD codes (e.g., ["P0171", "P0420"])
            symptoms: Symptom text from customer/mechanic
            vin_info: Dict with {make, model, year}
            **kwargs: Additional context (mileage, climate, etc.)

        Returns:
            Tuple of (overall_contradiction_score, list_of_contradiction_flags)
            - score: 0.0 (no contradictions) to 1.0 (severe contradictions)
            - flags: List of {code, severity, recommendation} dicts
        """
        flags = []
        severity_scores = []

        try:
            # 1. Check if freeze frame data makes sense
            if not obd_codes and "check engine light" in symptoms.lower():
                flags.append({
                    "flag": "check_light_without_codes",
                    "severity": "medium",
                    "recommendation": "OBDII reader may have lost connection. Scan again."
                })
                severity_scores.append(0.5)

            # 2. Check code-symptom pairs
            symptoms_lower = symptoms.lower()
            for code in obd_codes:
                contradiction = self._check_code_symptom_conflict(code, symptoms_lower)
                if contradiction:
                    flags.append(contradiction)
                    severity_scores.append(self._severity_to_score(contradiction["severity"]))

            # 3. Check VIN applicability (is this fault common for this vehicle?)
            vin_contradiction = self._check_vin_applicability(obd_codes, vin_info)
            if vin_contradiction:
                flags.append(vin_contradiction)
                severity_scores.append(self._severity_to_score(vin_contradiction["severity"]))

            # 4. Check semantic impossibilities
            semantic = self._check_semantic_contradiction(obd_codes, symptoms_lower)
            if semantic:
                flags.append(semantic)
                severity_scores.append(self._severity_to_score(semantic["severity"]))

            # 5. Calculate overall contradiction score
            if severity_scores:
                overall_score = sum(severity_scores) / len(severity_scores)
            else:
                overall_score = 0.0

            logger.debug(
                f"Contradiction detection: score={overall_score:.2f}, flags={len(flags)}"
            )

            return overall_score, flags

        except Exception as e:
            logger.error(f"Contradiction detection failed: {e}")
            return 0.0, []

    def _check_code_symptom_conflict(self, code: str, symptoms: str) -> dict[str, Any] | None:
        """Check if OBD code matches customer symptoms."""
        if code not in self.CODE_SYMPTOM_MATRIX:
            return None  # No known pattern for this code

        pattern = self.CODE_SYMPTOM_MATRIX[code]
        expected = pattern.get("expected_symptoms", [])
        unexpected = pattern.get("unexpected_with", [])

        # Check if symptoms match
        symptom_found = any(symptom in symptoms for symptom in expected)
        unexpected_found = any(symptom in symptoms for symptom in unexpected)

        if unexpected_found and not symptom_found:
            return {
                "flag": f"code_{code}_symptom_mismatch",
                "severity": "medium",
                "recommendation": f"{code} typically occurs with {expected}, not the reported symptoms."
            }

        return None

    def _check_vin_applicability(
        self, obd_codes: list[str], vin_info: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Check if fault codes are common for this VIN."""
        make = vin_info.get("make", "")
        model = vin_info.get("model", "")
        year = vin_info.get("year", 0)

        # Try to find VIN pattern match
        for (v_make, v_model, v_year_range), patterns in self.VIN_FAULT_PATTERNS.items():
            if make.lower() == v_make.lower() and model.lower() == v_model.lower():
                rare_faults = patterns.get("rare_faults", [])
                for code in obd_codes:
                    # Check if this fault is rare for this VIN
                    if any(fault in code.lower() for fault in rare_faults):
                        return {
                            "flag": f"rare_fault_{code}_for_{make}_{model}",
                            "severity": "low",
                            "recommendation": f"{code} is unusual for {year} {make} {model}. Verify scan validity."
                        }

        return None

    def _check_semantic_contradiction(
        self, obd_codes: list[str], symptoms: str
    ) -> dict[str, Any] | None:
        """Check semantic impossibilities."""
        for key, contradiction_info in self.SEMANTIC_CONTRADICTIONS.items():
            codes_to_check = contradiction_info["codes"]
            expected_symptoms = contradiction_info["symptoms"]

            # Check if codes match
            code_match = any(
                (code_pattern == "*") or (code_pattern in obd_codes)
                for code_pattern in codes_to_check
            )

            if code_match:
                # Check if symptoms match (contradiction is when they do)
                symptom_match = any(symptom in symptoms for symptom in expected_symptoms)

                if symptom_match:
                    return {
                        "flag": key,
                        "severity": contradiction_info["severity"],
                        "recommendation": contradiction_info["flag"]
                    }

        return None

    def _severity_to_score(self, severity: str) -> float:
        """Convert severity string to numeric score."""
        return {
            "high": 0.8,
            "medium": 0.5,
            "low": 0.2
        }.get(severity, 0.0)

    def get_warning_text(self, contradiction_score: float) -> str | None:
        """Generate warning text for high contradiction scores."""
        if contradiction_score >= 0.7:
            return "⚠️ MAJOR CONTRADICTION: Symptoms and codes don't align. Verify scan validity."
        elif contradiction_score >= 0.4:
            return "⚠️ Minor contradiction detected. Confirm with additional testing."
        else:
            return None
