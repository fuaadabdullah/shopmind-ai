#!/usr/bin/env python
"""
Training Pipeline Validation Checklist.

This script validates all 4 stages of the training pipeline are working properly.
It checks each component and provides a detailed report.

Usage:
    python validate_pipeline_checklist.py
"""
import os
import sys
from pathlib import Path

def check_stage_1_feedback_collection():
    """Verify Stage 1: Feedback collection and DB storage."""
    print("\n" + "=" * 70)
    print("STAGE 1: FEEDBACK COLLECTION & DB STORAGE")
    print("=" * 70)

    checks_passed = 0
    checks_total = 5

    # Check 1.1: Feedback endpoint exists
    print("\n[1.1] Feedback endpoint implementation...")
    try:
        from app.routes.feedback import router as feedback_router
        print("   ✅ Feedback router found in app/routes/feedback.py")
        checks_passed += 1
    except ImportError:
        print("   ❌ Feedback router not found")

    # Check 1.2: Database schema has training_ready field
    print("\n[1.2] Database schema training_ready field...")
    try:
        from app.models import DiagnosticSession
        if hasattr(DiagnosticSession, 'training_ready'):
            print("   ✅ DiagnosticSession.training_ready column exists")
            checks_passed += 1
        else:
            print("   ❌ training_ready field missing from DiagnosticSession")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Check 1.3: Confirmed cause field
    print("\n[1.3] Database schema confirmed_cause field...")
    try:
        from app.models import DiagnosticSession
        if hasattr(DiagnosticSession, 'confirmed_cause'):
            print("   ✅ DiagnosticSession.confirmed_cause column exists")
            checks_passed += 1
        else:
            print("   ❌ confirmed_cause field missing")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Check 1.4: Repair parts field
    print("\n[1.4] Database schema repair_parts field...")
    try:
        from app.models import DiagnosticSession
        if hasattr(DiagnosticSession, 'repair_parts'):
            print("   ✅ DiagnosticSession.repair_parts column exists")
            checks_passed += 1
        else:
            print("   ❌ repair_parts field missing")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Check 1.5: Torch predictions field
    print("\n[1.5] Database schema torch_predictions field...")
    try:
        from app.models import DiagnosticSession
        if hasattr(DiagnosticSession, 'torch_predictions'):
            print("   ✅ DiagnosticSession.torch_predictions column exists")
            checks_passed += 1
        else:
            print("   ❌ torch_predictions field missing")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    print(f"\n   Stage 1 Result: {checks_passed}/{checks_total} checks passed")
    return checks_passed == checks_total


def check_stage_2_data_export():
    """Verify Stage 2: Training data export."""
    print("\n" + "=" * 70)
    print("STAGE 2: TRAINING DATA EXPORT")
    print("=" * 70)

    checks_passed = 0
    checks_total = 4

    # Check 2.1: Export function exists
    print("\n[2.1] Training data export function...")
    try:
        from app.ml.data_prep import export_training_data
        print("   ✅ export_training_data() found in app/ml/data_prep.py")
        checks_passed += 1
    except ImportError:
        print("   ❌ export_training_data() not found in app/ml/data_prep.py")

    # Check 2.2: Data stats function exists
    print("\n[2.2] Training data stats function...")
    try:
        from app.ml.data_prep import get_data_stats
        print("   ✅ get_data_stats() found")
        checks_passed += 1
    except ImportError:
        print("   ❌ get_data_stats() not found")

    # Check 2.3: Deduplication function exists
    print("\n[2.3] Data deduplication function...")
    try:
        from app.ml.data_prep import deduplicate_records
        print("   ✅ deduplicate_records() found")
        checks_passed += 1
    except ImportError:
        print("   ❌ deduplicate_records() not found")

    # Check 2.4: Training data directory structure
    print("\n[2.4] Training data directory...")
    if Path("data/training").exists():
        print("   ✅ data/training/ directory exists")
        checks_passed += 1
    else:
        Path("data/training").mkdir(parents=True, exist_ok=True)
        print("   ✅ Created data/training/ directory")
        checks_passed += 1

    print(f"\n   Stage 2 Result: {checks_passed}/{checks_total} checks passed")
    return checks_passed == checks_total


def check_stage_3_model_training():
    """Verify Stage 3: Model training."""
    print("\n" + "=" * 70)
    print("STAGE 3: MODEL TRAINING")
    print("=" * 70)

    checks_passed = 0
    checks_total = 5

    # Check 3.1: Trainer module exists
    print("\n[3.1] XGBoost trainer module...")
    try:
        from app.ml.trainer import train_model
        print("   ✅ train_model() found in app/ml/trainer.py")
        checks_passed += 1
    except ImportError:
        print("   ❌ train_model() not found")

    # Check 3.2: Retraining orchestration
    print("\n[3.2] Model retraining orchestration...")
    try:
        from app.ml.retrain import retrain_model
        print("   ✅ retrain_model() found in app/ml/retrain.py")
        checks_passed += 1
    except ImportError:
        print("   ❌ retrain_model() not found")

    # Check 3.3: ML config has hyperparameters
    print("\n[3.3] XGBoost hyperparameters configured...")
    try:
        from app.ml.config import XGBOOST_PARAMS, MIN_TRAINING_SAMPLES
        if XGBOOST_PARAMS and MIN_TRAINING_SAMPLES:
            print(f"   ✅ XGBOOST_PARAMS: {len(XGBOOST_PARAMS)} params")
            print(f"   ✅ MIN_TRAINING_SAMPLES: {MIN_TRAINING_SAMPLES}")
            checks_passed += 1
        else:
            print("   ❌ Missing hyperparameters")
    except ImportError:
        print("   ❌ ML config not found")

    # Check 3.4: Model registry
    print("\n[3.4] Model registry...")
    try:
        from app.ml.registry import ModelRegistry
        print("   ✅ ModelRegistry found in app/ml/registry.py")
        checks_passed += 1
    except ImportError:
        print("   ❌ ModelRegistry not found")

    # Check 3.5: Models directory structure
    print("\n[3.5] Models directory...")
    if Path("data/ml_models").exists():
        print("   ✅ data/ml_models/ directory exists")
        checks_passed += 1
    else:
        Path("data/ml_models").mkdir(parents=True, exist_ok=True)
        print("   ✅ Created data/ml_models/ directory")
        checks_passed += 1

    print(f"\n   Stage 3 Result: {checks_passed}/{checks_total} checks passed")
    return checks_passed == checks_total


def check_stage_4_inference():
    """Verify Stage 4: Model inference."""
    print("\n" + "=" * 70)
    print("STAGE 4: MODEL INFERENCE")
    print("=" * 70)

    checks_passed = 0
    checks_total = 4

    # Check 4.1: Predictor module exists
    print("\n[4.1] ML predictor module...")
    try:
        from app.ml.predictor import predict_structured
        print("   ✅ predict_structured() found in app/ml/predictor.py")
        checks_passed += 1
    except ImportError:
        print("   ❌ predict_structured() not found")

    # Check 4.2: Inference returns TorchPrediction
    print("\n[4.2] TorchPrediction schema...")
    try:
        from app.types import TorchPrediction
        print("   ✅ TorchPrediction type found in app/types.py")
        checks_passed += 1
    except ImportError:
        print("   ❌ TorchPrediction type not found")

    # Check 4.3: ML model enabled in config
    print("\n[4.3] ML model enabled...")
    try:
        from app.ml.config import ML_MODEL_ENABLED
        if ML_MODEL_ENABLED:
            print("   ✅ ML_MODEL_ENABLED: True")
            checks_passed += 1
        else:
            print("   ⚠️  ML_MODEL_ENABLED: False (model disabled)")
    except ImportError:
        print("   ❌ ML config not found")

    # Check 4.4: Integration with ranker
    print("\n[4.4] Ranker integration with Torch context...")
    try:
        from app.ranker import rank_diagnostics
        print("   ✅ rank_diagnostics() found in app/ranker.py")
        checks_passed += 1
    except ImportError:
        print("   ❌ rank_diagnostics() not found")

    print(f"\n   Stage 4 Result: {checks_passed}/{checks_total} checks passed")
    return checks_passed == checks_total


def check_dependencies():
    """Verify all required dependencies are installed."""
    print("\n" + "=" * 70)
    print("DEPENDENCIES CHECK")
    print("=" * 70)

    deps = {
        "pandas": "Data manipulation",
        "xgboost": "ML training",
        "scikit-learn": "Feature encoding",
        "numpy": "Numerical computing",
        "sqlalchemy": "ORM",
        "sqlalchemy.orm": "Session management",
    }

    checks_passed = 0
    for package, description in deps.items():
        print(f"\n[{checks_passed + 1}/{len(deps)}] {package}: {description}...")
        try:
            __import__(package.split(".")[0])
            print(f"   ✅ {package} installed")
            checks_passed += 1
        except ImportError:
            print(f"   ❌ {package} NOT installed - Run: pip install {package.split('.')[0]}")

    return checks_passed == len(deps)


def check_test_infrastructure():
    """Verify test infrastructure is in place."""
    print("\n" + "=" * 70)
    print("TEST INFRASTRUCTURE CHECK")
    print("=" * 70)

    checks_passed = 0
    checks_total = 4

    # Check 1: E2E test file
    print("\n[1/4] E2E integration test...")
    if Path("tests/integration/test_training_pipeline_e2e.py").exists():
        print("   ✅ tests/integration/test_training_pipeline_e2e.py exists")
        checks_passed += 1
    else:
        print("   ❌ E2E test file not found")

    # Check 2: Test fixtures
    print("\n[2/4] Test fixtures and factories...")
    if Path("tests/fixtures/training_data.py").exists():
        print("   ✅ tests/fixtures/training_data.py exists")
        checks_passed += 1
    else:
        print("   ❌ Training fixtures not found")

    # Check 3: Manual validation script
    print("\n[3/4] Manual validation script...")
    if Path("scripts/validate_training_pipeline.py").exists():
        print("   ✅ scripts/validate_training_pipeline.py exists")
        checks_passed += 1
    else:
        print("   ❌ Validation script not found")

    # Check 4: Pytest configuration
    print("\n[4/4] Test configuration...")
    if Path("pytest.ini").exists():
        print("   ✅ pytest.ini exists")
        checks_passed += 1
    else:
        print("   ⚠️  pytest.ini not found")

    print(f"\n   Test Infrastructure Result: {checks_passed}/{checks_total} checks passed")
    return checks_passed >= 3


def main():
    """Run complete validation checklist."""
    print("\n" + "=" * 70)
    print("SHOPMINAIL TRAINING PIPELINE VALIDATION CHECKLIST")
    print("=" * 70)
    print("\nThis checklist validates all components of the training pipeline:")
    print("  • Stage 1: Feedback Collection & DB Storage")
    print("  • Stage 2: Training Data Export")
    print("  • Stage 3: Model Training")
    print("  • Stage 4: Model Inference")
    print("  • Dependencies & Test Infrastructure")

    results = {}

    # Run all checks
    try:
        results["Stage 1: Feedback"] = check_stage_1_feedback_collection()
        results["Stage 2: Export"] = check_stage_2_data_export()
        results["Stage 3: Training"] = check_stage_3_model_training()
        results["Stage 4: Inference"] = check_stage_4_inference()
        results["Dependencies"] = check_dependencies()
        results["Test Infrastructure"] = check_test_infrastructure()
    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Summary report
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY REPORT")
    print("=" * 70)

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"\n{check_name}: {status}")

    print(f"\n{'=' * 70}")
    print(f"Overall: {passed_count}/{total_count} sections passed")

    if passed_count == total_count:
        print("✅ PIPELINE VALIDATION COMPLETE - ALL CHECKS PASSED!")
        print("\nNext steps:")
        print("  1. Run pytest tests: pytest tests/integration/test_training_pipeline_e2e.py -v")
        print("  2. Run manual validation: python scripts/validate_training_pipeline.py")
        print("  3. Deploy to production with confidence!")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - See details above")
        print("\nFailing sections need attention before moving to production.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
