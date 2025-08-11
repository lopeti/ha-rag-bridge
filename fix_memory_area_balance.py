#!/usr/bin/env python3
"""Fix memory vs area boosting balance."""

# Read the entity reranker file
with open('/app/app/services/entity_reranker.py', 'r') as f:
    content = f.read()

# Find the area boosting section and make it stronger
old_boosting = """        # Calculate final score - additive instead of multiplicative to handle zero base scores
        final_score = base_score + context_boost"""

new_boosting = """        # Calculate final score with enhanced area boosting when areas are mentioned
        areas_mentioned = context.areas_mentioned if hasattr(context, 'areas_mentioned') else set()
        
        # If areas are explicitly mentioned and this entity matches, apply multiplicative area boost
        entity_area = entity.get("area") or ""
        area_match = False
        if entity_area and areas_mentioned:
            entity_area_lower = entity_area.lower()
            area_match = any(area.lower() == entity_area_lower or area.lower() in entity_area_lower 
                           for area in areas_mentioned)
        
        if area_match and base_score > 0:
            # For area matches with explicit mentions, use multiplicative boosting to compete with memory
            area_multiplier = 1.0 + (context_boost * 0.5)  # Convert additive to multiplicative boost
            final_score = base_score * area_multiplier
        else:
            # Default additive boosting for other cases
            final_score = base_score + context_boost"""

# Apply the fix
if old_boosting in content:
    new_content = content.replace(old_boosting, new_boosting)
    
    with open('/app/app/services/entity_reranker.py', 'w') as f:
        f.write(new_content)
    
    print("✅ Successfully applied memory vs area boosting balance fix!")
    print("Area matches will now use multiplicative boosting to compete with memory entities.")
else:
    print("❌ Could not find the target boosting code")
    print("The code structure may have changed")