"""
Diagnostic service layer for core business logic.

Handles validation, retrieval, scoring, persistence, and response building
for diagnostic requests. Separates concerns and improves testability.

Includes optional Torch V2 probability engine integration (Week 2).

## SECURITY

All database operations use SQLAlchemy ORM exclusively.
User input flows through Pydantic validation before any database access.
No raw SQL execution. All queries are parameterized by design.
"""
import hashlib
from typing import Any

from sqlalchemy.orm import Session

from ..exceptions import ValidationError as AppValidationError, ShopMindAIException
from ..logger import setup_logger
from ..ml.mock_predictor import predict_mock
from ..ml.predictor import is_model_available, predict_structured
from ..ml.schemas import TorchPrediction
from ..models import RootCause, DiagnosticSession
from ..ranker import rank_diagnostics as llm_rank_diagnostics
from ..retriever import retrieve
from ..schemas import DiagnosticRequest, DiagnosticResponse
from ..tools.vin_decoder import decode_vin

logger = setup_logger(__name__)


def validate_diagnostic_request(
    req: DiagnosticRequest,
    request_id: str,
) -> dict[str, Any]:
    """
    Perform additional validation beyond schema validators.

    Args:
        req: Diagnostic request object
        request_id: Request ID for logging

    Returns:
        Dictionary with validated data

    Raises:
        AppValidationError: If validation fails
    """
    logger.info(
        f"Validating diagnostic request for VIN: {req.vin}",
        extra={"request_id": request_id}
    )

    try:
        # Decode and validate VIN
        vehicle_info = decode_vin(req.vin)
        if not vehicle_info:
            raise AppValidationError(
                "Invalid or unrecognized VIN",
                details={"vin": req.vin}
            )

        logger.info(
            f"VIN decoded successfully: {vehicle_info.get('make')} "
            f"{vehicle_info.get('model')} {vehicle_info.get('year')}",
            extra={"request_id": request_id}
        )

        return {
            "vin": req.vin,
            "obdcodes": req.obdcodes,
            "symptoms": req.symptoms,
            "vehicle_info": vehicle_info
        }

    except AppValidationError:
        raise
    except Exception as e:
        logger.error(
            f"Validation error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise AppValidationError(
            "VIN validation failed",
            details={"error": str(e)}
        ) from e


def retrieve_diagnostic_documents(
    symptoms: str,
    obdcodes: str,
    request_id: str,
    top_k: int = 10
) -> list[dict[str, Any]]:
    """
    Retrieve relevant diagnostic documents from knowledge base.

    Args:
        symptoms: Customer-reported symptoms
        obdcodes: OBD diagnostic codes
        request_id: Request ID for logging
        top_k: Number of top results to retrieve

    Returns:
        List of retrieved documents

    Raises:
        AppValidationError: If no documents found
        ShopMindAIException: If retrieval fails
    """
    logger.info(
        "Retrieving diagnostic documents for symptoms and codes",
        extra={"request_id": request_id}
    )

    try:
        # Combine symptoms and codes for retrieval
        query = f"{symptoms} {obdcodes}"

        # Retrieve relevant documents
        retrieved_docs = retrieve(query, top_k=top_k)

        if not retrieved_docs:
            logger.warning(
                "No relevant documents found for query",
                extra={"request_id": request_id}
            )
            raise AppValidationError(
                "No relevant diagnostic information found. "
                "Please check your symptoms and OBD codes.",
                details={"symptoms": symptoms, "obdcodes": obdcodes}
            )

        logger.info(
            f"Retrieved {len(retrieved_docs)} diagnostic documents",
            extra={"request_id": request_id}
        )

        return retrieved_docs

    except AppValidationError:
        raise
    except ShopMindAIException:
        raise
    except Exception as e:
        logger.error(
            f"Document retrieval failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise


def get_torch_context(
    vin: str,
    obd_codes: str,
    symptoms: str,
    request_id: str
) -> TorchPrediction | None:
    """
    Optionally generate Torch V2 context for diagnostic ranking.

    Attempts to load real trained model; falls back to mock for demo.
    Returns None if Torch disabled or fails—gracefully degrades to Phase 1.

    Args:
        vin: Vehicle Identification Number
        obd_codes: OBD diagnostic codes
        symptoms: Customer symptoms
        request_id: Request ID for logging

    Returns:
        TorchPrediction object if available, None otherwise
    """
    try:
        # Try real model first (once trained)
        if is_model_available():
            logger.debug(
                "Using real Torch V2 model",
                extra={"request_id": request_id}
            )
            torch_pred = predict_structured(vin, obd_codes, symptoms)
            logger.info(
                f"[{torch_pred.request_id}] Torch prediction successful (real model)",
                extra={"request_id": request_id}
            )
            return torch_pred
        else:
            # Demo mode: use mock predictor
            logger.debug(
                "No trained model available, using mock Torch (demo mode)",
                extra={"request_id": request_id}
            )
            torch_pred = predict_mock(vin, obd_codes, symptoms)
            logger.info(
                f"[{torch_pred.request_id}] Torch prediction successful (demo mock)",
                extra={"request_id": request_id}
            )
            return torch_pred

    except Exception as e:
        logger.warning(
            f"Torch context generation failed, continuing without: {str(e)}",
            extra={"request_id": request_id}
        )
        return None


def score_diagnostics(
    symptoms: str,
    retrieved_docs: list[dict[str, Any]],
    vin: str,
    obd_codes: str,
    request_id: str
) -> tuple[str, dict[str, Any] | None]:
    """
    Score and rank diagnostics using LLM (optionally with Torch context).

    Phase 1 (Pure RAG): LLM ranks based on symptoms + manual docs.
    Phase 2 (Optional Torch): Also includes confidence scores and contradiction detection.

    Args:
        symptoms: Customer symptoms for context
        retrieved_docs: Documents retrieved from knowledge base
        vin: Vehicle Identification Number (for Torch)
        obd_codes: OBD codes (for Torch)
        request_id: Request ID for logging

    Returns:
        Tuple of (ranked_result_text, detailed_ranking_dict)
        Ranking dict includes torch_enabled: bool, torch_request_id if applicable

    Raises:
        ShopMindAIException: If scoring fails
    """
    logger.info(
        "Scoring diagnostics with LLM ranking (Phase 1)",
        extra={"request_id": request_id}
    )

    try:
        # Get optional Torch context (Week 2 enhancement)
        torch_context = get_torch_context(vin, obd_codes, symptoms, request_id)
        torch_enabled = torch_context is not None
        torch_request_id = torch_context.request_id if torch_context else None

        if torch_enabled:
            logger.debug(
                "Torch V2 context available for ranking",
                extra={"request_id": request_id, "torch_id": torch_request_id}
            )

        # Rank diagnostics using LLM (RAG ± optional Torch context)
        ranking_text, ranking_metadata = llm_rank_diagnostics(
            symptoms, retrieved_docs, vin=vin, obd_codes=obd_codes,
            torch_context=torch_context
        )

        # Add Torch metadata to response
        if ranking_metadata:
            ranking_metadata["torch_enabled"] = torch_enabled
            if torch_context:
                ranking_metadata["torch_request_id"] = torch_request_id
                ranking_metadata["top_torch_diagnosis"] = (
                    torch_context.top_diagnoses[0].code
                    if torch_context.top_diagnoses else None
                )
                ranking_metadata["torch_contradictions_detected"] = (
                    torch_context.contradiction_detection.has_contradiction
                )

        logger.info(
            "Diagnostic scoring completed successfully",
            extra={
                "request_id": request_id,
                "engine": ranking_metadata.get("engine") if ranking_metadata else "unknown",
                "torch_enabled": torch_enabled
            }
        )

        return ranking_text, ranking_metadata

    except ShopMindAIException:
        raise
    except Exception as e:
        logger.error(
            f"Diagnostic scoring failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise


def persist_diagnostic_session(
    db: Session | None,
    vin: str,
    symptoms: str,
    obdcodes: str,
    vehicle_info: dict[str, Any],
    ranked_result: str,
    request_id: str,
    ranking_metadata: dict[str, Any] | None = None
) -> int | None:
    """
    Persist diagnostic session to database.

    Creates DiagnosticSession record (for feedback loop & Torch Phase 2)
    and RootCause record (for historical tracking).

    Args:
        db: Database session
        vin: Vehicle Identification Number
        symptoms: Customer symptoms
        obdcodes: OBD codes
        vehicle_info: Decoded vehicle information
        ranked_result: LLM ranking result text
        request_id: Request ID for logging
        ranking_metadata: Optional Torch predictions and ranking metadata

    Returns:
        Session ID if persisted, None otherwise

    SECURITY: All user input (vin, symptoms, obdcodes, vehicle_info) is inserted
              using SQLAlchemy ORM's parameterized .add() method.
              Input is validated by Pydantic before reaching this function.
    """
    if not db:
        logger.debug(
            "Skipping persistence: no database session",
            extra={"request_id": request_id, "vin": vin}
        )
        return None

    try:
        # Create symptom hash for deduplication
        symptom_hash = hashlib.sha256(
            symptoms.encode()
        ).hexdigest()

        # Extract first suggested cause from ranked result
        # This is a simplified extraction; enhance as needed
        suggested_cause = (
            ranked_result.split('\n')[0]
            if ranked_result
            else "Unknown"
        )

        # Extract Torch predictions from ranking metadata (if available)
        torch_predictions = None
        confidence_score = None
        if ranking_metadata:
            if "torch_predictions" in ranking_metadata:
                torch_predictions = ranking_metadata["torch_predictions"]
            if "confidence_score" in ranking_metadata:
                confidence_score = ranking_metadata["confidence_score"]

        # Create DiagnosticSession record (main persistence for feedback loop)
        diagnostic_session = DiagnosticSession(
            vin=vin,
            symptoms=symptoms,
            obd_codes=obdcodes,
            make=vehicle_info.get("make"),
            model=vehicle_info.get("model"),
            year=vehicle_info.get("year"),
            top_cause=suggested_cause,
            confidence_score=confidence_score,
            torch_predictions=torch_predictions,
            predicted_causes=None,  # Future: structured LLM outputs
            training_ready=False  # Will be set to True on feedback confirmation
        )

        # Also create RootCause record (historical tracking)
        root_cause_record = RootCause(
            make=vehicle_info.get("make", "Unknown"),
            model=vehicle_info.get("model", "Unknown"),
            year=vehicle_info.get("year", "Unknown"),
            symptom_hash=symptom_hash,
            symptom_text=symptoms,
            cause=suggested_cause,
            confirmed_cause="",  # Empty until confirmed
            obd_codes=obdcodes,
            source_type="api_request",
            initial_confidence=confidence_score
        )

        db.add(diagnostic_session)
        db.add(root_cause_record)
        db.commit()

        logger.info(
            f"Diagnostic session persisted: DiagnosticSession ID={diagnostic_session.id}, "
            f"RootCause ID={root_cause_record.id}, torch_enabled={bool(torch_predictions)}",
            extra={"request_id": request_id}
        )

        return diagnostic_session.id

    except Exception as e:
        # Graceful degradation: log error with full context but don't crash
        logger.error(
            f"Failed to persist diagnostic session: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True  # Full stack trace for debugging
        )
        # Attempt rollback to ensure clean transaction state
        try:
            db.rollback()
        except Exception as rollback_error:
            logger.warning(
                f"Rollback failed during persistence error: {str(rollback_error)}",
                extra={"request_id": request_id}
            )
        # Don't raise - persistence failure shouldn't break the diagnostic response
        return None


def build_diagnostic_response(
    ranked_result: str,
    request_id: str,
    vehicle_info: dict[str, Any] | None = None,
    session_id: int | None = None,
    ranking_metadata: dict[str, Any] | None = None
) -> DiagnosticResponse:
    """
    Build the complete diagnostic response.

    Args:
        ranked_result: Ranked diagnostics text from LLM
        request_id: Request ID for tracing
        vehicle_info: Decoded vehicle information
        session_id: Persisted database session ID
        ranking_metadata: Metadata from ranking including Torch info

    Returns:
        DiagnosticResponse object ready for serialization
    """
    logger.info(
        "Building diagnostic response",
        extra={"request_id": request_id, "torch_enabled": ranking_metadata.get("torch_enabled") if ranking_metadata else False}
    )

    return DiagnosticResponse(
        result=ranked_result,
        request_id=request_id,
        vehicle_info=vehicle_info,
        ranked_results=None,  # Future: structured ranked results
        explanation=None,      # Future: detailed ranking explanation
        session_id=session_id
    )
