"""Circuit breaker pattern implementation for LLM providers.

Implements a standard circuit breaker with three states:
- Closed: Normal operation, requests pass through
- Open: Provider is failing, requests blocked immediately  
- Half-Open: Testing if provider recovered, window of requests tried

Prevents cascading failures when LLM providers go down.
"""
import time
from enum import Enum
from typing import Callable, TypeVar, Any
from datetime import datetime, timedelta

from .base import LLMProvider
from app.logger import setup_logger
from app.exceptions import ProviderError

logger = setup_logger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = 0       # Normal operation
    OPEN = 1         # Provider failing, requests blocked
    HALF_OPEN = 2    # Testing recovery, limited requests allowed


class CircuitBreaker:
    """
    Circuit breaker for LLM provider calls.
    
    Protects against cascading failures by:
    1. Tracking consecutive failures
    2. Opening circuit when threshold reached
    3. Periodically testing recovery
    4. Closing circuit when provider recovers
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.

        Args:
            provider_name: Name of the LLM provider (e.g., "gcp", "siliconeflow")
            failure_threshold: Number of failures before opening (default: 5)
            recovery_timeout: Seconds to wait before half-open (default: 30)
            success_threshold: Successes needed in half-open to close (default: 2)
        """
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.last_state_change: datetime = datetime.now()

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function

        Raises:
            ProviderError: If circuit is open or function fails
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                logger.info(
                    f"Circuit breaker for {self.provider_name}: "
                    f"attempting recovery (HALF_OPEN)",
                    extra={"provider": self.provider_name, "state": "HALF_OPEN"}
                )
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
            else:
                logger.warning(
                    f"Circuit breaker for {self.provider_name} is OPEN, "
                    f"request blocked",
                    extra={"provider": self.provider_name, "state": "OPEN"}
                )
                raise ProviderError(
                    f"Circuit breaker open for {self.provider_name}",
                    details={
                        "provider": self.provider_name,
                        "state": "OPEN",
                        "recovery_in_seconds": self._seconds_until_retry(),
                    },
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return False
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _seconds_until_retry(self) -> int:
        """Calculate seconds until circuit can retry recovery."""
        if self.last_failure_time is None:
            return 0
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        remaining = self.recovery_timeout - elapsed
        return max(0, int(remaining))

    def _on_success(self) -> None:
        """Handle successful request."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            logger.debug(
                f"Circuit breaker for {self.provider_name}: "
                f"success in HALF_OPEN ({self.success_count}/{self.success_threshold})",
                extra={
                    "provider": self.provider_name,
                    "state": "HALF_OPEN",
                    "successes": self.success_count,
                }
            )

            if self.success_count >= self.success_threshold:
                self._reset()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        logger.warning(
            f"Circuit breaker for {self.provider_name}: "
            f"failure #{self.failure_count}/{self.failure_threshold}",
            extra={
                "provider": self.provider_name,
                "failure_count": self.failure_count,
                "threshold": self.failure_threshold,
            }
        )

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Failure in half-open resets recovery process
            logger.error(
                f"Circuit breaker for {self.provider_name}: "
                f"failure during recovery, reopening",
                extra={"provider": self.provider_name, "state": "OPEN"},
            )
            self._open()
        elif self.failure_count >= self.failure_threshold:
            self._open()

    def _open(self) -> None:
        """Transition to OPEN state."""
        if self.state != CircuitBreakerState.OPEN:
            self.state = CircuitBreakerState.OPEN
            self.last_state_change = datetime.now()
            logger.error(
                f"Circuit breaker for {self.provider_name} opened "
                f"(too many failures)",
                extra={
                    "provider": self.provider_name,
                    "state": "OPEN",
                    "failure_count": self.failure_count,
                }
            )

    def _reset(self) -> None:
        """Transition to CLOSED state (recovered)."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()
        logger.info(
            f"Circuit breaker for {self.provider_name} closed (recovered)",
            extra={"provider": self.provider_name, "state": "CLOSED"}
        )

    def get_state(self) -> str:
        """Get current circuit breaker state name."""
        return self.state.name

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics for monitoring."""
        return {
            "provider": self.provider_name,
            "state": self.state.name,
            "state_value": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_state_change": self.last_state_change.isoformat(),
            "recovery_in_seconds": self._seconds_until_retry() if self.state == CircuitBreakerState.OPEN else 0,
        }


class CircuitBreakerProvider(LLMProvider):
    """
    Wraps an LLM provider with circuit breaker protection.
    
    Transparently implements the LLMProvider interface while protecting
    against cascading failures.
    """

    def __init__(
        self,
        provider: LLMProvider,
        provider_name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker provider wrapper.

        Args:
            provider: Underlying LLM provider to wrap
            provider_name: Name for logging and metrics
            failure_threshold: Failures before circuit opens
            recovery_timeout: Seconds before attempting recovery
            success_threshold: Successes to close circuit
        """
        self.provider = provider
        self.provider_name = provider_name
        self.name = getattr(provider, "name", provider_name)
        
        self.cb = CircuitBreaker(
            provider_name=provider_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
        )

    def generate(self, prompt: str) -> str:
        """
        Generate completion with circuit breaker protection.

        Args:
            prompt: Input prompt text

        Returns:
            Generated response text

        Raises:
            ProviderError: If circuit is open or generation fails
        """
        return self.cb.call(self.provider.generate, prompt)

    def get_state(self) -> str:
        """Get circuit breaker state."""
        return self.cb.get_state()

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics."""
        return self.cb.get_metrics()
