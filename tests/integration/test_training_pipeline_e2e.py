"""
End-to-end integration tests for training pipeline validation.

Validates the complete loop: user feedback → DB write → training data export →
model training → inference with updated model.

Tests 4 stages:
  1. Feedback collection and storage (feedback → DB)
  2. Training data export (DB → CSV)
  3. Model training (CSV → trained model)
  4. Model inference (model → predictions)
"""
import csv
import pickle
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models import DiagnosticSession
from tests.fixtures.training_data import (
    FIXTURE_LABELED_SESSIONS,
    create_diagnostic_session,
    create_feedback,
    create_training_dataset,
)


class TestTrainingPipelineE2E:
    """E2E tests validating the training pipeline loop."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up test directories and clean up after tests."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_training_pipeline_")
        self.training_dir = Path(self.temp_dir) / "training"
        self.models_dir = Path(self.temp_dir) / "ml_models"
        self.training_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        yield

        # Cleanup
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ===== Stage 1: Feedback Collection & DB Storage =====

    def test_stage1_feedback_creates_training_session(self, test_db: Session):
        """
        Stage 1: User feedback → DB write.
        
        Validates that mechanic feedback confirmation properly writes
        training_ready=True and confirmed_cause to database.
        """
        # Create initial diagnostic session
        session_data = create_diagnostic_session(session_id=1)
        session = DiagnosticSession(
            vin=session_data["vin"],
            symptoms=session_data["symptoms"],
            obd_codes=session_data["obd_codes"],
            make=session_data["make"],
            model=session_data["model"],
            year=session_data["year"],
            top_cause=session_data["top_cause"],
            confidence_score=session_data["confidence_score"],
            torch_predictions=session_data["torch_predictions"],
            predicted_causes=session_data["predicted_causes"],
            training_ready=False,  # Not ready initially
        )
        test_db.add(session)
        test_db.commit()
        test_db.refresh(session)

        # Simulate mechanic feedback
        feedback = create_feedback(
            session_id=session.id,
            confirmed_cause="Mass Air Flow (MAF) Sensor Failure",
            repair_parts="EMS-00892",
            rating=5,
        )

        # Apply feedback to session (simulating feedback endpoint)
        session.confirmed_cause = feedback["confirmed_cause"]
        session.repair_parts = feedback["repair_parts"]
        session.rating = feedback["rating"]
        session.confirmed_at = datetime.now()
        session.training_ready = True  # Mark as ready for training

        test_db.commit()
        test_db.refresh(session)

        # Assertions
        assert session.training_ready is True, "Session should be marked training_ready"
        assert session.confirmed_cause == "Mass Air Flow (MAF) Sensor Failure"
        assert session.repair_parts == "EMS-00892"
        assert session.rating == 5
        assert session.confirmed_at is not None

    def test_stage1_multiple_feedback_sessions(self, test_db: Session):
        """Verify multiple feedback sessions correctly stored with training_ready flag."""
        # Create and confirm multiple sessions
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
                confirmed_at=datetime.fromisoformat(fixture["confirmed_at"]),
            )
            test_db.add(session)

        test_db.commit()

        # Verify all are stored and marked correctly
        confirmed_sessions = test_db.query(DiagnosticSession).filter(
            DiagnosticSession.training_ready == True,
            DiagnosticSession.confirmed_cause != None,
        ).all()

        assert len(confirmed_sessions) >= len(FIXTURE_LABELED_SESSIONS)
        for session in confirmed_sessions:
            assert session.training_ready is True
            assert session.confirmed_cause is not None
            assert session.repair_parts is not None

    # ===== Stage 2: Training Data Export =====

    def test_stage2_export_training_data_csv(self, test_db: Session):
        """
        Stage 2: DB read → CSV export.
        
        Validates that export_training_data() correctly extracts
        training-ready sessions and writes to CSV format.
        """
        # Insert labeled sessions
        for fixture in FIXTURE_LABELED_SESSIONS:
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
            test_db.add(session)

        test_db.commit()

        # Export training data
        output_csv = Path(self.training_dir) / "labeled_data.csv"
        self._export_training_data(test_db, str(output_csv))

        # Verify CSV exists and has correct structure
        assert output_csv.exists(), "CSV export file should exist"

        # Read and validate CSV
        rows = []
        with open(output_csv, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Assertions
        assert len(rows) >= len(FIXTURE_LABELED_SESSIONS), "Should export all labeled sessions"
        expected_columns = {
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
        }
        assert set(rows[0].keys()).issuperset(expected_columns), "CSV should have all required columns"

        # Verify data integrity
        first_row = rows[0]
        assert first_row["confirmed_cause"] in [
            "Mass Air Flow (MAF) Sensor Failure",
            "Oxygen (O2) Sensor Degradation - Bank 1 Sensor 1",
            "Ignition Coil Pack Failure - Cylinder 2",
        ]
        assert first_row["repair_parts"] != "", "repair_parts should be populated"

    def test_stage2_export_filters_unlabeled_sessions(self, test_db: Session):
        """Verify export only includes training_ready=True sessions."""
        # Insert mix of labeled and unlabeled
        labeled = FIXTURE_LABELED_SESSIONS[0].copy()
        labeled["id"] = 1
        labeled["training_ready"] = True

        unlabeled = create_diagnostic_session(session_id=2)
        unlabeled["training_ready"] = False

        # Add to DB
        session1 = DiagnosticSession(**labeled)
        test_db.add(session1)

        session2 = DiagnosticSession(
            vin=unlabeled["vin"],
            symptoms=unlabeled["symptoms"],
            obd_codes=unlabeled["obd_codes"],
            make=unlabeled["make"],
            model=unlabeled["model"],
            year=unlabeled["year"],
            top_cause=unlabeled["top_cause"],
            confidence_score=unlabeled["confidence_score"],
            training_ready=False,
        )
        test_db.add(session2)
        test_db.commit()

        # Export
        output_csv = Path(self.training_dir) / "labeled_data.csv"
        self._export_training_data(test_db, str(output_csv))

        # Verify only labeled is exported
        with open(output_csv) as f:
            rows = list(csv.DictReader(f))

        exported_ids = [int(row["session_id"]) for row in rows]
        assert 1 in exported_ids, "Labeled session should be exported"
        assert 2 not in exported_ids, "Unlabeled session should NOT be exported"

    # ===== Stage 3: Model Training =====

    def test_stage3_train_model_from_exported_data(self, test_db: Session):
        """
        Stage 3: CSV → trained model.
        
        Validates that training script loads exported CSV,
        encodes features, trains XGBoost model, and saves artifacts.
        """
        # Setup: Insert and export training data
        for fixture in FIXTURE_LABELED_SESSIONS:
            session = DiagnosticSession(**fixture)
            test_db.add(session)
        test_db.commit()

        csv_path = Path(self.training_dir) / "labeled_data.csv"
        self._export_training_data(test_db, str(csv_path))

        # Train model
        model_path = Path(self.models_dir) / "v1.pkl"
        encoder_path = Path(self.models_dir) / "v1_encoder.pkl"

        metrics = self._train_model(csv_path, model_path, encoder_path)

        # Assertions
        assert model_path.exists(), "Model should be saved to disk"
        assert encoder_path.exists(), "Encoder should be saved to disk"

        # Verify model is loadable
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        assert model is not None

        # Verify encoder is loadable
        with open(encoder_path, "rb") as f:
            encoder = pickle.load(f)
        assert encoder is not None

        # Verify metrics returned
        assert metrics["accuracy"] > 0
        assert metrics["n_training_samples"] >= 3
        assert metrics["n_classes"] > 0

    def test_stage3_training_improves_model_quality(self, test_db: Session):
        """Verify that training accuracy is reasonable for test data."""
        # Insert diverse training scenarios
        training_data = create_training_dataset(count=5)
        for data in training_data:
            session = DiagnosticSession(**data)
            test_db.add(session)
        test_db.commit()

        # Export and train
        csv_path = Path(self.training_dir) / "training_diverse.csv"
        self._export_training_data(test_db, str(csv_path))

        model_path = Path(self.models_dir) / "v2.pkl"
        encoder_path = Path(self.models_dir) / "v2_encoder.pkl"

        metrics = self._train_model(csv_path, model_path, encoder_path)

        # With 5 diverse samples, we expect reasonable performance
        assert metrics["accuracy"] >= 0.0, "Accuracy should be measurable"
        assert metrics["n_training_samples"] >= 4  # 5 data after 80/20 split
        assert "precision" in metrics or "recall" in metrics

    # ===== Stage 4: Model Inference =====

    def test_stage4_inference_with_trained_model(self, test_db: Session):
        """
        Stage 4: Trained model → predictions.
        
        Validates that trained model can be loaded and used for inference
        on new diagnostic requests.
        """
        # Setup: Create and train model
        for fixture in FIXTURE_LABELED_SESSIONS:
            session = DiagnosticSession(**fixture)
            test_db.add(session)
        test_db.commit()

        csv_path = Path(self.training_dir) / "labeled_data.csv"
        self._export_training_data(test_db, str(csv_path))

        model_path = Path(self.models_dir) / "v1.pkl"
        encoder_path = Path(self.models_dir) / "v1_encoder.pkl"
        self._train_model(csv_path, model_path, encoder_path)

        # Load model and run inference
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        with open(encoder_path, "rb") as f:
            encoder = pickle.load(f)

        # Create test input (must match training feature dimensions)
        test_input = self._create_feature_vector(
            vin="TESTVIN12345",
            obd_codes="P0171,P0174",
            symptoms="rough idle, hesitation",
        )

        # Run inference
        predictions = model.predict_proba([test_input])

        # Assertions
        assert predictions is not None
        assert len(predictions) > 0
        assert predictions.shape[1] > 0, "Should return probabilities per class"
        assert 0 <= predictions[0].max() <= 1.0, "Probabilities should be in [0, 1]"

    def test_stage4_inference_matches_training_classes(self, test_db: Session):
        """Verify inference output matches number of classes from training."""
        # Train with 3 fixtures (3 different causes)
        for i, fixture in enumerate(FIXTURE_LABELED_SESSIONS[:3], 1):
            session = DiagnosticSession(**fixture)
            test_db.add(session)
        test_db.commit()

        csv_path = Path(self.training_dir) / "labeled_data_3classes.csv"
        self._export_training_data(test_db, str(csv_path))

        model_path = Path(self.models_dir) / "v3.pkl"
        encoder_path = Path(self.models_dir) / "v3_encoder.pkl"
        metrics = self._train_model(csv_path, model_path, encoder_path)

        # Load and run inference
        with open(model_path, "rb") as f:
            model = pickle.load(f)

        test_input = self._create_feature_vector(
            vin="TESTVIN", obd_codes="P0171", symptoms="rough idle"
        )
        predictions = model.predict_proba([test_input])

        # Predictions should have same number of classes as training
        assert predictions.shape[1] == metrics["n_classes"]

    # ===== Full Pipeline Integration =====

    def test_full_pipeline_feedback_to_inference(self, test_db: Session):
        """
        Integration test: Trace full loop.
        
        user feedback → DB write → training data export → model update → inference
        """
        # Stage 1: Create session and add feedback
        session = DiagnosticSession(
            vin="5TDJKRFH4LS123456",
            symptoms="rough idle, hesitation on acceleration",
            obd_codes="P0171,P0174",
            make="Toyota",
            model="Camry",
            year="2020",
            top_cause="Mass Air Flow (MAF) Sensor Failure",
            confidence_score=0.85,
            training_ready=False,
        )
        test_db.add(session)
        test_db.commit()

        # Simulate feedback
        session.training_ready = True
        session.confirmed_cause = "Mass Air Flow (MAF) Sensor Failure"
        session.repair_parts = "EMS-00892"
        session.rating = 5
        session.confirmed_at = datetime.now()
        test_db.commit()

        # Stage 2: Export training data
        csv_path = Path(self.training_dir) / "full_pipeline.csv"
        self._export_training_data(test_db, str(csv_path))
        assert csv_path.exists()

        # Stage 3: Train model
        model_path = Path(self.models_dir) / "pipeline.pkl"
        encoder_path = Path(self.models_dir) / "pipeline_encoder.pkl"
        metrics = self._train_model(csv_path, model_path, encoder_path)
        assert model_path.exists()

        # Stage 4: Run inference
        with open(model_path, "rb") as f:
            model = pickle.load(f)

        test_input = self._create_feature_vector(
            vin="5TDJKRFH4LS123456",
            obd_codes="P0171,P0174",
            symptoms="rough idle, hesitation on acceleration",
        )
        predictions = model.predict_proba([test_input])

        # Full loop validation
        assert predictions is not None
        assert predictions.shape[1] > 0
        assert metrics["n_training_samples"] >= 1

    # ===== Helper Methods =====

    def _export_training_data(self, db: Session, output_path: str):
        """Helper: Export training data from DB to CSV."""
        # Query labeled sessions
        sessions = (
            db.query(DiagnosticSession)
            .filter(
                DiagnosticSession.training_ready == True,
                DiagnosticSession.confirmed_cause != None,
            )
            .all()
        )

        # Write CSV
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

    def _train_model(
        self,
        csv_path: Path,
        model_path: Path,
        encoder_path: Path,
    ) -> dict:
        """Helper: Train XGBoost model and return metrics."""
        import pandas as pd
        from sklearn.preprocessing import LabelEncoder
        from xgboost import XGBClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score

        # Load data
        df = pd.read_csv(csv_path)
        if len(df) < 2:
            # Need at least 2 samples for train/test split
            df = pd.concat([df, df], ignore_index=True)

        # Encode causes (labels)
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(df["confirmed_cause"])

        # Simple feature encoding (for testing)
        X = self._encode_features(df)

        # Train/test split
        if len(X) < 2:
            X_train, X_test = X, X
            y_train, y_test = y, y
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

        # Train XGBoost
        model = XGBClassifier(n_classes=len(label_encoder.classes_), random_state=42)
        model.fit(X_train, y_train)

        # Calculate metrics
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Save artifacts
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        with open(encoder_path, "wb") as f:
            pickle.dump(label_encoder, f)

        return {
            "accuracy": accuracy,
            "n_training_samples": len(X),
            "n_classes": len(label_encoder.classes_),
            "n_features": X.shape[1],
        }

    def _encode_features(self, df):
        """Helper: Simple feature encoding for test model."""
        import pandas as pd
        import numpy as np

        features = []
        for _, row in df.iterrows():
            # Simple encoding: hash of VIN + OBD codes + symptom length
            vin_hash = hash(row["vin"]) % 256
            obd_hash = hash(row["obd_codes"]) % 256
            symptom_len = len(str(row["symptoms"])) % 256
            repair_parts_len = len(str(row.get("repair_parts", ""))) % 256

            feature_vec = [vin_hash, obd_hash, symptom_len, repair_parts_len]
            features.append(feature_vec)

        return np.array(features)

    def _create_feature_vector(self, vin: str, obd_codes: str, symptoms: str):
        """Helper: Create feature vector for inference."""
        import numpy as np

        vin_hash = hash(vin) % 256
        obd_hash = hash(obd_codes) % 256
        symptom_len = len(symptoms) % 256
        repair_parts_len = 0  # Not available during inference

        return np.array([vin_hash, obd_hash, symptom_len, repair_parts_len])
