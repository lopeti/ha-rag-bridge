#!/usr/bin/env python3
"""Fix to enable area-based entity boosting in context formatting node."""


# Read the current file
with open("/app/app/langgraph_workflow/nodes.py", "r") as f:
    content = f.read()

# Find the problematic section and replace it
old_code = """        # Convert retrieved entities to EntityScore format for compatibility
        entity_scores = []
        for entity in retrieved_entities:
            # Create a mock EntityScore-like object that has the .entity attribute
            class MockEntityScore:
                def __init__(self, entity_data):
                    self.entity = entity_data
                    self.base_score = entity_data.get("_score", 0.0)
                    self.context_boost = entity_data.get("_cluster_context", {}).get(
                        "context_boost", 0.0
                    )
                    self.final_score = self.base_score + self.context_boost
                    self.ranking_factors = {}

            entity_scores.append(MockEntityScore(entity))

        # Sort by final score
        entity_scores.sort(key=lambda x: x.final_score, reverse=True)"""

new_code = """        # Use actual entity reranker with area boosting
        conversation_history = state.get("conversation_history", [])
        user_query = state.get("user_query", "")
        session_id = state.get("session_id")
        
        logger.info(f"ContextFormatting: Reranking {len(retrieved_entities)} entities with area boosting")
        
        # Actually call the entity reranker to apply area/domain boosting
        entity_scores = entity_reranker.rank_entities(
            entities=retrieved_entities,
            query=user_query,
            conversation_history=conversation_history,
            conversation_id=session_id,
            k=len(retrieved_entities)  # Don't limit here, we want all scored entities
        )"""

# Apply the fix
if old_code in content:
    new_content = content.replace(old_code, new_code)

    # Write the fixed content
    with open("/app/app/langgraph_workflow/nodes.py", "w") as f:
        f.write(new_content)

    print("✅ Successfully applied area boosting fix!")
    print(
        "The entity reranker will now apply area-based boosting in the context formatting node."
    )
else:
    print("❌ Could not find the target code section to replace")
    print("The code may have already been modified or the structure has changed")
