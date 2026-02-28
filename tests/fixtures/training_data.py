"""
Training pipeline test data factories and fixtures.

Provides realistic diagnostic session and feedback data for validating
the complete training pipeline: feedback → DB → export → training → inference.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json


def create_diagnostic_session(
    session_id: Optional[int] = None,
    vin: str = "5TDJKRFH4LS123456",
    symptoms: str = "rough idle, hesitation on acceleration",
    obd_codes: str = "P0171,P0174",
    make: str = "Toyota",
    model: str = "Camry",
    year: str = "2020",
    top_cause: str = "Mass Air Flow (MAF) Sensor Failure",
    confidence_score: float = 0.85,
    torch_predictions: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Create a diagnostic session record for testing.
    
    Args:
        session_id: Optional session ID (auto-generated if None)
        vin: Vehicle VIN
        symptoms: Symptom description
        obd_codes: Comma-separated OBD codes
        make, model, year: Vehicle information
        top_cause: Initial diagnosis
        confidence_score: Initial confidence (0-1)
        torch_predictions: Dict of cause → probability from ML model
    
    Returns:
        Dict representing a DiagnosticSession record
    """
    if torch_predictions is None:
        torch_predictions = {
            "Mass Air Flow (MAF) Sensor Failure": 0.45,
            "Oxygen (O2) Sensor Degradation": 0.25,
            "Fuel Pressure Regulator Issue": 0.15,
            "Throttle Position Sensor Malfunction": 0.10,
            "Others": 0.05,
        }
    
    return {
        "id": session_id,
        "vin": vin,
        "symptoms": symptoms,
        "obd_codes": obd_codes,
        "make": make,
        "model": model,
        "year": year,
        "top_cause": top_cause,
        "confidence_score": confidence_score,
        "repair_outcome": None,
        "torch_predictions": torch_predictions,
        "predicted_causes": [top_cause, "Oxygen (O2) Sensor Degradation"],
        "confirmed_cause": None,
        "repair_parts": None,
        "training_ready": False,
        "created_at": datetime.now().isoformat(),
        "resolved_at": None,
        "confirmed_at": None,
        "user_feedback": None,
        "rating": None,
    }


def create_feedback(
    session_id: int,
    confirmed_cause: str = "Mass Air Flow (MAF) Sensor Failure",
    repair_parts: str = "EMS-00892",
    rating: int = 5,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create mechanic feedback for a diagnostic session.
    
    Args:
        session_id: ID of the session being confirmed
        confirmed_cause: Actual repair diagnosis
        repair_parts: Replaced parts (comma-separated part codes)
        rating: User satisfaction 1-5
        notes: Additional feedback
    
    Returns:
        Dict representing feedback/confirmation
    """
    return {
        "session_id": session_id,
        "confirmed_cause": confirmed_cause,
        "repair_parts": repair_parts,
        "rating": rating,
        "notes": notes or "Feedback from test",
        "confirmed_at": datetime.now().isoformat(),
    }


# Preset test scenarios covering various diagnostic conditions
SCENARIO_MAF_SENSOR = {
    "symptoms": "rough idle, hesitation on acceleration, black smoke from exhaust",
    "obd_codes": "P0171,P0174,P0101",
    "top_cause": "Mass Air Flow (MAF) Sensor Failure",
    "confirmed_cause": "Mass Air Flow (MAF) Sensor Failure",
    "repair_parts": "EMS-00892",
    "confidence_score": 0.85,
}

SCENARIO_O2_SENSOR = {
    "symptoms": "decreased fuel economy, rough idle, sluggish acceleration",
    "obd_codes": "P0131,P0133,P0171",
    "top_cause": "Oxygen (O2) Sensor Degradation - Bank 1 Sensor 1",
    "confirmed_cause": "Oxygen (O2) Sensor Degradation - Bank 1 Sensor 1",
    "repair_parts": "OXY-00456",
    "confidence_score": 0.78,
}

SCENARIO_CATALYST_CONVERTER = {
    "symptoms": "reduced power, sulfur smell, rattling noise underneath",
    "obd_codes": "P0420,P0430",
    "top_cause": "Catalytic Converter Efficiency Below Threshold",
    "confirmed_cause": "Catalytic Converter Efficiency Below Threshold",
    "repair_parts": "CAT-00789,GASKET-00123",
    "confidence_score": 0.72,
}

SCENARIO_EVAP_LEAK = {
    "symptoms": "fuel smell, hissing sound near fuel tank",
    "obd_codes": "P0455,P0456",
    "top_cause": "Evaporative Emission (EVAP) System Leak - Large",
    "confirmed_cause": "Evaporative Emission (EVAP) System Leak - Large",
    "repair_parts": "EVAP-HOSE-001",
    "confidence_score": 0.81,
}

SCENARIO_IGNITION_COIL = {
    "symptoms": "engine misfire, rough running, loss of power",
    "obd_codes": "P0300,P0302",
    "top_cause": "Ignition Coil Pack Failure - Cylinder 2",
    "confirmed_cause": "Ignition Coil Pack Failure - Cylinder 2",
    "repair_parts": "COIL-002",
    "confidence_score": 0.88,
}

SCENARIO_TPS = {
    "symptoms": "stalling, surging at steady throttle, poor acceleration",
    "obd_codes": "P0120,P0121",
    "top_cause": "Throttle Position Sensor (TPS) Malfunction",
    "confirmed_cause": "Throttle Position Sensor (TPS) Malfunction",
    "repair_parts": "TPS-001",
    "confidence_score": 0.76,
}

SCENARIO_MISFIRE_MULTI = {
    "symptoms": "severe rough idle, loss of power, excessive fuel consumption",
    "obd_codes": "P0300,P0420,P0171",
    "top_cause": "Random Multiple Cylinder Misfire",
    "confirmed_cause": "Valve Carbon Buildup + Fuel Pressure Issue",
    "repair_parts": "FUEL-REGULATOR-001,VALVE-CLEANING-KIT",
    "confidence_score": 0.65,  # Lower confidence for complex diagnosis
}

SCENARIO_CRANK_SENSOR = {
    "symptoms": "engine stalls while driving, no start when hot",
    "obd_codes": "P0335,P0336",
    "top_cause": "Crankshaft Position Sensor Intermittent Failure",
    "confirmed_cause": "Crankshaft Position Sensor Intermittent Failure",
    "repair_parts": "CRANK-SENSOR-001",
    "confidence_score": 0.82,
}


def create_training_dataset(
    count: int = 10,
    scenarios: Optional[list] = None,
) -> list[Dict[str, Any]]:
    """
    Create a realistic training dataset with varied diagnostic scenarios.
    
    Args:
        count: Number of sessions to generate
        scenarios: List of scenario configs to use (cycles through them)
    
    Returns:
        List of diagnostic sessions ready for training
    """
    if scenarios is None:
        scenarios = [
            SCENARIO_MAF_SENSOR,
            SCENARIO_O2_SENSOR,
            SCENARIO_CATALYST_CONVERTER,
            SCENARIO_EVAP_LEAK,
            SCENARIO_IGNITION_COIL,
            SCENARIO_TPS,
            SCENARIO_MISFIRE_MULTI,
            SCENARIO_CRANK_SENSOR,
        ]
    
    training_data = []
    vins = [
        "5TDJKRFH4LS123456",  # Toyota Camry
        "1HGBH41JXMN109186",  # Honda Accord
        "JH2RC5004LM200159",  # Honda Civic
        "WBADT43452G297186",  # BMW 3 Series
        "KMHLN4AJ5FU621834",  # Hyundai Elantra
        "2T1BF1K40CC519191",  # Toyota Corolla
        "JTHBP5C20D5009876",  # Lexus ES
        "1GNER3BE2DF111979",  # GMC Acadia
        "2HNYD18643H580420",  # Honda CR-V
        "JTHCE5C14E5035986",  # Lexus RX
    ]
    
    for i in range(count):
        scenario = scenarios[i % len(scenarios)]
        vin = vins[i % len(vins)]
        
        session = create_diagnostic_session(
            session_id=i + 1,
            vin=vin,
            symptoms=scenario["symptoms"],
            obd_codes=scenario["obd_codes"],
            top_cause=scenario["top_cause"],
            confidence_score=scenario["confidence_score"],
        )
        
        # Add feedback (marked as training_ready)
        session["training_ready"] = True
        session["confirmed_cause"] = scenario["confirmed_cause"]
        session["repair_parts"] = scenario["repair_parts"]
        session["confirmed_at"] = (datetime.now() - timedelta(days=count - i)).isoformat()
        session["rating"] = 4 + (i % 2)  # 4-5 stars
        session["user_feedback"] = "Good diagnosis" if i % 2 == 0 else "Saved us time and money"
        
        training_data.append(session)
    
    return training_data


def create_export_csv_data(training_data: list[Dict[str, Any]]) -> str:
    """
    Convert training dataset to CSV format for export.
    
    Args:
        training_data: List of diagnostic sessions with feedback
    
    Returns:
        CSV string with header and rows
    """
    rows = []
    header = "session_id,vin,make,model,year,obd_codes,symptoms,confirmed_cause,repair_parts,rating,created_at"
    rows.append(header)
    
    for session in training_data:
        if session.get("training_ready") and session.get("confirmed_cause"):
            row = (
                f"{session['id']},"
                f"{session['vin']},"
                f"{session['make']},"
                f"{session['model']},"
                f"{session['year']},"
                f"{session['obd_codes']},"
                f"\"{session['symptoms']}\"," 
                f"{session['confirmed_cause']},"
                f"{session['repair_parts']},"
                f"{session['rating']},"
                f"{session['created_at']}"
            )
            rows.append(row)
    
    return "\n".join(rows)


# Test fixture: sample labeled sessions for E2E testing
FIXTURE_LABELED_SESSIONS = [
    {
        **create_diagnostic_session(1),
        **{
            "training_ready": True,
            "confirmed_cause": "Mass Air Flow (MAF) Sensor Failure",
            "repair_parts": "EMS-00892",
            "rating": 5,
            "user_feedback": "Correct diagnosis, fixed the issue immediately",
            "confirmed_at": datetime.now().isoformat(),
        }
    },
    {
        **create_diagnostic_session(
            2,
            vin="1HGBH41JXMN109186",
            symptoms="decreased fuel economy, rough idle",
            obd_codes="P0131,P0133",
            make="Honda",
            model="Accord",
            top_cause="Oxygen (O2) Sensor Degradation",
            confidence_score=0.78,
        ),
        **{
            "training_ready": True,
            "confirmed_cause": "Oxygen (O2) Sensor Degradation - Bank 1 Sensor 1",
            "repair_parts": "OXY-00456",
            "rating": 4,
            "user_feedback": "Good diagnosis",
            "confirmed_at": (datetime.now() - timedelta(days=1)).isoformat(),
        }
    },
    {
        **create_diagnostic_session(
            3,
            vin="JH2RC5004LM200159",
            symptoms="engine misfire, loss of power",
            obd_codes="P0300,P0302",
            make="Honda",
            model="Civic",
            top_cause="Ignition Coil Pack Failure",
            confidence_score=0.88,
        ),
        **{
            "training_ready": True,
            "confirmed_cause": "Ignition Coil Pack Failure - Cylinder 2",
            "repair_parts": "COIL-002",
            "rating": 5,
            "user_feedback": "Perfect! Saved us hours of troubleshooting",
            "confirmed_at": (datetime.now() - timedelta(days=2)).isoformat(),
        }
    },
]
