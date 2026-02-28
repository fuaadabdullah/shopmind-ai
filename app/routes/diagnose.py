"""
Diagnostic reasoning endpoint for generating repair recommendations.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import ShopMindAIException
from ..logger import setup_logger
from ..schemas import DiagnosticRequest, DiagnosticResponse
from ..services import (
    build_diagnostic_response,
    persist_diagnostic_session,
    retrieve_diagnostic_documents,
    score_diagnostics,
    validate_diagnostic_request
)

logger = setup_logger(__name__)

router = APIRouter(prefix="/api", tags=["diagnostics"])


@router.post(
    "/diagnose",
    summary="Generate diagnostic recommendations",
    responses={
        200: {"description": "Successful diagnosis"},
        400: {"description": "Invalid input"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
        504: {"description": "Provider timeout"}
    }
)
async def diagnose(
    request: Request,
    req: DiagnosticRequest,
    db: Annotated[Session, Depends(get_db)]
) -> DiagnosticResponse:
    """
    Generate diagnostic recommendations based on VIN, OBD codes, and symptoms.

    This endpoint retrieves relevant diagnostic information from the knowledge base
    and uses an LLM to rank likely causes and provide repair recommendations.

    **Rate limit**: 10 requests per minute per IP address

    **Input validation**:
    - VIN: Must be exactly 17 alphanumeric characters
    - OBD codes: Must follow P/B/C/U + 4 digits format (max 500 chars)
    - Symptoms: 10-5000 characters

    **Returns**:
    - Ranked list of likely diagnostic causes
    - Recommended confirmatory tests
    - Estimated labor time
    """
    request_id = request.state.request_id

    try:
        # 1. Validate request and decode VIN
        validated_data = validate_diagnostic_request(req, request_id)
        vehicle_info = validated_data["vehicle_info"]

        # 2. Retrieve relevant diagnostic documents
        retrieved_docs = retrieve_diagnostic_documents(
            symptoms=req.symptoms,
            obdcodes=req.obdcodes,
            request_id=request_id
        )

        # 3. Score and rank diagnostics (with optional Torch V2 context)
        ranked_result, ranking_metadata = score_diagnostics(
            symptoms=req.symptoms,
            retrieved_docs=retrieved_docs,
            vin=req.vin,
            obd_codes=req.obdcodes,
            request_id=request_id
        )

        # 4. Persist diagnostic session (with Torch Phase 2 metadata)
        session_id = persist_diagnostic_session(
            db=db,
            vin=req.vin,
            symptoms=req.symptoms,
            obdcodes=req.obdcodes,
            vehicle_info=vehicle_info,
            ranked_result=ranked_result,
            request_id=request_id,
            ranking_metadata=ranking_metadata
        )

        # 5. Build and return response
        response = build_diagnostic_response(
            ranked_result=ranked_result,
            request_id=request_id,
            vehicle_info=vehicle_info,
            session_id=session_id,
            ranking_metadata=ranking_metadata
        )

        return response

    except ShopMindAIException:
        # Re-raise application exceptions to be handled by exception handler
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error in diagnose endpoint: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise
