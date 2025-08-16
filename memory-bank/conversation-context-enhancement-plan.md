# Conversation Context Enhancement Implementation Plan

## Executive Summary

Comprehensive plan to enhance the Home Assistant RAG Bridge with advanced conversation context tracking, query rewriting, and detailed pipeline tracing. The implementation focuses on understanding conversation flow, maintaining topic context, and providing full visibility into the semantic search pipeline.

## Problem Statement

### Current Issues
1. **No Query Rewriting**: Follow-up queries like "És a konyhában?" are not rewritten to full context
2. **Limited Context Tracking**: Only entity-level memory, no topic or conversation theme tracking
3. **Incomplete Pipeline Tracing**: Missing details about vector search, clustering, reranking, and memory boost
4. **OpenWebUI Meta-Tasks**: Tag generation queries pollute traces and confuse debugging
5. **No Local LLM Integration**: Query rewriting defaults to Mistral-7b but not connected to local inference

### Root Cause Analysis
- QueryRewriter service exists but is not integrated into the LangGraph workflow
- ConversationMemory only tracks entities, not conversation themes or topics
- WorkflowTracer captures high-level flow but misses pipeline implementation details
- No conversation summarization or meta-task generation for context understanding

## Solution Architecture

### Core Components

#### 1. Query Rewriting Integration
- **Service**: `ConversationalQueryRewriter`
- **Location**: `app/services/query_rewriter.py`
- **Integration Point**: `conversation_analysis_node` in workflow
- **Local LLM**: Use `home-llama-3b` at `192.168.1.115:8001`

#### 2. Conversation Summarization
- **New Service**: `ConversationSummarizer`
- **Purpose**: Generate topic summaries and track conversation focus
- **Output**: Structured summary with topic, focus, intent, and relevant entities
- **Meta-Task Pattern**: Similar to OpenWebUI's approach but for context understanding

#### 3. Enhanced Memory System
- **Extended ConversationMemory**: Add topic tracking, focus history, intent patterns
- **Smart Boost Calculation**: Topic-aware and time-decay based boosting
- **Contextual Relevance**: Area and domain matching with conversation focus

#### 4. Detailed Pipeline Tracing
- **Cluster Search Details**: Which clusters checked, similarity scores
- **Vector Search Details**: Query embeddings, search parameters, results
- **Memory Boost Details**: Applied boosts, decay factors, relevance scores
- **Reranking Details**: Cross-encoder scores, ranking factors breakdown

## Implementation Details

### Phase 1: Query Rewriter Integration

#### 1.1 Workflow Integration
```python
# app/langgraph_workflow/nodes.py
async def conversation_analysis_node(state: RAGState) -> Dict[str, Any]:
    # Existing conversation analysis...
    
    # NEW: Query rewriting
    query_rewriter = ConversationalQueryRewriter()
    rewrite_result = await query_rewriter.rewrite_query(
        current_query=state["user_query"],
        conversation_history=chat_messages,
        conversation_memory=memory_context
    )
    
    if rewrite_result.method != "no_rewrite_needed":
        state["original_query"] = state["user_query"]
        state["user_query"] = rewrite_result.rewritten_query
        state["query_rewrite_info"] = {
            "original": rewrite_result.original_query,
            "rewritten": rewrite_result.rewritten_query,
            "confidence": rewrite_result.confidence,
            "method": rewrite_result.method,
            "coreferences_resolved": rewrite_result.coreferences_resolved
        }
```

#### 1.2 Local LLM Configuration
```python
# app/services/query_rewriter.py
async def _call_llm_for_rewrite(self, prompt: str) -> str:
    """Call local LLM for query rewriting."""
    import litellm
    
    try:
        response = await litellm.acompletion(
            model=f"openai/{self.model}",
            messages=[
                {"role": "system", "content": "You are a query rewriting assistant."},
                {"role": "user", "content": prompt}
            ],
            api_base=self.settings.query_rewriting_api_base,
            api_key="fake-key",
            temperature=0.3,
            max_tokens=100,
            timeout=self.timeout_ms / 1000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM rewrite failed: {e}")
        return None
```

### Phase 2: Conversation Summarization

#### 2.1 New Service Implementation
```python
# app/services/conversation_summarizer.py
from dataclasses import dataclass
from typing import List, Optional, Set
import json
import litellm

@dataclass
class ConversationSummary:
    """Structured conversation summary."""
    topic: str  # Main conversation topic
    current_focus: str  # Current area/entity of focus
    intent_pattern: str  # Query intent (read, control, monitor)
    topic_domains: Set[str]  # Relevant domains
    context_entities: List[str]  # Important entities in context
    confidence: float

class ConversationSummarizer:
    """LLM-based conversation summarization service."""
    
    SUMMARY_PROMPT_TEMPLATE = """
    Analyze this conversation and provide a structured summary.
    
    ### Conversation History:
    {history}
    
    ### Current Query:
    {query}
    
    ### Previous Memory:
    Areas: {areas}
    Domains: {domains}
    Entities: {entities}
    
    ### Task:
    Generate a JSON summary with:
    1. topic: Main topic being discussed (e.g., "temperature monitoring")
    2. current_focus: Current area or aspect (e.g., "konyha")
    3. intent_pattern: Pattern of queries (e.g., "sequential room queries")
    4. topic_domains: Relevant domains (e.g., ["sensor", "climate"])
    5. context_entities: Important entity IDs
    
    ### Output JSON:
    """
    
    async def generate_summary(
        self,
        query: str,
        history: List[ChatMessage],
        memory: Optional[ConversationMemory] = None
    ) -> ConversationSummary:
        """Generate conversation summary using local LLM."""
        
        prompt = self._build_prompt(query, history, memory)
        
        response = await litellm.acompletion(
            model="openai/home-llama-3b",
            messages=[{"role": "user", "content": prompt}],
            api_base="http://192.168.1.115:8001/v1",
            api_key="fake-key",
            temperature=0.5,
            timeout=1.0
        )
        
        try:
            summary_data = json.loads(response.choices[0].message.content)
            return ConversationSummary(
                topic=summary_data.get("topic", "general"),
                current_focus=summary_data.get("current_focus", ""),
                intent_pattern=summary_data.get("intent_pattern", "read"),
                topic_domains=set(summary_data.get("topic_domains", [])),
                context_entities=summary_data.get("context_entities", []),
                confidence=summary_data.get("confidence", 0.8)
            )
        except json.JSONDecodeError:
            logger.error("Failed to parse summary JSON")
            return self._create_fallback_summary(query, history)
```

### Phase 3: Enhanced Memory System

#### 3.1 Extended ConversationMemory
```python
# app/services/conversation_memory.py
@dataclass
class ConversationMemory:
    """Enhanced conversation memory with topic tracking."""
    
    # Existing fields
    conversation_id: str
    entities: List[ConversationEntity]
    areas_mentioned: Set[str]
    domains_mentioned: Set[str]
    last_updated: datetime
    ttl: datetime
    query_count: int = 1
    
    # NEW fields for topic tracking
    topic_summary: Optional[str] = None
    current_focus: Optional[str] = None
    intent_pattern: Optional[str] = None
    topic_domains: Set[str] = field(default_factory=set)
    focus_history: List[str] = field(default_factory=list)
    conversation_summary: Optional[ConversationSummary] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            # Existing fields...
            "topic_summary": self.topic_summary,
            "current_focus": self.current_focus,
            "intent_pattern": self.intent_pattern,
            "topic_domains": list(self.topic_domains),
            "focus_history": self.focus_history[-10:],  # Keep last 10 focuses
            "conversation_summary": (
                self.conversation_summary.to_dict() 
                if self.conversation_summary else None
            )
        }
```

#### 3.2 Smart Boost Calculation
```python
# app/services/conversation_memory.py
def _calculate_topic_aware_boost(
    self, 
    entity: Dict[str, Any],
    summary: Optional[ConversationSummary] = None
) -> float:
    """Calculate boost weight with topic awareness."""
    
    base_weight = self._calculate_boost_weight(entity)  # Existing boost
    
    if not summary:
        return base_weight
    
    # Topic domain matching
    if entity.get("domain") in summary.topic_domains:
        base_weight *= 1.3  # 30% boost for topic relevance
        logger.debug(f"Topic boost for {entity['entity_id']}: domain match")
    
    # Current focus matching (strongest boost)
    if summary.current_focus:
        entity_area = entity.get("area", "").lower()
        focus_lower = summary.current_focus.lower()
        
        if entity_area == focus_lower:
            base_weight *= 2.0  # 100% boost for focus match
            logger.debug(f"Focus boost for {entity['entity_id']}: area match")
        elif focus_lower in entity.get("entity_id", "").lower():
            base_weight *= 1.5  # 50% boost for partial match
    
    # Intent pattern matching
    if summary.intent_pattern == "control" and entity.get("domain") in ["switch", "light"]:
        base_weight *= 1.2  # 20% boost for control entities
    elif summary.intent_pattern == "monitor" and entity.get("domain") == "sensor":
        base_weight *= 1.2  # 20% boost for sensor entities
    
    # Time decay
    if hasattr(entity, "mentioned_at"):
        time_since = (datetime.now() - entity.mentioned_at).total_seconds()
        decay_factor = math.exp(-time_since / 300)  # 5-minute half-life
        base_weight *= decay_factor
    
    return min(base_weight, 3.0)  # Cap at 3x boost
```

### Phase 4: Pipeline Trace Enhancement

#### 4.1 Detailed Stage Information
```python
# app/services/workflow_tracer.py
@dataclass
class EnhancedPipelineStage:
    """Detailed pipeline stage with full information."""
    
    stage_name: str
    stage_type: str  # "search", "filter", "rank", "boost"
    input_count: int
    output_count: int
    duration_ms: float
    
    # Stage-specific details
    query_rewrite: Optional[Dict[str, Any]] = None
    cluster_search: Optional[Dict[str, Any]] = None
    vector_search: Optional[Dict[str, Any]] = None
    memory_boost: Optional[Dict[str, Any]] = None
    reranking: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "stage_type": self.stage_type,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "duration_ms": self.duration_ms,
            "details": {
                k: v for k, v in {
                    "query_rewrite": self.query_rewrite,
                    "cluster_search": self.cluster_search,
                    "vector_search": self.vector_search,
                    "memory_boost": self.memory_boost,
                    "reranking": self.reranking
                }.items() if v is not None
            }
        }
```

#### 4.2 Trace Integration Points
```python
# app/langgraph_workflow/nodes.py - entity_retrieval_node

# Trace query rewriting
if state.get("query_rewrite_info"):
    tracer.add_pipeline_stage(EnhancedPipelineStage(
        stage_name="query_rewriting",
        stage_type="transform",
        input_count=1,
        output_count=1,
        duration_ms=state["query_rewrite_info"].get("processing_time_ms", 0),
        query_rewrite={
            "original": state["query_rewrite_info"]["original"],
            "rewritten": state["query_rewrite_info"]["rewritten"],
            "method": state["query_rewrite_info"]["method"],
            "confidence": state["query_rewrite_info"]["confidence"]
        }
    ))

# Trace cluster search
if cluster_entities:
    tracer.add_pipeline_stage(EnhancedPipelineStage(
        stage_name="cluster_search",
        stage_type="search",
        input_count=len(cluster_types),
        output_count=len(cluster_entities),
        duration_ms=cluster_search_time,
        cluster_search={
            "clusters_checked": cluster_types,
            "entities_found": len(cluster_entities),
            "top_similarities": [e.get("similarity", 0) for e in cluster_entities[:5]],
            "cluster_distribution": cluster_distribution
        }
    ))

# Trace memory boost
if memory_boosted_count > 0:
    tracer.add_pipeline_stage(EnhancedPipelineStage(
        stage_name="memory_boost",
        stage_type="boost",
        input_count=len(retrieved_entities),
        output_count=len(retrieved_entities),
        duration_ms=boost_time,
        memory_boost={
            "boosted_count": memory_boosted_count,
            "boost_weights": boost_weight_distribution,
            "average_boost": avg_boost,
            "max_boost": max_boost,
            "decay_applied": decay_info
        }
    ))
```

### Phase 5: Configuration Updates

#### 5.1 Config Schema Updates
```python
# ha_rag_bridge/config.py

# New configuration fields for query rewriting with local LLM
query_rewriting_api_base: str = Field(
    default="http://192.168.1.115:8001/v1",
    env="QUERY_REWRITING_API_BASE",
    title_hu="Query átíró API endpoint",
    title_en="Query Rewriting API Endpoint",
    description_hu="Local LLM API endpoint a query átíráshoz",
    description_en="Local LLM API endpoint for query rewriting",
    recommendation_hu="Használja a local inference szervert",
    recommendation_en="Use local inference server"
)

query_rewriting_api_key: str = Field(
    default="fake-key",
    env="QUERY_REWRITING_API_KEY",
    title_hu="Query átíró API kulcs",
    title_en="Query Rewriting API Key",
    description_hu="API kulcs (fake-key local LLM-hez)",
    description_en="API key (fake-key for local LLM)",
    is_secret=True
)

# Conversation summarization settings
conversation_summary_enabled: bool = Field(
    default=True,
    env="CONVERSATION_SUMMARY_ENABLED",
    title_hu="Beszélgetés összefoglaló engedélyezése",
    title_en="Enable Conversation Summarization",
    description_hu="LLM-alapú beszélgetés téma követés",
    description_en="LLM-based conversation topic tracking"
)

conversation_summary_model: str = Field(
    default="home-llama-3b",
    env="CONVERSATION_SUMMARY_MODEL",
    title_hu="Összefoglaló modell",
    title_en="Summary Model",
    description_hu="LLM modell a beszélgetés összefoglaláshoz",
    description_en="LLM model for conversation summarization",
    enum=["home-llama-3b", "qwen-7b", "disabled"]
)

# Enhanced memory settings
memory_topic_boost_enabled: bool = Field(
    default=True,
    env="MEMORY_TOPIC_BOOST_ENABLED",
    title_hu="Téma-alapú boost engedélyezése",
    title_en="Enable Topic-based Boost",
    description_hu="Entity boost a beszélgetés témája alapján",
    description_en="Entity boost based on conversation topic"
)

memory_decay_constant: int = Field(
    default=300,
    env="MEMORY_DECAY_CONSTANT",
    title_hu="Memory decay időállandó (sec)",
    title_en="Memory Decay Time Constant (sec)",
    description_hu="Időállandó a memory boost csökkenéséhez",
    description_en="Time constant for memory boost decay",
    ge=60,
    le=1800
)

# Pipeline tracing detail level
trace_detail_level: str = Field(
    default="full",
    env="TRACE_DETAIL_LEVEL",
    title_hu="Trace részletesség",
    title_en="Trace Detail Level",
    description_hu="Pipeline trace részletességi szint",
    description_en="Pipeline trace detail level",
    enum=["minimal", "standard", "full", "debug"]
)

trace_meta_tasks: bool = Field(
    default=False,
    env="TRACE_META_TASKS",
    title_hu="Meta-task trace engedélyezése",
    title_en="Enable Meta-task Tracing",
    description_hu="OpenWebUI meta-task-ok trace-elése",
    description_en="Trace OpenWebUI meta-tasks"
)
```

#### 5.2 Admin UI Configuration Components

```typescript
// apps/admin-ui/src/components/config/QueryProcessingConfig.tsx
// Add new fields for local LLM configuration

export const QueryProcessingConfig: React.FC = () => {
  return (
    <div className="space-y-4">
      {/* Existing query rewriting fields */}
      
      {/* NEW: Local LLM Configuration */}
      <div className="border-l-4 border-info pl-4">
        <h4 className="font-medium mb-2">Local LLM Settings</h4>
        
        <ConfigField
          field={{
            key: "query_rewriting_api_base",
            title: "API Endpoint",
            description: "Local LLM server endpoint",
            type: "string",
            value: config.query_rewriting_api_base
          }}
          onChange={handleChange}
        />
        
        <ConfigField
          field={{
            key: "query_rewriting_api_key",
            title: "API Key",
            description: "API key (use 'fake-key' for local)",
            type: "password",
            value: config.query_rewriting_api_key
          }}
          onChange={handleChange}
        />
        
        {/* Connection test for local LLM */}
        <ConnectionTest
          service="local_llm"
          endpoint={config.query_rewriting_api_base}
          apiKey={config.query_rewriting_api_key}
        />
      </div>
      
      {/* NEW: Conversation Summary Settings */}
      <div className="border-l-4 border-info pl-4">
        <h4 className="font-medium mb-2">Conversation Summary</h4>
        
        <ConfigField
          field={{
            key: "conversation_summary_enabled",
            title: "Enable Summarization",
            description: "Track conversation topics with LLM",
            type: "boolean",
            value: config.conversation_summary_enabled
          }}
          onChange={handleChange}
        />
        
        <ConfigField
          field={{
            key: "conversation_summary_model",
            title: "Summary Model",
            description: "LLM model for summarization",
            type: "select",
            options: ["home-llama-3b", "qwen-7b", "disabled"],
            value: config.conversation_summary_model
          }}
          onChange={handleChange}
        />
      </div>
    </div>
  );
};
```

```typescript
// apps/admin-ui/src/components/config/MemoryConfig.tsx
// Add topic-aware boost configuration

export const MemoryConfig: React.FC = () => {
  return (
    <div className="space-y-4">
      {/* Existing memory fields */}
      
      {/* NEW: Topic-aware Memory Boost */}
      <div className="border-l-4 border-warning pl-4">
        <h4 className="font-medium mb-2">Topic-aware Boost</h4>
        
        <ConfigField
          field={{
            key: "memory_topic_boost_enabled",
            title: "Enable Topic Boost",
            description: "Boost entities matching conversation topic",
            type: "boolean",
            value: config.memory_topic_boost_enabled
          }}
          onChange={handleChange}
        />
        
        <ConfigField
          field={{
            key: "memory_decay_constant",
            title: "Decay Time (seconds)",
            description: "Time constant for boost decay",
            type: "number",
            min: 60,
            max: 1800,
            value: config.memory_decay_constant
          }}
          onChange={handleChange}
        />
        
        {/* Visual decay curve preview */}
        <DecayCurvePreview constant={config.memory_decay_constant} />
      </div>
    </div>
  );
};
```

### Phase 6: Testing & Validation

#### Test Scenarios

1. **Query Rewriting Tests**
   ```python
   # tests/test_query_rewriting_integration.py
   async def test_follow_up_query_rewriting():
       """Test that 'És a konyhában?' gets rewritten correctly."""
       history = [
           ChatMessage(role="user", content="Hány fok van a nappaliban?"),
           ChatMessage(role="assistant", content="A nappaliban 23.5 fok van.")
       ]
       
       rewriter = ConversationalQueryRewriter()
       result = await rewriter.rewrite_query(
           current_query="És a konyhában?",
           conversation_history=history
       )
       
       assert result.rewritten_query == "Hány fok van a konyhában?"
       assert result.method == "llm"
       assert "konyhában" in result.coreferences_resolved
   ```

2. **Conversation Summary Tests**
   ```python
   async def test_conversation_summarization():
       """Test topic extraction from conversation."""
       summarizer = ConversationSummarizer()
       summary = await summarizer.generate_summary(
           query="És a hálószobában?",
           history=temperature_conversation_history
       )
       
       assert summary.topic == "temperature monitoring"
       assert summary.current_focus == "hálószoba"
       assert "sensor" in summary.topic_domains
   ```

3. **Memory Boost Tests**
   ```python
   async def test_topic_aware_boost():
       """Test that topic-matching entities get boosted."""
       memory = ConversationMemory(
           topic_summary="temperature monitoring",
           current_focus="konyha",
           topic_domains={"sensor", "climate"}
       )
       
       entity = {
           "entity_id": "sensor.konyha_temperature",
           "domain": "sensor",
           "area": "konyha"
       }
       
       boost = memory._calculate_topic_aware_boost(entity, memory.conversation_summary)
       assert boost > 2.0  # Should get strong boost for area + domain match
   ```

## Deployment Plan

### Step 1: Configuration (5 minutes)
1. Update `.env` with local LLM settings
2. Set query rewriting and summarization to enabled
3. Configure memory boost parameters

### Step 2: Code Deployment (15 minutes)
1. Deploy query rewriter integration
2. Deploy conversation summarizer
3. Deploy enhanced memory system
4. Deploy trace enhancements

### Step 3: Database Migration (5 minutes)
1. No schema changes required (using existing collections)
2. Clear conversation_memory collection for fresh start

### Step 4: Service Restart (5 minutes)
1. Restart bridge container
2. Restart LiteLLM if needed
3. Verify local LLM connectivity

### Step 5: Validation (10 minutes)
1. Test query rewriting with "És a konyhában?"
2. Check pipeline trace for all stages
3. Verify memory boost application
4. Confirm meta-task filtering

## Success Metrics

1. **Query Rewriting**: >90% accuracy on follow-up queries
2. **Response Time**: <500ms for rewriting with local LLM
3. **Memory Boost**: 2-3x boost for topic-relevant entities
4. **Trace Completeness**: All pipeline stages visible
5. **User Experience**: Natural conversation flow without manual context

## Risk Mitigation

1. **Local LLM Unavailable**: Fallback to rule-based rewriting
2. **Slow Response**: Timeout protection (500ms default)
3. **Memory Growth**: TTL-based cleanup (15 minutes)
4. **Trace Overhead**: Configurable detail levels

## Future Enhancements

1. **Multi-language Support**: Hungarian + English simultaneously
2. **Intent Learning**: Learn user patterns over time
3. **Proactive Suggestions**: Suggest next queries based on pattern
4. **Visual Pipeline**: Real-time pipeline visualization in UI
5. **Performance Analytics**: Track rewriting accuracy and boost effectiveness

## References

- Original Query Rewriter Design: `memory-bank/sbert-query-rewriting-plan.md`
- LangGraph Migration: `memory-bank/langgraph-migration-plan.md`
- Memory System: `memory-bank/conversation-memory-design.md`
- Pipeline Architecture: `memory-bank/cluster-based-rag-optimization.md`