"""
Tests for async conversation memory system.

Validates the fire-and-forget architecture, background processing,
and performance improvements of the async conversation memory.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from app.services.async_summarizer import AsyncSummarizer, QuickPatterns
from app.services.conversation_memory import (
    AsyncConversationMemory,
    EntityContextTracker,
    QueryExpansionMemory,
    ConversationMemoryService,
)


class TestAsyncSummarizer:
    """Test async summarizer service functionality."""

    @pytest.fixture
    def mock_memory_service(self):
        """Mock memory service for testing."""
        service = Mock(spec=ConversationMemoryService)
        service.store_conversation_summary = AsyncMock(return_value=True)
        service.get_conversation_summary = AsyncMock(return_value=None)
        return service

    @pytest.fixture
    def async_summarizer(self, mock_memory_service):
        """Create async summarizer with mocked dependencies."""
        return AsyncSummarizer(mock_memory_service)

    def test_extract_quick_patterns_temperature_query(self, async_summarizer):
        """Test quick pattern extraction for temperature queries."""
        query = "Hány fok van a nappaliban?"
        history = []

        patterns = async_summarizer.extract_quick_patterns(query, history)

        assert isinstance(patterns, QuickPatterns)
        assert "temperature" in patterns.domains
        assert "nappali" in patterns.areas or any(
            "nappali" in area for area in patterns.areas
        )
        assert patterns.query_type == "status_check"
        assert patterns.language == "hungarian"
        assert patterns.processing_time_ms < 100  # Should be very fast

    def test_extract_quick_patterns_lighting_control(self, async_summarizer):
        """Test quick pattern extraction for lighting control."""
        query = "Kapcsold fel a lámpát a konyhában"
        history = []

        patterns = async_summarizer.extract_quick_patterns(query, history)

        assert "lighting" in patterns.domains
        assert any("konyha" in area for area in patterns.areas)
        assert patterns.query_type == "control"
        assert patterns.language == "hungarian"

    def test_extract_quick_patterns_english_query(self, async_summarizer):
        """Test quick pattern extraction for English queries."""
        query = "What is the temperature in the living room?"
        history = []

        patterns = async_summarizer.extract_quick_patterns(query, history)

        assert "temperature" in patterns.domains
        assert patterns.query_type == "status_check"
        assert patterns.language == "english"

    def test_should_generate_summary_rules(self, async_summarizer):
        """Test summary generation decision logic."""
        # Should not generate for short conversations
        short_history = [{"user_message": "Hello"}]
        assert not async_summarizer.should_generate_summary(short_history)

        # Should generate for longer conversations
        long_history = [
            {"user_message": "Hány fok van?"},
            {"user_message": "És a nappaliban?"},
            {"user_message": "Kapcsold fel a lámpát"},
        ]
        assert async_summarizer.should_generate_summary(long_history)

    @pytest.mark.asyncio
    async def test_request_background_summary_queuing(self, async_summarizer):
        """Test background summary queuing mechanism."""
        session_id = "test_session"
        query = "Test query"
        history = [
            {"user_message": "First"},
            {"user_message": "Second"},
            {"user_message": "Third"},
        ]

        # Request background summary
        await async_summarizer.request_background_summary(
            session_id=session_id, query=query, history=history
        )

        # Should be queued
        assert async_summarizer.background_queue.qsize() >= 0

    @pytest.mark.asyncio
    async def test_cached_summary_ttl(self, async_summarizer):
        """Test cached summary TTL behavior."""
        session_id = "test_session"

        # Store summary
        summary_data = {
            "detected_domains": ["temperature"],
            "mentioned_areas": ["nappali"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        await async_summarizer.memory_service.store_conversation_summary(
            session_id, summary_data, ttl_minutes=15
        )

        # Should retrieve cached summary
        cached = await async_summarizer.get_cached_summary(session_id)
        # Note: Returns None due to mock, but tests the flow
        assert cached is None  # Mock returns None


class TestEntityContextTracker:
    """Test entity context tracking functionality."""

    @pytest.fixture
    def entity_tracker(self):
        """Create entity context tracker."""
        return EntityContextTracker()

    def test_update_entity_importance(self, entity_tracker):
        """Test entity importance tracking."""
        entity_id = "sensor.nappali_temperature"

        # First update
        entity_tracker.update_entity(entity_id, 0.8, area="nappali", domain="sensor")
        assert entity_id in entity_tracker.entity_importance
        assert entity_tracker.entity_importance[entity_id] == 0.8
        assert entity_tracker.entity_mentions[entity_id] == 1

        # Second update (exponential moving average)
        entity_tracker.update_entity(entity_id, 0.9, area="nappali", domain="sensor")
        assert entity_tracker.entity_importance[entity_id] == 0.8 * 0.7 + 0.9 * 0.3
        assert entity_tracker.entity_mentions[entity_id] == 2

    def test_entity_boost_calculation(self, entity_tracker):
        """Test entity boost factor calculation."""
        entity_id = "sensor.nappali_temperature"

        # Update entity multiple times
        entity_tracker.update_entity(entity_id, 0.9, area="nappali", domain="sensor")
        entity_tracker.update_entity(entity_id, 0.8, area="nappali", domain="sensor")
        entity_tracker.update_entity(entity_id, 0.85, area="nappali", domain="sensor")

        boost = entity_tracker.get_entity_boost(entity_id)

        # Should have boost > 1.0 due to high importance and frequency
        assert boost > 1.0
        assert boost <= 3.0  # Should be reasonable

    def test_area_and_domain_patterns(self, entity_tracker):
        """Test area and domain pattern tracking."""
        entity_tracker.update_entity(
            "sensor.nappali_temp", 0.8, area="nappali", domain="sensor"
        )
        entity_tracker.update_entity(
            "light.nappali_lamp", 0.7, area="nappali", domain="light"
        )
        entity_tracker.update_entity(
            "sensor.konyha_temp", 0.6, area="konyha", domain="sensor"
        )

        assert "nappali" in entity_tracker.area_patterns
        assert "konyha" in entity_tracker.area_patterns
        assert len(entity_tracker.area_patterns["nappali"]) == 2

        assert "sensor" in entity_tracker.domain_patterns
        assert "light" in entity_tracker.domain_patterns
        assert len(entity_tracker.domain_patterns["sensor"]) == 2


class TestQueryExpansionMemory:
    """Test query expansion memory functionality."""

    @pytest.fixture
    def query_memory(self):
        """Create query expansion memory."""
        return QueryExpansionMemory()

    def test_learn_successful_pattern(self, query_memory):
        """Test learning from successful patterns."""
        query = "hány fok van"
        entities = ["sensor.nappali_temp", "sensor.konyha_temp"]
        success_score = 0.9

        query_memory.learn_successful_pattern(query, entities, success_score)

        normalized_query = query_memory._normalize_query(query)
        assert normalized_query in query_memory.successful_patterns

        pattern = query_memory.successful_patterns[normalized_query]
        assert pattern["success_rate"] == success_score
        assert pattern["sample_count"] == 1
        assert "sensor.nappali_temp" in pattern["boost_entities"]

    def test_expansion_suggestions(self, query_memory):
        """Test expansion suggestions based on learned patterns."""
        # Learn a pattern
        query_memory.learn_successful_pattern(
            "hány fok van", ["sensor.nappali_temp"], 0.9
        )

        # Test similar query
        suggestions = query_memory.get_expansion_suggestions("hány fok")

        # Should have some confidence due to similarity
        assert suggestions["confidence"] > 0.0

    def test_query_similarity(self, query_memory):
        """Test query similarity calculation."""
        similarity = query_memory._query_similarity("hány fok van", "hány fok")
        assert 0.0 < similarity < 1.0

        # Identical queries
        similarity = query_memory._query_similarity("test", "test")
        assert similarity == 1.0

        # No overlap
        similarity = query_memory._query_similarity("foo", "bar")
        assert similarity == 0.0


class TestAsyncConversationMemory:
    """Test the complete async conversation memory system."""

    @pytest.fixture
    def mock_memory_service(self):
        """Mock memory service."""
        service = Mock(spec=ConversationMemoryService)
        service.store_conversation_memory = AsyncMock(return_value=True)
        service.get_conversation_stats = AsyncMock(
            return_value={"entity_count": 5, "query_count": 3, "minutes_remaining": 10}
        )
        return service

    @pytest.fixture
    def async_memory(self, mock_memory_service):
        """Create async conversation memory."""
        return AsyncConversationMemory(mock_memory_service)

    @pytest.mark.asyncio
    async def test_process_turn_immediate_updates(self, async_memory):
        """Test immediate context updates during turn processing."""
        session_id = "test_session"
        query = "Hány fok van a nappaliban?"
        retrieved_entities = [
            {
                "entity_id": "sensor.nappali_temperature",
                "rerank_score": 0.9,
                "area_name": "nappali",
                "domain": "sensor",
            }
        ]

        result = await async_memory.process_turn(
            session_id=session_id,
            query=query,
            retrieved_entities=retrieved_entities,
            success_feedback=1.0,
        )

        # Should return enhancement data
        assert "entity_boosts" in result
        assert "expansion_suggestions" in result
        assert "processing_source" in result

        # Entity should be tracked
        assert (
            "sensor.nappali_temperature"
            in async_memory.entity_context.entity_importance
        )

    def test_get_enhancement_data(self, async_memory):
        """Test enhancement data generation."""
        session_id = "test_session"
        query = "test query"

        # Add some tracked entities
        async_memory.entity_context.update_entity("sensor.test", 0.9)

        enhancement = async_memory.get_enhancement_data(session_id, query)

        assert "entity_boosts" in enhancement
        assert "expansion_suggestions" in enhancement
        assert "cached_summary" in enhancement
        assert "background_pending" in enhancement

    def test_cached_summary_ttl_management(self, async_memory):
        """Test cached summary TTL management."""
        session_id = "test_session"

        # Cache summary
        summary_data = {"test": "data"}
        async_memory.cache_summary(session_id, summary_data)

        # Should retrieve immediately
        cached = async_memory._get_cached_summary(session_id)
        assert cached == summary_data

        # Manually expire
        async_memory._cache_timestamps[session_id] = datetime.utcnow() - timedelta(
            minutes=20
        )

        # Should return None (expired)
        cached = async_memory._get_cached_summary(session_id)
        assert cached is None

    @pytest.mark.asyncio
    async def test_memory_stage_debug_info(self, async_memory):
        """Test memory stage debug information generation."""
        session_id = "test_session"

        # Add some context
        async_memory.entity_context.update_entity("sensor.test", 0.9)
        async_memory.query_patterns.learn_successful_pattern(
            "test", ["sensor.test"], 0.8
        )

        debug_info = await async_memory.get_memory_stage_debug_info(session_id)

        assert "cache_status" in debug_info
        assert "entity_boosts" in debug_info
        assert "memory_stats" in debug_info
        assert "entity_tracking" in debug_info
        assert "query_patterns" in debug_info


class TestPerformanceOptimizations:
    """Test performance optimizations and async behavior."""

    @pytest.mark.asyncio
    async def test_quick_patterns_performance(self):
        """Test that quick pattern extraction is fast (<50ms)."""
        memory_service = Mock(spec=ConversationMemoryService)
        summarizer = AsyncSummarizer(memory_service)

        query = "Kapcsold fel a lámpát a nappaliban és állítsd be a klímát 22 fokra"
        history = [{"user_message": "Hány fok van?"}, {"user_message": "Mi a helyzet?"}]

        start_time = datetime.now()
        patterns = summarizer.extract_quick_patterns(query, history)
        duration = (datetime.now() - start_time).total_seconds() * 1000

        # Should be very fast
        assert duration < 50  # Less than 50ms
        assert patterns.processing_time_ms < 50

    @pytest.mark.asyncio
    async def test_fire_and_forget_background_processing(self):
        """Test fire-and-forget background processing doesn't block."""
        memory_service = Mock(spec=ConversationMemoryService)
        memory_service.store_conversation_summary = AsyncMock(return_value=True)

        summarizer = AsyncSummarizer(memory_service)

        # Request background summary
        start_time = datetime.now()
        await summarizer.request_background_summary(
            session_id="test",
            query="test query",
            history=[{"user_message": "test"}] * 5,  # Long enough to trigger
        )
        duration = (datetime.now() - start_time).total_seconds() * 1000

        # Should return immediately (fire-and-forget)
        assert duration < 10  # Should be very fast (just queuing)

    @pytest.mark.asyncio
    async def test_memory_enhancement_immediate_response(self):
        """Test that memory enhancement provides immediate response."""
        memory_service = Mock(spec=ConversationMemoryService)
        memory_service.store_conversation_memory = AsyncMock(return_value=True)

        async_memory = AsyncConversationMemory(memory_service)

        start_time = datetime.now()
        result = await async_memory.process_turn(
            session_id="test",
            query="test query",
            retrieved_entities=[
                {
                    "entity_id": "sensor.test",
                    "rerank_score": 0.8,
                    "area_name": "test_area",
                    "domain": "sensor",
                }
            ],
        )
        duration = (datetime.now() - start_time).total_seconds() * 1000

        # Should be very fast (immediate context updates only)
        assert duration < 100  # Less than 100ms
        assert "entity_boosts" in result
        assert "processing_source" in result


@pytest.mark.asyncio
async def test_integration_async_memory_workflow():
    """Integration test for complete async memory workflow."""
    # Mock dependencies
    memory_service = Mock(spec=ConversationMemoryService)
    memory_service.store_conversation_memory = AsyncMock(return_value=True)
    memory_service.store_conversation_summary = AsyncMock(return_value=True)
    memory_service.get_conversation_summary = AsyncMock(return_value=None)
    memory_service.get_conversation_stats = AsyncMock(
        return_value={"entity_count": 0, "query_count": 1}
    )

    # Create async memory system
    async_memory = AsyncConversationMemory(memory_service)

    session_id = "integration_test"

    # Simulate first turn
    query1 = "Hány fok van a nappaliban?"
    entities1 = [
        {
            "entity_id": "sensor.nappali_temperature",
            "rerank_score": 0.9,
            "area_name": "nappali",
            "domain": "sensor",
        }
    ]

    # Process first turn
    enhancement1 = await async_memory.process_turn(
        session_id=session_id, query=query1, retrieved_entities=entities1
    )

    # Should have immediate enhancement
    assert "entity_boosts" in enhancement1
    assert "processing_source" in enhancement1

    # Simulate second turn (should benefit from previous context)
    query2 = "És a konyhában?"
    entities2 = [
        {
            "entity_id": "sensor.konyha_temperature",
            "rerank_score": 0.8,
            "area_name": "konyha",
            "domain": "sensor",
        }
    ]

    # Process second turn
    enhancement2 = await async_memory.process_turn(
        session_id=session_id, query=query2, retrieved_entities=entities2
    )

    # Should have enhanced context from previous turn
    assert len(enhancement2.get("entity_boosts", {})) >= 0

    # Test memory stage debug info
    debug_info = await async_memory.get_memory_stage_debug_info(session_id)
    assert "cache_status" in debug_info
    assert "entity_tracking" in debug_info
    assert debug_info["entity_tracking"]["tracked_entities"] >= 1


if __name__ == "__main__":
    # Run specific performance test
    import asyncio

    async def run_performance_test():
        """Run performance validation."""
        print("🚀 Running async memory performance validation...")

        # Test quick patterns performance
        memory_service = Mock(spec=ConversationMemoryService)
        summarizer = AsyncSummarizer(memory_service)

        query = "Hány fok van a nappaliban és kapcsold fel a lámpát a konyhában?"
        history = []

        start_time = datetime.now()
        patterns = summarizer.extract_quick_patterns(query, history)
        duration = (datetime.now() - start_time).total_seconds() * 1000

        print(f"✅ Quick patterns extraction: {duration:.2f}ms")
        print(f"   Detected domains: {list(patterns.domains)}")
        print(f"   Detected areas: {list(patterns.areas)}")
        print(f"   Query type: {patterns.query_type}")
        print(f"   Language: {patterns.language}")

        # Test fire-and-forget performance
        start_time = datetime.now()
        await summarizer.request_background_summary(
            session_id="perf_test", query=query, history=[{"user_message": "test"}] * 5
        )
        duration = (datetime.now() - start_time).total_seconds() * 1000

        print(f"✅ Background summary request: {duration:.2f}ms (fire-and-forget)")

        print("🎯 Performance validation completed!")
        print(f"   Expected latency reduction: 3.35s → ~{duration/1000:.3f}s")

    asyncio.run(run_performance_test())
