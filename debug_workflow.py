#!/usr/bin/env python3
"""Simple debugging tool for LangGraph Phase 3 workflow visualization."""

import asyncio
import time
from typing import List, Dict, Any
from app.langgraph_workflow.workflow import run_rag_workflow
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


async def debug_workflow_step_by_step(query: str, session_id: str = "debug_session"):
    """Run workflow with detailed step-by-step debugging output."""

    print("🚀 LangGraph Phase 3 Workflow Debugger")
    print("=" * 60)
    print(f"Query: '{query}'")
    print(f"Session ID: {session_id}")
    print("=" * 60)

    # Simple conversation history for multi-turn testing
    conversation_history: List[Dict[str, Any]] = []

    start_time = time.time()

    try:
        # Run the workflow
        result = await run_rag_workflow(
            user_query=query,
            session_id=session_id,
            conversation_history=conversation_history,
        )

        end_time = time.time()
        duration = end_time - start_time

        print(f"\n⏱️  Total execution time: {duration:.2f}s")
        print("\n📊 WORKFLOW RESULTS:")
        print("=" * 40)

        # Display key results
        sections = {
            "🗣️  Conversation Context": result.get("conversation_context", {}),
            "🎯 Scope Detection": {
                "scope": str(result.get("detected_scope", "unknown")),
                "confidence": result.get("scope_confidence", 0.0),
                "optimal_k": result.get("optimal_k", 0),
                "reasoning": result.get("scope_reasoning", ""),
            },
            "🔍 Entity Retrieval": {
                "total_entities": len(result.get("retrieved_entities", [])),
                "cluster_entities": len(result.get("cluster_entities", [])),
                "memory_entities": len(result.get("memory_entities", [])),
                "memory_boosted": len(
                    [
                        e
                        for e in result.get("retrieved_entities", [])
                        if e.get("_memory_boosted")
                    ]
                ),
            },
            "📝 Context Formatting": {
                "formatter_type": result.get("formatter_type", "unknown"),
                "context_length": len(result.get("formatted_context", "")),
                "context_preview": (
                    result.get("formatted_context", "")[:200] + "..."
                    if len(result.get("formatted_context", "")) > 200
                    else result.get("formatted_context", "")
                ),
            },
            "⚠️  Errors & Retries": {
                "errors": result.get("errors", []),
                "retry_count": result.get("retry_count", 0),
                "fallback_used": result.get("fallback_used", False),
            },
        }

        for title, data in sections.items():
            print(f"\n{title}")
            print("-" * len(title))
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 3:
                        print(f"  {key}: [{len(value)} items] {value[:2]}...")
                    else:
                        print(f"  {key}: {value}")
            else:
                print(f"  {data}")

        # Display top entities if available
        entities = result.get("retrieved_entities", [])[:5]
        if entities:
            print("\n🏠 Top 5 Retrieved Entities:")
            print("-" * 30)
            for i, entity in enumerate(entities, 1):
                entity_id = entity.get("entity_id", "unknown")
                score = entity.get("_score", 0.0)
                area = entity.get("area_name", "no area")
                memory_boost = " [MEMORY]" if entity.get("_memory_boosted") else ""
                cluster_context = " [CLUSTER]" if entity.get("_cluster_context") else ""
                print(
                    f"  {i}. {entity_id} (score: {score:.3f}) - {area}{memory_boost}{cluster_context}"
                )

        # Display diagnostics if available
        diagnostics = result.get("diagnostics", {})
        if diagnostics:
            print("\n🔬 Workflow Diagnostics:")
            print("-" * 25)
            overall_quality = diagnostics.get("overall_quality", 0.0)
            print(f"  Overall Quality: {overall_quality:.2f}")

            component_scores = {
                "Conversation Analysis": diagnostics.get(
                    "conversation_analysis_quality", 0.0
                ),
                "Scope Detection": diagnostics.get("scope_detection_quality", 0.0),
                "Entity Retrieval": diagnostics.get("entity_retrieval_quality", 0.0),
                "Context Formatting": diagnostics.get(
                    "context_formatting_quality", 0.0
                ),
            }

            for component, score in component_scores.items():
                print(f"  {component}: {score:.2f}")

            recommendations = diagnostics.get("recommendations", [])
            if recommendations:
                print("\n💡 Recommendations:")
                for rec in recommendations[:3]:
                    print(f"    • {rec}")

        print("\n✅ Workflow completed successfully!")
        return result

    except Exception as e:
        logger.error(f"Workflow debugging failed: {e}")
        print(f"\n❌ Workflow failed: {e}")
        return None


async def interactive_debugging():
    """Interactive debugging session."""
    print("🔧 Interactive LangGraph Workflow Debugging")
    print("Type 'exit' to quit, 'help' for commands")

    session_id = f"interactive_debug_{int(time.time())}"

    while True:
        try:
            query = input("\n🤖 Enter your query (Hungarian/English): ").strip()

            if query.lower() == "exit":
                print("Goodbye! 👋")
                break
            elif query.lower() == "help":
                print(
                    """
Available commands:
  - Any Home Assistant query (e.g. 'mi van a nappaliban?', 'kapcsold fel a lámpát')
  - 'exit' - quit the debugger
  - 'help' - show this help message
  
Example queries:
  - 'mi van a nappaliban?' (overview query)
  - 'kapcsold fel a lámpát' (control query) 
  - 'hány fok van?' (specific value query)
  - 'termel a napelem?' (solar performance query)
                """
                )
                continue
            elif not query:
                continue

            print(f"\n🔄 Processing: {query}")
            result = await debug_workflow_step_by_step(query, session_id)

            if result:
                print("\n⏭️  Ready for next query...")
            else:
                print("\n❌ Query failed, but you can try another one...")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Command line mode
        query = " ".join(sys.argv[1:])
        asyncio.run(debug_workflow_step_by_step(query))
    else:
        # Interactive mode
        asyncio.run(interactive_debugging())
