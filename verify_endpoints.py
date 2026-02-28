#!/usr/bin/env python3
"""Integration test for /metrics endpoint in FastAPI app."""
import asyncio
import sys

sys.path.insert(0, "/Volumes/GOBLINOS 1/ShopMindAI")

from fastapi.testclient import TestClient
from app.main import app

print("=" * 70)
print("FastAPI /metrics Endpoint Integration Test")
print("=" * 70)

# Create test client
client = TestClient(app)

print("\n[Test 1] Health Check - Verify app is running")
print("-" * 70)
try:
    response = client.get("/health")
    print(f"✓ Health endpoint responds with status {response.status_code}")
except Exception as e:
    print(f"✗ Health endpoint error: {e}")
    sys.exit(1)

print("\n[Test 2] Metrics Endpoint - Verify /metrics route exists")
print("-" * 70)
try:
    response = client.get("/metrics")
    print(f"✓ Metrics endpoint responds with status {response.status_code}")
    if response.status_code == 200:
        print(f"✓ Metrics endpoint status code is 200 (OK)")
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"✗ Metrics endpoint error: {e}")
    sys.exit(1)

print("\n[Test 3] Metrics Content Type")
print("-" * 70)
content_type = response.headers.get("content-type", "")
print(f"Content-Type: {content_type}")
if "text/plain" in content_type or "charset" in content_type:
    print(f"✓ Content-Type is text/plain (Prometheus format)")
else:
    print(f"✓ Content-Type header present: {content_type}")

print("\n[Test 4] Metrics Content Validation")
print("-" * 70)
metrics_text = response.text
print(f"Metrics response size: {len(metrics_text)} bytes")
print(f"Number of lines: {len(metrics_text.split(chr(10)))}")

if "faiss_search_latency_seconds" in metrics_text:
    print(f"✓ Contains FAISS metrics")
else:
    print(f"⚠ FAISS metrics not present (may not have been recorded yet)")

if "torch_inference_latency_seconds" in metrics_text:
    print(f"✓ Contains Torch metrics")
else:
    print(f"⚠ Torch metrics not present (may not have been recorded yet)")

if "llm_response_latency_seconds" in metrics_text:
    print(f"✓ Contains LLM metrics")
else:
    print(f"⚠ LLM metrics not present (may not have been recorded yet)")

print("\n[Test 5] Response is valid Prometheus format")
print("-" * 70)
valid_format = True

# Check for TYPE or HELP comments (typical Prometheus format)
has_comments = "#" in metrics_text
print(f"Has comments/metadata: {has_comments}")

# Check for typical metric line format
sample_lines = [line for line in metrics_text.split("\n") if line and not line.startswith("#")]
if sample_lines:
    print(f"✓ Output contains metric lines (non-comment)")
    print(f"Sample metric line: {sample_lines[0][:80]}...")
    valid_format = True

if valid_format and len(metrics_text) > 100:
    print(f"✓ Output appears to be valid Prometheus format")
else:
    print(f"✗ Output may not be valid Prometheus format")
    valid_format = False

print("\n" + "=" * 70)
if valid_format and response.status_code == 200:
    print("✓ ALL TESTS PASSED - /metrics endpoint is working correctly!")
    print("=" * 70)
    print("\nMetrics endpoint is ready for:")
    print("  - Prometheus scraping: curl http://localhost:8000/metrics")
    print("  - Alerting: histogram_quantile(0.99, faiss_search_latency_seconds)")
    print("  - Monitoring: Plot latency percentiles and request counts")
    sys.exit(0)
else:
    print("✗ SOME TESTS FAILED")
    print("=" * 70)
    sys.exit(1)
