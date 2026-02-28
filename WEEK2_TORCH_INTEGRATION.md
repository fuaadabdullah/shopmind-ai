# Week 2 Implementation: Torch V2 Probability Engine Integration

**Status**: 🔄 In Progress (Core Integration Complete, Deployment Pending)

## Overview

Week 2 adds optional Torch V2 probability engine to ShopMindAI diagnostic pipeline. This is a **completely optional enhancement** that doesn't break Phase 1 (Pure RAG).

### Architecture

```
Request (VIN, OBD codes, symptoms)
    ↓
Phase 1: RAG (Semantic search + LLM ranking) ✅ ACTIVE
    ├─ FAISS: Retrieve relevant manual passages
    ├─ LLM: Explain and rank causes
    └─ Output: Ranked diagnostics + sources
    ↓
Phase 2: Optional Torch V2 (Probability engine)
    ├─ Input: VIN + OBD codes + symptoms
    ├─ Options: Real XGBoost model (if trained) OR Mock demo
    ├─ Output: Confidence scores, contradictions, cost ranking
    └─ Integration: Torch context passed to LLM for enhanced ranking
    ↓
Response: Ranked diagnostics ± Torch insights
```

### Philosophy

> "Torch answers ONE question: What is most likely broken and how sure am I? Everything else is LLM's job."

- **Docs** teach WHAT EXISTS (knowledge library)
- **LLM** teaches HOW TO APPLY KNOWLEDGE (reasoning)
- **Torch** teaches WHAT USUALLY HAPPENS (probability from repair history)

## Implementation Status

### ✅ Completed

#### Week 1: Torch V2 Probability Engine Foundation
- [x] **Schemas** (`app/ml/schemas.py`): 11 Pydantic models for structured output
  - `TorchPrediction`: Root envelope with all intelligence layers
  - `DiagnosisProposal`: Individual diagnosis with probability
  - `ContradictionDetection`: Flags contradictory code combinations
  - `CostAnalysis`: Multi-strategy cost ranking
  - Full type safety via Pydantic v2

- [x] **Calibration** (`app/ml/calibration.py`): Platt scaling for confidence calibration
  - `ConfidenceCalibrator` class
  - Fit/calibrate methods for XGBoost probabilities
  - Ensures 0-1 range and well-calibrated confidence scores

- [x] **Contradiction Detector** (`app/ml/contradiction_detector.py`): Semantic contradiction detection
  - `ContradictionDetector` class
  - Detects impossible OBD code combinations
  - Flags unusual patterns (e.g., two "too lean" codes together)

- [x] **Cost Weighting** (`app/ml/cost_weighting.py`): Multi-strategy cost-weighted ranking
  - `CostWeightedRanker` class
  - 4 ranking strategies: probability, cost-efficiency, ROI, frequency
  - Builds cost ranking with labor estimates

- [x] **Predictor Refactor** (`app/ml/predictor.py`): Unified Torch inference interface
  - `predict_structured()`: 798D feature encoding (VIN + OBD + symptoms + temporal)
  - `is_model_available()`: Check if trained model exists
  - Falls back to mock if no model
  - Integrates calibration, contradiction detection, cost analysis

- [x] **Ranker Hook** (`app/ranker.py`): LLM ranking with optional Torch context
  - `rank_diagnostics()` now accepts `torch_context` parameter
  - `_format_torch_context()` helper for LLM prompt integration
  - Backward compatible: works with or without Torch

#### Week 2: Integration (Current)

- [x] **Mock Predictor** (`app/ml/mock_predictor.py`): Demo-mode prediction generation
  - `MockTorchPredictor` class with realistic fake predictions
  - OBD → diagnosis mapping (e.g., P0171 → MAF, O2, fuel_filter)
  - Symptom-based probability boosting
  - Contradiction pattern detection
  - Cost/labor estimates
  - Deterministic seeding for reproducibility

- [x] **Service Integration** (`app/services/diagnostic_service.py`):
  - `get_torch_context()`: Fallback logic (real model → mock demo → None)
  - Updated `score_diagnostics()`: Accepts VIN, OBD codes; calls `get_torch_context()`
  - Updated `build_diagnostic_response()`: Accepts ranking_metadata with torch tracking
  - Graceful degradation: Torch failure never breaks Phase 1

- [x] **Route Integration** (`app/routes/diagnose.py`):
  - `/api/diagnose` endpoint updated to pass VIN + OBD codes
  - Captures `ranking_metadata` from `score_diagnostics()`
  - Passes metadata to response builder

- [x] **Test Suite** (`tests/unit/test_week2_integration.py`):
  - Mock predictor tests: reproducibility, OBD mapping, symptom boosting, contradiction detection
  - Torch context retrieval tests: real model → mock → graceful fallback
  - Integration tests: metadata tracking, fallback behavior

### 🔄 In Progress

- [ ] Deploy to GCP (environment setup, model storage)
- [ ] Real XGBoost model training pipeline (requires repair history data)
- [ ] End-to-end testing on GCP
- [ ] Performance tuning and monitoring

### ⏳ Not Started

- [ ] Optional: Torch webhook for async/queued requests (high volume)
- [ ] Optional: Dashboard for Torch performance metrics
- [ ] Optional: A/B testing Torch rankings vs LLM-only

## Code Changes Summary

### New Files
```
app/ml/
  ├── calibration.py         (NEW - Week 1)
  ├── contradiction_detector.py (NEW - Week 1)
  ├── cost_weighting.py       (NEW - Week 1)
  ├── mock_predictor.py       (NEW - Week 2)
  ├── predictor.py            (NEW - Week 1, refactored Week 2)
  └── schemas.py              (NEW - Week 1)

tests/unit/
  └── test_week2_integration.py (NEW - Week 2)
```

### Modified Files
```
app/ranker.py
  - Updated rank_diagnostics() signature: +torch_context parameter
  - Added _format_torch_context() helper

app/services/diagnostic_service.py
  - Added imports: predict_mock, is_model_available, predict_structured, TorchPrediction
  - Added get_torch_context() function (150 lines)
  - Updated score_diagnostics() signature: +vin, +obd_codes
  - Updated build_diagnostic_response() signature: +ranking_metadata

app/routes/diagnose.py
  - Updated /api/diagnose endpoint to pass vin + obd_codes
  - Captures ranking_metadata; passes to response builder
```

## API Response Format

### Without Torch (Phase 1 Only)
```json
{
  "result": "Based on symptoms and OBD codes...",
  "request_id": "req-123",
  "vehicle_info": {
    "make": "Honda",
    "model": "Civic",
    "year": 2015
  },
  "session_id": null
}
```

### With Torch (Phase 1 + Phase 2)
```json
{
  "result": "Based on symptoms, OBD codes, and repair probability insights...",
  "request_id": "req-123",
  "vehicle_info": {
    "make": "Honda",
    "model": "Civic",
    "year": 2015
  },
  "session_id": null,
  "_torch_metadata": {
    "torch_enabled": true,
    "torch_request_id": "torch-123",
    "top_torch_diagnosis": "MAF_sensor",
    "torch_contradictions_detected": false
  }
}
```

**Note**: Torch metadata is currently in `ranking_metadata` internal dict. Can be exposed in response schema if needed.

## Deployment

### Local Development (Demo Mode)

1. **Install dependencies** (if using Torch)
   ```bash
   pip install -r requirements.txt
   # additional ML deps already included:
   # - numpy, scipy
   # - scikit-learn
   # - xgboost
   ```

2. **Set environment variables**
   ```bash
   export TORCH_DEMO_MODE=true  # Forces mock predictor
   export ML_MODEL_PATH="/path/to/model.pkl"  # Optional: path to trained model
   ```

3. **Run app**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

4. **Test endpoint**
   ```bash
   curl -X POST http://localhost:8000/api/diagnose \
     -H "Content-Type: application/json" \
     -d '{
       "vin": "1HGBH41JXMN109186",
       "obdcodes": "P0171,P0174",
       "symptoms": "rough idle, check engine light"
     }'
   ```

   Response will include `"torch_enabled": true` and mock predictions.

### GCP Deployment

#### VM Requirements
- **CPU**: n1-standard-2 (2 vCPU) minimum; n1-standard-4 recommended for production
- **Memory**: 4 GB minimum; 8 GB recommended
- **Storage**: 20 GB (includes OS + container image + model cache)
- **OS**: Ubuntu 22.04 LTS (via Google Cloud Compute optimized image)

#### Model Storage
- **Option A**: GCS bucket (recommended for production)
  ```bash
  gsutil mb gs://shopmindai-models
  gsutil cp model.pkl gs://shopmindai-models/
  ```

- **Option B**: Mounted volume on VM (simpler for now)
  ```bash
  # In Dockerfile:
  ENV ML_MODEL_PATH=/mnt/models/model.pkl
  # In docker-compose: mount /data/models → /mnt/models
  ```

#### Dockerfile Update
```dockerfile
FROM python:3.11-slim

# Install ML dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ gfortran libopenblas-dev liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app/ app/
COPY main.py .

# Set ML environment
ENV ML_MODEL_PATH=/models/model.pkl
ENV TORCH_DEMO_MODE=false

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker-Compose Update
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - TORCH_DEMO_MODE=false
      - ML_MODEL_PATH=/models/model.pkl
      - FAISSindex_PATH=/data/faiss_index
    volumes:
      - ./data/models:/models:ro
      - ./data/faiss_index:/data/faiss_index:ro
    restart: always
```

#### Deployment Steps (via gcloud/gke)
1. Build and push Docker image to GCR
   ```bash
   docker build -t gcr.io/PROJECT_ID/shopmindai:v2 .
   docker push gcr.io/PROJECT_ID/shopmindai:v2
   ```

2. Deploy to Cloud Run or GKE
   ```bash
   # Cloud Run (serverless - recommended for initial testing)
   gcloud run deploy shopmindai \
     --image gcr.io/PROJECT_ID/shopmindai:v2 \
     --memory 4Gi \
     --cpu 2 \
     --region us-central1 \
     --timeout 60 \
     --set-env-vars TORCH_DEMO_MODE=false
   ```

3. Monitor with Cloud Logging
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND 
     resource.labels.service_name=shopmindai" --limit 50 --format json
   ```

## Testing

### Unit Tests
```bash
pytest tests/unit/test_week2_integration.py -v
```

### Integration Tests (Mock)
```bash
pytest tests/integration/ -v -k "torch" --tb=short
```

### Manual E2E Test (Local)
```bash
# Terminal 1: Start app
python -m uvicorn app.main:app --reload

# Terminal 2: Test endpoints
python tests/e2e/test_diagnose_endpoint.py
```

## Troubleshooting

### Torch context returning None in production
**Symptom**: `torch_enabled: false` in responses
**Causes**:
1. Model file not found → Check `ML_MODEL_PATH`
2. Mock predictor exception → Check logs for `predict_mock` errors
3. Environment flag → Verify `TORCH_DEMO_MODE` setting

**Solution**:
```bash
# Check logs
gcloud logging read "resource.type=cloud_run_revision" --grep="Torch" --limit 10

# Verify model path
docker exec <container_id> ls -la /models/

# Force demo mode
export TORCH_DEMO_MODE=true
# Redeploy
```

### Performance issues (slow diagnosis generation)
**Symptom**: Response time > 5 seconds
**Causes**:
1. Torch feature encoding overhead → Check 798D encoding performance
2. LLM ranking timeout → Increase timeout in provider config
3. FAISS search slow → Ensure index is in memory

**Solution**:
1. Profile with `python -m cProfile -o profile.prof app/main.py`
2. Analyze with `python -m pstats profile.prof`
3. Optimize hot paths (likely: FAISS search or LLM latency)

## Next Steps for Real Model Training

Once repair history data is available:

1. **Feature Engineering** → Extract VIN features (age, make, model, engine)
2. **Label Preparation** → Confirmed root causes from feedback loop
3. **Model Training** → XGBoost with cross-validation
4. **Calibration** → Platt scaling for well-calibrated confidences
5. **Validation** → Test on holdout repair cases
6. **Deployment** → Replace mock predictor with trained model

## Monitoring & Observability

### Metrics to Track (Torch-specific)
- `torch_enabled` ratio (% requests using real vs mock vs fallback)
- `torch_inference_latency_ms` (feature encoding + model prediction time)
- `torch_contradiction_flag_rate` (% predictions flagged for contradiction)
- `torch_prediction_confidence_mean` (average confidence scores)
- `llm_ranking_latency_with_torch_ms` vs without Torch

### Logging
```python
# In diagnostic_service.py get_torch_context():
logger.info(
    f"Torch prediction successful",
    extra={
        "request_id": request_id,
        "torch_id": torch_pred.request_id,
        "engine": "demo_mock" if is_demo else "real_model",
        "top_diagnosis": torch_pred.top_diagnoses[0].code if torch_pred.top_diagnoses else None,
        "confidence": torch_pred.top_diagnoses[0].probability if torch_pred.top_diagnoses else 0,
        "inference_time_ms": torch_pred.inference_time_ms
    }
)
```

## References

- [Torch V2 Architecture](../ARCHITECTURE.md#torch-v2-probability-engine)
- [ML Module Schemas](../app/ml/README.md)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [GCP Deployment Guide](../DEPLOYMENT.md#gcp-production-deployment)
