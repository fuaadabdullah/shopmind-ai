# E2E Torch Integration Tests

This directory contains **end-to-end integration tests** for the ShopMindAI Torch V2 pipeline, validating the complete inference path from raw input through to ranked diagnostic outputs.

## 🎯 Test Philosophy

**"Mock nothing in the critical path"**

These tests use:
- ✅ **Real SentenceTransformer embeddings** (all-MiniLM-L6-v2, 384D)
- ✅ **Real FAISS vector search** (IndexFlatIP with cosine similarity)
- ✅ **Real VectorStore singleton** (thread-safe retrieval)
- ✅ **Real/Mock Torch predictor** (XGBoost model with fallback)
- ✅ **Contract-validated LLM mock** (template-based, cost-free)
- ✅ **In-memory SQLite database** (session persistence testing)

This approach validates that all components work correctly together, catching integration bugs that unit tests miss.

---

## 📁 Test Structure

```
tests/e2e/
├── README.md                          # This file
├── test_real_torch_integration.py     # Core E2E pipeline tests (12 tests)
└── test_torch_model_loading.py        # Model loading/fallback tests (7 tests)

tests/fixtures/
├── generate_test_data.py              # 20 automotive diagnostic scenarios
├── build_test_faiss_index.py          # FAISS index builder with real embeddings
└── test_faiss_index/                  # Generated test index (index.bin + meta.pkl)

tests/mocks/
└── llm_contract_mock.py               # ContractValidatedLLMMock for LLM responses
```

---

## 🚀 Quick Start

### 1. Prerequisites

Ensure you have all dependencies installed:

```bash
pip install -r requirements.txt
```

Required packages:
- `pytest >= 7.4.0`
- `pytest-asyncio`
- `sentence-transformers`
- `faiss-cpu` (or `faiss-gpu`)
- `xgboost`
- `fastapi`
- `psutil`

### 2. Build Test FAISS Index

The E2E tests require a test FAISS index with real embeddings. Build it once:

```bash
python tests/fixtures/build_test_faiss_index.py --rebuild --verify
```

This will:
- Load 20 automotive diagnostic scenarios
- Generate 384D embeddings using SentenceTransformer
- Build and save FAISS index to `tests/fixtures/test_faiss_index/`
- Verify index integrity
- **Duration**: ~1-2 minutes on first run

### 3. Run E2E Tests

#### Option A: Use the convenience script (recommended)

```bash
bash tests/run_e2e_torch.sh
```

This automatically:
- Checks for test FAISS index (builds if missing)
- Runs all E2E Torch tests with `-m e2e_torch`
- Shows timing breakdown (`--durations=10`)
- Provides colored output and summary

**Options:**
```bash
bash tests/run_e2e_torch.sh --rebuild-index   # Force rebuild test index
bash tests/run_e2e_torch.sh --verify-index    # Verify index after building
bash tests/run_e2e_torch.sh --coverage        # Generate coverage report
```

#### Option B: Run pytest directly

```bash
pytest -m e2e_torch -v
```

**Useful variations:**
```bash
# Run specific test file
pytest tests/e2e/test_real_torch_integration.py -v

# Run specific test
pytest tests/e2e/test_real_torch_integration.py::TestFullPipelineIntegration::test_full_pipeline_with_mock_torch -v

# Show full tracebacks
pytest -m e2e_torch --tb=long

# Drop into debugger on failure
pytest -m e2e_torch --pdb

# Show timing breakdown
pytest -m e2e_torch --durations=10

# Generate coverage report
pytest -m e2e_torch --cov=app --cov-report=html
```

---

## 🧪 Test Scenarios

### Core Pipeline Tests (`test_real_torch_integration.py`)

#### TestFullPipelineIntegration
- **test_full_pipeline_with_mock_torch**: Complete E2E validation (input → embedding → FAISS → Torch → LLM → ranked output)
- **test_full_pipeline_torch_fallback_graceful**: Verifies graceful fallback when Torch model unavailable
- **test_retrieval_quality_scoring**: Validates FAISS retrieval relevance for P0171 (MAF/O2 sensor)
- **test_database_persistence_complete**: Confirms DB writes for queries/manuals/embeddings
- **test_edge_case_no_obd_codes**: Handles symptom-only diagnosis (no OBD codes provided)

#### TestRetrievalPipelineIntegration
- **test_embedding_generation_real_model**: Validates SentenceTransformer produces 384D normalized vectors
- **test_faiss_index_populated**: Checks test index integrity (20 documents with metadata)

#### TestContractValidation
- **test_mock_llm_contract_adherence**: Verifies LLM mock produces contract-compliant responses

#### TestPerformanceAndStress
- **test_concurrent_requests**: 5 simultaneous requests (ThreadPoolExecutor), validates thread safety
- **test_large_symptom_text_handling**: Processes 500+ word symptom descriptions
- **test_latency_breakdown_tracing**: Instruments embed/search/rank stages (<5s total)
- **test_memory_leak_multiple_requests**: 10 sequential requests, monitors memory growth (<100MB threshold)

### Model Loading Tests (`test_torch_model_loading.py`)

#### TestTorchModelLoading
- **test_model_unavailable_uses_mock_predictor**: Validates mock fallback when model missing
- **test_real_model_when_available**: Tests real XGBoost model loading with feature extraction
- **test_model_loading_error_graceful_fallback**: Handles corrupted pickle files
- **test_model_hot_reload_capability**: Deploys new model mid-session without restart
- **test_torch_context_optional_in_ranker**: Ranker works with Torch=None and Torch=mock

#### TestTorchFeatureEngineering
- **test_feature_vector_dimension**: Validates 798D feature vector (VIN:100D + OBD:300D + Symptoms:384D + Temporal:14D)

---

## ⏱️ Expected Performance

| Test Category | Count | Typical Duration | Threshold |
|---------------|-------|------------------|-----------|
| Full Pipeline | 5 tests | 2-3s each | <5s per test |
| Retrieval     | 2 tests | 0.5-1s each | <2s per test |
| Contract      | 1 test | <0.5s | <1s |
| Performance   | 4 tests | 3-5s each | <10s per test |
| Model Loading | 7 tests | 1-2s each | <5s per test |
| **TOTAL**     | **19 tests** | **30-45s** | **<60s** |

---

## 🔍 Troubleshooting

### Issue: `FileNotFoundError: tests/fixtures/test_faiss_index/index.bin`

**Solution**: Build the test FAISS index:
```bash
python tests/fixtures/build_test_faiss_index.py --rebuild --verify
```

---

### Issue: `OSError: [Errno 28] No space left on device`

**Solution**: The SentenceTransformer model (~90MB) downloads to `~/.cache/torch/sentence_transformers/`. Ensure you have sufficient disk space.

---

### Issue: `ImportError: cannot import name 'SentenceTransformer'`

**Solution**: Install sentence-transformers:
```bash
pip install sentence-transformers
```

---

### Issue: `ModuleNotFoundError: No module named 'faiss'`

**Solution**: Install FAISS:
```bash
# CPU version (most common)
pip install faiss-cpu

# GPU version (requires CUDA)
pip install faiss-gpu
```

---

### Issue: Tests fail with `AttributeError: 'NoneType' object has no attribute 'search'`

**Cause**: VectorStore singleton not initialized with test index.

**Solution**: The `test_faiss_index` fixture should handle this, but you can debug with:
```python
from app.vector_store import VectorStore
store = VectorStore.get_instance(force_reload=True)
print(f"Index loaded: {store.index is not None}")
print(f"Metadata count: {len(store.metadata)}")
```

---

### Issue: Tests hang or timeout

**Possible causes**:
1. SentenceTransformer model downloading for the first time (~90MB, 1-2 min)
2. Thread deadlock in concurrent tests
3. Database lock contention

**Debug**:
```bash
# Run with verbose output
pytest -m e2e_torch -v -s

# Run single test to isolate issue
pytest tests/e2e/test_real_torch_integration.py::TestFullPipelineIntegration::test_full_pipeline_with_mock_torch -v -s
```

---

### Issue: Memory warnings during `test_memory_leak_multiple_requests`

**Expected behavior**: Memory growth <100MB over 10 requests.

**If exceeding threshold**:
1. Check for circular references in embeddings/ranker
2. Verify VectorStore singleton properly releases resources
3. Review FAISS index memory usage

---

## 📊 Coverage Expectations

Run with coverage to ensure >85% code coverage:

```bash
pytest -m e2e_torch --cov=app --cov-report=term-missing --cov-report=html
```

**Target coverage** (as per `pytest.ini`):
- Overall: ≥85%
- app/ranker.py: ≥90% (critical ranking logic)
- app/retriever.py: ≥90% (critical retrieval path)
- app/embeddings.py: ≥85% (embedding generation)
- app/vector_store.py: ≥80% (FAISS operations)

---

## 🔧 Maintenance

### Adding New Test Scenarios

1. **Update test data**:
   - Edit `tests/fixtures/generate_test_data.py`
   - Add new scenario to `get_test_diagnostic_scenarios()`
   - Rebuild FAISS index: `python tests/fixtures/build_test_faiss_index.py --rebuild`

2. **Create test**:
   - Add to appropriate test class in `test_real_torch_integration.py` or `test_torch_model_loading.py`
   - Use existing fixtures: `test_faiss_index`, `test_app_with_db`, `mock_llm_provider`
   - Follow naming: `test_<scenario>_<expected_behavior>`

3. **Verify**:
   ```bash
   pytest tests/e2e/test_real_torch_integration.py::TestClassName::test_new_scenario -v
   ```

### Updating LLM Mock Responses

Edit `tests/mocks/llm_contract_mock.py`:
- Add templates to `DIAGNOSIS_TEMPLATES` dict (keyed by OBD code)
- Ensure templates follow contract (numbered lists, Why/Tests/Labor/Parts sections)
- Test with: `pytest tests/e2e/test_real_torch_integration.py::TestContractValidation -v`

### Changing Embedding Model

If switching SentenceTransformer model (e.g., to `all-mpnet-base-v2`):
1. Update `build_test_faiss_index.py` with new model name
2. Rebuild test index with `--rebuild`
3. Update dimension assertions (384D → new dimension)
4. Verify: `pytest -m e2e_torch -v`

---

## 📚 Related Documentation

- [Torch V2 Implementation](../../V2_TORCH_IMPLEMENTATION.md)
- [Week 2 Torch Integration](../../WEEK2_TORCH_INTEGRATION.md)
- [API Documentation](../../API.md)
- [Deployment Guide](../../DEPLOYMENT.md)

---

## ✅ Success Criteria

Before merging Phase 2 Torch integration, all E2E tests must:
- ✅ Pass consistently (no flaky tests)
- ✅ Complete in <60s total
- ✅ Achieve ≥85% code coverage
- ✅ Handle edge cases gracefully (no OBD codes, large text, concurrent requests)
- ✅ Validate performance (<5s per request, <100MB memory growth)
- ✅ Confirm thread safety (concurrent request test passes)

---

## 📞 Support

If tests fail unexpectedly:
1. Check this README's troubleshooting section
2. Run with verbose output: `pytest -m e2e_torch -v -s`
3. Review test logs in `.pytest_cache/`
4. Check GitHub issues for similar problems
5. Open new issue with:
   - Test command used
   - Full error output
   - Environment details (`python --version`, `pip freeze`)
