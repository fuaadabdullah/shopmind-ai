"""
Pydantic request/response models for ShopMindAI API endpoints.
"""
from pydantic import BaseModel, Field, field_validator


class DiagnosticRequest(BaseModel):
    """Request model for diagnostic endpoint."""

    vin: str = Field(
        ...,
        min_length=17,
        max_length=17,
        description="17-character Vehicle Identification Number",
        examples=["1HGBH41JXMN109186"]
    )
    obdcodes: str = Field(
        ...,
        max_length=500,
        description="OBD-II diagnostic trouble codes (comma-separated)",
        examples=["P0300,P0420"]
    )
    symptoms: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Customer-reported symptoms",
        examples=["Engine misfiring, check engine light on, rough idle"]
    )

    @field_validator("vin")
    @classmethod
    def validate_vin(cls, v: str) -> str:
        """Validate VIN format."""
        if not v.isalnum():
            raise ValueError("VIN must contain only alphanumeric characters")
        # Note: Full VIN validation would check check digit, but basic validation for now
        return v.upper()

    @field_validator("obdcodes")
    @classmethod
    def validate_obdcodes(cls, v: str) -> str:
        """Validate OBD code format."""
        if not v.strip():
            return v

        codes = [code.strip().upper() for code in v.split(",")]
        for code in codes:
            if code and not (
                len(code) == 5 and
                code[0] in "PBCU" and
                code[1:].isdigit()
            ):
                raise ValueError(
                    f"Invalid OBD code format: {code}. "
                    f"Expected format: P/B/C/U followed by 4 digits"
                )

        return ",".join(codes)

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, v: str) -> str:
        """Validate symptoms content."""
        if not v.strip():
            raise ValueError("Symptoms cannot be empty")
        return v.strip()


class DiagnosticResponse(BaseModel):
    """Response model for diagnostic endpoint."""

    result: str = Field(
        ...,
        description="Ranked diagnostic causes with repair recommendations"
    )
    request_id: str | None = Field(
        None,
        description="Request ID for tracing"
    )
    # New fields for hybrid scoring
    ranked_results: list | None = Field(
        None,
        description="Structured ranked results with confidence scores"
    )
    explanation: str | None = Field(
        None,
        description="Detailed explanation of ranking"
    )
    vehicle_info: dict | None = Field(
        None,
        description="Decoded vehicle information from VIN"
    )
    session_id: int | None = Field(
        None,
        description="Persisted diagnostic session ID (if available)"
    )


class HybridDiagnosticRequest(BaseModel):
    """Request model for hybrid scoring diagnostic endpoint."""

    vin: str = Field(
        ...,
        min_length=17,
        max_length=17,
        description="17-character Vehicle Identification Number",
        examples=["1HGBH41JXMN109186"]
    )
    obdcodes: str = Field(
        ...,
        max_length=500,
        description="OBD-II diagnostic trouble codes (comma-separated)",
        examples=["P0300,P0420"]
    )
    symptoms: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Customer-reported symptoms",
        examples=["Engine misfiring, check engine light on, rough idle"]
    )
    use_llm: bool = Field(
        default=False,
        description="Whether to also generate LLM-based recommendations"
    )

    @field_validator("vin")
    @classmethod
    def validate_vin(cls, v: str) -> str:
        """Validate VIN format."""
        if not v.isalnum():
            raise ValueError("VIN must contain only alphanumeric characters")
        return v.upper()
    
    @field_validator("obdcodes")
    @classmethod
    def validate_obdcodes(cls, v: str) -> str:
        """Validate OBD code format."""
        if not v.strip():
            return v

        codes = [code.strip().upper() for code in v.split(",")]
        for code in codes:
            if code and not (
                len(code) == 5 and
                code[0] in "PBCU" and
                code[1:].isdigit()
            ):
                raise ValueError(
                    f"Invalid OBD code format: {code}. "
                    f"Expected format: P/B/C/U followed by 4 digits"
                )

        return ",".join(codes)

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, v: str) -> str:
        """Validate symptoms content."""
        if not v.strip():
            raise ValueError("Symptoms cannot be empty")
        return v.strip()
