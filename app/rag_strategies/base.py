"""Base types and protocols for RAG strategies"""

from typing import Protocol, List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
import time

if TYPE_CHECKING:
    from . import StrategyConfig


@dataclass
class StrategyResult:
    """Result returned by a RAG strategy"""

    entities: List[Dict[str, Any]]
    strategy_used: str
    execution_time_ms: float
    message_count: int
    success: bool
    error: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None


@dataclass
class StrategyMetrics:
    """Metrics tracking for a strategy"""

    name: str
    total_executions: int = 0
    successful_executions: int = 0
    total_duration_ms: float = 0
    avg_duration_ms: float = 0
    avg_entity_count: float = 0
    last_execution: Optional[float] = None
    error_count: int = 0

    def record_execution(self, duration_ms: float, entity_count: int, success: bool):
        """Record a strategy execution"""
        self.total_executions += 1
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.total_executions
        self.last_execution = time.time()

        if success:
            self.successful_executions += 1
            # Update rolling average of entity count (only for successful runs)
            if self.successful_executions == 1:
                self.avg_entity_count = entity_count
            else:
                # Simple exponential moving average
                alpha = 0.1
                self.avg_entity_count = (
                    alpha * entity_count + (1 - alpha) * self.avg_entity_count
                )
        else:
            self.error_count += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "success_rate": self.success_rate,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "avg_entity_count": round(self.avg_entity_count, 1),
            "last_execution": self.last_execution,
            "error_count": self.error_count,
        }


class RAGStrategy(Protocol):
    """Protocol defining the interface for RAG strategies

    Using Protocol instead of ABC for minimal overhead and flexibility.
    Strategies are implemented as async functions that can be registered
    with the @register_strategy decorator.
    """

    async def __call__(
        self, messages: List[Dict[str, str]], config: "StrategyConfig"
    ) -> List[Dict[str, Any]]:
        """
        Execute the RAG strategy

        Args:
            messages: List of conversation messages in format:
                     [{"role": "user", "content": "..."}, ...]
            config: Strategy configuration object

        Returns:
            List of ranked entities with scores and metadata

        The returned entities should have the format:
        {
            "entity_id": "sensor.example",
            "score": 0.95,
            "text": "Entity description",
            "area": "living_room",
            "domain": "sensor",
            # ... other entity fields
        }
        """
        ...


# Type aliases for convenience
MessageList = List[Dict[str, str]]
EntityList = List[Dict[str, Any]]
