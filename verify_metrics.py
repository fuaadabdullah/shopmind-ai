#!/usr/bin/env python3
"""Simple verification script for metrics instrumentation."""
import time
import sys

# Add app to path
sys.path.insert(0, "/Volumes/GOBLINOS 1/ShopMindAI")

from app.metrics import (
    faiss_search_latency_seconds,
    faiss_search_total,
    torch_inference_latency_seconds,
    torch_inference_total,
    torch_predictions_confidence_distribution,
    llm_response_latency_seconds,
    llm_calls_total,
)
from prometheus_client import generate_latest

print("=" * 70)
print("Prometheus Metrics Instrumentation Verification")
print("=" * 70)

# Test 1: FAISS search latency recording
print("\n[Test 1] FAISS Search Latency Recording")
print("-" * 70)
faiss_search_latency_seconds.labels(
    method="search", status="success"
).observe(0.025)
faiss_search_total.labels(method="search", status="success").inc()
print("✓ Recorded FAISS search: 25ms latency + 1 request count")

# Test 2: Torch inference latency recording
print("\n[Test 2] Torch Inference Latency Recording")
print("-" * 70)
torch_inference_latency_seconds.labels(
    model_version="2.0.0", status="success"
).observe(0.150)
torch_inference_total.labels(model_version="2.0.0", status="success").inc()
torch_predictions_confidence_distribution.labels(
    model_version="2.0.0"
).observe(0.95)
torch_predictions_confidence_distribution.labels(
    model_version="2.0.0"
).observe(0.72)
print("✓ Recorded Torch inference: 150ms latency + 1 request count")
print("✓ Recorded 2 confidence values: 0.95, 0.72")

# Test 3: LLM response latency recording
print("\n[Test 3] LLM Response Latency Recording")
print("-" * 70)
llm_response_latency_seconds.labels(
    provider="gcp", model_status="success"
).observe(2.5)
llm_calls_total.labels(provider="gcp", model_status="success").inc()
print("✓ Recorded LLM response: 2.5s latency + 1 request count")

# Test 4: Verify metrics are in output
print("\n[Test 4] Metrics Exposition Format")
print("-" * 70)
metrics_output = generate_latest().decode("utf-8")

checks = [
    ("faiss_search_latency_seconds", "FAISS search latency histogram"),
    ("faiss_search_total", "FAISS search counter"),
    ("torch_inference_latency_seconds", "Torch inference latency histogram"),
    ("torch_inference_total", "Torch inference counter"),
    ("torch_predictions_confidence", "Confidence distribution"),
    ("llm_response_latency_seconds", "LLM response latency histogram"),
    ("llm_calls_total", "LLM calls counter"),
]

all_passed = True
for metric_name, description in checks:
    if metric_name in metrics_output:
        print(f"✓ {description}: {metric_name}")
    else:
        print(f"✗ {description}: {metric_name} NOT FOUND")
        all_passed = False

# Test 5: Histogram structure verification
print("\n[Test 5] Histogram Structure Verification")
print("-" * 70)
structure_checks = [
    ("faiss_search_latency_seconds_bucket", "FAISS bucket boundaries"),
    ("faiss_search_latency_seconds_sum", "FAISS latency sum"),
    ("faiss_search_latency_seconds_count", "FAISS request count"),
    ("torch_inference_latency_seconds_bucket", "Torch bucket boundaries"),
    ("torch_inference_latency_seconds_sum", "Torch latency sum"),
]

for metric_name, description in structure_checks:
    if metric_name in metrics_output:
        print(f"✓ {description}")
    else:
        print(f"✗ {description} NOT FOUND")
        all_passed = False

# Test 6: Label verification
print("\n[Test 6] Label Verification")
print("-" * 70)
label_checks = [
    ('method="search"', "FAISS method label"),
    ('status="success"', "Success status label"),
    ('model_version="2.0.0"', "Torch model version label"),
    ('provider="gcp"', "LLM provider label"),
]

for label, description in label_checks:
    if label in metrics_output:
        print(f"✓ {description}: {label}")
    else:
        print(f"✗ {description}: {label} NOT FOUND")
        all_passed = False

# Test 7: Metrics endpoint simulation
print("\n[Test 7] Metrics Endpoint Simulation")
print("-" * 70)
try:
    # Simulating what the /metrics endpoint would return
    metrics_bytes = generate_latest()
    print(f"✓ Metrics endpoint returns {len(metrics_bytes)} bytes")
    print(f"✓ Metrics output is valid bytes")
    print(f"✓ Total lines in metrics output: {len(metrics_output.split(chr(10)))}")
except Exception as e:
    print(f"✗ Metrics endpoint error: {e}")
    all_passed = False

# Summary
print("\n" + "=" * 70)
if all_passed:
    print("✓ ALL TESTS PASSED - Metrics instrumentation is working correctly!")
    print("=" * 70)
    sys.exit(0)
else:
    print("✗ SOME TESTS FAILED - See above for details")
    print("=" * 70)
    sys.exit(1)
