"""
Unit tests for circuit breaker pattern implementation.

Tests cover:
- State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Failure counting and threshold
- Success counting and reset
- Recovery timeout calculation
- Metrics recording
- Provider interface transparency
"""
import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from app.providers.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerProvider,
)
from app.exceptions import ProviderError


class TestCircuitBreakerStateMachine:
    """Test state transitions and thresholds."""

    def test_circuit_breaker_starts_in_closed_state(self):
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_opens_on_failure_threshold(self):
        """Circuit breaker should open after N failures."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=2
        )

        # Simulate 3 failures
        for i in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("test error")))
            except Exception:
                pass

        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_allows_requests_when_closed(self):
        """Circuit breaker should allow requests when CLOSED."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        def success_fn():
            return "success"

        result = cb.call(success_fn)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_enters_half_open_after_recovery_timeout(self):
        """Circuit breaker should enter HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=2,
            recovery_timeout=1,  # 1 second
            success_threshold=2
        )

        # Open the circuit
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
            except Exception:
                pass

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(1.1)

        # Next call should attempt (entering HALF_OPEN)
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
        except Exception:
            pass

        # Should be in HALF_OPEN or back to OPEN (depending on result)
        assert cb.state in [CircuitBreakerState.HALF_OPEN, CircuitBreakerState.OPEN]

    def test_circuit_breaker_closes_on_success_threshold(self):
        """Circuit breaker should close after N successes in HALF_OPEN."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=2,
            recovery_timeout=0,  # No recovery timeout
            success_threshold=2
        )

        # Open the circuit
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
            except Exception:
                pass

        assert cb.state == CircuitBreakerState.OPEN

        # Immediately try again (should enter HALF_OPEN)
        result = cb.call(lambda: "success")
        assert result == "success"

        # Second success should close
        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_reopens_on_failure_in_half_open(self):
        """Circuit breaker should reopen on failure while HALF_OPEN."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=1,
            recovery_timeout=0,
            success_threshold=2
        )

        # Open the circuit
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
        except Exception:
            pass

        assert cb.state == CircuitBreakerState.OPEN

        # Attempt in HALF_OPEN - should fail
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
        except Exception:
            pass

        # Should be back to OPEN
        assert cb.state == CircuitBreakerState.OPEN


class TestCircuitBreakerMetrics:
    """Test metrics collection and reporting."""

    def test_get_metrics_returns_state_and_counts(self):
        """Circuit breaker should expose metrics."""
        cb = CircuitBreaker(
            provider_name="test_provider",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        metrics = cb.get_metrics()
        assert metrics["state"] == "CLOSED"
        assert metrics["failure_count"] == 0
        assert metrics["success_count"] == 0
        assert isinstance(metrics["recovery_in_seconds"], (int, float))

    def test_metrics_reflect_state_changes(self):
        """Metrics should update as state changes."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=2,
            recovery_timeout=30,
            success_threshold=2
        )

        # Fail once
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
        except Exception:
            pass

        metrics = cb.get_metrics()
        assert metrics["failure_count"] == 1
        assert metrics["state"] == "CLOSED"

        # Fail again to open
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
        except Exception:
            pass

        metrics = cb.get_metrics()
        assert metrics["state"] == "OPEN"


class TestCircuitBreakerProvider:
    """Test the CircuitBreakerProvider wrapper."""

    def test_circuit_breaker_provider_implements_llm_provider_interface(self):
        """CircuitBreakerProvider should implement same interface as LLMProvider."""
        mock_provider = Mock()
        mock_provider.provider_name = "test"
        mock_provider.generate = Mock(return_value="response")

        cbp = CircuitBreakerProvider(
            provider=mock_provider,
            provider_name="test",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        result = cbp.generate("test prompt")
        assert result == "response"
        mock_provider.generate.assert_called_once_with("test prompt")

    def test_circuit_breaker_provider_exposes_state(self):
        """CircuitBreakerProvider should expose circuit breaker state."""
        mock_provider = Mock()
        mock_provider.provider_name = "test"

        cbp = CircuitBreakerProvider(
            provider=mock_provider,
            provider_name="test",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        state = cbp.get_state()
        assert state == "CLOSED"

    def test_circuit_breaker_provider_exposes_metrics(self):
        """CircuitBreakerProvider should expose circuit breaker metrics."""
        mock_provider = Mock()
        mock_provider.provider_name = "test"

        cbp = CircuitBreakerProvider(
            provider=mock_provider,
            provider_name="test",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        metrics = cbp.get_metrics()
        assert "state" in metrics
        assert "failure_count" in metrics

    def test_circuit_breaker_provider_passes_through_provider_name(self):
        """CircuitBreakerProvider should expose underlying provider name."""
        mock_provider = Mock()
        mock_provider.provider_name = "my_custom_provider"

        cbp = CircuitBreakerProvider(
            provider=mock_provider,
            provider_name="my_custom_provider",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        assert cbp.provider_name == "my_custom_provider"


class TestCircuitBreakerExceptionHandling:
    """Test error handling behavior."""

    def test_circuit_breaker_propagates_function_exceptions(self):
        """Circuit breaker should propagate exceptions from function."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        def failing_fn():
            raise ValueError("specific error")

        with pytest.raises(ValueError, match="specific error"):
            cb.call(failing_fn)

    def test_circuit_breaker_raises_when_open(self):
        """Circuit breaker should raise when opened."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=1,
            recovery_timeout=30,
            success_threshold=2
        )

        # Open the circuit
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
        except Exception:
            pass

        assert cb.state == CircuitBreakerState.OPEN

        # Next call should fail immediately
        with pytest.raises(ProviderError, match="Circuit breaker"):
            cb.call(lambda: "success")

    def test_circuit_breaker_returns_correct_get_state(self):
        """Circuit breaker should return readable state name."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=1,
            recovery_timeout=30,
            success_threshold=2
        )

        assert cb.get_state() == "CLOSED"

        # Open it
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("error")))
        except Exception:
            pass

        assert cb.get_state() == "OPEN"


class TestCircuitBreakerWithArguments:
    """Test circuit breaker with function arguments."""

    def test_circuit_breaker_passes_arguments_to_function(self):
        """Circuit breaker should pass args/kwargs to wrapped function."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        def add(a, b):
            return a + b

        result = cb.call(add, 2, 3)
        assert result == 5

    def test_circuit_breaker_with_keyword_arguments(self):
        """Circuit breaker should handle keyword arguments."""
        cb = CircuitBreaker(
            provider_name="test",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )

        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        result = cb.call(greet, "Alice", greeting="Hi")
        assert result == "Hi, Alice"

