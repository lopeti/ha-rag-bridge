# Conversation RAG Strategies

## 🎯 Overview

This implementation introduces a strategy pattern for RAG (Retrieval Augmented Generation) pipelines, allowing flexible experimentation with different approaches to conversation-based entity search.

## 📊 Status: 🚧 In Development

- **Started**: 2025-08-23
- **Current Phase**: Implementation
- **Target**: Replace single-query pipeline with conversation-aware search

## 🔍 Problem Statement

### Current Issues
1. **Meta-task prompt handling**: OpenWebUI sends tag generation prompts instead of user queries
2. **Single-query limitation**: Cannot handle multi-turn conversations effectively
3. **Context loss**: Assistant messages ignored in search context
4. **Fixed pipeline**: Difficult to experiment with new approaches

### Example Problem
```
Input: "### Task: Generate 1-3 broad tags... USER: Hány fok van a nappaliban?"
Current result: mold_indicator (wrong entity due to meta-task text)
Expected: sensor.nappali_homerseklet
```

## 🏗️ Architecture

### Strategy Pattern Implementation
```
app/
├── rag_strategies/
│   ├── __init__.py              # Strategy registry
│   ├── base.py                  # Protocol definition  
│   ├── legacy_workflow.py       # Current LangGraph pipeline
│   ├── hybrid_embedding.py      # New conversation-aware search
│   ├── cluster_enhanced.py      # Future: cluster integration
│   └── experimental.py          # Playground for new ideas
├── conversation_utils/
│   ├── __init__.py
│   ├── message_parser.py        # OpenWebUI format parsing
│   └── embedding_utils.py       # Weighted embedding creation
└── config/litellm/
    └── litellm_hook.py          # Updated to use strategies
```

### Strategy Interface
```python
from typing import Protocol, List, Dict, Any

class RAGStrategy(Protocol):
    """Minimal interface for RAG strategies"""
    
    async def search(
        self, 
        messages: List[Dict[str, str]], 
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            config: Strategy configuration
            
        Returns:
            List of ranked entities with scores
        """
        ...
```

## 📋 Strategies

### 1. Legacy Workflow Strategy
- **Purpose**: Maintain backward compatibility
- **Approach**: Use existing LangGraph pipeline with first message only
- **Performance**: ~500ms for single query
- **Status**: ✅ Working (current system)

### 2. Hybrid Embedding Strategy  
- **Purpose**: Conversation-aware search with single embedding
- **Approach**: Weight and combine all messages into unified embedding
- **Performance**: ~500ms for entire conversation
- **Status**: 🚧 In Development

**Implementation concept:**
```python
async def hybrid_search(messages: List[Dict]) -> List[Entity]:
    # 1. Parse OpenWebUI format
    parsed_messages = extract_messages_from_meta_task(raw_input)
    
    # 2. Weight messages by recency and role
    weighted_texts = []
    for i, msg in enumerate(messages[-3:]):  # Last 3 messages
        recency_weight = 1.0 + (i * 0.3)
        role_weight = 1.0 if msg['role'] == 'user' else 0.5
        
        weighted_texts.append(msg['content'] * recency_weight * role_weight)
    
    # 3. Single embedding for efficiency  
    combined_text = ' [SEP] '.join(weighted_texts)
    embedding = embed(combined_text)
    
    # 4. Standard vector search
    return await vector_search(embedding, k=30)
```

### 3. Cluster Enhanced Strategy (Future)
- **Purpose**: Combine conversation search with cluster guarantees
- **Approach**: Hybrid embedding + cluster detection + priority merge
- **Performance**: ~550ms (parallel cluster + vector)
- **Status**: 📋 Planned

### 4. Experimental Strategy
- **Purpose**: Rapid prototyping of new ideas
- **Approach**: Flexible playground for testing concepts
- **Status**: 📋 Ready for experiments

## 🔄 Implementation Phases

### Phase 1: Core Infrastructure ✅
- [x] Create feature branch
- [x] Documentation setup
- [ ] Strategy registry implementation
- [ ] Message parser for OpenWebUI format
- [ ] Basic hybrid embedding strategy

### Phase 2: Integration
- [ ] Update LiteLLM hook to use strategies
- [ ] Strategy selection logic (env var + header override)
- [ ] Metrics collection per strategy
- [ ] A/B testing framework

### Phase 3: Testing & Optimization
- [ ] Performance benchmarking
- [ ] Accuracy testing with real queries
- [ ] Strategy comparison metrics
- [ ] Documentation updates

### Phase 4: Advanced Features
- [ ] Cluster enhanced strategy
- [ ] Dynamic strategy selection
- [ ] Query pattern learning
- [ ] Advanced metrics dashboard

## 🧪 Test Scenarios

### 1. Single Turn Queries
```
Input: "Hány fok van a nappaliban?"
Expected: sensor.nappali_homerseklet (primary)
```

### 2. Multi-turn Conversations
```
Messages:
- User: "Hány fok van a nappaliban?"
- Assistant: "23 fok van. Érdekel a kert hőmérséklete is?"
- User: "Igen"

Expected: Both nappali and kert temperature sensors
```

### 3. OpenWebUI Meta-task Handling
```
Input: "### Task: Generate tags... USER: Hány fok van? ..."
Expected: Extract "Hány fok van?" and find temperature sensors
```

### 4. Context Awareness
```
Messages:
- User: "Mi a helyzet otthon?"
- Assistant: "Minden rendben. 22 fok a nappaliban."
- User: "És kint?"

Expected: Outdoor temperature sensors (context from assistant message)
```

## 📈 Success Metrics

### Performance Targets
- **Latency**: < 600ms per strategy
- **Accuracy**: > 90% correct entity ranking for test queries
- **Throughput**: Handle 10+ concurrent requests

### Quality Metrics
- **Precision**: Relevant entities in top 5 results
- **Recall**: Critical entities not missed
- **Context Awareness**: Multi-turn query resolution accuracy

### Operational Metrics
- **Strategy Usage**: Distribution across different strategies
- **Error Rate**: < 1% failures
- **A/B Test Results**: Conversion metrics per strategy

## 🔄 Migration Strategy

### Week 1: Development
- Implement strategies on feature branch
- Unit testing and basic integration

### Week 2: Testing
- Deploy to staging environment
- Performance and accuracy testing
- Bug fixes and optimization

### Week 3: Staged Rollout
- Deploy with feature flag (10% -> 50% -> 100%)
- Monitor metrics and user feedback
- A/B test between strategies

### Week 4: Full Migration
- Default to best performing strategy
- Deprecate legacy pipeline
- Clean up unused code

## 🛠️ Configuration

### Environment Variables
```bash
# Strategy selection
RAG_STRATEGY=hybrid              # Default strategy
RAG_ENABLE_AB_TESTING=true       # Enable A/B testing

# Strategy-specific settings  
HYBRID_MAX_MESSAGES=5            # Max conversation history
HYBRID_USER_WEIGHT=1.0           # User message weight
HYBRID_ASSISTANT_WEIGHT=0.5      # Assistant message weight
HYBRID_RECENCY_BOOST=0.3         # Recency multiplier

# Experimental features
RAG_ENABLE_CLUSTERS=false        # Cluster integration
RAG_LOG_STRATEGY_METRICS=true    # Detailed logging
```

### Request Headers (for testing)
```
X-RAG-Strategy: experimental     # Override default strategy
X-RAG-Debug: true               # Enable debug output
```

## 📚 API Changes

### New Hook Behavior
```python
# Before: Single message processing
process_query("Hány fok van?")

# After: Message list processing with strategy
process_conversation([
    {"role": "user", "content": "Hány fok van?"},
    {"role": "assistant", "content": "23 fok van."},
    {"role": "user", "content": "És kint?"}
], strategy="hybrid")
```

### Backward Compatibility
- Legacy single-query format still supported
- Automatic detection of OpenWebUI meta-task prompts
- Graceful degradation if strategy fails

## 🔍 Debug Features

### Strategy Metrics Endpoint
```
GET /admin/debug/strategy-metrics
{
  "current_strategy": "hybrid",
  "last_24h_requests": {
    "hybrid": 1240,
    "legacy": 86,
    "experimental": 12
  },
  "average_latency": {
    "hybrid": "487ms",
    "legacy": "523ms"
  },
  "accuracy_scores": {
    "hybrid": 0.94,
    "legacy": 0.87
  }
}
```

### Conversation Debug
```
POST /admin/debug/conversation-search
{
  "messages": [...],
  "strategy": "hybrid",
  "show_weights": true,
  "show_intermediate_results": true
}
```

## 🎯 Next Steps

1. **Implement strategy registry and hybrid strategy**
2. **Test with real OpenWebUI queries**
3. **Compare performance with legacy pipeline**
4. **Iterate based on results**
5. **Plan cluster integration**

## 📝 Notes

- Keep strategies lightweight and focused
- Prioritize performance and maintainability
- Use clear naming conventions
- Document all configuration options
- Plan for easy rollback if needed

---

*Last updated: 2025-08-23*
*Status: Active Development*