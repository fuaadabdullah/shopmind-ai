"""
Cost-weighted ranking for Torch V2.

Generate multiple ranked diagnostic strategies based on:
- Probability (most likely broken)
- Cost (cheapest to fix)
- ROI (best bang for buck = highest probability / cost ratio)
"""
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class DiagnosticOption:
    """Single diagnostic rank with cost estimate."""

    rank: int
    code: str
    description: str
    probability: float
    estimated_cost: float  # USD
    estimated_labor_hours: float
    roi_score: float  # probability / cost ratio


class CostWeightedRanker:
    """
    Generate multiple diagnostic ranking strategies.

    Given probabilities and costs, Produce:
    1. ByProbability: Most likely diagnoses first
    2. ByCost: Cheapest fixes first
    3. ROI: Best probability/cost ratio first
    """

    # Approximate repair costs (can be updated from feedback loop)
    DIAGNOSIS_COSTS = {
        "maf": {"parts": 180, "labor_hours": 0.5},
        "o2": {"parts": 120, "labor_hours": 1.0},
        "spark_plugs": {"parts": 40, "labor_hours": 1.5},
        "fuel_filter": {"parts": 30, "labor_hours": 0.75},
        "intake_valve_carbon": {"parts": 0, "labor_hours": 3.0},
        "engine_knock": {"parts": 0, "labor_hours": 0.25},
        "transmission_solenoid": {"parts": 250, "labor_hours": 2.5},
        "timing_belt": {"parts": 400, "labor_hours": 5.0},
        "head_gasket": {"parts": 600, "labor_hours": 8.0},
        "catalytic_converter": {"parts": 800, "labor_hours": 2.0},
    }

    # Labor rate (USD/hour) - used to compute total cost
    LABOR_RATE = 125.0

    def __init__(self):
        """Initialize ranker."""
        logger.debug("CostWeightedRanker initialized")

    def rank_by_probability(
        self,
        diagnoses: dict[str, float]
    ) -> list[DiagnosticOption]:
        """
        Sort diagnostics by probability (descending).

        Args:
            diagnoses: {code: probability}

        Returns:
            List of DiagnosticOption sorted by probability
        """
        options = []
        for rank, (code, prob) in enumerate(
            sorted(diagnoses.items(), key=lambda x: x[1], reverse=True), 1
        ):
            cost = self._get_total_cost(code)
            roi = prob / (cost + 1) if cost >= 0 else 0

            options.append(
                DiagnosticOption(
                    rank=rank,
                    code=code,
                    description=self._get_description(code),
                    probability=prob,
                    estimated_cost=cost,
                    estimated_labor_hours=self._get_labor_hours(code),
                    roi_score=roi
                )
            )

        return options

    def rank_by_cost(
        self,
        diagnoses: dict[str, float]
    ) -> list[DiagnosticOption]:
        """
        Sort diagnostics by cost (ascending).

        Args:
            diagnoses: {code: probability}

        Returns:
            List of DiagnosticOption sorted by total cost
        """
        options = []
        for rank, (code, prob) in enumerate(
            sorted(
                diagnoses.items(),
                key=lambda x: self._get_total_cost(x[0])
            ),
            1
        ):
            cost = self._get_total_cost(code)
            roi = prob / (cost + 1) if cost >= 0 else 0

            options.append(
                DiagnosticOption(
                    rank=rank,
                    code=code,
                    description=self._get_description(code),
                    probability=prob,
                    estimated_cost=cost,
                    estimated_labor_hours=self._get_labor_hours(code),
                    roi_score=roi
                )
            )

        return options

    def rank_by_roi(
        self,
        diagnoses: dict[str, float]
    ) -> list[DiagnosticOption]:
        """
        Sort diagnostics by ROI = probability / cost (descending).

        Repairs that are likely AND cheap should be attempted first.

        Args:
            diagnoses: {code: probability}

        Returns:
            List of DiagnosticOption sorted by ROI score
        """
        options = []
        roi_items = []

        for code, prob in diagnoses.items():
            cost = self._get_total_cost(code)
            # Avoid division by zero + prefer low-cost fixes
            roi = prob / (cost + 1)
            roi_items.append((code, prob, roi))

        # Sort by ROI descending
        for rank, (code, prob, roi) in enumerate(
            sorted(roi_items, key=lambda x: x[2], reverse=True), 1
        ):
            cost = self._get_total_cost(code)

            options.append(
                DiagnosticOption(
                    rank=rank,
                    code=code,
                    description=self._get_description(code),
                    probability=prob,
                    estimated_cost=cost,
                    estimated_labor_hours=self._get_labor_hours(code),
                    roi_score=roi
                )
            )

        return options

    def rank_by_frequency(
        self,
        diagnoses: dict[str, float],
        repair_history_metrics: dict[str, dict[str, Any]] | None = None
    ) -> list[DiagnosticOption]:
        """
        Sort by repair frequency (how common is this fix for similar vehicles).

        Higher frequency = mechanic knows how to fix it fast.

        Args:
            diagnoses: {code: probability}
            repair_history_metrics: {code: {recurrence_rate, avg_labor_hours, avg_cost}}

        Returns:
            List of DiagnosticOption sorted by frequency
        """
        if repair_history_metrics is None:
            repair_history_metrics = {}

        options = []
        frequency_items = []

        for code, prob in diagnoses.items():
            # Get frequency from history or default to 0.5
            history = repair_history_metrics.get(code, {})
            frequency = history.get("recurrence_rate", 0.5)
            frequency_items.append((code, prob, frequency))

        # Sort by frequency descending
        for rank, (code, prob, frequency) in enumerate(
            sorted(frequency_items, key=lambda x: x[2], reverse=True), 1
        ):
            cost = self._get_total_cost(code)

            options.append(
                DiagnosticOption(
                    rank=rank,
                    code=code,
                    description=self._get_description(code),
                    probability=prob,
                    estimated_cost=cost,
                    estimated_labor_hours=self._get_labor_hours(code),
                    roi_score=prob / (cost + 1)
                )
            )

        return options

    def _get_total_cost(self, code: str) -> float:
        """
        Get total cost estimate (parts + labor) in USD.

        Args:
            code: Diagnostic code

        Returns:
            Total cost in USD
        """
        code_lower = code.lower().replace(" ", "_")
        default_cost = {"parts": 100, "labor_hours": 1.0}
        cost_dict = self.DIAGNOSIS_COSTS.get(code_lower, default_cost)

        parts_cost = cost_dict.get("parts", 0)
        labor_cost = cost_dict.get("labor_hours", 1.0) * self.LABOR_RATE

        return float(parts_cost + labor_cost)

    def _get_labor_hours(self, code: str) -> float:
        """Get estimated labor hours."""
        code_lower = code.lower().replace(" ", "_")
        default = 1.0
        return float(self.DIAGNOSIS_COSTS.get(code_lower, {"labor_hours": default}).get("labor_hours", default))

    @staticmethod
    def _get_description(code: str) -> str:
        """
        Get human-readable description for diagnostic code.

        Args:
            code: Diagnostic code

        Returns:
            Human-readable description
        """
        descriptions = {
            "maf": "Mass Airflow Sensor - detects air intake",
            "o2": "Oxygen Sensor - exhaust emissions detection",
            "spark_plugs": "Spark Plugs - engine ignition",
            "fuel_filter": "Fuel Filter - fuel system filtration",
            "intake_valve_carbon": "Intake Valve Carbon Buildup - engine deposits",
            "engine_knock": "Engine Knock Detection - pre-ignition",
            "transmission_solenoid": "Transmission Solenoid - shift control",
            "timing_belt": "Timing Belt - engine synchronization",
            "head_gasket": "Head Gasket - cylinder sealing",
            "catalytic_converter": "Catalytic Converter - emissions control",
        }
        code_lower = code.lower().replace(" ", "_")
        return descriptions.get(code_lower, code)

    def format_ranking_for_response(
        self,
        by_probability: list[DiagnosticOption],
        by_cost: list[DiagnosticOption] | None = None,
        by_roi: list[DiagnosticOption] | None = None,
        by_frequency: list[DiagnosticOption] | None = None,
    ) -> dict[str, list[dict]]:
        """
        Format ranked diagnostics for API response.

        Args:
            by_probability: Ranked by probability
            by_cost: Ranked by cost (optional)
            by_roi: Ranked by ROI (optional)
            by_frequency: Ranked by frequency (optional)

        Returns:
            Dict with {strategy: [{rank, code, description, probability, cost, ...}]}
        """
        result = {}

        if by_probability:
            result["by_probability"] = [self._option_to_dict(opt) for opt in by_probability]

        if by_cost:
            result["by_cost"] = [self._option_to_dict(opt) for opt in by_cost]

        if by_roi:
            result["by_roi"] = [self._option_to_dict(opt) for opt in by_roi]

        if by_frequency:
            result["by_frequency"] = [self._option_to_dict(opt) for opt in by_frequency]

        return result

    @staticmethod
    def _option_to_dict(option: DiagnosticOption) -> dict:
        """Convert DiagnosticOption to dictionary."""
        return {
            "rank": option.rank,
            "code": option.code,
            "description": option.description,
            "probability": round(option.probability, 3),
            "estimated_cost_usd": round(option.estimated_cost, 2),
            "estimated_labor_hours": round(option.estimated_labor_hours, 1),
            "roi_score": round(option.roi_score, 3),
        }
