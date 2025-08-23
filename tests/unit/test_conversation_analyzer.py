"""
Unit tests for conversation analyzer service.
Tests Hungarian area detection, domain extraction, and conversation context analysis.
"""

from app.services.conversation_analyzer import (
    ConversationAnalyzer,
    conversation_analyzer,
)
from app.schemas import ChatMessage


class TestConversationAnalyzer:
    """Test cases for ConversationAnalyzer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = ConversationAnalyzer()

    def test_area_detection_hungarian(self):
        """Test Hungarian area detection patterns."""
        test_cases = [
            ("Mekkora a nedveség a kertben?", {"kert"}),
            ("Mi a hőmérséklet a nappaliban?", {"nappali"}),
            ("Kapcsold fel a világítást a konyhában", {"konyha"}),
            ("Milyen a levegő a hálószobában?", {"hálószoba"}),
            ("Van mozgás a fürdőszobában?", {"fürdőszoba"}),
            ("Nyisd ki az ablakot a dolgozószobában", {"dolgozószoba"}),
            ("Mi van az előszobában?", {"előszoba"}),
            ("Meleg van a pincében?", {"pince"}),
            ("Kapcsold le a fényt a padláson", {"padlás"}),
            ("Milyen idő van a teraszon?", {"terasz"}),
            ("Zárd be a garázs ajtót", {"garázs"}),
            ("Mi újság otthon?", {"ház"}),
        ]

        for query, expected_areas in test_cases:
            context = self.analyzer.analyze_conversation(query)
            assert context.areas_mentioned == expected_areas, f"Query: {query}"

    def test_domain_device_class_detection(self):
        """Test domain and device class detection."""
        test_cases = [
            ("Mekkora a nedveség?", {"sensor"}, {"humidity"}),
            ("Mi a hőmérséklet?", {"sensor"}, {"temperature"}),
            ("Kapcsold fel a világítást", {"light"}, set()),
            ("Kapcsold be a kapcsolót", {"switch"}, set()),
            ("Állítsd be a klímát", {"climate"}, set()),
            ("Van mozgás?", {"sensor"}, {"motion"}),
            ("Nyisd ki az ablakot", {"sensor"}, {"window"}),
            ("Mi az energia fogyasztás?", {"sensor"}, {"energy"}),
        ]

        for query, expected_domains, expected_classes in test_cases:
            context = self.analyzer.analyze_conversation(query)
            assert context.domains_mentioned == expected_domains, f"Query: {query}"
            assert (
                context.device_classes_mentioned == expected_classes
            ), f"Query: {query}"

    def test_intent_detection(self):
        """Test intent detection (control vs read)."""
        control_queries = [
            "Kapcsold fel a világítást",
            "Indítsd el a mosógépet",
            "Állítsd be a hőmérsékletet",
            "Turn on the lights",
            "Nyisd ki az ablakot",
            "Zárd be az ajtót",
        ]

        read_queries = [
            "Mekkora a nedveség?",
            "Mi a hőmérséklet?",
            "Hány fok van?",
            "What's the temperature?",
            "Milyen az állapot?",
            "Van mozgás?",
        ]

        for query in control_queries:
            context = self.analyzer.analyze_conversation(query)
            assert context.intent == "control", f"Query: {query}"

        for query in read_queries:
            context = self.analyzer.analyze_conversation(query)
            assert context.intent == "read", f"Query: {query}"

    def test_follow_up_detection(self):
        """Test follow-up question detection."""
        follow_up_queries = [
            "És a házban?",
            "Mi a helyzet ott?",
            "What about there?",
            "És itt?",
            "Akkor mi van?",
        ]

        regular_queries = [
            "Mekkora a nedveség a kertben?",
            "Mi a hőmérséklet?",
            "Kapcsold fel a világítást",
        ]

        for query in follow_up_queries:
            context = self.analyzer.analyze_conversation(query)
            assert context.is_follow_up is True, f"Query: {query}"

        for query in regular_queries:
            context = self.analyzer.analyze_conversation(query)
            assert context.is_follow_up is False, f"Query: {query}"

    def test_conversation_history_context(self):
        """Test conversation history context extraction."""
        history = [
            ChatMessage(role="user", content="Mekkora a nedveség a kertben?"),
            ChatMessage(
                role="system",
                content="Relevant entities: sensor.kert_aqara_szenzor_humidity\\nRelevant domains: sensor",
            ),
            ChatMessage(role="user", content="És a házban?"),
        ]

        context = self.analyzer.analyze_conversation("És a házban?", history)

        # Should inherit area from previous context
        assert context.is_follow_up is True
        assert "kert" in context.areas_mentioned  # Should inherit from history

    def test_previous_entities_extraction(self):
        """Test extraction of previously mentioned entities."""
        history = [
            ChatMessage(
                role="system",
                content="Relevant entities: sensor.kert_humidity,sensor.nappali_temp\\nRelevant domains: sensor",
            ),
            ChatMessage(role="user", content="És mi van a konyhában?"),
        ]

        context = self.analyzer.analyze_conversation("És mi van a konyhában?", history)

        # Should extract entity IDs from system messages
        assert "sensor.kert_humidity" in context.previous_entities
        assert "sensor.nappali_temp" in context.previous_entities

    def test_area_boost_factors(self):
        """Test area boost factor calculation."""
        context = self.analyzer.analyze_conversation("Mekkora a nedveség a kertben?")
        boost_factors = self.analyzer.get_area_boost_factors(context)

        assert "kert" in boost_factors
        assert boost_factors["kert"] == 2.0  # Specific area boost

        # Test generic house reference
        context_house = self.analyzer.analyze_conversation("Mi újság otthon?")
        boost_factors_house = self.analyzer.get_area_boost_factors(context_house)

        assert "ház" in boost_factors_house
        assert boost_factors_house["ház"] == 1.2  # Generic house boost

    def test_domain_boost_factors(self):
        """Test domain and device class boost factors."""
        context = self.analyzer.analyze_conversation("Mekkora a nedveség a kertben?")
        boost_factors = self.analyzer.get_domain_boost_factors(context)

        assert "domain:sensor" in boost_factors
        assert boost_factors["domain:sensor"] == 1.5

        assert "device_class:humidity" in boost_factors
        assert boost_factors["device_class:humidity"] == 2.0

    def test_complex_query_analysis(self):
        """Test analysis of complex queries with multiple context elements."""
        query = "Kapcsold fel a világítást a nappali és a konyha között"
        context = self.analyzer.analyze_conversation(query)

        # Should detect multiple areas
        assert "nappali" in context.areas_mentioned
        assert "konyha" in context.areas_mentioned

        # Should detect light domain
        assert "light" in context.domains_mentioned

        # Should detect control intent
        assert context.intent == "control"

    def test_multilingual_support(self):
        """Test English language support alongside Hungarian."""
        test_cases = [
            (
                "What's the temperature in the kitchen?",
                {"konyha"},
                {"sensor"},
                {"temperature"},
            ),
            ("Turn on the lights in the living room", {"nappali"}, {"light"}, set()),
            ("Is there motion in the bedroom?", {"hálószoba"}, {"sensor"}, {"motion"}),
        ]

        for query, expected_areas, expected_domains, expected_classes in test_cases:
            context = self.analyzer.analyze_conversation(query)
            assert context.areas_mentioned == expected_areas, f"Query: {query}"
            assert context.domains_mentioned == expected_domains, f"Query: {query}"
            assert (
                context.device_classes_mentioned == expected_classes
            ), f"Query: {query}"


class TestConversationAnalyzerIntegration:
    """Integration tests for the global conversation analyzer instance."""

    def test_global_instance(self):
        """Test that the global conversation_analyzer instance works correctly."""
        context = conversation_analyzer.analyze_conversation(
            "Mekkora a nedveség a kertben?"
        )

        assert "kert" in context.areas_mentioned
        assert "sensor" in context.domains_mentioned
        assert "humidity" in context.device_classes_mentioned
        assert context.intent == "read"
        assert context.is_follow_up is False

    def test_pattern_compilation(self):
        """Test that regex patterns are compiled correctly."""
        # Test that compiled patterns exist
        assert hasattr(conversation_analyzer, "control_re")
        assert hasattr(conversation_analyzer, "read_re")
        assert hasattr(conversation_analyzer, "follow_up_re")

        # Test pattern matching
        assert conversation_analyzer.control_re.search("kapcsold fel")
        assert conversation_analyzer.read_re.search("mennyi")
        assert conversation_analyzer.follow_up_re.search("és a")


# Performance tests
class TestConversationAnalyzerPerformance:
    """Performance tests to ensure analyzer meets Sprint 1 requirements."""

    def test_analysis_performance(self):
        """Test that conversation analysis completes within acceptable time."""
        import time

        query = "Mekkora a nedveség a kertben és mi a hőmérséklet a nappaliban?"

        start_time = time.time()
        context = conversation_analyzer.analyze_conversation(query)
        end_time = time.time()

        analysis_time = end_time - start_time

        # Should complete analysis in under 10ms for Sprint 1 performance target
        assert (
            analysis_time < 0.01
        ), f"Analysis took {analysis_time:.4f}s, expected < 0.01s"

        # Verify correct analysis
        assert "kert" in context.areas_mentioned
        assert "nappali" in context.areas_mentioned
        assert "sensor" in context.domains_mentioned

    def test_large_conversation_history(self):
        """Test performance with large conversation history."""
        import time

        # Create large conversation history
        history = []
        for i in range(50):  # 50 message pairs
            history.append(
                ChatMessage(role="user", content=f"Query {i} about sensor data")
            )
            history.append(
                ChatMessage(
                    role="system",
                    content=f"Relevant entities: sensor.test_{i}\\nRelevant domains: sensor",
                )
            )

        start_time = time.time()
        context = conversation_analyzer.analyze_conversation("És a kertben?", history)
        end_time = time.time()

        analysis_time = end_time - start_time

        # Should handle large history efficiently
        assert analysis_time < 0.05, f"Large history analysis took {analysis_time:.4f}s"
        assert context.is_follow_up is True
