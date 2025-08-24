"""RAG Strategy Pattern Implementation

This module provides a flexible strategy pattern for different RAG approaches,
allowing easy experimentation and A/B testing of various search methodologies.

Strategies:
- legacy: Current LangGraph-based workflow
- hybrid: Conversation-aware weighted embedding search  
- cluster: Enhanced search with cluster integration (future)
- experimental: Playground for new ideas
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import time
import logging

from .base import RAGStrategy, StrategyResult, StrategyMetrics

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Configuration for strategy execution"""

    max_messages: int = 5
    user_weight: float = 1.0
    assistant_weight: float = 0.5
    recency_boost: float = 0.3
    enable_metrics: bool = True
    timeout_seconds: int = 10


class StrategyRegistry:
    """Lightweight strategy registry using function-based approach"""

    def __init__(self):
        self._strategies: Dict[str, Callable] = {}
        self._metrics: Dict[str, StrategyMetrics] = {}

    def register(self, name: str):
        """Decorator for registering strategies"""

        def decorator(func: RAGStrategy):
            self._strategies[name] = func
            self._metrics[name] = StrategyMetrics(name=name)
            logger.info(f"Registered RAG strategy: {name}")
            return func

        return decorator

    async def execute(
        self,
        strategy_name: str,
        messages: List[Dict[str, str]],
        config: Optional[StrategyConfig] = None,
    ) -> StrategyResult:
        """Execute a strategy with metrics collection"""

        config = config or StrategyConfig()

        if strategy_name not in self._strategies:
            logger.warning(
                f"Unknown strategy: {strategy_name}, falling back to 'hybrid'"
            )
            strategy_name = "hybrid"

        strategy_func = self._strategies[strategy_name]
        metrics = self._metrics[strategy_name]

        # Execute with timing
        start_time = time.time()

        try:
            entities = await strategy_func(messages, config)

            duration = time.time() - start_time

            # Update metrics
            if config.enable_metrics:
                metrics.record_execution(
                    duration_ms=duration * 1000,
                    entity_count=len(entities),
                    success=True,
                )

            return StrategyResult(
                entities=entities,
                strategy_used=strategy_name,
                execution_time_ms=duration * 1000,
                message_count=len(messages),
                success=True,
            )

        except Exception as e:
            duration = time.time() - start_time

            logger.error(f"Strategy {strategy_name} failed: {e}", exc_info=True)

            if config.enable_metrics:
                metrics.record_execution(
                    duration_ms=duration * 1000, entity_count=0, success=False
                )

            return StrategyResult(
                entities=[],
                strategy_used=strategy_name,
                execution_time_ms=duration * 1000,
                message_count=len(messages),
                success=False,
                error=str(e),
            )

    def get_available_strategies(self) -> List[str]:
        """Get list of available strategy names"""
        return list(self._strategies.keys())

    def get_metrics(self, strategy_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for specific strategy or all strategies"""
        if strategy_name:
            if strategy_name in self._metrics:
                return self._metrics[strategy_name].to_dict()
            return {}

        return {name: metrics.to_dict() for name, metrics in self._metrics.items()}


# Global registry instance
registry = StrategyRegistry()

# Convenience functions
register_strategy = registry.register
execute_strategy = registry.execute
get_strategy_metrics = registry.get_metrics
get_available_strategies = registry.get_available_strategies


# Import strategy implementations to register them
from . import (
    hybrid_embedding,
)  # This will register the 'hybrid' and 'legacy' strategies


__all__ = [
    "RAGStrategy",
    "StrategyResult",
    "StrategyMetrics",
    "StrategyConfig",
    "StrategyRegistry",
    "registry",
    "register_strategy",
    "execute_strategy",
    "get_strategy_metrics",
    "get_available_strategies",
]
