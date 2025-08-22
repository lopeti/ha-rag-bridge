#!/usr/bin/env python3
"""
Embedding quality and relevance test for HA-RAG Bridge.
Tests semantic similarity, multilingual capabilities, and domain-specific performance.
"""

import os
import numpy as np
from typing import List
from sklearn.metrics.pairwise import cosine_similarity

from app.services.integrations.embeddings import LocalBackend

# Set environment after importing
os.environ["SENTENCE_TRANSFORMER_MODEL"] = "paraphrase-multilingual-MiniLM-L12-v2"
os.environ["EMBEDDING_CPU_THREADS"] = "4"


def calculate_similarity(emb1: List[float], emb2: List[float]) -> float:
    """Calculate cosine similarity between two embeddings."""
    return float(cosine_similarity([emb1], [emb2])[0][0])


def test_semantic_similarity():
    """Test semantic understanding with various text pairs."""

    print("🧠 Semantic Similarity Test")
    print("=" * 40)

    backend = LocalBackend()

    # Test cases: (text1, text2, expected_similarity_category)
    test_cases = [
        # Hungarian synonyms/paraphrases
        ("Kapcsold be a világítást!", "Gyújtsd fel a lámpákat!", "HIGH"),
        ("A hőmérséklet magas a szobában", "Meleg van a helyiségben", "HIGH"),
        ("Zárj be minden ablakot", "Csukd le az összes ablakot", "HIGH"),
        # English synonyms/paraphrases
        ("Turn on the lights", "Switch on the illumination", "HIGH"),
        ("Temperature is high in the room", "It's warm in the chamber", "HIGH"),
        ("Close all windows", "Shut every window", "HIGH"),
        # Cross-language (same meaning)
        ("Kapcsold be a világítást", "Turn on the lights", "HIGH"),
        ("Hőmérséklet", "Temperature", "HIGH"),
        ("Ajtó", "Door", "HIGH"),
        # Related concepts
        ("Világítás", "Lámpa", "MEDIUM"),
        ("Hőmérséklet", "Fűtés", "MEDIUM"),
        ("Mozgásérzékelő", "Szenzor", "MEDIUM"),
        # Home Assistant specific
        ("entity_id: light.living_room", "nappali világítás", "MEDIUM"),
        ("sensor.temperature_bedroom", "hálószoba hőmérséklet", "MEDIUM"),
        ("automation triggered", "automatizálás elindult", "MEDIUM"),
        # Unrelated concepts
        ("Világítás", "Zene", "LOW"),
        ("Hőmérséklet", "Videó", "LOW"),
        ("Ajtó", "Internet", "LOW"),
    ]

    results = []

    for text1, text2, expected in test_cases:
        # Get embeddings
        embeddings = backend.embed([text1, text2])
        similarity = calculate_similarity(embeddings[0], embeddings[1])

        # Categorize actual similarity
        if similarity >= 0.7:
            actual = "HIGH"
        elif similarity >= 0.4:
            actual = "MEDIUM"
        else:
            actual = "LOW"

        # Check if expectation matches
        match = "✅" if actual == expected else "❌"

        results.append(
            {
                "text1": text1,
                "text2": text2,
                "similarity": similarity,
                "expected": expected,
                "actual": actual,
                "match": match,
            }
        )

        print(
            f"{match} {similarity:.3f} | {text1[:30]:<30} | {text2[:30]:<30} | {expected} -> {actual}"
        )

    # Summary
    matches = sum(1 for r in results if r["match"] == "✅")
    total = len(results)
    accuracy = matches / total * 100

    print("\n📊 Semantic Similarity Results:")
    print(f"   • Accuracy: {matches}/{total} ({accuracy:.1f}%)")
    print(f"   • Average similarity: {np.mean([r['similarity'] for r in results]):.3f}")

    return results


def test_domain_specific_understanding():
    """Test understanding of Home Assistant specific concepts."""

    print("\n🏠 Home Assistant Domain Knowledge Test")
    print("=" * 45)

    backend = LocalBackend()

    # HA-specific terms and their related concepts
    ha_concepts = {
        "Entity Types": [
            "light entity",
            "sensor reading",
            "switch state",
            "automation rule",
            "script execution",
        ],
        "States & Attributes": [
            "device is on",
            "brightness level 80%",
            "temperature 23.5°C",
            "motion detected",
            "battery level low",
        ],
        "Actions": [
            "turn on living room light",
            "set thermostat to 22 degrees",
            "trigger security automation",
            "send notification to phone",
            "play music on speaker",
        ],
        "Locations": [
            "living room sensor",
            "kitchen light switch",
            "bedroom temperature",
            "garage door status",
            "bathroom fan control",
        ],
    }

    print("Testing semantic clustering within categories:")

    for category, concepts in ha_concepts.items():
        print(f"\n📂 {category}:")

        # Get embeddings for all concepts in this category
        embeddings = backend.embed(concepts)

        # Calculate average similarity within category
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = calculate_similarity(embeddings[i], embeddings[j])
                similarities.append(sim)

        avg_similarity = np.mean(similarities) if similarities else 0

        # Show individual similarities
        for i, concept1 in enumerate(concepts):
            for j, concept2 in enumerate(concepts[i + 1 :], i + 1):
                sim = calculate_similarity(embeddings[i], embeddings[j])
                print(f"   {sim:.3f} | {concept1} ↔ {concept2}")

        print(f"   📊 Average intra-category similarity: {avg_similarity:.3f}")


def test_multilingual_consistency():
    """Test consistency between Hungarian and English."""

    print("\n🌍 Multilingual Consistency Test")
    print("=" * 35)

    backend = LocalBackend()

    # Translation pairs
    translation_pairs = [
        ("világítás", "lighting"),
        ("hőmérséklet", "temperature"),
        ("ajtó", "door"),
        ("ablak", "window"),
        ("szenzor", "sensor"),
        ("kapcsoló", "switch"),
        ("fűtés", "heating"),
        ("hűtés", "cooling"),
        ("biztonság", "security"),
        ("értesítés", "notification"),
    ]

    print("Hungarian-English translation consistency:")

    similarities = []
    for hu, en in translation_pairs:
        embeddings = backend.embed([hu, en])
        similarity = calculate_similarity(embeddings[0], embeddings[1])
        similarities.append(similarity)

        status = "✅" if similarity >= 0.6 else "⚠️" if similarity >= 0.4 else "❌"
        print(f"{status} {similarity:.3f} | {hu:<15} ↔ {en:<15}")

    avg_similarity = np.mean(similarities)
    print(f"\n📊 Average translation similarity: {avg_similarity:.3f}")

    return similarities


def test_context_understanding():
    """Test understanding of context and intent."""

    print("\n🎯 Context & Intent Understanding Test")
    print("=" * 40)

    backend = LocalBackend()

    # Context scenarios
    scenarios = [
        {
            "context": "user wants to control lighting",
            "queries": [
                "turn on the lights",
                "kapcsold be a lámpákat",
                "make it brighter",
                "I need more light",
                "it's too dark in here",
            ],
        },
        {
            "context": "user asks about temperature",
            "queries": [
                "what's the temperature?",
                "hány fok van?",
                "is it warm enough?",
                "how hot is it?",
                "check the thermostat",
            ],
        },
        {
            "context": "user wants security status",
            "queries": [
                "are doors locked?",
                "be vannak zárva az ajtók?",
                "is the house secure?",
                "check security system",
                "arm the alarm",
            ],
        },
    ]

    for scenario in scenarios:
        print(f"\n🎭 Scenario: {scenario['context']}")

        queries = scenario["queries"]
        embeddings = backend.embed(queries)

        # Calculate similarities within context
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = calculate_similarity(embeddings[i], embeddings[j])
                similarities.append(sim)

        avg_similarity = np.mean(similarities) if similarities else 0

        print("   Queries:")
        for query in queries:
            print(f"   • {query}")

        print(f"   📊 Context coherence: {avg_similarity:.3f}")


def main():
    """Run all embedding quality tests."""

    print("🔬 HA-RAG Bridge Embedding Quality Assessment")
    print("=" * 55)
    print()

    # Run all tests
    semantic_results = test_semantic_similarity()
    test_domain_specific_understanding()
    multilingual_similarities = test_multilingual_consistency()
    test_context_understanding()

    # Overall assessment
    print("\n" + "=" * 55)
    print("📋 OVERALL ASSESSMENT")
    print("=" * 55)

    semantic_accuracy = (
        sum(1 for r in semantic_results if r["match"] == "✅")
        / len(semantic_results)
        * 100
    )
    multilingual_avg = np.mean(multilingual_similarities)

    print(f"🎯 Semantic Understanding: {semantic_accuracy:.1f}%")
    print(f"🌍 Multilingual Consistency: {multilingual_avg:.3f}")

    if semantic_accuracy >= 80:
        print("✅ Excellent semantic understanding!")
    elif semantic_accuracy >= 60:
        print("✅ Good semantic understanding")
    else:
        print("⚠️  Semantic understanding needs improvement")

    if multilingual_avg >= 0.6:
        print("✅ Strong multilingual capability!")
    elif multilingual_avg >= 0.4:
        print("✅ Adequate multilingual capability")
    else:
        print("⚠️  Multilingual capability needs improvement")

    print("\n🔧 RECOMMENDATIONS:")

    if semantic_accuracy < 80:
        print(
            "• Consider upgrading to 'all-mpnet-base-v2' for better semantic understanding"
        )

    if multilingual_avg < 0.6:
        print(
            "• Current model handles multilingual well, but specialized models might help"
        )

    print(
        "• For Home Assistant specific terms, consider fine-tuning or domain-specific models"
    )
    print("• Monitor real-world query relevance and adjust based on user feedback")


if __name__ == "__main__":
    main()
