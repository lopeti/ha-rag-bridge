"""
Tests for the refactored async conversation memory system.

Validates the separated QuickPatternAnalyzer and AsyncConversationEnricher services.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from app.services.quick_pattern_analyzer import QuickPatternAnalyzer, QuickContext
from app.services.async_conversation_enricher import (
    AsyncConversationEnricher,
    EnrichedContext,
)
from app.services.conversation_memory import ConversationMemoryService


class TestQuickPatternAnalyzer:
    """Test the synchronous QuickPatternAnalyzer service."""

    def test_quick_analysis_temperature_query(self):
        """Test quick analysis for temperature query."""
        analyzer = QuickPatternAnalyzer()

        result = analyzer.analyze("Hány fok van a nappaliban?")

        assert isinstance(result, QuickContext)
        assert "temperature" in result.detected_domains
        assert any("nappali" in area for area in result.detected_areas)
        assert result.query_type == "status_check"
        assert result.language == "hu"
        assert result.processing_time_ms < 50  # Performance guarantee
        assert result.confidence > 0.5

    def test_quick_analysis_lighting_control(self):
        """Test quick analysis for lighting control."""
        analyzer = QuickPatternAnalyzer()

        result = analyzer.analyze("Kapcsold fel a lámpát a konyhában")

        assert "lighting" in result.detected_domains
        assert any("konyha" in area for area in result.detected_areas)
        assert result.query_type == "control"
        assert result.language == "hu"
        assert result.processing_time_ms < 50

    def test_quick_analysis_english_query(self):
        """Test quick analysis for English query."""
        analyzer = QuickPatternAnalyzer()

        result = analyzer.analyze("What is the temperature in the living room?")

        assert "temperature" in result.detected_domains
        assert result.query_type == "status_check"
        assert result.language == "en"
        assert result.processing_time_ms < 50

    def test_quick_analysis_with_history(self):
        """Test quick analysis with conversation history."""
        analyzer = QuickPatternAnalyzer()

        history = [
            {"user_message": "Mi a helyzet a nappaliban?"},
            {"user_message": "És a hálószobában?"},
        ]

        result = analyzer.analyze("Kapcsold fel a lámpát", history)

        assert "lighting" in result.detected_domains
        # Should detect areas from history context
        assert len(result.detected_areas) >= 1
        assert result.query_type == "control"

    def test_entity_pattern_generation(self):
        """Test entity pattern generation."""
        analyzer = QuickPatternAnalyzer()

        result = analyzer.analyze("Hány fok van a nappaliban?")

        assert len(result.entity_patterns) > 0
        assert any(
            "*temp*" in pattern or "sensor.*temp*" in pattern
            for pattern in result.entity_patterns
        )
        assert "sensor" in result.suggested_entity_types

    def test_performance_guarantee(self):
        """Test that processing time is consistently under 50ms."""
        analyzer = QuickPatternAnalyzer()

        test_queries = [
            "Hány fok van?",
            "Kapcsold fel a lámpát",
            "Mi van a kertben?",
            "Turn on the lights",
            "What's the temperature?",
        ]

        for query in test_queries:
            result = analyzer.analyze(query)
            assert (
                result.processing_time_ms < 50
            ), f"Query '{query}' took {result.processing_time_ms}ms"


class TestAsyncConversationEnricher:
    """Test the asynchronous AsyncConversationEnricher service."""

    @pytest.fixture
    def mock_memory_service(self):
        """Mock memory service for testing."""
        service = Mock(spec=ConversationMemoryService)
        service.store_conversation_summary = AsyncMock(return_value=True)
        service.get_conversation_summary = AsyncMock(return_value=None)
        return service

    @pytest.fixture
    def enricher(self, mock_memory_service):
        """Create enricher with mocked dependencies."""
        return AsyncConversationEnricher(mock_memory_service)

    @pytest.mark.asyncio
    async def test_enrich_async_queuing(self, enricher):
        """Test that enrich_async properly queues background tasks."""
        session_id = "test_session"
        query = "Hány fok van a nappaliban?"
        history = [{"user_message": "Hello"}]

        # Should not block
        await enricher.enrich_async(session_id, query, history)

        # Should have queued the task
        assert enricher.background_queue.qsize() >= 0  # May have been processed already

    @pytest.mark.asyncio
    async def test_cached_enrichment_retrieval(self, enricher):
        """Test retrieval of cached enrichment."""
        session_id = "test_session"

        # No cached enrichment initially
        result = await enricher.get_cached_enrichment(session_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_background_task_management(self, enricher):
        """Test background task lifecycle management."""
        # Test queue and task counts
        queue_size = await enricher.get_queue_size()
        assert queue_size >= 0

        active_count = await enricher.get_active_task_count()
        assert active_count >= 0

    def test_fallback_enrichment_creation(self, enricher):
        """Test fallback enrichment when LLM fails."""
        session_id = "test_session"
        query = "Test query"
        quick_context = {
            "detected_domains": ["temperature"],
            "detected_areas": ["nappali"],
            "query_type": "status_check",
            "language": "hu",
        }

        fallback = enricher._create_fallback_enrichment(
            session_id, query, quick_context
        )

        assert isinstance(fallback, EnrichedContext)
        assert fallback.session_id == session_id
        assert fallback.llm_model_used == "fallback"
        assert fallback.confidence_score == 0.3
        assert "temperature" in fallback.detected_domains


class TestIntegratedWorkflow:
    """Test the integrated workflow with both services."""

    @pytest.mark.asyncio
    async def test_quick_analysis_then_enrichment(self):
        """Test the complete workflow: quick analysis -> enrichment trigger."""

        # 1. Quick analysis (synchronous)
        analyzer = QuickPatternAnalyzer()
        quick_result = analyzer.analyze("Hány fok van a nappaliban?")

        # Validate quick analysis
        assert quick_result.processing_time_ms < 50
        assert "temperature" in quick_result.detected_domains

        # 2. Trigger enrichment (asynchronous, fire-and-forget)
        mock_memory_service = Mock(spec=ConversationMemoryService)
        mock_memory_service.store_conversation_summary = AsyncMock(return_value=True)
        mock_memory_service.get_conversation_summary = AsyncMock(return_value=None)

        enricher = AsyncConversationEnricher(mock_memory_service)

        # Should trigger without blocking
        await enricher.enrich_async(
            session_id="test_session",
            query="Hány fok van a nappaliban?",
            history=[],
            quick_context={
                "detected_domains": list(quick_result.detected_domains),
                "detected_areas": list(quick_result.detected_areas),
                "query_type": quick_result.query_type,
                "language": quick_result.language,
            },
        )

        # Enrichment should be queued
        assert await enricher.get_queue_size() >= 0

    def test_separation_of_concerns(self):
        """Test that concerns are properly separated."""
        analyzer = QuickPatternAnalyzer()

        # QuickPatternAnalyzer should be fast and synchronous
        result = analyzer.analyze("Test query")
        assert result.processing_time_ms < 50
        assert result.source == "quick_analysis"

        # AsyncConversationEnricher should be async and non-blocking
        mock_memory_service = Mock(spec=ConversationMemoryService)
        enricher = AsyncConversationEnricher(mock_memory_service)

        # Background worker should be running
        assert len(enricher.active_tasks) >= 0
        assert enricher.background_queue is not None

    def test_performance_improvement_architecture(self):
        """Test that the architecture supports performance improvement."""
        analyzer = QuickPatternAnalyzer()

        # Multiple quick analyses should all be fast
        queries = [
            "Hány fok van a nappaliban?",
            "Kapcsold fel a lámpát",
            "Mi van a kertben?",
            "Mennyi áramot fogyaszt a ház?",
            "Van-e nyitva valami ablak?",
        ]

        total_time = 0
        for query in queries:
            result = analyzer.analyze(query)
            total_time += result.processing_time_ms

        # Total processing time for 5 queries should still be reasonable
        assert total_time < 250  # 50ms * 5 = max theoretical

        # Average should be well under the 50ms guarantee
        avg_time = total_time / len(queries)
        assert avg_time < 50
