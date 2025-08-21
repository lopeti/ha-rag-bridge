#!/usr/bin/env python3
"""
Sprint 1 validation script.
Tests the key functionality without async loop conflicts.
"""

import os
import sys

# Set environment variables to use local backend for testing
os.environ["EMBEDDING_BACKEND"] = "local"
os.environ["AUTO_BOOTSTRAP"] = "false"  # Skip bootstrap for validation
os.environ["SKIP_ARANGO_HEALTHCHECK"] = "1"  # Skip health check

# Import our modules after setting environment variables  # noqa: E402
from app.services.conversation_analyzer import conversation_analyzer  # noqa: E402
from app.services.entity_reranker import entity_reranker  # noqa: E402


def test_conversation_analyzer():
    """Test conversation analyzer functionality."""
    print("🧠 Testing Conversation Analyzer...")

    test_cases = [
        ("Mekkora a nedveség a kertben?", {"kert"}, {"sensor"}, {"humidity"}),
        ("Mi a hőmérséklet a nappaliban?", {"nappali"}, {"sensor"}, {"temperature"}),
        ("Kapcsold fel a világítást a konyhában", {"konyha"}, {"light"}, set()),
        ("És a házban?", {"ház"}, set(), set()),
    ]

    passed = 0
    total = len(test_cases)

    for query, expected_areas, expected_domains, expected_classes in test_cases:
        context = conversation_analyzer.analyze_conversation(query)

        areas_match = context.areas_mentioned == expected_areas
        domains_match = context.domains_mentioned >= expected_domains  # Allow supersets
        classes_match = context.device_classes_mentioned >= expected_classes

        if areas_match and domains_match and classes_match:
            print(f"  ✅ '{query}' - PASSED")
            passed += 1
        else:
            print(f"  ❌ '{query}' - FAILED")
            print(
                f"    Expected areas: {expected_areas}, got: {context.areas_mentioned}"
            )
            print(
                f"    Expected domains: {expected_domains}, got: {context.domains_mentioned}"
            )
            print(
                f"    Expected classes: {expected_classes}, got: {context.device_classes_mentioned}"
            )

    print(f"Conversation Analyzer: {passed}/{total} tests passed")
    return passed == total


def test_entity_reranker():
    """Test entity reranker functionality."""
    print("\n🔄 Testing Entity Reranker...")

    # Sample entities for testing
    sample_entities = [
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
            "entity_id": "sensor.nappali_temperature",
            "domain": "sensor",
            "device_class": "temperature",
            "area": "nappali",
            "friendly_name": "Nappali hőmérséklet",
            "text": "nappali hőmérséklet szenzor",
        },
    ]

    test_cases = [
        ("Mekkora a nedveség a kertben?", "sensor.kert_aqara_szenzor_humidity"),
        ("Mi a páratartalom a nappaliban?", "sensor.lumi_lumi_weather_humidity"),
        ("Mi a hőmérséklet a nappaliban?", "sensor.nappali_temperature"),
    ]

    passed = 0
    total = len(test_cases)

    for query, expected_top_entity in test_cases:
        try:
            ranked_entities = entity_reranker.rank_entities(
                entities=sample_entities, query=query, k=3
            )

            if (
                ranked_entities
                and ranked_entities[0].entity["entity_id"] == expected_top_entity
            ):
                print(f"  ✅ '{query}' -> {expected_top_entity} - PASSED")
                passed += 1
            else:
                top_entity = (
                    ranked_entities[0].entity["entity_id"]
                    if ranked_entities
                    else "None"
                )
                print(
                    f"  ❌ '{query}' -> expected {expected_top_entity}, got {top_entity} - FAILED"
                )
        except Exception as e:
            print(f"  ❌ '{query}' - ERROR: {e}")

    print(f"Entity Reranker: {passed}/{total} tests passed")
    return passed == total


def test_hierarchical_system_prompt():
    """Test hierarchical system prompt generation."""
    print("\n📝 Testing Hierarchical System Prompt...")

    sample_entities = [
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
    ]

    try:
        ranked_entities = entity_reranker.rank_entities(
            entities=sample_entities, query="Mekkora a nedveség a kertben?", k=2
        )

        prompt = entity_reranker.create_hierarchical_system_prompt(
            ranked_entities=ranked_entities,
            query="Mekkora a nedveség a kertben?",
            max_primary=1,
            max_related=1,
        )

        # Check for required elements
        required_elements = [
            "You are a Home Assistant agent.",
            "Primary entity:",
            "sensor.kert_aqara_szenzor_humidity [kert]",
            "Related entities:",
            "Relevant domains: sensor",
        ]

        passed_checks = 0
        for element in required_elements:
            if element in prompt:
                passed_checks += 1
                print(f"  ✅ Found: '{element}'")
            else:
                print(f"  ❌ Missing: '{element}'")

        print("\nGenerated prompt:")
        print("─" * 50)
        print(prompt)
        print("─" * 50)

        success = passed_checks == len(required_elements)
        print(
            f"Hierarchical System Prompt: {passed_checks}/{len(required_elements)} checks passed"
        )
        return success

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False


def test_performance():
    """Test performance requirements."""
    print("\n⚡ Testing Performance Requirements...")

    import time

    # Test conversation analysis performance
    start_time = time.time()
    for _ in range(100):  # 100 iterations
        conversation_analyzer.analyze_conversation("Mekkora a nedveség a kertben?")
    analysis_time = (time.time() - start_time) / 100  # Average per call

    analysis_passed = analysis_time < 0.01  # <10ms target
    print(
        f"  Conversation Analysis: {analysis_time*1000:.2f}ms avg {'✅' if analysis_passed else '❌'}"
    )

    # Test entity ranking performance (smaller test due to model loading)
    sample_entities = [
        {
            "entity_id": f"sensor.test_{i}",
            "domain": "sensor",
            "area": f"area_{i % 3}",
            "text": f"test sensor {i}",
        }
        for i in range(10)
    ]

    start_time = time.time()
    try:
        entity_reranker.rank_entities(sample_entities, "test query", k=5)
        ranking_time = time.time() - start_time
        ranking_passed = ranking_time < 0.2  # <200ms target
        print(
            f"  Entity Ranking: {ranking_time*1000:.2f}ms {'✅' if ranking_passed else '❌'}"
        )
    except Exception as e:
        print(f"  Entity Ranking: ERROR - {e} ❌")
        ranking_passed = False

    return analysis_passed and ranking_passed


def main():
    """Run all Sprint 1 validation tests."""
    print("🚀 Sprint 1 Validation - Context-Aware Entity Prioritization")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("Conversation Analyzer", test_conversation_analyzer()))
    results.append(("Entity Reranker", test_entity_reranker()))
    results.append(("Hierarchical System Prompt", test_hierarchical_system_prompt()))
    results.append(("Performance Requirements", test_performance()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 SPRINT 1 VALIDATION SUMMARY")
    print("-" * 30)

    passed_tests = 0
    total_tests = len(results)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:25} {status}")
        if passed:
            passed_tests += 1

    print("-" * 30)
    success_rate = (passed_tests / total_tests) * 100
    print(f"Overall Success Rate: {passed_tests}/{total_tests} ({success_rate:.1f}%)")

    if passed_tests == total_tests:
        print("\n🎉 Sprint 1 implementation is READY!")
        print("✅ Context-aware entity prioritization works correctly")
        print("✅ 'Mekkora a nedveség a kertben?' will return garden sensor first")
        print("✅ Hierarchical system prompts are generated properly")
        print("✅ Performance targets are met")
        return 0
    else:
        print(
            f"\n⚠️  Sprint 1 needs attention: {total_tests - passed_tests} issues found"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
