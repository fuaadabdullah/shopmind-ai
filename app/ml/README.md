"""
ShopMindAI v2 Intelligence Layer (Torch Integration Guide)

This module implements the Torch-based diagnostic classifier as Layer 1 of the 
hybrid 3-layer architecture:

  ┌─────────────────────────────────────────────────┐
  │ Layer 3: LLM Ranker                             │
  │ (Writes explanations in mechanic language)      │
  │ ← Receives Torch predictions as context         │
  │ ← Receives manual retrieval results             │
  └─────────────────────────────────────────────────┘
                     ▲
                     │
  ┌─────────────────────────────────────────────────┐
  │ Layer 2: Semantic Search (Vector DB)            │
  │ (Fetches supporting documents from FAISS)       │
  └─────────────────────────────────────────────────┘
                     ▲
                     │
  ┌─────────────────────────────────────────────────┐
  │ Layer 1: Torch Classifier (XGBoost)             │
  │ (Brain stem: outputs ranked probabilities)      │
  │ Features: VIN (50D) + OBD (200D) + Symptoms (384D) │
  │ Output: {cause→confidence, ...}                 │
  └─────────────────────────────────────────────────┘

## Quick Start

### 1. Collect Training Data (No Torch Yet)

The feedback mechanism in `app/routes/feedback.py` enables mechanics to confirm diagnoses:

```bash
# Mechanic confirms: "Yes, it was a bad O2 sensor"
POST /feedback/confirm/{session_id}
{
  "confirmed_cause": "O2 Sensor Malfunction",
  "repair_parts": "EMS-00892,DIAG-KIT",
  "rating": 5,
  "notes": "Replaced sensor, cleared code, problem gone"
}
```

This marks the session as `training_ready=True` for retraining.

### 2. Export Data & Train Offline

```bash
# Export labeled sessions from DB
python -c "from app.ml.data_prep import export_training_data; export_training_data()"
# → data/training/labeled_data.csv (50k+ records = powerful)

# Train XGBoost classifier
python -c "from app.ml.trainer import train_model; train_model()"
# → Save to data/ml_models/v1.pkl + encoder + registry

# Or via retraining pipeline:
python -m app.ml.retrain
```

### 3. Enable Torch in Production

```bash
# .env or environment:
ML_MODEL_ENABLED=True
USE_TORCH_PREDICTIONS=True
```

### 4. Torch Predictions Auto-Inject into LLM

When you call the ranker with `vin` + `obd_codes`:

```python
from app.ranker import rank_diagnostics
from app.retriever import retrieve

# Torch inference happens automatically
ranking, metadata = rank_diagnostics(
    symptoms="P0420, check engine light, rough idle",
    retrieved_docs=retrieve(...),
    vin="1HGBH41JXMN109186",
    obd_codes="P0420,P0171"
)

# metadata['torch_predictions'] = {'Catalytic Converter': 0.67, 'O2 Sensor': 0.21, ...}
# metadata['torch_used'] = True
```

The LLM receives the predictions in the prompt and uses them to bias output.

## Architecture Deep-Dive

### Data Flow

```
Client Request
  │ {vin, obd_codes, symptoms}
  ▼
┌─────────────────────┐
│ Torch Predictor     │
│ encode_features()   │
│  - VIN → 50D vector │
│  - OBD → 200D vec   │
│  - Symptoms → embed │
│ Total: 634D         │
│ predict()           │
│  → {cause: conf}    │
└─────────────────────┘
  │ Predictions
  ▼
┌─────────────────────┐
│ Ranker              │
│ _get_torch_predict()│
│ Inject into Prompt: │
│ "ML Predictions:    │
│  - Converter: 67%"  │
└─────────────────────┘
  │ Enhanced Prompt
  ▼
┌─────────────────────┐
│ LLM Provider        │
│ Reasons over:       │
│  - ML predictions   │
│  - Manual docs      │
│  - Symptoms/codes   │
│ Returns ranked list │
└─────────────────────┘
  │ Ranked explanation
  ▼
Client (Mechanic)
```

### Feature Engineering

1. **VIN Features** (50D):
   - Encode VIN characters as normalized bytes
   - Captures vehicle-specific diagnostic patterns
   - E.g., Honda vs. Toyota have different failure modes

2. **OBD Features** (200D):
   - Multi-hot encode OBD-II codes
   - Example: P0420 → bucket 42, P0171 → bucket 171
   - Captures combinations of diagnostic codes

3. **Symptom Features** (384D):
   - Embed symptoms using existing `embed_text()` (all-MiniLM-L6-v2)
   - Captures semantic meaning of customer description
   - "Won't start" = low battery, starter, fuel pump, etc.

**Total: 634-dimensional feature vector** → XGBoost classifier

### Model Training (Offline)

```python
# 1. Load labeled data from DB
# 2. Encode features (VIN + OBD + symptoms)
# 3. Encode labels (causes → class indices)
# 4. Train XGBoost:
#    - Num classes: ~100-500 (unique causes)
#    - Objective: multi:softprob (multiclass)
#    - Output: P(cause_1), P(cause_2), ..., P(cause_N)
# 5. Save model + encoder + registry
```

### Inference (Online, <50ms)

```python
# encode_features() - 10ms
# model.predict_proba() - 30ms
# post-process (filter, sort) - 5ms
# → {cause: confidence, ...}
```

## Important: Without Data, Torch is Useless

The model is **only as good as the training data**. For MVP v1:

- **50 labels**: Can work, low confidence
- **500 labels**: Useful signal, ~60% accuracy
- **5k labels**: Strong classifier, ~75% accuracy  
- **50k+ labels**: Production-ready, ~85%+ accuracy

**Call: Aim for 500 labels in first month**, then expand.

## Monitoring & Rollback

```bash
# Check model version
GET /ml/models/latest
# → {version: "v1.0", accuracy: 0.847, trained_at: "2026-02-25T..."}

# Check training readiness
GET /feedback/stats
# → {total_sessions: 10000, training_ready: 5242, training_data_readiness: 52.4%}

# If new model worse than old:
# 1. Deprecate new version in registry
# 2. Revert ML_MODEL_VERSION env var
# 3. Restart app
```

## Next Steps

1. **Start collecting feedback** via `POST /feedback/confirm/{session_id}`
2. **Monitor `/feedback/stats`** to track labeling progress
3. **When ≥500 labeled samples exist**, trigger offline training
4. **A/B test** new model: use_torch=True for 50% of requests
5. **Measure**: Does Torch bias + LLM improve mechanic satisfaction?
6. **Iterate**: Retrain weekly as feedback accumulates

## Configuration

See `app/ml/config.py` for tuning:

- `ML_MODEL_ENABLED`: Enable/disable Torch inference
- `MAX_CAUSES_PER_PREDICTION`: Top-K predictions to inject
- `CONFIDENCE_THRESHOLD`: Min confidence to include  
- `XGBOOST_PARAMS`: Hyperparameters (max_depth, learning_rate, etc.)

## Troubleshooting

**Q: Torch predictions not appearing in ranker**
- Check: Is `ML_MODEL_PATH` present? `data/ml_models/v1.pkl`
- Check: Are `vin` + `obd_codes` being passed to `rank_diagnostics()`?
- Check: Is `use_torch=True`?
- Logs: Look for "Torch model available" debug message

**Q: Model inference slow**
- Profile with: `python -m cProfile -s cumtime app/ml/predictor.py`
- Likely bottleneck: `embed_text()` semantic embedding
- Solution: Cache symptom embeddings if repeated queries

**Q: Training data imbalanced (many "Battery Issues", few "Transmission")**
- Use class_weight="balanced" in XGBoost
- Or oversample minority classes during data prep

**Q: Model accuracy low**
- Check feature distribution: Print `X[0]` to verify encoding
- Check label distribution: Plot histogram of confirmed causes
- Need more data? Retraining with ≥5k samples helps significantly
"""
