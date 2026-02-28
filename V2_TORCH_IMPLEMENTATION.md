"""
V2 Intelligence Layer Implementation Guide

Complete walkthrough of Torch integration: training pipeline, deployment,
and integration with existing semantic search + LLM ranker.
"""

# ============================================================================
# ARCHITECTURE OVERVIEW
# ============================================================================
"""
┌──────────────────────────────────────────────────────────────────┐
│                      CLIENT (Mechanic)                           │
│                  VIN + OBD + Symptoms Input                      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │    API: POST /api/diagnose         │
        │    NEW PARAMS: vin, obd_codes      │
        └────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌───────────────┐ ┌──────────────┐ ┌─────────────────┐
│ Retriever     │ │ Torch (v2)   │ │ VIN Decoder     │
│ (Semantic)    │ │ Classifier   │ │                 │
│ ↓ FAISS       │ │ ↓ XGBoost    │ │ ↓ Make/Model/Yr │
│ Manual chunks │ │ {cause:conf} │ │ Features        │
└───┬───────────┘ └──────┬───────┘ └────────┬────────┘
    │                    │                  │
    └────────────────────┴──────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │ Ranker (Enhanced)                  │
        │ • Injects Torch predictions        │
        │ • Semantic search in context       │
        │ • Calls LLM with enriched prompt   │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │ LLM Provider (GCP/SiliconeFlow)    │
        │ Reasoning layer                    │
        │ → Ranked causes with explanations  │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │ API Response + Metadata            │
        │ • ranked_diagnostics              │
        │ • torch_predictions (tracked)      │
        │ • confidence_scores                │
        └────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │ Store Session (DB)                 │
        │ Save: torch_predictions            │
        │ Save: prediction_causes            │
        └────────────────────────────────────┘
                     │
        (Mechanic confirms repair)
                     │
                     ▼
        ┌────────────────────────────────────┐
        │ Feedback Endpoint                  │
        │ POST /feedback/confirm/{id}        │
        │ → confirmed_cause                  │
        │ → repair_parts                     │
        │ → training_ready = True            │
        └────────────────────────────────────┘
                     │
        (Offline: Daily retraining job)
                     │
                     ▼
        ┌────────────────────────────────────┐
        │ Retraining Pipeline                │
        │ 1. Export labeled data             │
        │ 2. Encode features                 │
        │ 3. Train XGBoost                   │
        │ 4. Save v1.1 model + encoder      │
        │ 5. Register in model registry      │
        └────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │ Next Request (Torch Improved)      │
        │ Calls new model version            │
        └────────────────────────────────────┘
"""

# ============================================================================
# STEP 1: DATABASE MIGRATIONS
# ============================================================================
"""
The DiagnosticSession model now has new fields for training:

- torch_predictions (JSON): {cause: confidence, ...} from model
- predicted_causes (JSON): Initial predictions (LLM output)
- confirmed_cause (str): Actual diagnosed root cause (mechanic feedback)
- repair_parts (str): Parts replaced/repaired
- training_ready (bool): Mark for retraining
- confirmed_at (datetime): When mechanic confirmed

Migration:
  ALTER TABLE diagnostic_sessions ADD COLUMN torch_predictions JSON;
  ALTER TABLE diagnostic_sessions ADD COLUMN predicted_causes JSON;
  ALTER TABLE diagnostic_sessions ADD COLUMN confirmed_cause VARCHAR(255);
  ALTER TABLE diagnostic_sessions ADD COLUMN repair_parts TEXT;
  ALTER TABLE diagnostic_sessions ADD COLUMN training_ready BOOLEAN DEFAULT FALSE;
  ALTER TABLE diagnostic_sessions ADD COLUMN confirmed_at DATETIME;
  CREATE INDEX idx_training_ready ON diagnostic_sessions (training_ready);
"""

# ============================================================================
# STEP 2: ENABLED FEEDBACK API
# ============================================================================
"""
NEW ENDPOINT: POST /feedback/confirm/{session_id}

Request:
{
  "confirmed_cause": "Catalytic Converter Efficiency Below Threshold",
  "repair_parts": "OEM-CAT-8823,GASKET-001",
  "rating": 5,
  "notes": "Replaced converter, cleared P0420, verified with scan tool"
}

Response:
{
  "session_id": 42,
  "status": "confirmed",
  "message": "Diagnosis confirmed: Catalytic Converter...",
  "training_ready": true
}

Side effect:
  - Sets training_ready = True
  - Sets confirmed_at = now()
  - Record becomes available for retraining export

STATS ENDPOINT: GET /feedback/stats
{
  "total_sessions": 10000,
  "confirmed_sessions": 5242,
  "confirmation_rate": 52.4,
  "training_ready_sessions": 5242,
  "training_data_readiness": 52.4
}
"""

# ============================================================================
# STEP 3: ML DATA PIPELINE (OFFLINE)
# ============================================================================
"""
FILE: app/ml/data_prep.py

export_training_data(output_path="data/training/labeled_data.csv")
  → Queries: WHERE training_ready=True AND confirmed_cause IS NOT NULL
  → Exports: session_id, vin, make, model, year, obd_codes, symptoms, 
             confirmed_cause (label), repair_parts, rating, created_at
  → OUTPUT: CSV file ready for training

get_data_stats()
  → Returns: {
      total_sessions: 10000,
      labeled_sessions: 5242,
      labeling_rate: 52.4,
      top_causes: {...}
    }

deduplicate_records(df)
  → Drops duplicate (VIN, OBD, symptoms_hash) pairs
  → Keeps most recent confirmed diagnosis
  → Reduces data redundancy
"""

# ============================================================================
# STEP 4: TORCH MODEL TRAINING
# ============================================================================
"""
FILE: app/ml/trainer.py

train_model(csv_path="data/training/labeled_data.csv")
  
  Process:
  1. Load CSV (50k+ records ideal)
  2. Encode features:
     - VIN: Extract make/model/year → 50D one-hot vector
     - OBD: Split codes, map to buckets → 200D multi-hot vector
     - Symptoms: embed_text() → 384D vector
     - TOTAL: 634D feature vector
  3. Encode labels: confirmed_cause → class indices (0...N)
  4. Split: 80% train, 20% test, stratified
  5. Train XGBoost:
     - num_class = number of unique causes (~100-500)
     - objective = "multi:softprob" (softmax probabilities)
     - depth=6, learning_rate=0.1, n_estimators=100
  6. Evaluate: accuracy, precision, recall
  7. Save:
     - Model: data/ml_models/v1.pkl (pickle)
     - Encoder: data/ml_models/v1_encoder.pkl (sklearn.preprocessing.LabelEncoder)
     - Registry: data/ml_models/registry.json (metadata)

Return: (model, encoder, {accuracy, precision, recall, n_classes, ...})

Expected Accuracy Progression:
  - 100 samples: ~50% (random baseline ~40%)
  - 500 samples: ~60%
  - 5k samples: ~75%
  - 50k samples: ~85%+
  
Calling:
  from app.ml.trainer import train_model
  model, encoder, metrics = train_model()
  print(f"Accuracy: {metrics['accuracy']:.2%}")
"""

# ============================================================================
# STEP 5: INFERENCE & RANKER INTEGRATION
# ============================================================================
"""
FILE: app/ml/predictor.py

is_model_available() → bool
  Checks: Does data/ml_models/v1.pkl exist?

encode_features(vin, obd_codes, symptoms) → np.ndarray (1, 634)
  1. VIN features: ord(char)/256 → pad to 50D
  2. OBD features: hash(code) % 200 multi-hot → 200D
  3. Symptoms: embed_text([symptoms])[0] → 384D
  4. Concatenate: [VIN + OBD + symptoms]
  5. Return: shape (1, 634) for model.predict_proba()

predict(vin, obd_codes, symptoms) → dict[str, float] | None
  1. encode_features()
  2. model.predict_proba(X) → [p_1, p_2, ..., p_N]
  3. encoder.inverse_transform() → cause names
  4. Filter: confidence >= THRESHOLD (10%)
  5. Sort: descending confidence
  6. Top-K: return MAX_CAUSES_PER_PREDICTION (5)
  7. Return: {"Catalytic Converter": 0.67, "O2 Sensor": 0.21, ...}
  
Latency: <50ms (10ms encode, 30ms predict, 5ms post-process)

Integrated into ranker (app/ranker.py):

rank_diagnostics(
    symptoms, retrieved_docs,
    vin="1HG...", obd_codes="P0420,P0171",
    use_torch=True
) → (ranking_text, metadata)

  1. If use_torch=True and model available:
       → Call predict(vin, obd_codes, symptoms)
       → Format: "ML Predictions: Converter 67%, O2 Sensor 21%"
       → Inject into LLM prompt
  2. Build enhanced prompt with:
       - Torch predictions (context)
       - Symptoms + OBD + VIN
       - Retrieved manual passages
  3. Call LLM: generate(prompt)
  4. Return: (ranking, {torch_predictions, torch_used, ...})
"""

# ============================================================================
# STEP 6: RETRAINING PIPELINE (DAILY)
# ============================================================================
"""
FILE: app/ml/retrain.py

retrain_model(min_samples=100)
  
  1. Check data readiness:
     - get_data_stats() → labeled_sessions
     - If < min_samples, return early
  
  2. Export data:
     - export_training_data("data/training/labeled_data.csv")
  
  3. Train:
     - train_model(save_model=True)
     - Returns: metrics dict
  
  4. Register:
     - get_registry().register_model(version, accuracy, ...)
     - Incremented version: v1.0 → v1.1 → v1.2
  
  5. Return status:
     {
       "success": true,
       "version": "v1.0",
       "metrics": {accuracy: 0.847, ...},
       "trained_at": "2026-02-25T...",
       "message": "Model v1.0 trained successfully"
     }

Cron setup (Linux):
  # Daily at 2 AM UTC
  0 2 * * * python -m app.ml.retrain >> /var/log/shopmindai_retrain.log 2>&1
"""

# ============================================================================
# STEP 7: ROLLOUT STRATEGY
# ============================================================================
"""
Phase 1: Feedback Collection (Week 1-2)
  - Deploy /feedback/confirm endpoint
  - Mechanics start submitting confirmed diagnoses
  - Monitor: GET /feedback/stats
  - Goal: Collect ≥100 labeled samples

Phase 2: Initial Training (Week 3)
  - Have ≥500 labeled samples
  - Run: python -m app.ml.trainer
  - Save model v1.0
  - Test: Torch predictions ≥60% accuracy

Phase 3: A/B Test (Week 4)
  - Feature flag: USE_TORCH_PREDICTIONS=True for 50% requests
  - Monitor: Are mechanics more satisfied when Torch is included?
  - Metrics: rating, time_to_diagnosis, parts_ordered_match

Phase 4: Production Rollout (Week 5+)
  - Gradually increase: 50% → 75% → 100% Torch enabled
  - Daily: Collect feedback, retrain overnight
  - Target: ≥5k samples by Week 8, ≥85% accuracy

Phase 5: Enhancement (Ongoing)
  - Collect more edge cases
  - Retrain weekly: v1.0 → v1.1 → v1.2
  - Monitor accuracy trends
  - Add more features if needed (repair history, labor time, etc.)
"""

# ============================================================================
# EXAMPLE: END-TO-END REQUEST
# ============================================================================
"""
CLIENT REQUEST:
POST /api/diagnose
{
  "vin": "1HGBH41JXMN109186",
  "obdcodes": "P0420",
  "symptoms": "Check engine light on, rough idle, poor fuel economy"
}

INTERNAL FLOW:

1. retriever.retrieve(symptoms) 
   → Query FAISS → [manual_chunk_1, manual_chunk_2, ...]

2. ranker.rank_diagnostics(
     symptoms,
     retrieved_docs,
     vin="1HGBH41JXMN109186",
     obd_codes="P0420"
   )
   
   2a. ranker._get_torch_predictions(...)
       → predictor.encode_features(vin, obd, symptoms)
       → Load model, run inference
       → model.predict_proba() → softmax probabilities
       → Filter by confidence threshold
       → Return: {
            "Catalytic Converter": 0.67,
            "O2 Sensor (Downstream)": 0.21,
            ...
          }
   
   2b. Build LLM prompt:
       "You are an expert automotive diagnostic assistant.
        
        Customer Symptoms: Check engine light, rough idle, poor fuel economy
        Vehicle: Honda Accord 2021
        OBD Codes: P0420
        
        ML Diagnostic Predictions (confidence):
          - Catalytic Converter: 67%
          - O2 Sensor (Downstream): 21%
          
        **Note**: Consider the ML predictions above but verify against manual data.
        
        Supporting Manual Data:
        [manual_chunk_1, manual_chunk_2, ...]
        
        Task: Rank top 5 most likely diagnostic causes..."
   
   2c. LLM generates:
       "1. Catalytic Converter Efficiency Below Threshold (P0420 code)
           - Matches ML prediction (67% confidence)
           - Customer symptoms: rough idle, check engine
           - Tests: 1) Measure O2 sensor voltage, 2) Check exhaust backpressure
           - Labor: ~1.5 hours core time
        
        2. Oxygen Sensor (Downstream) Failure
           - Secondary prediction from ML
           - Also explains P0420
           - Tests: 1) Voltage checks, 2) Response time test
           - Labor: ~0.5 hours
        
        ..."

3. Store response + metadata:
   session.top_cause = "Catalytic Converter Efficiency Below Threshold"
   session.confidence_score = 0.87
   session.torch_predictions = {
     "Catalytic Converter": 0.67,
     "O2 Sensor": 0.21
   }
   session.predicted_causes = [LLM outputs]

CLIENT RESPONSE:
{
  "request_id": "550e8400-...",
  "vin": "1HGBH41JXMN109186",
  "vehicle_info": {"make": "Honda", "model": "Accord", "year": "2021"},
  "diagnostics": [
    {
      "rank": 1,
      "cause": "Catalytic Converter Efficiency",
      "confidence": 0.87,
      "explanation": "...",
      "supporting_docs": [...],
      "suggested_tests": [...]
    },
    ...
  ],
  "processing_time_ms": 1742,
  "model_info": {
    "torch_used": true,
    "torch_predictions": {"Catalytic Converter": 0.67, ...},
    "model_version": "v1.0"
  }
}

MECHANIC FEEDBACK (Later):
POST /feedback/confirm/42
{
  "confirmed_cause": "Catalytic Converter Efficiency Below Threshold",
  "repair_parts": "OEM-CAT-8823,CAT-GASKET-001",
  "rating": 5,
  "notes": "Replaced converter, verified fix with scanner"
}
→ Marks session.training_ready = True

NEXT DAY RETRAINING:
python -m app.ml.retrain
  → Exports 10,000 sessions (500 new ones)
  → Trains v1.1 model
  → Accuracy improves from 0.847 → 0.851
  → Registers v1.1 in model registry
"""

# ============================================================================
# MONITORING & METRICS
# ============================================================================
"""
Key Metrics to Track:

1. TRAINING DATA READINESS
   GET /feedback/stats
   → labeling_rate: % of sessions with confirmed_cause
   → training_data_readiness: % marked training_ready
   → Target: ≥50% labeling rate before training

2. MODEL ACCURACY
   GET /ml/models/latest
   → accuracy: Overall multiclass accuracy on test set
   → precision/recall per cause
   → samples_used: Number of training samples
   → Target: ≥85% for production

3. TORCH PREDICTION USAGE
   → torch_used: % of requests where Torch was available
   → Target: 100% once model is ready

4. MECHANIC SATISFACTION
   → rating: Post-diagnosis feedback (1-5 stars)
   → time_to_diagnosis: Minutes from input to recommendation
   → Target: Rating ≥4.0, time <2 minutes

5. PREDICTION ALIGNMENT
   → Compare Torch predictions vs. confirmed_cause
   → "Did Torch predict top 5 causes? Top 1?"
   → Precision@1, Recall@5
   → Target: P@1 ≥60%, R@5 ≥90%

DASHBOARDS:
  - Grafana: Model accuracy over time
  - Logs: torch_predictions injected in each request
  - Database: Query top causes, prediction misalignments
"""

# ============================================================================
# ROLLBACK PROCEDURE
# ============================================================================
"""
If new model performs worse:

1. Identify regression:
   - New model v1.1 accuracy drops from 0.847 to 0.821
   - Mechanic satisfaction ↓ (rating 4.2 → 3.8)

2. Deprecate model:
   registry.deprecate_model("v1.1")

3. Revert environment:
   ML_MODEL_VERSION=v1.0  # or disable
   USE_TORCH_PREDICTIONS=False

4. Restart service:
   docker-compose restart shopmindai

5. Investigate:
   - Check training data quality (corrupted labels?)
   - Check feature engineering (encoding bugs?)
   - Check hyperparameters (overfitting?)
   - Retrain with different params or more data

6. Try again next week with more data + fixes
"""

# ============================================================================
# DEPLOYMENT CHECKLIST
# ============================================================================
"""
Before Production Torch Launch:

Database:
  ☐ Migrate schema: Add torch_predictions, confirmed_cause, etc.
  ☐ Create indexes: idx_training_ready, idx_confirmed_at

API:
  ☐ Deploy feedback.py router
  ☐ Register feedback_router in main.py
  ☐ Update ranker.py with Torch integration
  ☐ Update models.py with new fields
  ☐ Update schemas.py if needed (rank_diagnostics return type)

ML Module:
  ☐ Create app/ml/ directory with __init__.py
  ☐ Add config.py with hyperparameters
  ☐ Add predictor.py with inference
  ☐ Add trainer.py with training logic
  ☐ Add data_prep.py with data export
  ☐ Add registry.py with model versioning
  ☐ Add retrain.py with retraining pipeline
  ☐ Add README.md with documentation

Data:
  ☐ Collect ≥100 labeled diagnostics via feedback
  ☐ Export CSV: data/training/labeled_data.csv
  ☐ Verify feature distribution (no extreme outliers)

Model:
  ☐ Train offline: python -m app.ml.trainer
  ☐ Validate accuracy ≥60% on test set
  ☐ Save to data/ml_models/v1.pkl
  ☐ Test predictor.py standalone

Integration:
  ☐ Test ranker with vin + obd_codes parameters
  ☐ Verify torch_predictions in response metadata
  ☐ Verify LLM prompt includes predictions
  ☐ End-to-end test: request → Torch → LLM → feedback

Monitoring:
  ☐ Log all Torch calls (hit rate, latency)
  ☐ Log prediction mismatches (Torch vs. actual)
  ☐ Set up alerts: model loading failure, inference errors
  ☐ Dashboard: Model accuracy, feedback rate

Rollout:
  ☐ Feature flag: USE_TORCH_PREDICTIONS (default False)
  ☐ Enable for 1% requests first (canary)
  ☐ Monitor for 24h: Any errors or slowdowns?
  ☐ Gradual: 1% → 10% → 50% → 100%
  ☐ Full rollout: Enable for all requests
"""

# ============================================================================
# SUMMARY
# ============================================================================
"""
ShopMindAI v2 Torch Layer Deployed ✅

What You Get:
✓ Torch XGBoost classifier (Layer 1: brain stem)
✓ Auto-injected into LLM prompts (Layer 3: mouth)
✓ Feedback API for training data collection
✓ Automatic retraining pipeline (daily)
✓ Model versioning & registry
✓ Graceful fallback if model unavailable

Key Insight:
  Torch doesn't replace LLM. It's hidden.
  LLM sees Torch predictions as context.
  LLM reasons over BOTH predictions + docs + codes.
  Result: More confident, more accurate diagnoses.

Next 30 Days:
  Week 1-2: Collect feedback (100+ samples)
  Week 3: Train initial model
  Week 4: A/B test with 50% traffic
  Week 5+: Full rollout, continuous improvement

Success Metric:
  Mechanic satisfaction (rating) increases by ≥10%
  Diagnosis time decreases by ≥20%
  Model accuracy improves 1-2% per week as data grows
"""
