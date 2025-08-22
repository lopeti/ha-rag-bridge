#!/usr/bin/env python3
"""
Embedding backend performance test for homelab environment.
Tests different models and thread configurations.
"""

import os
import time
import psutil

from app.services.integrations.embeddings import LocalBackend

# Set environment after importing
os.environ["SENTENCE_TRANSFORMER_MODEL"] = "paraphrase-multilingual-MiniLM-L12-v2"
os.environ["EMBEDDING_CPU_THREADS"] = "4"


def test_embedding_performance():
    """Test embedding performance with current configuration."""

    # Test texts (mix of Hungarian and English)
    test_texts = [
        "Ez egy magyar teszt szöveg a Home Assistant rendszerhez.",
        "This is an English test text for the Home Assistant system.",
        "A szenzor állapota megváltozott a nappaliban.",
        "The sensor state changed in the living room.",
        "Kapcsold be a konyhában a világítást!",
        "Turn on the lights in the kitchen!",
        "A hőmérséklet 23.5 Celsius fok a hálószobában.",
        "Temperature is 23.5 degrees Celsius in the bedroom.",
    ]

    print("🏠 HA-RAG Bridge Embedding Performance Test")
    print("=" * 50)

    # System info
    print(f"💻 CPU cores: {psutil.cpu_count()}")
    print(f"🧠 RAM total: {psutil.virtual_memory().total / 1024**3:.1f} GB")
    print(f"📊 RAM available: {psutil.virtual_memory().available / 1024**3:.1f} GB")
    print()

    # Initialize backend
    print("🔄 Initializing Local Embedding Backend...")
    start_time = time.time()
    backend = LocalBackend()
    init_time = time.time() - start_time

    print(f"✅ Model loaded in {init_time:.2f} seconds")
    print(f"📏 Embedding dimension: {backend.DIMENSION}")
    print()

    # Memory usage after model load
    mem_after_load = psutil.virtual_memory()
    print(f"🧠 RAM after model load: {mem_after_load.used / 1024**3:.1f} GB used")
    print()

    # Performance test
    print("⚡ Running embedding performance test...")
    start_time = time.time()
    embeddings = backend.embed(test_texts)
    embedding_time = time.time() - start_time

    # Results
    print("📊 Results:")
    print(f"   • Texts processed: {len(test_texts)}")
    print(f"   • Processing time: {embedding_time:.3f} seconds")
    print(f"   • Speed: {len(test_texts) / embedding_time:.1f} texts/second")
    print(f"   • Average per text: {embedding_time / len(test_texts) * 1000:.1f} ms")
    print()

    # Verify embeddings
    if embeddings and len(embeddings) == len(test_texts):
        print("✅ All embeddings generated successfully!")
        print(f"   • Embedding dimensions: {len(embeddings[0])}")

        # Sample embedding (first few values)
        sample = embeddings[0][:5]
        print(f"   • Sample values: [{', '.join(f'{x:.4f}' for x in sample)}...]")
    else:
        print("❌ Error in embedding generation!")

    print()
    print("🎯 Recommendations for your homelab:")

    if embedding_time / len(test_texts) < 0.1:  # < 100ms per text
        print("   ✅ Excellent performance! Current model is optimal.")
    elif embedding_time / len(test_texts) < 0.5:  # < 500ms per text
        print("   ✅ Good performance! Consider increasing CPU threads.")
    else:
        print("   ⚠️  Consider switching to a faster model like 'all-MiniLM-L6-v2'")

    mem_usage = mem_after_load.used / 1024**3
    if mem_usage < 8:
        print(
            f"   ✅ Low memory usage ({mem_usage:.1f} GB) - you can use larger models"
        )
    elif mem_usage < 12:
        print(
            f"   ✅ Moderate memory usage ({mem_usage:.1f} GB) - current model is good"
        )
    else:
        print(
            f"   ⚠️  High memory usage ({mem_usage:.1f} GB) - consider a smaller model"
        )


if __name__ == "__main__":
    test_embedding_performance()
