# LangGraph Migration Plan - HA RAG System

## Executive Summary

Migrate the current Home Assistant RAG bridge from manual service orchestration to LangGraph-based workflow management. This addresses current pain points:

- ❌ Hard-coded scope detection (regex patterns)
- ❌ Manual state passing between services  
- ❌ Complex conversation memory handling
- ❌ Limited error recovery and fallbacks
- ❌ Difficult observability and debugging

## Current Architecture Analysis

### Current Flow
```
User Query → LiteLLM Hook → Bridge → Services → Main LLM → Tool Execution
                ↓              ↓        ↓          ↓         ↓
            Extract msg    Scope Det.  Entity    Format   HA API
                          Conv. Ctx    Retrieval  Context   Calls
                                      Reranking
```

### Current Services (to be migrated)
```python
# app/services/
├── conversation_analyzer.py      # → ConversationAnalysisNode
├── query_scope_detector.py       # → ScopeDetectionNode  
├── entity_reranker.py           # → EntityRerankingNode
├── retrieve_entities.py         # → EntityRetrievalNode
└── [formatter logic]            # → ContextFormattingNode
```

## LangGraph Architecture Design

### Core State Schema
```python
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph
from enum import Enum

class QueryScope(Enum):
    MICRO = "micro"      # k=5-10, specific actions
    MACRO = "macro"      # k=15-30, area-based  
    OVERVIEW = "overview" # k=30-50, house-wide

class RAGState(TypedDict):
    # Input
    user_query: str
    session_id: str
    conversation_history: List[Dict[str, Any]]
    
    # Analysis Results
    conversation_context: Optional[Dict[str, Any]]
    detected_scope: Optional[QueryScope]
    scope_confidence: float
    
    # Entity Retrieval
    retrieved_entities: List[Dict[str, Any]]
    cluster_entities: List[Dict[str, Any]]
    reranked_entities: List[Dict[str, Any]]
    
    # Context Building
    formatted_context: str
    formatter_type: str
    
    # LLM Integration
    llm_messages: List[Dict[str, str]]
    llm_response: Optional[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    
    # Execution Results
    ha_results: List[Dict[str, Any]]
    final_response: Optional[str]
    
    # Error Handling
    errors: List[str]
    retry_count: int
    fallback_used: bool
```

### Node Architecture

#### 1. ConversationAnalysisNode
```python
async def analyze_conversation_node(state: RAGState) -> RAGState:
    """Analyze conversation context and extract metadata."""
    analyzer = ConversationAnalyzer()
    context = analyzer.analyze_conversation(
        state["user_query"], 
        state["conversation_history"]
    )
    
    return {
        **state,
        "conversation_context": context,
    }
```

#### 2. ScopeDetectionNode (LLM-based)
```python
async def detect_scope_node(state: RAGState) -> RAGState:
    """LLM-based scope detection replacing regex patterns."""
    
    prompt = f"""Classify this smart home query scope:
    
    Query: "{state['user_query']}"
    Context: Areas: {state.get('conversation_context', {}).get('areas_mentioned', [])}
             Domains: {state.get('conversation_context', {}).get('domains_mentioned', [])}
             Is follow-up: {state.get('conversation_context', {}).get('is_follow_up', False)}
    
    Return JSON:
    {{
        "scope": "micro|macro|overview",
        "confidence": 0.0-1.0,
        "reasoning": "explanation",
        "optimal_k": 5-50
    }}
    
    Rules:
    - micro: Single device/entity actions (turn on, check temperature)  
    - macro: Room/area-based queries (living room status, kitchen lights)
    - overview: House-wide queries (energy summary, all sensors)
    """
    
    # Call local LLM for classification
    result = await llm_classify(prompt)
    
    return {
        **state,
        "detected_scope": QueryScope(result["scope"]),
        "scope_confidence": result["confidence"],
        "optimal_k": result["optimal_k"]
    }
```

#### 3. EntityRetrievalNode (with clustering)
```python
async def retrieve_entities_node(state: RAGState) -> RAGState:
    """Cluster-first entity retrieval with vector fallback."""
    
    # Cluster-based retrieval
    cluster_entities = await retrieve_from_clusters(
        state["user_query"],
        state["detected_scope"],
        state["session_id"]
    )
    
    # Vector search fallback
    vector_entities = await retrieve_from_vector_search(
        state["user_query"],
        k=state.get("optimal_k", 20)
    )
    
    return {
        **state,
        "cluster_entities": cluster_entities,
        "retrieved_entities": vector_entities
    }
```

#### 4. EntityRerankingNode
```python
async def rerank_entities_node(state: RAGState) -> RAGState:
    """Cross-encoder reranking with conversation boosting."""
    
    # Combine cluster + vector entities
    all_entities = state["cluster_entities"] + state["retrieved_entities"]
    
    # Apply conversation context boosting
    reranked = await rerank_with_conversation_boost(
        all_entities,
        state["user_query"],
        state["conversation_context"],
        state["session_id"]
    )
    
    return {
        **state,
        "reranked_entities": reranked
    }
```

#### 5. ContextFormattingNode
```python
async def format_context_node(state: RAGState) -> RAGState:
    """Smart context formatting based on scope."""
    
    formatter_map = {
        QueryScope.MICRO: "detailed",
        QueryScope.MACRO: "grouped_by_area", 
        QueryScope.OVERVIEW: "tldr"
    }
    
    formatter = formatter_map[state["detected_scope"]]
    formatted_context = await format_entities(
        state["reranked_entities"],
        formatter_type=formatter
    )
    
    return {
        **state,
        "formatted_context": formatted_context,
        "formatter_type": formatter
    }
```

#### 6. LLMInteractionNode
```python
async def llm_interaction_node(state: RAGState) -> RAGState:
    """Build messages and call main LLM."""
    
    # Build cache-friendly messages (entities in user message)
    messages = [
        {"role": "system", "content": STATIC_SYSTEM_PROMPT},
        {"role": "user", "content": f"{state['formatted_context']}\n\nUser Query: {state['user_query']}"}
    ]
    
    # Add conversation history
    if state["conversation_history"]:
        messages = build_conversation_messages(messages, state["conversation_history"])
    
    # Call main LLM
    response = await call_main_llm(messages)
    
    return {
        **state,
        "llm_messages": messages,
        "llm_response": response,
        "tool_calls": extract_tool_calls(response)
    }
```

#### 7. ToolExecutionNode
```python
async def execute_tools_node(state: RAGState) -> RAGState:
    """Execute Home Assistant tool calls."""
    
    if not state["tool_calls"]:
        return state
    
    # Filter HA tools
    ha_tools = filter_ha_tools(state["tool_calls"])
    
    # Execute via HA API
    results = await execute_ha_tools(ha_tools)
    
    return {
        **state,
        "ha_results": results,
        "final_response": format_final_response(state["llm_response"], results)
    }
```

### Conditional Routing Logic

```python
def route_after_scope_detection(state: RAGState) -> str:
    """Route based on detected scope and confidence."""
    
    if state["scope_confidence"] < 0.6:
        return "fallback_scope_detection"  # Regex backup
    
    scope = state["detected_scope"]
    if scope == QueryScope.MICRO:
        return "micro_entity_retrieval"
    elif scope == QueryScope.MACRO:
        return "macro_entity_retrieval"
    else:
        return "overview_entity_retrieval"

def should_retry_retrieval(state: RAGState) -> str:
    """Retry logic for failed entity retrieval."""
    
    if not state["retrieved_entities"] and state["retry_count"] < 2:
        return "retry_retrieval"
    elif not state["retrieved_entities"]:
        return "fallback_retrieval"
    else:
        return "continue_to_reranking"

def needs_tool_execution(state: RAGState) -> str:
    """Check if tool execution is needed."""
    
    if state["tool_calls"]:
        return "execute_tools"
    else:
        return "finalize_response"
```

### Complete Workflow Graph

```python
def create_rag_workflow() -> StateGraph:
    """Create the complete RAG workflow graph."""
    
    workflow = StateGraph(RAGState)
    
    # Add all nodes
    workflow.add_node("analyze_conversation", analyze_conversation_node)
    workflow.add_node("detect_scope", detect_scope_node)
    workflow.add_node("retrieve_entities", retrieve_entities_node)
    workflow.add_node("rerank_entities", rerank_entities_node)
    workflow.add_node("format_context", format_context_node)
    workflow.add_node("llm_interaction", llm_interaction_node)
    workflow.add_node("execute_tools", execute_tools_node)
    
    # Error handling and fallback nodes
    workflow.add_node("fallback_scope_detection", fallback_scope_node)
    workflow.add_node("retry_retrieval", retry_retrieval_node)
    workflow.add_node("fallback_retrieval", fallback_retrieval_node)
    
    # Define the main flow
    workflow.set_entry_point("analyze_conversation")
    workflow.add_edge("analyze_conversation", "detect_scope")
    
    # Conditional routing after scope detection
    workflow.add_conditional_edges(
        "detect_scope",
        route_after_scope_detection,
        {
            "micro_entity_retrieval": "retrieve_entities",
            "macro_entity_retrieval": "retrieve_entities", 
            "overview_entity_retrieval": "retrieve_entities",
            "fallback_scope_detection": "fallback_scope_detection"
        }
    )
    
    # Retrieval retry logic
    workflow.add_conditional_edges(
        "retrieve_entities",
        should_retry_retrieval,
        {
            "retry_retrieval": "retry_retrieval",
            "fallback_retrieval": "fallback_retrieval",
            "continue_to_reranking": "rerank_entities"
        }
    )
    
    # Main flow continuation
    workflow.add_edge("rerank_entities", "format_context")
    workflow.add_edge("format_context", "llm_interaction")
    
    # Tool execution logic
    workflow.add_conditional_edges(
        "llm_interaction",
        needs_tool_execution,
        {
            "execute_tools": "execute_tools",
            "finalize_response": END
        }
    )
    
    workflow.add_edge("execute_tools", END)
    
    return workflow.compile()
```

## Integration Points

### 1. LiteLLM Hook Integration
```python
# litellm_ha_rag_hooks.py
async def async_pre_call_hook(self, data: dict, call_type: str) -> Dict[str, Any]:
    """Modified hook to use LangGraph workflow."""
    
    # Extract inputs  
    messages = data.get("messages", [])
    user_question, conversation_context = _extract_user_question_and_context(messages)
    session_id = _extract_stable_session_id(data, messages)
    
    # Initialize workflow state
    initial_state = {
        "user_query": user_question,
        "session_id": session_id,
        "conversation_history": conversation_context,
        "errors": [],
        "retry_count": 0,
        "fallback_used": False
    }
    
    # Run LangGraph workflow
    workflow = create_rag_workflow()
    final_state = await workflow.ainvoke(initial_state)
    
    # Inject formatted context into user message
    messages[user_idx]["content"] = f"{final_state['formatted_context']}\n\nUser Query: {user_question}"
    data["messages"] = messages
    
    return data
```

### 2. Conversation Memory Integration
```python
# Enhanced with LangGraph memory persistence
from langgraph.checkpoint.memory import MemorySaver

# Persistent memory for conversation state
memory = MemorySaver()

workflow = create_rag_workflow().with_memory(
    memory,
    thread_id=session_id
)
```

### 3. ArangoDB Integration
```python
# Enhanced cluster and entity retrieval nodes
async def retrieve_from_clusters(query: str, scope: QueryScope, session_id: str):
    """Cluster-first retrieval with session context."""
    
    # Get previous entities from conversation memory
    previous_entities = await get_conversation_entities(session_id)
    
    # Boost relevant clusters
    relevant_clusters = await find_relevant_clusters(
        query, scope, previous_entities
    )
    
    return await retrieve_cluster_entities(relevant_clusters)
```

## Migration Strategy

### Phase 1: Foundation Setup (Week 1-2)
1. **Install LangGraph dependencies**
   ```bash
   poetry add langgraph langchain-core langchain-community
   ```

2. **Create basic state schema and first nodes**
   - RAGState definition
   - ConversationAnalysisNode (port existing logic)
   - ScopeDetectionNode (LLM-based replacement)

3. **Build simple linear workflow**  
   - No conditional routing yet
   - Single path: analyze → scope → retrieve → format

### Phase 2: Core Workflow (Week 3-4)  
1. **Implement all core nodes**
   - EntityRetrievalNode with clustering
   - EntityRerankingNode with conversation boosting
   - ContextFormattingNode with scope-aware formatting
   - LLMInteractionNode

2. **Add conditional routing**
   - Scope-based retrieval routing  
   - Error handling and retry logic
   - Tool execution branching

3. **Integration with existing bridge**
   - Modify LiteLLM hook to use workflow
   - Maintain backward compatibility

### Phase 3: Advanced Features (Week 5-6)
1. **Conversation memory persistence**
   - LangGraph memory integration
   - Session-based entity boosting
   - TTL-based cleanup

2. **Observability and monitoring** 
   - LangSmith integration for tracing
   - Performance metrics collection
   - Error tracking and alerting

3. **Optimization and tuning**
   - Node performance optimization
   - Caching strategies
   - Parallel execution where possible

### Phase 4: Testing and Rollout (Week 7-8)
1. **Comprehensive testing**
   - Unit tests for each node
   - Integration tests for full workflow  
   - Performance benchmarking

2. **Gradual rollout**
   - A/B testing with current system
   - Monitoring and adjustment
   - Full cutover

## Benefits Expected

### 1. Maintainability
- **Clean separation of concerns** - each node has single responsibility
- **Testable components** - easy unit testing of individual nodes
- **Reusable logic** - nodes can be shared across workflows

### 2. Reliability  
- **Robust error handling** - automatic retries and fallbacks
- **State persistence** - conversation memory across failures
- **Observability** - complete workflow tracing

### 3. Performance
- **Parallel execution** - independent nodes can run concurrently
- **Smart caching** - LangGraph handles state and result caching
- **Efficient routing** - avoid unnecessary work with conditional edges

### 4. Scalability
- **Easy to extend** - add new nodes without changing existing ones
- **A/B testing** - route different users to different workflows  
- **Multi-model support** - easy to swap LLM providers

## Risk Assessment

### Technical Risks
- **Learning curve** - team needs to learn LangGraph concepts
- **Migration complexity** - ensuring feature parity during transition
- **Dependency risk** - adding LangGraph as critical dependency

### Mitigation Strategies  
- **Parallel development** - build LangGraph version alongside current
- **Feature flagging** - gradual rollout with fallback to old system
- **Comprehensive testing** - ensure no regression in functionality

## Success Metrics

### Functional Metrics
- **Scope detection accuracy** - target >90% vs current ~67%
- **Entity retrieval precision** - maintain or improve current metrics
- **Response latency** - target <5% increase from LLM classification overhead

### Operational Metrics  
- **Error rate** - target 50% reduction with better error handling
- **Debugging time** - target 60% reduction with workflow tracing
- **Feature development speed** - target 40% improvement with modular architecture

## Conclusion

LangGraph migration represents a significant architectural upgrade that addresses current technical debt while providing a foundation for advanced features like robust conversation memory, intelligent routing, and sophisticated error recovery.

The gradual migration approach minimizes risk while maximizing learning and adaptation opportunities. Expected completion: 8 weeks with immediate benefits starting from Phase 2.

---

**Next Steps:**
1. Approve migration plan and timeline
2. Set up development environment with LangGraph
3. Begin Phase 1 implementation with basic state schema
4. Create PoC of scope detection node replacement

**Documentation Status:** ✅ Complete architectural plan documented
**Review Required:** Architecture review and implementation timeline approval