#!/usr/bin/env python3
"""
Search threshold optimization for current embedding model.
Helps improve relevance by adjusting similarity thresholds based on model characteristics.
"""

import os
import numpy as np

from app.services.integrations.embeddings import LocalBackend

# Set environment after importing
os.environ["SENTENCE_TRANSFORMER_MODEL"] = "paraphrase-multilingual-MiniLM-L12-v2"
os.environ["EMBEDDING_CPU_THREADS"] = "4"


def analyze_threshold_distribution():
    """Analyze similarity score distribution to recommend optimal thresholds."""

    print("🎯 Similarity Threshold Analysis")
    print("=" * 40)

    backend = LocalBackend()

    # Test cases with known relevance levels
    test_cases = [
        # High relevance pairs
        ("Kapcsold be a világítást!", "Turn on the lights", "HIGH"),
        ("Hőmérséklet szenzor", "Temperature sensor", "HIGH"),
        ("Zárj be minden ablakot", "Close all windows", "HIGH"),
        ("automation triggered", "automatizálás elindult", "HIGH"),
        # Medium relevance pairs
        ("világítás", "lámpa", "MEDIUM"),
        ("szenzor", "érzékelő", "MEDIUM"),
        ("entity_id: light.living_room", "nappali világítás", "MEDIUM"),
        ("hőmérséklet", "fűtés", "MEDIUM"),
        # Low relevance pairs
        ("világítás", "zene", "LOW"),
        ("hőmérséklet", "videó", "LOW"),
        ("ajtó", "internet", "LOW"),
        ("szenzor", "kávé", "LOW"),
    ]

    high_scores = []
    medium_scores = []
    low_scores = []

    print("Similarity scores by relevance category:")
    print()

    for text1, text2, relevance in test_cases:
        embeddings = backend.embed([text1, text2])
        score = float(
            np.dot(embeddings[0], embeddings[1])
            / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
        )

        if relevance == "HIGH":
            high_scores.append(score)
        elif relevance == "MEDIUM":
            medium_scores.append(score)
        elif relevance == "LOW":
            low_scores.append(score)

        print(f"{relevance:6} | {score:.3f} | {text1[:25]:<25} ↔ {text2[:25]:<25}")

    print("\n📊 Score Distribution:")
    print(
        f"   HIGH relevance:   avg={np.mean(high_scores):.3f}, min={np.min(high_scores):.3f}, max={np.max(high_scores):.3f}"
    )
    print(
        f"   MEDIUM relevance: avg={np.mean(medium_scores):.3f}, min={np.min(medium_scores):.3f}, max={np.max(medium_scores):.3f}"
    )
    print(
        f"   LOW relevance:    avg={np.mean(low_scores):.3f}, min={np.min(low_scores):.3f}, max={np.max(low_scores):.3f}"
    )

    # Calculate optimal thresholds
    high_min = np.min(high_scores)
    medium_max = np.max(medium_scores)
    medium_min = np.min(medium_scores)

    # Suggested thresholds with some buffer
    excellent_threshold = high_min - 0.05
    good_threshold = medium_max - 0.05
    acceptable_threshold = medium_min - 0.05

    print("\n🎯 Recommended Search Thresholds:")
    print(f"   EXCELLENT (highly relevant): >= {excellent_threshold:.3f}")
    print(f"   GOOD (relevant):             >= {good_threshold:.3f}")
    print(f"   ACCEPTABLE (may be relevant): >= {acceptable_threshold:.3f}")
    print(f"   POOR (likely irrelevant):    <  {acceptable_threshold:.3f}")

    # Configuration suggestions
    print("\n⚙️  Configuration Suggestions:")
    print("   # In your search/retrieval code:")
    print(f"   SIMILARITY_THRESHOLD_EXCELLENT = {excellent_threshold:.3f}")
    print(f"   SIMILARITY_THRESHOLD_GOOD = {good_threshold:.3f}")
    print(f"   SIMILARITY_THRESHOLD_MINIMUM = {acceptable_threshold:.3f}")
    print("   ")
    print("   # Search strategy:")
    print(f"   # 1. Return results >= {excellent_threshold:.3f} with high confidence")
    print(f"   # 2. Return results >= {good_threshold:.3f} as good matches")
    print(
        f"   # 3. Show results >= {acceptable_threshold:.3f} but mark as 'might be relevant'"
    )
    print(f"   # 4. Filter out results < {acceptable_threshold:.3f}")


def test_optimal_thresholds():
    """Test the effectiveness of recommended thresholds."""

    print("\n🧪 Testing Optimal Thresholds")
    print("=" * 30)

    # Use the thresholds we calculated (approximate values)
    EXCELLENT = 0.88  # Based on analysis
    GOOD = 0.80
    ACCEPTABLE = 0.45

    backend = LocalBackend()

    # Test with diverse queries
    test_queries = [
        (
            "Turn on the living room light",
            [
                "kapcsold be a nappali lámpát",
                "light.living_room state on",
                "világítás vezérlés nappali",
                "play music in living room",  # irrelevant
                "hőmérséklet nappali",  # somewhat related
            ],
        ),
        (
            "What's the temperature?",
            [
                "hány fok van?",
                "sensor.temperature_bedroom",
                "hőmérséklet szenzor érték",
                "turn on the lights",  # irrelevant
                "fűtés bekapcsolása",  # related
            ],
        ),
    ]

    for query, candidates in test_queries:
        print(f"\n🔍 Query: '{query}'")

        query_embedding = backend.embed([query])[0]
        candidate_embeddings = backend.embed(candidates)

        results = []
        for i, candidate in enumerate(candidates):
            score = float(
                np.dot(query_embedding, candidate_embeddings[i])
                / (
                    np.linalg.norm(query_embedding)
                    * np.linalg.norm(candidate_embeddings[i])
                )
            )

            if score >= EXCELLENT:
                category = "🟢 EXCELLENT"
            elif score >= GOOD:
                category = "🟡 GOOD"
            elif score >= ACCEPTABLE:
                category = "🟠 ACCEPTABLE"
            else:
                category = "🔴 POOR"

            results.append((score, category, candidate))

        # Sort by score
        results.sort(reverse=True)

        print("   Results (sorted by relevance):")
        for score, category, candidate in results:
            print(f"   {category} {score:.3f} | {candidate}")


if __name__ == "__main__":
    analyze_threshold_distribution()
    test_optimal_thresholds()
