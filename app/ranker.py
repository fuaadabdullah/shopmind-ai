"""
Diagnostic ranking functionality (Phase 1: Pure RAG + Optional Torch V2).

Rank and explain likely diagnostic causes using semantic search (FAISS) + LLM reasoning.
Optionally integrates Torch V2 probability engine for confidence calibration and cost analysis.

Architecture:
    Input (symptoms, OBD, VIN)
        ↓
    Retriever (semantic search via FAISS)
        ↓ (pulls relevant manual chunks)
    Torch V2 [Optional] (probability engine + confidence calibration)
        ↓ (adds: confidence scores, contradictions, cost ranking)
    Ranker (this module - LLM reasoning with optional Torch context)
        ↓ (explains and ranks causes)
    Output (ranked diagnostics with sources + optional Torch insights)

Philosophy:
    - Docs teach WHAT EXISTS (knowledge library)
    - LLM teaches HOW TO APPLY KNOWLEDGE (reasoning)
    - Torch teaches WHAT USUALLY HAPPENS (probability/instinct from repair history)

Resilience:
    - LLM providers wrapped with circuit breaker to prevent cascading failures
    - Automatic fallback to alternate provider (GCP <-> SiliconeFlow) when primary fails
    - Degraded mode: returns raw FAISS results if both providers unavailable
"""
import time
from typing import Any

from .exceptions import RankingError, ProviderError
from .logger import setup_logger
from .metrics import llm_response_latency_seconds, llm_calls_total, llm_fallback_activated_total
from .providers.base import get_provider, get_fallback_provider

logger = setup_logger(__name__)



def _format_docs_with_sources(
    retrieved_docs: list[dict[str, Any]],
) -> str:
    """
    Format retrieved documents with source attribution.

    Each doc becomes a numbered source block so LLM can cite which manual
    informed each diagnosis.

    Args:
        retrieved_docs: List of doc dicts from FAISS retrieval
            Expected keys: 'content' or 'text', 'source' or 'file'

    Returns:
        Formatted string with doc content and sources
    """
    if not retrieved_docs:
        return "No supporting manual data available."

    lines = []
    for i, doc in enumerate(retrieved_docs, 1):
        # Extract content and source (flexible keys)
        content = doc.get("content", doc.get("text", ""))
        source = doc.get("source", doc.get("file", "Manual"))

        lines.append(f"[Source {i}: {source}]")
        lines.append(content[:500])  # Truncate to avoid token bloat
        lines.append("")

    return "\n".join(lines)


def _format_torch_context(torch_prediction: Any) -> str:
    """
    Format Torch V2 predictions for LLM context.

    Torch provides:
    - Calibrated probability estimates from trained model
    - Contradiction flags (impossible combinations)
    - Uncertainty quantification
    - Cost-weighted rankings

    Args:
        torch_prediction: TorchPrediction object from ml.predictor.predict_structured()

    Returns:
        Formatted string with Torch insights for LLM prompt

    Example output:
        TORCH V2 INTELLIGENCE (Trained on 5000+ repair confirmations):
        Top diagnoses by probability:
        1. MAF Sensor: 78% confidence (±12% uncertainty)
        2. EGR Valve: 45% confidence (±8% uncertainty)

        Cost analysis (by ROI):
        1. Fuel Filter: 89% ROI (75% prob, $45 total)
        2. Spark Plugs: 62% ROI (68% prob, $85 total)

        Warnings:
        - Contradiction detected: P0171 + P0174 together = rare combo (flag: 0.68)
        - High uncertainty: Only 62% confident in top diagnosis
    """
    if torch_prediction is None:
        return ""

    try:
        lines = [
            "TORCH V2 INTELLIGENCE (Trained model - probability calibration from repair history):"
        ]

        # Top diagnoses with confidence
        if torch_prediction.top_diagnoses:
            lines.append("\nMost likely causes (by probability):")
            for diag in torch_prediction.top_diagnoses[:5]:
                uncertainty = torch_prediction.uncertainty_factors.total_uncertainty
                lines.append(
                    f"  {diag.rank}. [{diag.code}] {diag.description}: "
                    f"{diag.calibrated_probability:.0%} confidence "
                    f"(±{uncertainty:.1%} uncertainty)"
                )

        # Contradiction warnings
        if torch_prediction.contradiction_detection.has_contradiction:
            lines.append("\n⚠️ CONTRADICTION DETECTED (Unusual combination):")
            for flag in torch_prediction.contradiction_detection.flags[:3]:
                desc = flag.description if hasattr(flag, 'description') else str(flag)
                sev = flag.severity if hasattr(flag, 'severity') else 'unknown'
                lines.append(
                    f"  - {desc} "
                    f"(severity: {sev})"
                )

        # Cost-benefit ranking
        if torch_prediction.cost_weighted_ranking.by_roi:
            lines.append("\nBest repair ROI (probability vs cost):")
            for opt in torch_prediction.cost_weighted_ranking.by_roi[:3]:
                lines.append(
                    f"  {opt['rank']}. {opt['description']}: "
                    f"${opt['estimated_cost_usd']:.0f} "
                    f"({opt['roi_score']:.2f} ROI)"
                )

        return "\n".join(lines)

    except Exception as e:
        logger.warning("Failed to format Torch context: %s", e)
        return ""


def _format_degraded_mode_results(docs: list[dict[str, Any]]) -> str:
    """
    Format documents for degraded mode response (LLM unavailable).
    
    Returns raw FAISS results ranked by relevance when LLM provider(s) fail.
    This provides partial functionality instead of total service failure.
    
    Args:
        docs: Retrieved documents from FAISS
        
    Returns:
        Formatted string with ranked documents
    """
    if not docs:
        return (
            "Connection to diagnostic reasoning service (LLM) is temporarily unavailable. "
            "No supporting manual data is available to provide recommendations at this time. "
            "Please try again later."
        )
    
    lines = [
        "DEGRADED MODE: Diagnostic reasoning service (LLM) is temporarily unavailable.",
        "Below are relevant manual sections retrieved from knowledge base (ranked by relevance):",
        "",
    ]
    
    for i, doc in enumerate(docs, 1):
        content = doc.get("content", doc.get("text", ""))
        source = doc.get("source", doc.get("file", "Manual"))
        relevance = doc.get("relevance_score", doc.get("score", 0.0))
        
        lines.append(f"{i}. [{source}] (Relevance: {relevance:.2%})")
        lines.append(f"   {content[:300]}...")
        lines.append("")
    
    lines.append(
        "Note: For complete diagnostics with AI reasoning, please wait for "
        "service recovery."
    )
    
    return "\n".join(lines)


def _call_llm_with_fallback(prompt: str) -> tuple[str | None, str, bool]:
    """
    Call LLM with automatic fallback on circuit breaker failure.
    
    Attempts primary provider first, then fallback provider if primary's
    circuit is open. Returns None if both fail.
    
    Args:
        prompt: Diagnostic prompt for LLM
        
    Returns:
        Tuple of (result_text, primary_provider_name, used_fallback_flag)
    """
    llm_start = time.time()
    provider = get_provider()
    result = None
    used_fallback = False
    provider_name = getattr(provider, "provider_name", "unknown")
    
    try:
        result = provider.generate(prompt)
        llm_elapsed = time.time() - llm_start
        llm_response_latency_seconds.labels(
            provider=provider_name,
            model_status="success"
        ).observe(llm_elapsed)
        llm_calls_total.labels(
            provider=provider_name,
            model_status="success"
        ).inc()
    except ProviderError as e:
        llm_elapsed = time.time() - llm_start
        
        # Log failure
        llm_response_latency_seconds.labels(
            provider=provider_name,
            model_status="error"
        ).observe(llm_elapsed)
        llm_calls_total.labels(
            provider=provider_name,
            model_status="error"
        ).inc()
        
        # Check if this is circuit breaker and attempt fallback
        if "Circuit breaker" in str(e) or "open" in str(e).lower():
            logger.warning(
                "Primary provider (%s) circuit breaker open, attempting fallback",
                provider_name,
                extra={"provider": provider_name}
            )
            
            fallback = get_fallback_provider()
            if fallback:
                fallback_name = getattr(fallback, "provider_name", "unknown")
                fallback_start = time.time()
                used_fallback = True  # Mark as used when attempting
                try:
                    result = fallback.generate(prompt)
                    fallback_elapsed = time.time() - fallback_start
                    
                    llm_fallback_activated_total.labels(
                        primary_provider=provider_name,
                        fallback_provider=fallback_name,
                        reason="circuit_breaker"
                    ).inc()
                    
                    llm_response_latency_seconds.labels(
                        provider=fallback_name,
                        model_status="success"
                    ).observe(fallback_elapsed)
                    llm_calls_total.labels(
                        provider=fallback_name,
                        model_status="success"
                    ).inc()
                    
                    logger.info(
                        "Fallback provider (%s) succeeded",
                        fallback_name
                    )
                except ProviderError:
                    fallback_elapsed = time.time() - fallback_start
                    logger.error(
                        "Fallback provider (%s) also failed",
                        fallback_name
                    )
                    llm_response_latency_seconds.labels(
                        provider=fallback_name,
                        model_status="error"
                    ).observe(fallback_elapsed)
                    llm_calls_total.labels(
                        provider=fallback_name,
                        model_status="error"
                    ).inc()
                    result = None
            else:
                logger.warning("No fallback provider available")
                result = None
        else:
            # Not circuit breaker, re-raise
            raise
    
    return result, provider_name, used_fallback


def rank_diagnostics(
    symptoms: str,
    retrieved_docs: list[dict[str, Any]],
    vin: str = "",
    obd_codes: str = "",
    torch_context: Any = None,
) -> tuple[str, dict[str, Any]]:
    """
    Rank diagnostic causes using semantic search (RAG) + optional Torch V2.

    Uses vector DB retrieval (FAISS) to pull relevant manual passages,
    then feeds them (+ optional Torch insights) to LLM for cause ranking.

    This is Phase 1 (docs + LLM) with optional Phase 2 context (Torch probabilities).
    Torch is strictly optional—Phase 1 works standalone.

    Args:
        symptoms: Customer-reported symptoms and diagnostic codes
        retrieved_docs: List of relevant diagnostic manual passages from FAISS
            Each doc should have 'content' and 'source' keys
        vin: Vehicle Identification Number (optional, for context only)
        obd_codes: OBD-II codes comma-separated (optional, for context)
        torch_context: TorchPrediction object from ml.predictor.predict_structured()
            (Optional—adds confidence scores, contradictions, cost analysis if provided)

    Returns:
        Tuple of (formatted_ranking_text, metadata_dict)
        - ranking_text: Ranked diagnostics with explanations and sources
        - metadata: {
            'engine': 'RAG + optional Torch V2',
            'num_docs': int,
            'doc_sources': list[str],
            'torch_enabled': bool,
            'phase': 'Phase 1 + optional Phase 2'
          }

    Raises:
        RankingError: If ranking generation fails

    Example:
        >>> ranking, meta = rank_diagnostics(
        ...     "Check engine light, rough idle",
        ...     [{"content": "...", "source": "TSB-001"}, ...],
        ...     vin="1HG...",
        ...     obd_codes="P0420",
        ...     torch_context=None  # Optional
        ... )
    """
    if not symptoms or not symptoms.strip():
        logger.warning("Empty symptoms provided for ranking")
        return "Error: No symptoms provided", {}

    if not retrieved_docs:
        logger.warning("No documents provided for ranking")
        return "Error: No relevant diagnostic information found", {}

    try:
        logger.info(
            "Ranking diagnostics (RAG) - symptoms: %d chars, docs: %d sources",
            len(symptoms),
            len(retrieved_docs)
        )

        # Format docs with source attribution
        formatted_docs = _format_docs_with_sources(retrieved_docs)

        # Format Torch context if available (optional Phase 2 enhancement)
        torch_section = ""
        torch_enabled = False
        if torch_context is not None:
            torch_section = _format_torch_context(torch_context)
            torch_enabled = True
            logger.debug("Torch V2 context included in ranking prompt")

        # Build RAG prompt: symptoms + docs + optional Torch + reasoning task
        prompt = f"""You are an expert automotive diagnostic assistant for mechanics.

CUSTOMER INPUT:
Symptoms: {symptoms}
Vehicle: {vin if vin else "Unknown"}
OBD Codes: {obd_codes if obd_codes else "None"}

KNOWLEDGE BASE (Retrieved Manual Data):
{formatted_docs}
"""
        if torch_section:
            prompt += f"\n{torch_section}\n"

        prompt += """
TASK:
Rank the top 5 most likely diagnostic causes based on the symptoms and manual data.

For each cause, provide:
1. **Cause Name**
2. **Why**: 1-2 sentence explanation (cite the manual sources)
3. **Tests**: 2-3 confirmatory diagnostic tests
4. **Labor**: Approximate repair time in hours
5. **Parts**: Common parts to replace or inspect

INSTRUCTIONS:
- Prioritize causes that align with BOTH the symptoms AND the manual data
- Include source citations: [Source 1], [Source 2], etc.
- Be practical and mechanic-focused (not chatbot vibes)
- Rank by likelihood, not alphabetically
- If a cause appears in multiple sources, it's likely correct
- If Torch probabilities are provided, use them as a tiebreaker (confidence calibration)
- Do NOT invent causes not in the manual data

RESPONSE FORMAT:
1. [Cause Name]
   Why: [explanation with sources]
   Tests: [diagnostic steps]
   Labor: [hours]
   Parts: [part names/numbers]

2. [Next Cause]
   [same format...]

BEGIN YOUR RANKING:
"""

        logger.debug("Sending RAG ranking request to LLM provider")
        result, _, used_fallback = _call_llm_with_fallback(prompt)

        logger.info("RAG diagnostic ranking generation attempt completed")

        # Extract source info from docs
        sources = [
            doc.get("source", doc.get("file", "Manual")) for doc in retrieved_docs
        ]

        # Handle degraded mode if LLM is unavailable
        if result is None:
            logger.warning(
                "Both primary and fallback LLM providers unavailable, "
                "returning degraded mode (raw FAISS results)"
            )
            # In degraded mode, return raw FAISS results ranked by relevance
            result = _format_degraded_mode_results(retrieved_docs)
            metadata = {
                "engine": "FAISS retrieval (degraded mode - LLM unavailable)",
                "num_docs": len(retrieved_docs),
                "doc_sources": list(set(sources)),
                "torch_enabled": torch_enabled,
                "phase": "Degraded mode (no LLM ranking)",
                "llm_unavailable": True,
                "fallback_used": used_fallback,
            }
        else:
            metadata = {
                "engine": "RAG + optional Torch V2",
                "num_docs": len(retrieved_docs),
                "doc_sources": list(set(sources)),  # Unique sources
                "torch_enabled": torch_enabled,
                "phase": "Phase 1 (RAG) + optional Phase 2 (Torch probability)",
                "llm_unavailable": False,
                "fallback_used": used_fallback,
            }

        return result, metadata

    except Exception as e:
        logger.error("RAG ranking failed: %s", str(e), exc_info=True)
        raise RankingError(
            "Failed to rank diagnostics",
            details={
                "error": str(e),
                "symptoms_length": len(symptoms),
                "num_docs": len(retrieved_docs),
            },
        ) from e

