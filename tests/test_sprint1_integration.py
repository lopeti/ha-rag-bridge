"""
Integration tests for Sprint 1: Context-Aware Entity Prioritization.
Tests the key scenario: "Mekkora a nedveség a kertben?" should return garden sensor first.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app


class TestSprint1GardenSensorScenario:
    """Test the key Sprint 1 scenario: Garden sensor prioritization."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_entities(self):
        """Mock entity data representing the Sprint 1 scenario."""
        return [
            {
                "_key": "sensor.kert_aqara_szenzor_humidity",
                "entity_id": "sensor.kert_aqara_szenzor_humidity",
                "domain": "sensor",
                "device_class": "humidity",
                "area": "kert",
                "friendly_name": "Kerti Aqara szenzor nedveség",
                "text": "kerti nedveség szenzor páratartalom kert",
                "embedding": [0.1] * 384,  # Mock embedding
            },
            {
                "_key": "sensor.lumi_lumi_weather_humidity",
                "entity_id": "sensor.lumi_lumi_weather_humidity",
                "domain": "sensor",
                "device_class": "humidity",
                "area": "nappali",
                "friendly_name": "Nappali páratartalom",
                "text": "nappali nedveség szenzor páratartalom",
                "embedding": [0.2] * 384,
            },
            {
                "_key": "sensor.lumi_lumi_weather_humidity_3",
                "entity_id": "sensor.lumi_lumi_weather_humidity_3",
                "domain": "sensor",
                "device_class": "humidity",
                "area": "hálószoba",
                "friendly_name": "Hálószoba páratartalom",
                "text": "hálószoba nedveség szenzor páratartalom háló",
                "embedding": [0.3] * 384,
            },
        ]

    @patch("app.main.ArangoClient")
    @patch("app.main.get_embedding_backend")
    @patch("app.services.entity_reranker.CrossEncoder")
    def test_garden_humidity_query_prioritization(
        self, mock_cross_encoder, mock_get_backend, mock_arango, mock_entities, client
    ):
        """Test that 'Mekkora a nedveség a kertben?' prioritizes garden sensor."""

        # Mock embedding backend
        mock_backend = Mock()
        mock_backend.embed.return_value = [[0.5] * 384]
        mock_get_backend.return_value = mock_backend

        # Mock cross-encoder to give garden sensor highest relevance
        mock_ce_instance = Mock()
        mock_ce_instance.predict.return_value = [
            0.9,
            0.6,
            0.5,
        ]  # Garden sensor gets highest score
        mock_cross_encoder.return_value = mock_ce_instance

        # Mock ArangoDB query results
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.__iter__.return_value = mock_entities
        mock_db.aql.execute.return_value = mock_cursor

        mock_arango_client = Mock()
        mock_arango_client.db.return_value = mock_db
        mock_arango.return_value = mock_arango_client

        # Test the API endpoint
        response = client.post(
            "/process-request", json={"user_message": "Mekkora a nedveség a kertben?"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify system prompt structure
        system_message = data["messages"][0]
        assert system_message["role"] == "system"

        # Should have hierarchical structure with garden sensor as primary
        assert (
            "Primary entity: sensor.kert_aqara_szenzor_humidity [kert]"
            in system_message["content"]
        )

        # Should have related entities
        assert "Related entities:" in system_message["content"]
        assert (
            "sensor.lumi_lumi_weather_humidity [nappali]" in system_message["content"]
        )

        # Should have relevant domains
        assert "Relevant domains: sensor" in system_message["content"]

    @patch("app.main.ArangoClient")
    @patch("app.main.get_embedding_backend")
    @patch("app.services.entity_reranker.CrossEncoder")
    @patch("app.services.state_service.get_last_state")
    def test_garden_sensor_current_value_integration(
        self,
        mock_get_state,
        mock_cross_encoder,
        mock_get_backend,
        mock_arango,
        mock_entities,
        client,
    ):
        """Test that current sensor value is included for garden sensor."""

        # Mock current sensor value
        mock_get_state.return_value = "59.2%"

        # Mock embedding backend
        mock_backend = Mock()
        mock_backend.embed.return_value = [[0.5] * 384]
        mock_get_backend.return_value = mock_backend

        # Mock cross-encoder
        mock_ce_instance = Mock()
        mock_ce_instance.predict.return_value = [0.9, 0.6, 0.5]
        mock_cross_encoder.return_value = mock_ce_instance

        # Mock ArangoDB
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.__iter__.return_value = mock_entities
        mock_db.aql.execute.return_value = mock_cursor

        mock_arango_client = Mock()
        mock_arango_client.db.return_value = mock_db
        mock_arango.return_value = mock_arango_client

        response = client.post(
            "/process-request", json={"user_message": "Mekkora a nedveség a kertben?"}
        )

        assert response.status_code == 200
        data = response.json()

        system_message = data["messages"][0]["content"]

        # Should include current value for primary sensor
        assert "Current value: 59.2%" in system_message

        # Verify get_last_state was called with correct entity
        mock_get_state.assert_called_with("sensor.kert_aqara_szenzor_humidity")

    @patch("app.main.ArangoClient")
    @patch("app.main.get_embedding_backend")
    @patch("app.services.entity_reranker.CrossEncoder")
    def test_follow_up_question_context_preservation(
        self, mock_cross_encoder, mock_get_backend, mock_arango, mock_entities, client
    ):
        """Test follow-up question: 'És a házban?' should expand context."""

        # Mock embedding backend
        mock_backend = Mock()
        mock_backend.embed.return_value = [[0.5] * 384]
        mock_get_backend.return_value = mock_backend

        # Mock cross-encoder - for follow-up, indoor sensors should rank higher
        mock_ce_instance = Mock()
        mock_ce_instance.predict.return_value = [
            0.5,
            0.8,
            0.9,
        ]  # Indoor sensors get higher scores
        mock_cross_encoder.return_value = mock_ce_instance

        # Mock ArangoDB
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.__iter__.return_value = mock_entities
        mock_db.aql.execute.return_value = mock_cursor

        mock_arango_client = Mock()
        mock_arango_client.db.return_value = mock_db
        mock_arango.return_value = mock_arango_client

        # Test follow-up question with conversation history
        conversation_history = [
            {"role": "user", "content": "Mekkora a nedveség a kertben?"},
            {
                "role": "system",
                "content": "Primary entity: sensor.kert_aqara_szenzor_humidity [kert]\\nRelevant domains: sensor",
            },
        ]

        response = client.post(
            "/process-request",
            json={
                "user_message": "És a házban?",
                "conversation_history": conversation_history,
            },
        )

        assert response.status_code == 200
        data = response.json()

        system_message = data["messages"][0]["content"]

        # Should prioritize indoor sensors for house context
        # The primary entity should be one of the indoor sensors
        assert (
            "sensor.lumi_lumi_weather_humidity [nappali]" in system_message
            or "sensor.lumi_lumi_weather_humidity_3 [hálószoba]" in system_message
        )

    @patch("app.main.ArangoClient")
    @patch("app.main.get_embedding_backend")
    @patch("app.services.entity_reranker.CrossEncoder")
    def test_cross_encoder_fallback_handling(
        self, mock_cross_encoder, mock_get_backend, mock_arango, mock_entities, client
    ):
        """Test graceful fallback when cross-encoder fails."""

        # Mock embedding backend
        mock_backend = Mock()
        mock_backend.embed.return_value = [[0.5] * 384]
        mock_get_backend.return_value = mock_backend

        # Mock cross-encoder to raise exception
        mock_cross_encoder.side_effect = Exception("Cross-encoder loading failed")

        # Mock ArangoDB
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.__iter__.return_value = mock_entities
        mock_db.aql.execute.return_value = mock_cursor

        mock_arango_client = Mock()
        mock_arango_client.db.return_value = mock_db
        mock_arango.return_value = mock_arango_client

        # Should still work with fallback text scoring
        response = client.post(
            "/process-request", json={"user_message": "Mekkora a nedveség a kertben?"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should still generate hierarchical prompt (even with fallback scoring)
        system_message = data["messages"][0]["content"]
        assert "Primary entity:" in system_message
        assert "sensor" in system_message.lower()

    @patch("app.main.ArangoClient")
    @patch("app.main.get_embedding_backend")
    @patch("app.services.entity_reranker.CrossEncoder")
    def test_multilingual_query_support(
        self, mock_cross_encoder, mock_get_backend, mock_arango, mock_entities, client
    ):
        """Test support for English queries alongside Hungarian."""

        # Mock embedding backend
        mock_backend = Mock()
        mock_backend.embed.return_value = [[0.5] * 384]
        mock_get_backend.return_value = mock_backend

        # Mock cross-encoder
        mock_ce_instance = Mock()
        mock_ce_instance.predict.return_value = [0.9, 0.6, 0.5]
        mock_cross_encoder.return_value = mock_ce_instance

        # Mock ArangoDB
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.__iter__.return_value = mock_entities
        mock_db.aql.execute.return_value = mock_cursor

        mock_arango_client = Mock()
        mock_arango_client.db.return_value = mock_db
        mock_arango.return_value = mock_arango_client

        # Test English query
        response = client.post(
            "/process-request",
            json={"user_message": "What's the humidity in the garden?"},
        )

        assert response.status_code == 200
        data = response.json()

        system_message = data["messages"][0]["content"]

        # Should still prioritize garden sensor correctly
        assert (
            "Primary entity: sensor.kert_aqara_szenzor_humidity [kert]"
            in system_message
        )

    def test_conversation_analyzer_integration(self):
        """Test direct integration with conversation analyzer."""
        from app.services.conversation_analyzer import conversation_analyzer

        # Test Hungarian area detection
        context = conversation_analyzer.analyze_conversation(
            "Mekkora a nedveség a kertben?"
        )

        assert "kert" in context.areas_mentioned
        assert "sensor" in context.domains_mentioned
        assert "humidity" in context.device_classes_mentioned
        assert context.intent == "read"
        assert context.is_follow_up is False

        # Test follow-up detection
        follow_up_context = conversation_analyzer.analyze_conversation("És a házban?")
        assert follow_up_context.is_follow_up is True
        assert "ház" in follow_up_context.areas_mentioned

    def test_entity_reranker_integration(self, mock_entities):
        """Test direct integration with entity reranker."""
        from app.services.entity_reranker import entity_reranker

        with patch.object(entity_reranker, "_model") as mock_model:
            mock_model.predict.return_value = [0.9, 0.6, 0.5]  # Garden sensor highest

            ranked_entities = entity_reranker.rank_entities(
                entities=mock_entities, query="Mekkora a nedveség a kertben?", k=3
            )

            # Garden sensor should be first
            assert len(ranked_entities) == 3
            assert (
                ranked_entities[0].entity["entity_id"]
                == "sensor.kert_aqara_szenzor_humidity"
            )
            assert ranked_entities[0].final_score > ranked_entities[1].final_score

            # Should have context boosts
            assert ranked_entities[0].context_boost > 0


class TestSprint1PerformanceRequirements:
    """Test Sprint 1 performance requirements."""

    @patch("app.main.ArangoClient")
    @patch("app.main.get_embedding_backend")
    @patch("app.services.entity_reranker.CrossEncoder")
    def test_response_time_under_target(
        self, mock_cross_encoder, mock_get_backend, mock_arango, client
    ):
        """Test that response time meets Sprint 1 target (<1s for context-aware queries)."""
        import time

        # Mock fast responses
        mock_backend = Mock()
        mock_backend.embed.return_value = [[0.5] * 384]
        mock_get_backend.return_value = mock_backend

        mock_ce_instance = Mock()
        mock_ce_instance.predict.return_value = [0.9]
        mock_cross_encoder.return_value = mock_ce_instance

        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.__iter__.return_value = [
            {"entity_id": "sensor.test", "domain": "sensor", "area": "test"}
        ]
        mock_db.aql.execute.return_value = mock_cursor

        mock_arango_client = Mock()
        mock_arango_client.db.return_value = mock_db
        mock_arango.return_value = mock_arango_client

        start_time = time.time()

        response = client.post(
            "/process-request", json={"user_message": "Mekkora a nedveség a kertben?"}
        )

        end_time = time.time()
        response_time = end_time - start_time

        assert response.status_code == 200
        # Sprint 1 target: <1s for context-aware queries
        assert (
            response_time < 1.0
        ), f"Response time {response_time:.3f}s exceeds 1s target"

    def test_large_entity_set_performance(self):
        """Test performance with large entity sets."""
        from app.services.entity_reranker import entity_reranker
        import time

        # Create large entity set (100 entities)
        large_entity_set = []
        for i in range(100):
            large_entity_set.append(
                {
                    "entity_id": f"sensor.test_{i}",
                    "domain": "sensor",
                    "area": f"area_{i % 10}",
                    "device_class": "humidity",
                    "text": f"test sensor {i}",
                }
            )

        with patch.object(entity_reranker, "_model") as mock_model:
            mock_model.predict.return_value = [0.5] * 100

            start_time = time.time()

            ranked = entity_reranker.rank_entities(
                entities=large_entity_set, query="nedveség", k=10
            )

            end_time = time.time()
            ranking_time = end_time - start_time

            assert len(ranked) == 10
            # Should handle large sets efficiently
            assert ranking_time < 0.5, f"Large set ranking took {ranking_time:.3f}s"


class TestSprint1SuccessCriteria:
    """Test Sprint 1 success criteria validation."""

    def test_entity_relevance_accuracy_target(self, mock_entities):
        """Test >90% correct primary entity accuracy target."""
        from app.services.entity_reranker import entity_reranker

        test_cases = [
            ("Mekkora a nedveság a kertben?", "sensor.kert_aqara_szenzor_humidity"),
            ("Mi a páratartalom a nappaliban?", "sensor.lumi_lumi_weather_humidity"),
            (
                "Milyen a nedveség a hálószobában?",
                "sensor.lumi_lumi_weather_humidity_3",
            ),
        ]

        correct_predictions = 0

        with patch.object(entity_reranker, "_model") as mock_model:
            for query, expected_entity in test_cases:
                # Mock cross-encoder to prioritize correct entity based on area matching
                if "kert" in query:
                    mock_model.predict.return_value = [0.9, 0.6, 0.5]  # Garden first
                elif "nappali" in query:
                    mock_model.predict.return_value = [
                        0.5,
                        0.9,
                        0.6,
                    ]  # Living room first
                elif "háló" in query:
                    mock_model.predict.return_value = [0.5, 0.6, 0.9]  # Bedroom first

                ranked = entity_reranker.rank_entities(
                    entities=mock_entities, query=query, k=3
                )

                if ranked and ranked[0].entity["entity_id"] == expected_entity:
                    correct_predictions += 1

        accuracy = correct_predictions / len(test_cases)

        # Sprint 1 target: >90% entity relevance accuracy
        assert accuracy >= 0.9, f"Accuracy {accuracy:.1%} below 90% target"

    def test_hierarchical_system_prompt_structure(self):
        """Test hierarchical entity presentation requirement."""
        from app.services.entity_reranker import entity_reranker
        from app.services.entity_reranker import EntityScore

        # Create mock entities
        mock_entities = [
            {
                "entity_id": "sensor.kert_aqara_szenzor_humidity",
                "domain": "sensor",
                "device_class": "humidity",
                "area": "kert",
                "friendly_name": "Kerti páratartalom szenzor",
                "text": "kerti nedveség szenzor páratartalom kert",
            },
            {
                "entity_id": "sensor.lumi_lumi_weather_humidity",
                "domain": "sensor",
                "device_class": "humidity",
                "area": "nappali",
                "friendly_name": "Nappali páratartalom",
                "text": "nappali nedveség szenzor páratartalom",
            },
            {
                "entity_id": "sensor.lumi_lumi_weather_humidity_3",
                "domain": "sensor",
                "device_class": "humidity",
                "area": "hálószoba",
                "friendly_name": "Hálószoba páratartalom",
                "text": "hálószoba nedveség szenzor páratartalom háló",
            },
        ]

        # Create mock scored entities
        entity_scores = [
            EntityScore(
                entity=mock_entities[0],  # Garden sensor
                base_score=0.8,
                context_boost=0.5,
                final_score=1.3,
                ranking_factors={"area_kert": 1.0},
            ),
            EntityScore(
                entity=mock_entities[1],  # Living room sensor
                base_score=0.6,
                context_boost=0.2,
                final_score=0.8,
                ranking_factors={},
            ),
            EntityScore(
                entity=mock_entities[2],  # Bedroom sensor
                base_score=0.5,
                context_boost=0.1,
                final_score=0.6,
                ranking_factors={},
            ),
        ]

        prompt = entity_reranker.create_hierarchical_system_prompt(
            ranked_entities=entity_scores, query="Mekkora a nedveség a kertben?"
        )

        # Verify hierarchical structure requirements
        assert "Primary entity:" in prompt
        assert "Related entities:" in prompt
        assert "Relevant domains:" in prompt

        # Verify correct primary entity
        assert "sensor.kert_aqara_szenzor_humidity [kert]" in prompt

        # Verify area information is preserved
        assert "[nappali]" in prompt
        assert "[hálószoba]" in prompt
