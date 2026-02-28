"""Prometheus metrics instrumentation for ShopMindAI.

Tracks latency distributions (with percentile bucketing) and request counts for:
- FAISS semantic search (5-50ms range)
- Torch inference (30-200ms range)
- LLM API calls (200-5000ms range)

Each metric uses component-specific bucket boundaries optimized for its latency
characteristics, enabling accurate percentile calculations at p50/p90/p95/p99.

Usage:
    from app.metrics import faiss_search_latency_seconds, torch_inference_latency_seconds

    # Automatic timing via decorator
    with faiss_search_latency_seconds.labels(method="search").time():
        results = vector_store.search(query, top_k=5)

    # Or manual timing
    start = time.time()
    predictions = model.predict(X)
    torch_inference_latency_seconds.labels(model_version="v1.1").observe(
        time.time() - start
    )
"""
from prometheus_client import Counter, Gauge, Histogram

# ============================================================================
# FAISS Search Metrics
# ============================================================================
# Buckets optimized for sub-50ms searches: 1ms → 5ms → 10ms → 20ms → 50ms
faiss_search_latency_seconds = Histogram(
    "faiss_search_latency_seconds",
    "Time spent in FAISS vector similarity search",
    labelnames=["method", "status"],
    buckets=(0.001, 0.005, 0.01, 0.02, 0.05, 0.1),
)

faiss_search_total = Counter(
    "faiss_search_total",
    "Total number of FAISS searches",
    labelnames=["method", "status"],
)

faiss_index_vectors_count = Gauge(
    "faiss_index_vectors_count",
    "Total number of vectors in FAISS index",
)

# ============================================================================
# Torch Inference Metrics
# ============================================================================
# Buckets optimized for 30-200ms inference: 10ms → 30ms → 50ms → 100ms → 200ms
torch_inference_latency_seconds = Histogram(
    "torch_inference_latency_seconds",
    "Time spent in Torch model inference (feature encoding + prediction)",
    labelnames=["model_version", "status"],
    buckets=(0.01, 0.03, 0.05, 0.1, 0.2, 0.5),
)

torch_inference_total = Counter(
    "torch_inference_total",
    "Total number of Torch inferences",
    labelnames=["model_version", "status"],
)

torch_predictions_confidence_distribution = Histogram(
    "torch_predictions_confidence",
    "Distribution of prediction confidence scores from Torch model",
    labelnames=["model_version"],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# ============================================================================
# LLM API Call Metrics
# ============================================================================
# Buckets optimized for 200-5000ms LLM calls: 100ms → 500ms → 1s → 2s → 5s → 10s
llm_response_latency_seconds = Histogram(
    "llm_response_latency_seconds",
    "Time spent waiting for LLM API response",
    labelnames=["provider", "model_status"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

llm_calls_total = Counter(
    "llm_calls_total",
    "Total number of LLM API calls",
    labelnames=["provider", "model_status"],
)

llm_tokens_used = Counter(
    "llm_tokens_used",
    "Total tokens consumed by LLM API calls (input + output)",
    labelnames=["provider"],
)

# ============================================================================
# Circuit Breaker Metrics
# ============================================================================
circuit_breaker_trips_total = Counter(
    "circuit_breaker_trips_total",
    "Total circuit breaker state changes (opened or recovered)",
    labelnames=["provider", "state_change"],
)

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Current circuit breaker state (0=Closed, 1=Open, 2=Half-Open)",
    labelnames=["provider"],
)

circuit_breaker_failure_count = Gauge(
    "circuit_breaker_failure_count",
    "Current failure count in circuit breaker",
    labelnames=["provider"],
)

llm_fallback_activated_total = Counter(
    "llm_fallback_activated_total",
    "Total times LLM fallback provider was activated",
    labelnames=["primary_provider", "fallback_provider", "reason"],
)

# ============================================================================
# Request-Level Metrics (for full diagnostic pipeline)
# ============================================================================
# Total time from request entry to response
diagnostic_request_latency_seconds = Histogram(
    "diagnostic_request_latency_seconds",
    "Total time to complete a diagnostic request (search + inference + LLM)",
    labelnames=["endpoint"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

diagnostic_requests_total = Counter(
    "diagnostic_requests_total",
    "Total diagnostic requests processed",
    labelnames=["endpoint", "status"],
)
