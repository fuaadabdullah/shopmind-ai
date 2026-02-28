# Training Pipeline Validation Guide

## Overview

The ShopMindAI training pipeline validates the complete loop: **user feedback → DB write → training data export → model update → inference**.

This guide covers all the validation tools, tests, and checkpoints for verifying the training pipeline is working correctly.

---

## The Complete Pipeline Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                 TRAINING PIPELINE FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐                                            │
│  │ STAGE 1         │                                            │
│  │ Mechanic        │                                            │
│  │ Feedback        │  confirmed_cause, repair_parts, rating    │
│  │ Confirmation    │  → training_ready = True                  │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │ STAGE 2         │                                            │
│  │ Data Export     │  Query: training_ready=True                │
│  │ to CSV          │  → labeled_data.csv                        │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │ STAGE 3         │                                            │
│  │ Model Training  │  Encode features, train XGBoost           │
│  │                 │  → model.pkl + encoder.pkl                │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │ STAGE 4         │                                            │
│  │ Inference       │  Load model, run predictions              │
│  │                 │  → Torch predictions in next request      │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │ Loop Back       │  Improved rankings, better diagnoses      │
│  │                 │  → New feedback collected...              │
│  └─────────────────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Files & Components

### Database Schema
- **File**: [app/models.py](../app/models.py)
- **Table**: `DiagnosticSession`
- **Training Fields**:
  - `training_ready` (Boolean): Flag for retraining readiness
  - `confirmed_cause` (String): Actual repair diagnosis from mechanic
  - `repair_parts` (Text): Parts replaced (comma-separated)
  - `torch_predictions` (JSON): ML model probabilities
  - `rating` (Integer): User satisfaction (1-5)
  - `confirmed_at` (DateTime): When feedback was recorded

### Feedback Collection
- **File**: [app/routes/feedback.py](../app/routes/feedback.py)
- **Endpoint**: `POST /feedback/confirm/{session_id}`
- **Request Body**:
  ```json
  {
    "confirmed_cause": "Mass Air Flow (MAF) Sensor Failure",
    "repair_parts": "EMS-00892",
    "rating": 5,
    "notes": "Diagnosis was accurate and helpful"
  }
  ```

### Training Data Export
- **File**: [app/ml/data_prep.py](../app/ml/data_prep.py)
- **Function**: `export_training_data(output_path="data/training/labeled_data.csv")`
- **Output**: CSV with columns: `session_id, vin, make, model, year, obd_codes, symptoms, confirmed_cause, repair_parts, rating, created_at`

### Model Training
- **File**: [app/ml/trainer.py](../app/ml/trainer.py)
- **Function**: `train_model(csv_path, save_model=True)`
- **Process**:
  1. Load CSV with labeled data
  2. Encode features (VIN, OBD codes, symptoms)
  3. Train XGBoost classifier
  4. Save model artifacts to `data/ml_models/`
  5. Register version in `registry.json`

### Model Inference
- **File**: [app/ml/predictor.py](../app/ml/predictor.py)
- **Function**: `predict_structured(vin, obd_codes, symptoms)`
- **Output**: `TorchPrediction` with ranked diagnoses and probabilities

### Configuration
- **File**: [app/ml/config.py](../app/ml/config.py)
- **Key Settings**:
  - `MIN_TRAINING_SAMPLES`: 100 (minimum samples before training)
  - `CONFIDENCE_THRESHOLD`: 0.10 (10%)
  - `XGBOOST_PARAMS`: Hyperparameters for model training

---

## Validation Tools

### 1. Automated E2E Integration Tests

**File**: [tests/integration/test_training_pipeline_e2e.py](../tests/integration/test_training_pipeline_e2e.py)

**What it tests**:
- ✅ Stage 1: Feedback creates `training_ready=True` records
- ✅ Stage 2: Export correctly filters labeled data to CSV
- ✅ Stage 3: Model trains successfully and saves artifacts
- ✅ Stage 4: Trained model runs inference and produces predictions
- ✅ Full loop: Feedback → Export → Train → Inference

**How to run**:
```bash
# Run all training pipeline tests
pytest tests/integration/test_training_pipeline_e2e.py -v

# Run specific stage test
pytest tests/integration/test_training_pipeline_e2e.py::TestTrainingPipelineE2E::test_stage1_feedback_creates_training_session -v

# Run with coverage
pytest tests/integration/test_training_pipeline_e2e.py --cov=app --cov-report=html
```

**Test Classes**:
1. `test_stage1_feedback_creates_training_session` - Feedback → DB
2. `test_stage1_multiple_feedback_sessions` - Multiple confirmations
3. `test_stage2_export_training_data_csv` - Export to CSV
4. `test_stage2_export_filters_unlabeled_sessions` - Filter logic
5. `test_stage3_train_model_from_exported_data` - Training
6. `test_stage3_training_improves_model_quality` - Quality metrics
7. `test_stage4_inference_with_trained_model` - Inference
8. `test_stage4_inference_matches_training_classes` - Class matching
9. `test_full_pipeline_feedback_to_inference` - Full loop

---

### 2. Test Fixtures & Data Factories

**File**: [tests/fixtures/training_data.py](../tests/fixtures/training_data.py)

**Provides**:
- `create_diagnostic_session()` - Factory for test sessions
- `create_feedback()` - Factory for mechanic feedback
- `create_training_dataset(count=10)` - Generate N test scenarios
- `FIXTURE_LABELED_SESSIONS` - Pre-defined test fixtures
- `SCENARIO_*` - Specific diagnostic scenarios (MAF sensor, O2 sensor, etc.)

**Example usage**:
```python
from tests.fixtures.training_data import create_diagnostic_session, create_feedback

# Create a test session
session = create_diagnostic_session(
    session_id=1,
    vin="5TDJKRFH4LS123456",
    symptoms="rough idle, hesitation on acceleration",
    confirmed_cause="Mass Air Flow (MAF) Sensor Failure"
)

# Create feedback for the session
feedback = create_feedback(
    session_id=1,
    confirmed_cause="Mass Air Flow (MAF) Sensor Failure",
    repair_parts="EMS-00892",
    rating=5
)
```

---

### 3. Manual Validation Script (Interactive)

**File**: [scripts/validate_training_pipeline.py](../scripts/validate_training_pipeline.py)

**What it does**:
- ✅ Check 4 critical blockers (schema, dependencies, config, DB connection)
- ✅ Create sample feedback data in database
- ✅ Export training data to CSV
- ✅ Train model on exported data
- ✅ Run inference with trained model

**How to run**:
```bash
# Run all stages in sequence
python scripts/validate_training_pipeline.py

# Run specific stage
python scripts/validate_training_pipeline.py --stage 1  # Check blockers
python scripts/validate_training_pipeline.py --stage 2  # Create feedback
python scripts/validate_training_pipeline.py --stage 3  # Export data
python scripts/validate_training_pipeline.py --stage 4  # Train model
python scripts/validate_training_pipeline.py --stage 5  # Run inference

# Verbose output
python scripts/validate_training_pipeline.py --verbose
```

**Output**:
```
=======================================================================
        SHOPMINAI TRAINING PIPELINE VALIDATION
=======================================================================

[1/4] Checking database schema...
   ✓ DiagnosticSession has all required training fields
[2/4] Checking dependencies...
   ✓ pandas: Data manipulation
   ✓ xgboost: ML training
   ✓ scikit-learn: Feature encoding
   ✓ numpy: Numerical computing
[3/4] Checking ML configuration...
   ✓ ML_MODEL_ENABLED: True
   ✓ MIN_TRAINING_SAMPLES: 100
   ✓ XGBOOST_PARAMS configured: 7 params
[4/4] Checking database connection...
   ✓ Database connected: postgresql://...
```

---

### 4. Pipeline Checklist Script

**File**: [scripts/pipeline_checklist.py](../scripts/pipeline_checklist.py)

**What it validates**:
- Stage 1: Feedback collection infrastructure
- Stage 2: Data export modules
- Stage 3: Model training pipeline
- Stage 4: Inference implementation
- Dependencies: All required packages
- Test infrastructure: E2E tests, fixtures, validation scripts

**How to run**:
```bash
python scripts/pipeline_checklist.py
```

**Output**:
```
=======================================================================
        VALIDATION SUMMARY REPORT
=======================================================================

Stage 1: Feedback: ✅ PASS
Stage 2: Export: ✅ PASS
Stage 3: Training: ✅ PASS
Stage 4: Inference: ✅ PASS
Dependencies: ✅ PASS
Test Infrastructure: ✅ PASS

=======================================================================
Overall: 6/6 sections passed
✅ PIPELINE VALIDATION COMPLETE - ALL CHECKS PASSED!
```

---

## Quick Start: Validation Workflow

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run Blockers Check
```bash
python scripts/validate_training_pipeline.py --stage 1
```

**Expected output**: All 4 blockers cleared
- ✅ Database schema
- ✅ Dependencies
- ✅ ML configuration
- ✅ Database connection

### Step 3: Run Automated Tests
```bash
pytest tests/integration/test_training_pipeline_e2e.py -v
```

**Expected**: All 9 tests pass green ✅

### Step 4: Run Full Manual Validation
```bash
python scripts/validate_training_pipeline.py
```

**Expected output**: All 5 stages complete successfully
- Stage 1: Check blockers ✅
- Stage 2: Create feedback data ✅
- Stage 3: Export training data ✅
- Stage 4: Train model ✅
- Stage 5: Run inference ✅

### Step 5: Run Complete Checklist
```bash
python scripts/pipeline_checklist.py
```

**Expected**: 6/6 validation sections pass ✅

---

## Production Readiness Checklist

Before deploying the training pipeline to production, verify:

- [ ] **Database Migration**: Alembic migration applied (`alembic upgrade head`)
- [ ] **Dependencies Installed**: pandas, xgboost, scikit-learn, numpy
- [ ] **Schema Verified**: All training_ready, confirmed_cause, repair_parts fields present
- [ ] **Configuration Set**: ML params in app/ml/config.py, MIN_TRAINING_SAMPLES defined
- [ ] **Tests Passing**: `pytest tests/integration/test_training_pipeline_e2e.py -v` all green
- [ ] **Feedback Endpoint**: Tested `/feedback/confirm/{session_id}` accepts mechanic input
- [ ] **Data Export**: `export_training_data()` generates valid CSV
- [ ] **Model Training**: `train_model()` produces model.pkl + encoder.pkl
- [ ] **Inference Working**: `predict_structured()` returns predictions
- [ ] **Full Loop Tested**: Manual validation script completes all 5 stages
- [ ] **Monitoring Ready**: Metrics logged, model versions tracked
- [ ] **Cron Job Configured**: Scheduled retraining set up (optional)

---

## Common Issues & Troubleshooting

### Issue: "Database migration not run"
**Solution**:
```bash
alembic revision --autogenerate -m "Add training fields"
alembic upgrade head
```

### Issue: "Module not found: xgboost"
**Solution**:
```bash
pip install xgboost scikit-learn pandas
```

### Issue: "CSV export is empty"
**Solution**:
- Ensure feedback has been submitted: `POST /feedback/confirm/{session_id}`
- Check `training_ready=True` in database: `SELECT COUNT(*) FROM diagnostic_sessions WHERE training_ready=True`
- Verify `confirmed_cause` is not NULL

### Issue: "Model training fails"
**Solution**:
- Need minimum 2 samples for train/test split
- Check CSV format: required columns are session_id, vin, make, model, year, obd_codes, symptoms, confirmed_cause, repair_parts
- Verify pandas/xgboost versions: `pip show pandas xgboost`

### Issue: "Inference returns no predictions"
**Solution**:
- Ensure model.pkl exists at `data/ml_models/v1.pkl`
- Check encoder.pkl exists at `data/ml_models/v1_encoder.pkl`
- Verify input features match training feature dimensions

---

## Next Steps for Enhancement

### Phase 1: Foundation (Current)
- ✅ 4-stage pipeline validation
- ✅ E2E integration tests
- ✅ Manual validation scripts
- ✅ Test data factories

### Phase 2: Automation
- [ ] Scheduled retraining cron job
- [ ] Automated model versioning
- [ ] Performance monitoring & alerting
- [ ] Model evaluation metrics tracking

### Phase 3: Advanced ML
- [ ] Hyperparameter tuning
- [ ] Cross-validation
- [ ] Feature importance analysis
- [ ] Model comparison & selection
- [ ] A/B testing infrastructure

---

## Files Summary

| File | Purpose |
|------|---------|
| `app/models.py` | DiagnosticSession schema with training fields |
| `app/routes/feedback.py` | Feedback confirmation endpoint |
| `app/ml/data_prep.py` | Training data export functionality |
| `app/ml/trainer.py` | XGBoost model training |
| `app/ml/predictor.py` | Model inference |
| `app/ml/config.py` | ML configuration & hyperparameters |
| `app/ml/registry.py` | Model version tracking |
| `tests/fixtures/training_data.py` | Test data factories |
| `tests/integration/test_training_pipeline_e2e.py` | 9 integration tests |
| `scripts/validate_training_pipeline.py` | Manual validation (5 stages) |
| `scripts/pipeline_checklist.py` | Complete validation checklist |
| `requirements.txt` | Dependencies: pandas, xgboost, scikit-learn |

---

## Performance Expectations

### Data Export
- Time: < 1 sec for 1000 rows
- Output: CSV file with all confirmed diagnoses

### Model Training
- Time: 2-5 seconds for 1000 samples (CPU)
- Output: model.pkl (xgboost model) + encoder.pkl (label encoder)
- Accuracy: 85-90% on test split for diagnostic data

### Inference
- Time: < 100ms per request
- Output: Top 5 diagnoses with probabilities
- Integration: Used in `/diagnose` endpoint for enhanced ranking

### Test Execution
- E2E tests: ~30 seconds
- Manual validation: ~1 minute (all stages)
- Checklist: < 5 seconds

---

For more details, see:
- [app/ml/README.md](../app/ml/README.md) - ML module documentation
- [API.md](../API.md) - API endpoint documentation
- [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md) - Current implementation status
