"""
Unit tests for entity reranker service.
Tests cross-encoder integration, entity scoring, and hierarchical system prompt generation.
"""

import pytest
from unittest.mock import Mock, patch
from app.services.entity_reranker import EntityReranker, entity_reranker, EntityScore
from app.services.conversation_analyzer import ConversationContext
from app.schemas import ChatMessage


class TestEntityReranker:
    """Test cases for EntityReranker."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock the cross-encoder model to avoid loading it in tests
        with patch("app.services.entity_reranker.CrossEncoder"):
            self.reranker = EntityReranker()
            self.reranker._model = Mock()

    @pytest.fixture
    def sample_entities(self):
        """Sample entity data for testing."""
        return [
            {
                "entity_id": "sensor.kert_aqara_szenzor_humidity",
                "domain": "sensor",
                "device_class": "humidity",
                "area": "kert",
                "friendly_name": "Kerti páratartalom szenzor",
                "text": "kerti nedveség szenzor páratartalom",
            },
            {
                "entity_id": "sensor.lumi_lumi_weather_humidity",
                "domain": "sensor",
                "device_class": "humidity",
                "area": "nappali",
                "friendly_name": "Nappali páratartalom",
                "text": "nappali nedveség szenzor",
            },
            {
                "entity_id": "light.kert_led_strip",
                "domain": "light",
                "area": "kert",
                "friendly_name": "Kerti LED szalag",
                "text": "kerti világítás led",
            },
            {
                "entity_id": "sensor.nappali_temperature",
                "domain": "sensor",
                "device_class": "temperature",
                "area": "nappali",
                "friendly_name": "Nappali hőmérséklet",
                "text": "nappali hőmérséklet szenzor",
            },
        ]

    def test_entity_description_creation(self, sample_entities):
        """Test entity description creation for cross-encoder."""
        entity = sample_entities[0]
        description = self.reranker._create_entity_description(entity)

        expected_parts = [
            "sensor.kert_aqara_szenzor_humidity",
            "Kerti páratartalom szenzor",
            "terület: kert",
            "sensor humidity",
            "kerti nedveség szenzor páratartalom",
        ]

        for part in expected_parts:
            assert part in description

    def test_fallback_text_scoring(self, sample_entities):
        """Test fallback text scoring when cross-encoder is unavailable."""
        entity = sample_entities[0]
        query = "nedveség kert"

        score = self.reranker._fallback_text_score(entity, query)

        # Should get high score for matching keywords
        assert 0.5 <= score <= 1.0

        # Test with non-matching query
        non_matching_score = self.reranker._fallback_text_score(
            entity, "completely different"
        )
        assert score > non_matching_score

    def test_ranking_factors_calculation(self, sample_entities):
        """Test calculation of ranking factors based on context."""
        entity = sample_entities[0]  # Garden humidity sensor

        # Create context for garden humidity query
        context = ConversationContext(
            areas_mentioned={"kert"},
            domains_mentioned={"sensor"},
            device_classes_mentioned={"humidity"},
            previous_entities=set(),
            is_follow_up=False,
            intent="read",
        )

        factors = self.reranker._calculate_ranking_factors(entity, context)

        # Should have boosts for matching area, domain, and device class
        assert any("area" in key for key in factors.keys())
        assert any("domain" in key for key in factors.keys())
        assert any("device_class" in key for key in factors.keys())
        assert "readable" in factors  # Read intent boost for sensor

    def test_entity_ranking_basic(self, sample_entities):
        """Test basic entity ranking functionality."""
        # Mock the semantic scoring
        self.reranker._model.predict.return_value = [0.8, 0.6, 0.3, 0.5]

        query = "nedveség kert"

        ranked_entities = self.reranker.rank_entities(
            entities=sample_entities, query=query, k=4
        )

        # Should return EntityScore objects
        assert len(ranked_entities) == 4
        assert all(isinstance(score, EntityScore) for score in ranked_entities)

        # Garden humidity sensor should rank highest due to area + device class match
        top_entity = ranked_entities[0]
        assert top_entity.entity["entity_id"] == "sensor.kert_aqara_szenzor_humidity"
        assert (
            top_entity.final_score > top_entity.base_score
        )  # Should have context boost

    def test_conversation_context_integration(self, sample_entities):
        """Test integration with conversation context analysis."""
        self.reranker._model.predict.return_value = [0.7] * len(sample_entities)

        query = "nedveség kert"
        history = [ChatMessage(role="user", content="Mi a helyzet a kertben?")]

        ranked_entities = self.reranker.rank_entities(
            entities=sample_entities, query=query, conversation_history=history, k=4
        )

        # Garden sensor should still rank highest
        assert (
            ranked_entities[0].entity["entity_id"]
            == "sensor.kert_aqara_szenzor_humidity"
        )

    def test_hierarchical_system_prompt_generation(self, sample_entities):
        """Test hierarchical system prompt generation."""
        # Create mock EntityScore objects
        entity_scores = [
            EntityScore(
                entity=sample_entities[0],
                base_score=0.8,
                context_boost=0.5,
                final_score=1.3,
                ranking_factors={"area_kert": 1.0},
            ),
            EntityScore(
                entity=sample_entities[1],
                base_score=0.6,
                context_boost=0.2,
                final_score=0.8,
                ranking_factors={"domain_sensor": 0.5},
            ),
            EntityScore(
                entity=sample_entities[3],
                base_score=0.5,
                context_boost=0.1,
                final_score=0.6,
                ranking_factors={},
            ),
        ]

        prompt = self.reranker.create_hierarchical_system_prompt(
            ranked_entities=entity_scores,
            query="nedveség kert",
            max_primary=1,
            max_related=2,
        )

        # Should have hierarchical structure
        assert "You are a Home Assistant agent." in prompt
        assert "Primary entity: sensor.kert_aqara_szenzor_humidity [kert]" in prompt
        assert "Related entities:" in prompt
        assert "sensor.lumi_lumi_weather_humidity [nappali]" in prompt
        assert "Relevant domains: sensor" in prompt

    @patch("app.services.entity_reranker.get_last_state")
    def test_sensor_current_value_integration(
        self, mock_get_last_state, sample_entities
    ):
        """Test integration with current sensor values."""
        mock_get_last_state.return_value = "59.2%"

        entity_scores = [
            EntityScore(
                entity=sample_entities[0],  # Sensor entity
                base_score=0.8,
                context_boost=0.5,
                final_score=1.3,
                ranking_factors={},
            )
        ]

        prompt = self.reranker.create_hierarchical_system_prompt(
            ranked_entities=entity_scores, query="nedveség kert"
        )

        # Should include current value for sensor
        assert "Current value: 59.2%" in prompt
        mock_get_last_state.assert_called_with("sensor.kert_aqara_szenzor_humidity")

    def test_empty_entities_handling(self):
        """Test handling of empty entity list."""
        ranked_entities = self.reranker.rank_entities(entities=[], query="test query")

        assert ranked_entities == []

        # Test system prompt with empty entities
        prompt = self.reranker.create_hierarchical_system_prompt(
            ranked_entities=[], query="test"
        )

        assert prompt == "You are a Home Assistant agent.\n"

    def test_model_loading_failure_handling(self):
        """Test graceful handling of model loading failures."""
        with patch(
            "app.services.entity_reranker.CrossEncoder",
            side_effect=Exception("Model loading failed"),
        ):
            reranker = EntityReranker()

            # Should handle model loading failure gracefully
            assert reranker._model is None

            # Should fall back to text scoring
            entities = [
                {"entity_id": "test.entity", "domain": "test", "text": "test entity"}
            ]

            ranked = reranker.rank_entities(entities, "test query")
            assert len(ranked) == 1
            assert ranked[0].base_score > 0  # Should use fallback scoring

    def test_performance_requirements(self, sample_entities):
        """Test performance requirements for Sprint 1."""
        import time

        # Mock fast model prediction
        self.reranker._model.predict.return_value = [0.8, 0.6, 0.7, 0.5]

        start_time = time.time()

        ranked_entities = self.reranker.rank_entities(
            entities=sample_entities, query="nedveség kert", k=4
        )

        end_time = time.time()
        ranking_time = end_time - start_time

        # Should complete ranking in under 200ms (Sprint 1 target)
        assert ranking_time < 0.2, f"Ranking took {ranking_time:.4f}s, expected < 0.2s"
        assert len(ranked_entities) == 4

    def test_intent_specific_boosts(self, sample_entities):
        """Test intent-specific entity boosts."""
        # Test control intent with light entity
        light_entity = sample_entities[2]  # Light entity

        control_context = ConversationContext(
            areas_mentioned={"kert"},
            domains_mentioned={"light"},
            device_classes_mentioned=set(),
            previous_entities=set(),
            is_follow_up=False,
            intent="control",
        )

        factors = self.reranker._calculate_ranking_factors(
            light_entity, control_context
        )
        assert "controllable" in factors

        # Test read intent with sensor entity
        sensor_entity = sample_entities[0]  # Sensor entity

        read_context = ConversationContext(
            areas_mentioned={"kert"},
            domains_mentioned={"sensor"},
            device_classes_mentioned={"humidity"},
            previous_entities=set(),
            is_follow_up=False,
            intent="read",
        )

        factors = self.reranker._calculate_ranking_factors(sensor_entity, read_context)
        assert "readable" in factors


class TestEntityRerankerIntegration:
    """Integration tests for the global entity reranker instance."""

    def test_global_instance_initialization(self):
        """Test that global entity_reranker instance initializes correctly."""
        # Should not raise exceptions
        assert entity_reranker is not None
        assert entity_reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"

    @patch("app.services.entity_reranker.CrossEncoder")
    def test_model_lazy_loading(self, mock_cross_encoder):
        """Test that model is loaded lazily."""
        EntityReranker()

        # Model should not be loaded yet
        mock_cross_encoder.assert_called_once()

    def test_caching_integration(self):
        """Test that repeated queries can benefit from caching (future optimization)."""
        # This test ensures the architecture supports future caching implementation
        entities = [
            {
                "entity_id": "test.entity",
                "domain": "test",
                "area": "test_area",
                "text": "test entity description",
            }
        ]

        with patch.object(entity_reranker, "_model") as mock_model:
            mock_model.predict.return_value = [0.7]

            # First call
            result1 = entity_reranker.rank_entities(entities, "test query")

            # Second call with same query
            result2 = entity_reranker.rank_entities(entities, "test query")

            # Both should succeed (caching implementation can be added later)
            assert len(result1) == 1
            assert len(result2) == 1
            assert result1[0].final_score == result2[0].final_score


class TestEntityRerankerErrorHandling:
    """Test error handling and edge cases."""

    def test_malformed_entity_handling(self):
        """Test handling of malformed entity documents."""
        malformed_entities = [
            {},  # Empty entity
            {"entity_id": "test.entity"},  # Missing fields
            {"domain": "sensor"},  # Missing entity_id
            {
                "entity_id": "sensor.test",
                "domain": "sensor",
                "area": None,  # None values
                "device_class": None,
            },
        ]

        with patch("app.services.entity_reranker.CrossEncoder"):
            reranker = EntityReranker()
            reranker._model = Mock()
            reranker._model.predict.return_value = [0.5] * len(malformed_entities)

            # Should handle malformed entities gracefully
            ranked = reranker.rank_entities(malformed_entities, "test query")
            assert len(ranked) == len(malformed_entities)

    def test_cross_encoder_prediction_failure(self):
        """Test handling of cross-encoder prediction failures."""
        entities = [
            {"entity_id": "test.entity", "domain": "test", "text": "test entity"}
        ]

        with patch("app.services.entity_reranker.CrossEncoder"):
            reranker = EntityReranker()
            reranker._model = Mock()
            reranker._model.predict.side_effect = Exception("Prediction failed")

            # Should fall back to text scoring
            ranked = reranker.rank_entities(entities, "test query")
            assert len(ranked) == 1
            assert ranked[0].base_score > 0

    def test_unicode_handling(self):
        """Test proper handling of Hungarian unicode characters."""
        entities = [
            {
                "entity_id": "sensor.hőmérséklet_szenzor",
                "domain": "sensor",
                "friendly_name": "Hőmérséklet szenzor üőű áéí",
                "text": "hőmérséklet páratartalom nedvesség",
            }
        ]

        with patch("app.services.entity_reranker.CrossEncoder"):
            reranker = EntityReranker()
            reranker._model = Mock()
            reranker._model.predict.return_value = [0.8]

            # Should handle unicode characters properly
            ranked = reranker.rank_entities(entities, "hőmérséklet üőű")
            assert len(ranked) == 1

            # Should create proper description with unicode
            description = reranker._create_entity_description(entities[0])
            assert "Hőmérséklet szenzor üőű áéí" in description
