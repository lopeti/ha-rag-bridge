#!/usr/bin/env python3
"""Clean LangGraph Phase 3 workflow debugger with minimal noise."""

import asyncio
import os
import sys
import time
import logging
from typing import Dict, Any

# Suppress verbose logging
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from app.langgraph_workflow.workflow import run_rag_workflow
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)

# Suppress HA RAG bridge verbose logging
logging.getLogger("ha_rag_bridge").setLevel(logging.WARNING)
logging.getLogger("app").setLevel(logging.WARNING)


async def debug_workflow_clean(query: str, session_id: str = "debug_session"):
    """Clean workflow debugging with focus on results."""
    
    print("🚀 LangGraph Phase 3 Workflow Debugger (Clean)")
    print("=" * 60)
    print(f"Query: '{query}'")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        print("⏳ Running workflow...")
        
        # Redirect stdout to suppress model loading noise
        original_stdout = sys.stdout
        if not os.getenv("DEBUG_VERBOSE"):
            sys.stdout = open(os.devnull, 'w')
        
        try:
            result = await run_rag_workflow(
                user_query=query,
                session_id=session_id,
                conversation_history=[]
            )
        finally:
            if not os.getenv("DEBUG_VERBOSE"):
                sys.stdout.close()
                sys.stdout = original_stdout
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Completed in {duration:.2f}s")
        print("\n📊 WORKFLOW RESULTS:")
        print("=" * 40)
        
        # 🗣️ Conversation Analysis
        conv_ctx = result.get("conversation_context", {})
        print(f"🗣️  Conversation Analysis:")
        print(f"    Areas: {', '.join(conv_ctx.get('areas_mentioned', []))}")
        print(f"    Domains: {', '.join(conv_ctx.get('domains_mentioned', []))}")
        print(f"    Intent: {conv_ctx.get('intent', 'unknown')} (conf: {conv_ctx.get('confidence', 0):.1f})")
        
        # 🎯 Scope Detection
        scope = str(result.get("detected_scope", "unknown")).replace("QueryScope.", "")
        print(f"\n🎯 Scope Detection: {scope.upper()}")
        print(f"    Confidence: {result.get('scope_confidence', 0):.2f}")
        print(f"    Optimal K: {result.get('optimal_k', 0)}")
        reasoning = result.get("scope_reasoning", "")
        if reasoning:
            print(f"    Logic: {reasoning}")
        
        # 🔍 Entity Retrieval Summary
        entities = result.get("retrieved_entities", [])
        cluster_entities = result.get("cluster_entities", [])
        memory_entities = result.get("memory_entities", [])
        memory_boosted = [e for e in entities if e.get("_memory_boosted")]
        
        print(f"\n🔍 Entity Retrieval:")
        print(f"    Total: {len(entities)} entities")
        print(f"    Clusters: {len(cluster_entities)} | Memory: {len(memory_entities)} | Boosted: {len(memory_boosted)}")
        
        # 📝 Context Formatting
        formatter_type = result.get("formatter_type", "unknown")
        context_len = len(result.get("formatted_context", ""))
        
        # Count actual entities injected into prompt
        formatted_context = result.get("formatted_context", "")
        lines = formatted_context.split('\n')
        primary_line = next((line for line in lines if line.startswith('Primary:')), "")
        related_line = next((line for line in lines if line.startswith('Related:')), "")
        
        primary_count = primary_line.count(' | ') + 1 if primary_line and ':' in primary_line else 0
        related_count = related_line.count(' | ') + 1 if related_line and ':' in related_line else 0
        total_injected = primary_count + related_count
        
        print(f"\n📝 Context Formatting: {formatter_type} ({context_len} chars)")
        print(f"    Entities in final prompt: {total_injected} ({primary_count} primary + {related_count} related)")
        
        # 🏠 Top Entities (only show meaningful ones)
        relevant_entities = [e for e in entities[:8] if e.get("_score", 0) > 0.1 or e.get("_memory_boosted")]
        if not relevant_entities:
            relevant_entities = entities[:5]  # Show top 5 even if low scores
            
        print(f"\n🏠 Top Retrieved Entities:")
        if relevant_entities:
            for i, entity in enumerate(relevant_entities, 1):
                entity_id = entity.get("entity_id", "unknown")
                score = entity.get("_score", 0.0)
                area = entity.get("area_name") or entity.get("area") or "no area"
                
                badges = []
                if entity.get("_memory_boosted"):
                    badges.append("MEM")
                if entity.get("_cluster_context"):
                    badges.append("CLUSTER") 
                badge_str = f" [{'/'.join(badges)}]" if badges else ""
                
                # Highlight good scores
                score_indicator = "🔥" if score > 0.7 else "⭐" if score > 0.4 else "📍"
                
                # Get ranking factors for zombie detection
                rf = entity.get("_ranking_factors", {})
                active_val = rf.get("has_active_value", 0)
                unavail_penalty = rf.get("unavailable_penalty", 0)
                status_indicator = ""
                if active_val > 0:
                    status_indicator = " ✅"
                elif unavail_penalty < 0:
                    status_indicator = " 🧟"  # zombie
                
                # Get clean name to understand relevance
                try:
                    from app.services.entity_reranker import entity_reranker
                    clean_name = entity_reranker.SystemPromptFormatter._get_clean_name(entity)
                except:
                    clean_name = "N/A"
                
                print(f"    {i}. {score_indicator} {entity_id}{status_indicator}")
                print(f"        Score: {score:.3f} | Area: {area} | Clean Name: '{clean_name}'{badge_str}")
        else:
            print("    ❌ No relevant entities found")
        
        # ⚠️ Issues & Diagnostics
        errors = result.get("errors", [])
        diagnostics = result.get("diagnostics", {})
        
        if errors or diagnostics:
            print(f"\n⚠️  Issues & Quality:")
            
            if errors:
                print(f"    Errors: {len(errors)}")
                for error in errors[:2]:
                    print(f"      • {error}")
            
            if diagnostics:
                overall = diagnostics.get("overall_quality", 0.0)
                print(f"    Overall Quality: {overall:.2f}/1.0")
                
                # Component breakdown
                components = {
                    "Conv": diagnostics.get("conversation_analysis_quality", 0.0),
                    "Scope": diagnostics.get("scope_detection_quality", 0.0),
                    "Entities": diagnostics.get("entity_retrieval_quality", 0.0),
                    "Format": diagnostics.get("context_formatting_quality", 0.0)
                }
                component_str = " | ".join([f"{k}:{v:.1f}" for k,v in components.items()])
                print(f"    Components: {component_str}")
                
                # Recommendations
                recommendations = diagnostics.get("recommendations", [])
                if recommendations:
                    print(f"    💡 Suggestions:")
                    for rec in recommendations[:2]:
                        print(f"      • {rec}")
        
        # 📋 Quick Analysis
        print(f"\n📋 Quick Analysis:")
        
        # Check for common issues
        issues = []
        if len([e for e in entities[:5] if e.get("_score", 0) > 0.3]) == 0:
            issues.append("Low semantic similarity scores")
        
        if len(cluster_entities) == 0:
            issues.append("No semantic clusters found")
            
        if len([e for e in entities[:10] if e.get("area_name") or e.get("area")]) < 3:
            issues.append("Poor area mapping")
        
        if issues:
            print("    ⚠️  Potential Issues:")
            for issue in issues:
                print(f"      • {issue}")
        else:
            print("    ✅ Workflow operating normally")
        
        # 💬 Final System Prompt (truncated for readability)
        final_prompt = result.get("formatted_context", "")
        if final_prompt:
            print(f"\n💬 Final System Prompt Injection:")
            print("=" * 50)
            # Show first 1500 chars to see structure but not overwhelm
            if len(final_prompt) > 1500:
                print(final_prompt[:1500] + f"\n... [truncated, total: {len(final_prompt)} chars]")
            else:
                print(final_prompt)
            print("=" * 50)
        
        return result
        
    except Exception as e:
        logger.error(f"Clean workflow debugging failed: {e}")
        print(f"\n❌ Workflow failed: {e}")
        return None


async def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        await debug_workflow_clean(query)
    else:
        print("Usage: python debug_workflow_clean.py 'your query here'")
        print("Example: python debug_workflow_clean.py 'hány fok van a nappaliban?'")


if __name__ == "__main__":
    asyncio.run(main())