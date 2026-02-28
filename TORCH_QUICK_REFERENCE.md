"""
Quick Reference: Torch v2 ML Operations

Essential commands and endpoints for running ML pipeline in production.
"""

# ============================================================================
# QUICK START (5 minutes)
# ============================================================================

# Step 1: Verify model is not already installed
python -c "from app.ml.predictor import is_model_available; print('Model ready!' if is_model_available() else 'Need training')"

# Step 2: Collect labels via mechanic feedback (automatic via API)
# Mechanics use: POST /feedback/confirm/{session_id}

# Step 3: Check if ready to train
curl http://localhost:8000/feedback/stats
# Look for: "training_data_readiness": 52.4

# Step 4: Export training data
python -c "from app.ml.data_prep import export_training_data; export_training_data(); print('Exported to data/training/labeled_data.csv')"

# Step 5: Train model
python -m app.ml.trainer
# Produces: data/ml_models/v1.pkl + registry.json

# Step 6: Enable Torch in production
export USE_TORCH_PREDICTIONS=True
docker-compose restart shopmindai

# ============================================================================
# API ENDPOINTS
# ============================================================================

# FEEDBACK (New)
# Submit mechanic confirmation
POST /feedback/confirm/{session_id}
{
  "confirmed_cause": "Catalytic Converter Efficiency Below Threshold",
  "repair_parts": "OEM-CAT-8823",
  "rating": 5,
  "notes": "Replaced converter"
}
Response: {"status": "confirmed", "training_ready": true}

# Check training data stats
GET /feedback/stats
Response: {
  "total_sessions": 10000,
  "confirmed_sessions": 5242,
  "confirmation_rate": 52.4,
  "training_ready_sessions": 5242,
  "training_data_readiness": 52.4
}

# DIAGNOSTICS (Enhanced)
# Now accepts vin + obd_codes for Torch
POST /api/diagnose
{
  "vin": "1HGBH41JXMN109186",
  "obd_codes": ["P0420"],
  "symptoms": "Check engine light, rough idle"
}
Response includes: {
  "diagnostics": [...]
  "model_info": {
    "torch_used": true,
    "torch_predictions": {"Catalytic Converter": 0.67, ...},
    "model_version": "v1.0"
  }
}

# ============================================================================
# ML PIPELINE COMMANDS
# ============================================================================

# Check training data stats
python -c "
from app.ml.data_prep import get_data_stats
stats = get_data_stats()
print(f\"Labeled sessions: {stats['labeled_sessions']}\")
print(f\"Labeling rate: {stats['labeling_rate']:.1%}\")
"

# Export training data
python -c "
from app.ml.data_prep import export_training_data
path = export_training_data()
print(f'Data exported to {path}')
"

# Train model (offline)
python -m app.ml.trainer
# Watch for: accuracy, precision, recall metrics
# Produces: data/ml_models/v1.pkl

# Train model with custom path
python -c "
from app.ml.trainer import train_model
model, encoder, metrics = train_model('/path/to/data.csv')
print(f\"Accuracy: {metrics['accuracy']:.1%}\")
"

# Get model info
python -c "
from app.ml.registry import get_registry
registry = get_registry()
print(registry.list_models())  # ['v1.0', 'v1.1', ...]
print(registry.get_model_info('v1.0'))  # metadata
"

# Retrain pipeline (check → export → train → register)
python -m app.ml.retrain

# Or with custom min_samples threshold
python -c "
from app.ml.retrain import retrain_model
result = retrain_model(min_samples=500)
print(result)
"

# ============================================================================
# TEST TORCH INFERENCE
# ============================================================================

# 1. Verify model is loaded
python -c "from app.ml.predictor import is_model_available; print(is_model_available())"

# 2. Test feature encoding
python -c "
from app.ml.predictor import encode_features
import numpy as np
features = encode_features(
    vin='1HGBH41JXMN109186',
    obd_codes=['P0420'],
    symptoms='Check engine light, rough idle'
)
print(f'Feature shape: {features.shape}')  # Should be (1, 634)
print(f'Feature values: min={features.min():.2f}, max={features.max():.2f}')
"

# 3. Test prediction
python -c "
from app.ml.predictor import predict
result = predict(
    vin='1HGBH41JXMN109186',
    obd_codes=['P0420'],
    symptoms='Check engine light, rough idle'
)
for cause, confidence in result.items():
    print(f'{cause}: {confidence:.1%}')
"

# ============================================================================
# MONITORING & TROUBLESHOOTING
# ============================================================================

# Check Torch inference latency (in logs)
grep "torch_inference_ms" /var/log/shopmindai.log | tail -10

# Check prediction hit rate
grep "torch_used.*true" /var/log/shopmindai.log | wc -l

# Find prediction mismatches (Torch said X, mechanic confirmed Y)
python -c "
from sqlalchemy import select
from app.database import get_db_session
from app.models import DiagnosticSession
import json

with get_db_session() as session:
    sessions = session.query(DiagnosticSession).filter(
        DiagnosticSession.torch_predictions != None,
        DiagnosticSession.confirmed_cause != None
    ).all()
    
    mismatches = 0
    for s in sessions:
        torch_preds = json.loads(s.torch_predictions)
        top_pred = list(torch_preds.keys())[0]
        if top_pred not in s.confirmed_cause:
            mismatches += 1
    
    print(f'Mismatch rate: {mismatches}/{len(sessions)} ({mismatches/len(sessions):.1%})')
"

# Check model registry
cat data/ml_models/registry.json | python -m json.tool

# View model performance trends
python -c "
import json
with open('data/ml_models/registry.json') as f:
    registry = json.load(f)
    for model, info in registry['models'].items():
        print(f\"{model}: accuracy={info['metrics']['accuracy']:.1%}, samples={info['metrics']['samples_used']}\")
"

# ============================================================================
# DATABASE QUERIES (Diagnostics)
# ============================================================================

-- Total labeled sessions
SELECT COUNT(*) FROM diagnostic_sessions WHERE confirmed_cause IS NOT NULL;

-- Confirmation rate
SELECT COUNT(*) FILTER (WHERE confirmed_cause IS NOT NULL) as confirmed,
       COUNT(*) as total,
       COUNT(*) FILTER (WHERE confirmed_cause IS NOT NULL)::float / COUNT(*) as rate
FROM diagnostic_sessions;

-- Top predicted causes (vs. actual)
SELECT torch_predictions ->> 'top_cause' as predicted,
       confirmed_cause as actual,
       COUNT(*) as count
FROM diagnostic_sessions
WHERE torch_predictions IS NOT NULL AND confirmed_cause IS NOT NULL
GROUP BY 1, 2
ORDER BY 3 DESC;

-- Training readiness
SELECT COUNT(*) FILTER (WHERE training_ready = true) as ready,
       COUNT(*) as total
FROM diagnostic_sessions;

-- Feedback timeline
SELECT DATE(confirmed_at) as date,
       COUNT(*) as confirmations
FROM diagnostic_sessions
WHERE confirmed_at IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

# ============================================================================
# CONFIGURATION (Environment Variables)
# ============================================================================

export USE_TORCH_PREDICTIONS=True      # Enable Torch inference
export TORCH_CONFIDENCE_THRESHOLD=0.10 # Min confidence to include
export TORCH_MAX_CAUSES=5              # Top-K predictions
export ML_MODEL_VERSION=v1.0           # Active model version
export RETRAIN_MIN_SAMPLES=500         # Min labeled samples for retraining

# ============================================================================
# DEPLOYMENT CHECKLIST (Pre-Launch)
# ============================================================================

[ ] Database schema migrated (6 new columns added)
[ ] Feedback API deployed (POST /feedback/confirm/{id})
[ ] ≥100 labeled samples collected
[ ] Training data exported: data/training/labeled_data.csv
[ ] Model trained: data/ml_models/v1.pkl created
[ ] Model accuracy ≥60% verified
[ ] Integration test: Torch → Ranker → LLM works
[ ] Monitored for 24h on canary (1% traffic)
[ ] Rollout to 100% traffic
[ ] Retraining cron job scheduled (daily 2 AM UTC)
[ ] Monitoring dashboards set up
[ ] Rollback procedure tested

# ============================================================================
# EMERGENCY PROCEDURES
# ============================================================================

DISABLE TORCH (Emergency):
  export USE_TORCH_PREDICTIONS=False
  docker-compose restart shopmindai
  → Falls back to semantic + LLM only

ROLLBACK MODEL (If accuracy degraded):
  export ML_MODEL_VERSION=v1.0  # Use previous version
  docker-compose restart shopmindai

CLEAR MODEL (Force retrain):
  rm data/ml_models/v1.pkl data/ml_models/v1_encoder.pkl
  # Next request will trigger retraining

# ============================================================================
# METRICS CHECKLIST (Weekly)
# ============================================================================

Weekly Report Template:

1. TRAINING DATA GROWTH
   - Labeled sessions this week: ?
   - Total labeled sessions: ?
   - Labeling rate: ?%
   - On track for 5k samples by Week 8?

2. MODEL ACCURACY (If trained)
   - Current model version: ?
   - Accuracy on test set: ?%
   - Is it ≥60%?
   - Trend: Improving / Stable / Degrading?

3. PRODUCTION TORCH USAGE
   - % requests with Torch: ?%
   - Torch inference latency: ?ms
   - Errors: 0 / ?

4. MECHANIC SATISFACTION
   - Average rating: ?/5.0
   - Trend: ↑ / → / ↓
   - Diagnosis time: ? min (target: <2 min)

5. PREDICTION ACCURACY
   - Precision@1 (top-1 correct): ?%
   - Recall@5 (actual in top-5): ?%
   - Target: P@1 ≥60%, R@5 ≥90%

# ============================================================================
# RESOURCES
# ============================================================================

Full docs: V2_TORCH_IMPLEMENTATION.md
Model README: app/ml/README.md
Source: app/ml/*.py
Tests: tests/unit/test_ml_*.py (TODO: create)
Logs: See docker-compose logs shopmindai | grep torch
API: curl http://localhost:8000/docs (FastAPI schema)

Contacts:
- ML Pipeline Issues: Spark-ML team
- Database Issues: Database team
- API Issues: Backend team
- Mechanic feedback: Support team
"""
