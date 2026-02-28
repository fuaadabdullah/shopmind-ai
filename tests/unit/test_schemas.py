import pytest
from pydantic import ValidationError

from app.schemas import DiagnosticRequest, HybridDiagnosticRequest


def test_diagnostic_request_normalizes_fields():
    req = DiagnosticRequest(
        vin="1hgbh41jxmN109186",
        obdcodes="p0420, b1234",
        symptoms="  Engine misfiring at idle  ",
    )

    assert req.vin == "1HGBH41JXMN109186"
    assert req.obdcodes == "P0420,B1234"
    assert req.symptoms == "Engine misfiring at idle"


def test_diagnostic_request_invalid_vin_rejected():
    with pytest.raises(ValidationError):
        DiagnosticRequest(
            vin="1HGBH41JXMN10918!",
            obdcodes="P0420",
            symptoms="Engine misfiring at idle",
        )


def test_diagnostic_request_invalid_obdcodes_rejected():
    with pytest.raises(ValidationError):
        DiagnosticRequest(
            vin="1HGBH41JXMN109186",
            obdcodes="P0X20",
            symptoms="Engine misfiring at idle",
        )


def test_diagnostic_request_empty_symptoms_rejected():
    with pytest.raises(ValidationError):
        DiagnosticRequest(
            vin="1HGBH41JXMN109186",
            obdcodes="P0420",
            symptoms="   ",
        )


def test_hybrid_request_defaults_and_vin_normalization():
    req = HybridDiagnosticRequest(
        vin="jm1bk343551316012",
        obdcodes="P0171",
        symptoms="Rough idle and check engine light",
    )

    assert req.use_llm is False
    assert req.vin == "JM1BK343551316012"
