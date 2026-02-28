"""
Integration test for Torch Phase 2 feedback loop persistence.

Verifies that DiagnosticSession records with Torch predictions
are correctly persisted to the database.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import DiagnosticSession, RootCause
from app.services.diagnostic_service import persist_diagnostic_session


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


def test_persist_diagnostic_session_with_torch_predictions(test_db: Session):
    """
    Test that DiagnosticSession persists torch_predictions correctly.
    
    Verifies:
    - DiagnosticSession record created with Torch metadata
    - RootCause record created for historical tracking
    - torch_predictions JSON field populated
    - confidence_score stored
    - training_ready defaults to False
    """
    # Arrange
    vin = "1HGBH41JXMN109186"
    symptoms = "Check engine light, rough idle"
    obdcodes = "P0420,P0171"
    vehicle_info = {
        "make": "Honda",
        "model": "Civic",
        "year": "2015"
    }
    ranked_result = "1. Catalytic Converter Efficiency Below Threshold\n2. O2 Sensor Failure"
    request_id = "test-123"
    
    ranking_metadata = {
        "torch_predictions": {
            "catalytic_converter": 0.67,
            "o2_sensor_downstream": 0.21,
            "maf_sensor": 0.08
        },
        "confidence_score": 0.87,
        "torch_enabled": True
    }
    
    # Act
    session_id = persist_diagnostic_session(
        db=test_db,
        vin=vin,
        symptoms=symptoms,
        obdcodes=obdcodes,
        vehicle_info=vehicle_info,
        ranked_result=ranked_result,
        request_id=request_id,
        ranking_metadata=ranking_metadata
    )
    
    # Assert
    assert session_id is not None
    
    # Verify DiagnosticSession record
    diagnostic_session = test_db.query(DiagnosticSession).filter(
        DiagnosticSession.id == session_id
    ).first()
    
    assert diagnostic_session is not None
    assert diagnostic_session.vin == vin
    assert diagnostic_session.symptoms == symptoms
    assert diagnostic_session.obd_codes == obdcodes
    assert diagnostic_session.make == "Honda"
    assert diagnostic_session.model == "Civic"
    assert diagnostic_session.year == "2015"
    assert diagnostic_session.top_cause == "1. Catalytic Converter Efficiency Below Threshold"
    assert diagnostic_session.confidence_score == 0.87
    assert diagnostic_session.torch_predictions == ranking_metadata["torch_predictions"]
    assert diagnostic_session.training_ready is False  # Should default to False until feedback
    assert diagnostic_session.confirmed_cause is None  # Not yet confirmed
    
    # Verify RootCause record also created
    root_cause = test_db.query(RootCause).first()
    assert root_cause is not None
    assert root_cause.make == "Honda"
    assert root_cause.model == "Civic"
    assert root_cause.obd_codes == obdcodes
    assert root_cause.initial_confidence == 0.87


def test_persist_diagnostic_session_without_torch(test_db: Session):
    """
    Test persistence when Torch predictions are not available (Phase 1 only).
    
    Verifies graceful handling when ranking_metadata is None or empty.
    """
    # Arrange
    vin = "WVWZZZ3CZ9P123456"
    symptoms = "Engine stalling"
    obdcodes = "P0300"
    vehicle_info = {
        "make": "Volkswagen",
        "model": "Golf",
        "year": "2009"
    }
    ranked_result = "1. Ignition Coil Failure\n2. Spark Plug Fouling"
    request_id = "test-456"
    
    # Act - No ranking_metadata provided
    session_id = persist_diagnostic_session(
        db=test_db,
        vin=vin,
        symptoms=symptoms,
        obdcodes=obdcodes,
        vehicle_info=vehicle_info,
        ranked_result=ranked_result,
        request_id=request_id,
        ranking_metadata=None
    )
    
    # Assert
    assert session_id is not None
    
    diagnostic_session = test_db.query(DiagnosticSession).filter(
        DiagnosticSession.id == session_id
    ).first()
    
    assert diagnostic_session is not None
    assert diagnostic_session.vin == vin
    assert diagnostic_session.torch_predictions is None  # Should be None when not available
    assert diagnostic_session.confidence_score is None
    assert diagnostic_session.training_ready is False


def test_persist_diagnostic_session_db_failure():
    """
    Test graceful degradation when database operations fail.
    
    Verifies:
    - No exception raised on persistence failure
    - Returns None session_id
    - Diagnostic pipeline continues
    """
    # Arrange - Pass None as db session to simulate unavailable database
    vin = "1G1ZT53826F109149"
    symptoms = "Transmission slipping"
    obdcodes = "P0700"
    vehicle_info = {"make": "Chevrolet", "model": "Malibu", "year": "2006"}
    ranked_result = "1. Transmission Control Module"
    request_id = "test-789"
    
    # Act - Should not raise exception
    session_id = persist_diagnostic_session(
        db=None,  # No database available
        vin=vin,
        symptoms=symptoms,
        obdcodes=obdcodes,
        vehicle_info=vehicle_info,
        ranked_result=ranked_result,
        request_id=request_id,
        ranking_metadata=None
    )
    
    # Assert - Returns None on failure, doesn't crash
    assert session_id is None
