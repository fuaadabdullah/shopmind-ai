#!/usr/bin/env python
"""
Manual validation script for training pipeline.

Walks through the complete training pipeline step-by-step for manual testing,
debugging, and demonstration purposes.

Usage:
    python scripts/validate_training_pipeline.py [--stage STAGE_NUM] [--verbose]

Stages:
    1. Check blockers (migrations, dependencies, schema)
    2. Create sample feedback data
    3. Export training data to CSV
    4. Train model on exported data
    5. Run inference with trained model
    all: Run all stages (default)
"""
import argparse
import csv
import json
import pickle
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def check_blockers():
    """Check critical blockers for pipeline setup."""
    print("\n" + "=" * 70)
    print("STAGE 1: CHECK BLOCKERS")
    print("=" * 70)

    blockers = []

    # Check 1: Database schema
    print("\n[1/4] Checking database schema...")
    try:
        from app.models import DiagnosticSession
        from app.database import Base

        # Check if all required fields exist
        required_fields = {
            "training_ready",
            "confirmed_cause",
            "repair_parts",
            "confirmed_at",
            "torch_predictions",
        }
        model_columns = {col.name for col in DiagnosticSession.__table__.columns}

        missing_fields = required_fields - model_columns
        if missing_fields:
            blockers.append(
                f"❌ Missing columns in DiagnosticSession: {missing_fields}\n"
                f"   Run: alembic upgrade head"
            )
        else:
            print("   ✓ DiagnosticSession has all required training fields")
    except Exception as e:
        blockers.append(f"❌ Failed to load models: {e}")

    # Check 2: Required dependencies
    print("\n[2/4] Checking dependencies...")
    dependencies = [
        ("pandas", "Data manipulation"),
        ("xgboost", "ML training"),
        ("scikit-learn", "Feature encoding"),
        ("numpy", "Numerical computing"),
    ]

    for pkg_name, reason in dependencies:
        try:
            __import__(pkg_name)
            print(f"   ✓ {pkg_name}: {reason}")
        except ImportError:
            blockers.append(f"❌ {pkg_name} not installed")

    # Check 3: Configuration
    print("\n[3/4] Checking ML configuration...")
    try:
        from app.ml.config import (
            ML_MODEL_ENABLED,
            MIN_TRAINING_SAMPLES,
            XGBOOST_PARAMS,
        )

        print(f"   ✓ ML_MODEL_ENABLED: {ML_MODEL_ENABLED}")
        print(f"   ✓ MIN_TRAINING_SAMPLES: {MIN_TRAINING_SAMPLES}")
        print(f"   ✓ XGBOOST_PARAMS configured: {len(XGBOOST_PARAMS)} params")
    except Exception as e:
        blockers.append(f"❌ ML config error: {e}")

    # Check 4: Database connection
    print("\n[4/4] Checking database connection...")
    try:
        from app.database import DATABASE_URL

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            print(f"   ✓ Database connected: {DATABASE_URL}")
    except Exception as e:
        blockers.append(f"❌ Database connection failed: {e}")

    # Summary
    print("\n" + "-" * 70)
    if blockers:
        print("⚠️  BLOCKERS FOUND:")
        for blocker in blockers:
            print(f"\n{blocker}")
        return False
    else:
        print("✅ All blockers cleared - pipeline is ready")
        return True


def create_sample_feedback():
    """Create sample feedback data in database."""
    print("\n" + "=" * 70)
    print("STAGE 2: CREATE SAMPLE FEEDBACK DATA")
    print("=" * 70)

    try:
        from app.database import SessionLocal
        from app.models import DiagnosticSession
        from tests.fixtures.training_data import FIXTURE_LABELED_SESSIONS

        db = SessionLocal()

        print(f"\nInserting {len(FIXTURE_LABELED_SESSIONS)} labeled sessions...")

        for i, fixture in enumerate(FIXTURE_LABELED_SESSIONS, 1):
            session = DiagnosticSession(
                vin=fixture["vin"],
                symptoms=fixture["symptoms"],
                obd_codes=fixture["obd_codes"],
                make=fixture["make"],
                model=fixture["model"],
                year=fixture["year"],
                top_cause=fixture["top_cause"],
                confidence_score=fixture["confidence_score"],
                torch_predictions=fixture["torch_predictions"],
                predicted_causes=fixture["predicted_causes"],
                training_ready=fixture["training_ready"],
                confirmed_cause=fixture["confirmed_cause"],
                repair_parts=fixture["repair_parts"],
                rating=fixture["rating"],
                user_feedback=fixture["user_feedback"],
                confirmed_at=datetime.fromisoformat(fixture["confirmed_at"]),
            )
            db.add(session)

        db.commit()

        # Verify insertion
        confirmed_count = db.query(DiagnosticSession).filter(
            DiagnosticSession.training_ready == True,
            DiagnosticSession.confirmed_cause != None,
        ).count()

        print(f"   ✓ Inserted {len(FIXTURE_LABELED_SESSIONS)} sessions")
        print(f"   ✓ {confirmed_count} sessions marked training_ready=True")

        db.close()
        return True

    except Exception as e:
        print(f"   ❌ Error creating feedback: {e}")
        return False


def export_training_data(db_session=None, output_path=None):
    """Export training data from database to CSV."""
    print("\n" + "=" * 70)
    print("STAGE 3: EXPORT TRAINING DATA")
    print("=" * 70)

    try:
        if db_session is None:
            from app.database import SessionLocal

            db_session = SessionLocal()

        from app.models import DiagnosticSession

        # Query labeled sessions
        sessions = (
            db_session.query(DiagnosticSession)
            .filter(
                DiagnosticSession.training_ready == True,
                DiagnosticSession.confirmed_cause != None,
            )
            .all()
        )

        print(f"\nFound {len(sessions)} training-ready sessions")

        if not sessions:
            print("   ⚠️  No training data available. Run STAGE 2 first.")
            return None

        # Determine output path
        if output_path is None:
            output_path = Path("data/training/labeled_data.csv")
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Export to CSV
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "session_id",
                    "vin",
                    "make",
                    "model",
                    "year",
                    "obd_codes",
                    "symptoms",
                    "confirmed_cause",
                    "repair_parts",
                    "rating",
                    "created_at",
                ],
            )
            writer.writeheader()
            for s in sessions:
                writer.writerow(
                    {
                        "session_id": s.id,
                        "vin": s.vin,
                        "make": s.make,
                        "model": s.model,
                        "year": s.year,
                        "obd_codes": s.obd_codes,
                        "symptoms": s.symptoms,
                        "confirmed_cause": s.confirmed_cause,
                        "repair_parts": s.repair_parts,
                        "rating": s.rating,
                        "created_at": s.created_at.isoformat() if s.created_at else "",
                    }
                )

        print(f"   ✓ Exported {len(sessions)} sessions to {output_path}")
        print(f"   ✓ File size: {output_path.stat().st_size} bytes")

        # Show sample rows
        print("\n   Sample exported data:")
        with open(output_path) as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i < 2:  # Show first 2 rows
                    print(f"     - {row['vin']}: {row['confirmed_cause']} ({row['rating']}⭐)")

        return str(output_path)

    except Exception as e:
        print(f"   ❌ Error exporting data: {e}")
        import traceback

        traceback.print_exc()
        return None


def train_model(csv_path):
    """Train ML model on exported data."""
    print("\n" + "=" * 70)
    print("STAGE 4: TRAIN MODEL")
    print("=" * 70)

    try:
        import numpy as np
        import pandas as pd
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder
        from xgboost import XGBClassifier
        from sklearn.metrics import accuracy_score, precision_score, recall_score

        if not Path(csv_path).exists():
            print(f"   ❌ CSV file not found: {csv_path}")
            return None

        print(f"\nLoading training data from {csv_path}...")

        # Load data
        df = pd.read_csv(csv_path)
        print(f"   ✓ Loaded {len(df)} rows")

        if len(df) < 2:
            print("   ⚠️  Need at least 2 samples for training. Adding duplicates...")
            df = pd.concat([df, df], ignore_index=True)

        # Encode labels
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(df["confirmed_cause"])

        # Simple feature encoding (for demo)
        X = np.array(
            [
                [
                    hash(vin) % 256,
                    hash(obd) % 256,
                    len(symptoms) % 256,
                    len(str(parts)) % 256,
                ]
                for vin, obd, symptoms, parts in zip(
                    df["vin"],
                    df["obd_codes"],
                    df["symptoms"],
                    df.get("repair_parts", [""] * len(df)),
                )
            ]
        )

        print(f"   ✓ Feature shape: {X.shape}")
        print(f"   ✓ Classes: {len(label_encoder.classes_)} unique causes")
        print(f"   ✓ Features: {X.shape[1]} features per sample")

        # Train/test split
        if len(X) < 2:
            X_train, X_test = X, X
            y_train, y_test = y, y
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

        print(
            f"\n   ✓ Train size: {len(X_train)}, Test size: {len(X_test)}"
        )

        # Train XGBoost
        print("\n   Training XGBoost model...")
        model = XGBClassifier(
            n_classes=len(label_encoder.classes_),
            random_state=42,
            verbosity=0,
        )
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        print(f"   ✓ Training accuracy: {accuracy:.2%}")

        # Save model artifacts
        model_dir = Path("data/ml_models")
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "v1.pkl"
        encoder_path = model_dir / "v1_encoder.pkl"

        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        with open(encoder_path, "wb") as f:
            pickle.dump(label_encoder, f)

        print(f"\n   ✓ Model saved to {model_path}")
        print(f"   ✓ Encoder saved to {encoder_path}")

        # Log metrics
        metrics = {
            "accuracy": float(accuracy),
            "n_training_samples": len(X),
            "n_classes": len(label_encoder.classes_),
            "n_features": X.shape[1],
            "trained_at": datetime.now().isoformat(),
        }

        print(f"\n   Model Metrics:")
        print(f"     - Accuracy: {metrics['accuracy']:.2%}")
        print(f"     - Training samples: {metrics['n_training_samples']}")
        print(f"     - Classes: {metrics['n_classes']}")

        return {"model_path": str(model_path), "metrics": metrics}

    except Exception as e:
        print(f"   ❌ Error training model: {e}")
        import traceback

        traceback.print_exc()
        return None


def run_inference(model_path):
    """Run inference with trained model."""
    print("\n" + "=" * 70)
    print("STAGE 5: RUN INFERENCE")
    print("=" * 70)

    try:
        import numpy as np

        if not Path(model_path).exists():
            print(f"   ❌ Model not found: {model_path}")
            return False

        print(f"\nLoading model from {model_path}...")

        with open(model_path, "rb") as f:
            model = pickle.load(f)

        print("   ✓ Model loaded successfully")

        # Create test input
        test_cases = [
            {
                "vin": "5TDJKRFH4LS123456",
                "obd_codes": "P0171,P0174",
                "symptoms": "rough idle, hesitation on acceleration",
            },
            {
                "vin": "1HGBH41JXMN109186",
                "obd_codes": "P0131,P0133",
                "symptoms": "decreased fuel economy, rough idle",
            },
        ]

        print(f"\nRunning inference on {len(test_cases)} test cases...")

        for i, test_case in enumerate(test_cases, 1):
            # Create feature vector
            feature_vec = np.array(
                [
                    hash(test_case["vin"]) % 256,
                    hash(test_case["obd_codes"]) % 256,
                    len(test_case["symptoms"]) % 256,
                    0,  # No repair_parts during inference
                ]
            )

            # Run prediction
            probs = model.predict_proba([feature_vec])
            top_class = model.predict([feature_vec])[0]

            print(f"\n   Test Case {i}:")
            print(f"     VIN: {test_case['vin']}")
            print(f"     OBD: {test_case['obd_codes']}")
            print(f"     Symptoms: {test_case['symptoms']}")
            print(f"     Prediction confidence: {probs[0].max():.2%}")

        print("\n   ✓ Inference completed successfully")
        return True

    except Exception as e:
        print(f"   ❌ Error running inference: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate training pipeline"
    )
    parser.add_argument(
        "--stage",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=None,
        help="Run specific stage (default: all)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Verbose output"
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("SHOPMINIAL TRAINING PIPELINE VALIDATION")
    print("=" * 70)
    print("\nThis script validates the complete training loop:")
    print("  1. Feedback collection & DB write")
    print("  2. Training data export")
    print("  3. Model training")
    print("  4. Model inference")

    stages_to_run = [args.stage] if args.stage else [1, 2, 3, 4, 5]

    results = {}

    # Stage 1: Check blockers
    if 1 in stages_to_run:
        results[1] = check_blockers()
        if not results[1]:
            print("\n❌ STAGE 1 FAILED - Fix blockers before proceeding")
            return 1

    # Stage 2: Create feedback
    if 2 in stages_to_run and results.get(1, True):
        results[2] = create_sample_feedback()
        if not results[2]:
            print("\n❌ STAGE 2 FAILED - Cannot proceed")
            return 1

    # Stage 3: Export data
    csv_path = None
    if 3 in stages_to_run and results.get(2, True):
        csv_path = export_training_data()
        results[3] = csv_path is not None
        if not results[3]:
            print("\n❌ STAGE 3 FAILED - Cannot proceed")
            return 1

    # Stage 4: Train model
    model_info = None
    if 4 in stages_to_run and results.get(3, True) and csv_path:
        model_info = train_model(csv_path)
        results[4] = model_info is not None
        if not results[4]:
            print("\n❌ STAGE 4 FAILED - Cannot proceed")
            return 1

    # Stage 5: Run inference
    if 5 in stages_to_run and results.get(4, True) and model_info:
        results[5] = run_inference(model_info["model_path"])

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    stage_names = {
        1: "Check blockers",
        2: "Create feedback data",
        3: "Export training data",
        4: "Train model",
        5: "Run inference",
    }

    for stage_num, stage_name in stage_names.items():
        if stage_num in results:
            status = "✅ PASS" if results[stage_num] else "❌ FAIL"
            print(f"\n{stage_num}. {stage_name}: {status}")

    # Overall result
    all_passed = all(v for k, v in results.items() if k in stages_to_run)
    if all_passed:
        print("\n✅ All stages passed - Training pipeline is valid!")
        return 0
    else:
        print("\n❌ Some stages failed - See details above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
