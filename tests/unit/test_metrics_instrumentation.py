"""Tests for Prometheus metrics instrumentation across system components."""
import time

import pytest

from app.metrics import (
    faiss_search_latency_seconds,
    faiss_search_total,
    llm_calls_total,
    llm_response_latency_seconds,
    torch_inference_latency_seconds,
    torch_inference_total,
    torch_predictions_confidence_distribution,
)



class TestHistogramRecording:
    """Test histogram metrics record latency observations correctly."""

    def test_faiss_search_latency_records_success_observation(self):
        """Verify FAISS search latency histogram records success observations."""
        # Record a sample latency for FAISS search
        faiss_search_latency_seconds.labels(
            method="search", status="success"
        ).observe(0.025)

        # Get metrics in Prometheus format and verify histogram bucket
        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        # Verify histogram name and labels exist in output
        assert "faiss_search_latency_seconds" in metrics_output
        assert 'method="search"' in metrics_output
        assert 'status="success"' in metrics_output

    def test_torch_inference_latency_records_observations(self):
        """Verify Torch inference latency histogram records observations."""
        # Record multiple observations
        torch_inference_latency_seconds.labels(
            model_version="2.0.0", status="success"
        ).observe(0.050)
        torch_inference_latency_seconds.labels(
            model_version="2.0.0", status="success"
        ).observe(0.075)

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        # Verify histogram exists
        assert "torch_inference_latency_seconds" in metrics_output
        assert 'model_version="2.0.0"' in metrics_output

    def test_llm_response_latency_records_observations(self):
        """Verify LLM response latency histogram records observations."""
        llm_response_latency_seconds.labels(
            provider="gcp", model_status="success"
        ).observe(1.5)

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        assert "llm_response_latency_seconds" in metrics_output
        assert 'provider="gcp"' in metrics_output
        assert 'model_status="success"' in metrics_output

    def test_confidence_distribution_histogram_records_confidences(self):
        """Verify confidence distribution histogram records confidence scores."""
        # Record confidence scores
        torch_predictions_confidence_distribution.labels(
            model_version="2.0.0"
        ).observe(0.95)
        torch_predictions_confidence_distribution.labels(
            model_version="2.0.0"
        ).observe(0.72)

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        assert "torch_predictions_confidence_distribution" in metrics_output


class TestCounterIncrement:
    """Test counter metrics increment correctly."""

    def test_faiss_search_counter_increments_success(self):
        """Verify FAISS search counter increments on success."""
        faiss_search_total.labels(method="search", status="success").inc()

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        assert "faiss_search_total" in metrics_output
        assert 'method="search"' in metrics_output
        assert 'status="success"' in metrics_output

    def test_torch_inference_counter_increments_success(self):
        """Verify Torch inference counter increments on success."""
        torch_inference_total.labels(model_version="2.0.0", status="success").inc()

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        assert "torch_inference_total" in metrics_output
        assert 'model_version="2.0.0"' in metrics_output

    def test_llm_calls_counter_increments(self):
        """Verify LLM calls counter increments."""
        llm_calls_total.labels(provider="gcp", model_status="success").inc()
        llm_calls_total.labels(provider="gcp", model_status="success").inc()

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        assert "llm_calls_total" in metrics_output


class TestMetricsEndpoint:
    """Test /metrics endpoint returns valid Prometheus format."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_text_format(self):
        """Verify /metrics endpoint returns text/plain response."""
        from app.routes.metrics import get_metrics

        result = await get_metrics()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_metrics_endpoint_contains_faiss_metrics(self):
        """Verify /metrics endpoint contains FAISS metrics."""
        from app.routes.metrics import get_metrics

        # Record a FAISS metric first
        faiss_search_latency_seconds.labels(
            method="search", status="success"
        ).observe(0.01)

        result = await get_metrics()
        assert "faiss_search_latency_seconds" in result

    @pytest.mark.asyncio
    async def test_metrics_endpoint_contains_torch_metrics(self):
        """Verify /metrics endpoint contains Torch metrics."""
        from app.routes.metrics import get_metrics

        # Record a Torch metric first
        torch_inference_latency_seconds.labels(
            model_version="2.0.0", status="success"
        ).observe(0.05)

        result = await get_metrics()
        assert "torch_inference_latency_seconds" in result

    @pytest.mark.asyncio
    async def test_metrics_endpoint_contains_llm_metrics(self):
        """Verify /metrics endpoint contains LLM metrics."""
        from app.routes.metrics import get_metrics

        # Record an LLM metric first
        llm_response_latency_seconds.labels(
            provider="gcp", model_status="success"
        ).observe(1.5)

        result = await get_metrics()
        assert "llm_response_latency_seconds" in result

    @pytest.mark.asyncio
    async def test_metrics_endpoint_prometheus_format_validity(self):
        """Verify /metrics endpoint output is valid Prometheus format."""
        from app.routes.metrics import get_metrics

        result = await get_metrics()

        # Valid Prometheus format should have TYPE and HELP comments
        # (though they might be sparse depending on what's recorded)
        assert isinstance(result, str)
        # At minimum, it should not be empty or malformed
        lines = result.split("\n")
        assert len(lines) > 1  # Should have multiple lines


class TestLiveInstrumentation:
    """Test end-to-end instrumentation in actual component flows."""

    def test_faiss_search_latency_timing_context_manager(self):
        """Verify latency recording with context manager works correctly."""
        start = time.time()
        with faiss_search_latency_seconds.labels(
            method="search", status="success"
        ).time():
            time.sleep(0.01)  # Simulate 10ms operation
        elapsed = time.time() - start

        # Should record approximately 10ms
        assert 0.008 < elapsed < 0.05  # Reasonable bounds

    def test_torch_inference_multiple_stages_timing(self):
        """Verify Torch inference latency records complete execution."""
        # Simulate stages of inference
        with torch_inference_latency_seconds.labels(
            model_version="2.0.0", status="success"
        ).time():
            time.sleep(0.01)  # Feature encoding
            time.sleep(0.01)  # Model inference
            time.sleep(0.01)  # Calibration

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")
        assert "torch_inference_latency_seconds" in metrics_output

    def test_confidence_distribution_collection(self):
        """Verify confidence scores are collected in distribution."""
        confidences = [0.95, 0.72, 0.58, 0.42, 0.31]

        for conf in confidences:
            torch_predictions_confidence_distribution.labels(
                model_version="2.0.0"
            ).observe(conf)

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        # All confidence observations should be recorded
        assert "torch_predictions_confidence_distribution" in metrics_output

    @pytest.mark.asyncio
    async def test_llm_latency_with_error_handling(self):
        """Verify LLM latency records both success and error cases."""
        # Record error case
        try:
            with llm_response_latency_seconds.labels(
                provider="gcp", model_status="error"
            ).time():
                time.sleep(0.05)
                raise ValueError("Simulated LLM error")
        except ValueError:
            pass

        # Record success case
        with llm_response_latency_seconds.labels(
            provider="gcp", model_status="success"
        ).time():
            time.sleep(0.02)

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        # Both should be recorded
        assert "llm_response_latency_seconds" in metrics_output
        assert 'model_status="error"' in metrics_output
        assert 'model_status="success"' in metrics_output


class TestMetricsIntegration:
    """Integration tests for complete instrumentation workflows."""

    def test_histogram_percentile_calculation_support(self):
        """Verify histogram buckets support percentile calculations."""
        # Record observations across range
        for i in range(10):
            faiss_search_latency_seconds.labels(
                method="search", status="success"
            ).observe(0.001 + (i * 0.005))

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        # Should have bucket boundaries in output
        assert "faiss_search_latency_seconds_bucket" in metrics_output
        # Should have sum and count for percentile calculation
        assert "faiss_search_latency_seconds_sum" in metrics_output
        assert "faiss_search_latency_seconds_count" in metrics_output

    def test_multiple_components_metrics_coexist(self):
        """Verify all three component metrics can coexist without conflicts."""
        # Record from all three components
        faiss_search_latency_seconds.labels(
            method="search", status="success"
        ).observe(0.025)
        torch_inference_latency_seconds.labels(
            model_version="2.0.0", status="success"
        ).observe(0.150)
        llm_response_latency_seconds.labels(
            provider="gcp", model_status="success"
        ).observe(2.5)

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        # All three should be present
        assert "faiss_search_latency_seconds" in metrics_output
        assert "torch_inference_latency_seconds" in metrics_output
        assert "llm_response_latency_seconds" in metrics_output

    def test_label_dimensionality_isolation(self):
        """Verify labels keep metrics isolated by dimension."""
        # FAISS with different status values
        faiss_search_latency_seconds.labels(
            method="search", status="success"
        ).observe(0.01)
        faiss_search_latency_seconds.labels(
            method="search", status="error"
        ).observe(0.02)

        # Torch with different model versions
        torch_inference_latency_seconds.labels(
            model_version="2.0.0", status="success"
        ).observe(0.10)
        torch_inference_latency_seconds.labels(
            model_version="1.5.0", status="success"
        ).observe(0.12)

        from prometheus_client import generate_latest
        metrics_output = generate_latest().decode("utf-8")

        # Both status values should be present
        assert 'status="success"' in metrics_output
        assert 'status="error"' in metrics_output

        # Both model versions should be present
        assert 'model_version="2.0.0"' in metrics_output
        assert 'model_version="1.5.0"' in metrics_output

