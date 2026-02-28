"""Prometheus metrics exposition endpoint."""
from fastapi import APIRouter
from prometheus_client import generate_latest

router = APIRouter(tags=["monitoring"])


@router.get("/metrics", response_class="text/plain; charset=utf-8")
async def get_metrics() -> str:
    """
    Expose Prometheus metrics in text exposition format.

    See: https://prometheus.io/docs/instrumenting/exposition_formats/

    Returns:
        Prometheus-formatted metrics string including:
        - FAISS search latency and request counts (percentiles p50/p90/p95/p99)
        - Torch inference latency and confidence distribution (percentiles)
        - LLM response latency by provider (percentiles)
        - Diagnostic request end-to-end latency (percentiles)
        - Custom gauges for index size and prediction confidence

    Example metrics output:
        faiss_search_latency_seconds_bucket{method="search", status="success", le="0.001"} 5.0
        faiss_search_latency_seconds_bucket{method="search", status="success", le="0.005"} 15.0
        faiss_search_latency_seconds_sum{method="search", status="success"} 0.042
        faiss_search_latency_seconds_count{method="search", status="success"} 25.0

    Scrape Configuration (add to Prometheus):
        scrape_configs:
          - job_name: 'shopmindai'
            static_configs:
              - targets: ['localhost:8000']
            metrics_path: '/metrics'
            scrape_interval: 15s

    Alert Rule Examples:
        # Alert if FAISS search latency p99 exceeds 100ms
        - alert: FAISSSearchSlow
          expr: histogram_quantile(0.99, faiss_search_latency_seconds) > 0.1
          for: 5m

        # Alert if Torch inference latency p99 exceeds 500ms
        - alert: TorchInferenceSlow
          expr: histogram_quantile(0.99, torch_inference_latency_seconds) > 0.5
          for: 5m

        # Alert if LLM response latency p99 exceeds 10s
        - alert: LLMResponseSlow
          expr: histogram_quantile(0.99, llm_response_latency_seconds) > 10
          for: 5m
    """
    return generate_latest()

