# 🚀 LangGraph Phase 3 Workflow Debugging Guide

Ez a dokumentáció bemutatja, hogyan lehet debugolni és vizualizálni a Phase 3 LangGraph workflow-t.

## 🔧 Available Debugging Tools

### 1. **Command Line Debugger** (`debug_workflow.py`)

Real-time node-by-node workflow execution tracking.

```bash
# Single query debugging
docker exec ha-rag-bridge-bridge-1 python /app/debug_workflow.py "mi van a nappaliban?"

# Interactive session (within container)
docker exec -it ha-rag-bridge-bridge-1 python /app/debug_workflow.py
```

**Features:**
- ⏱️ Execution time tracking
- 🗣️ Conversation analysis details
- 🎯 Scope detection reasoning 
- 🔍 Entity retrieval breakdown
- 📝 Context formatting preview
- 🔬 Quality diagnostics
- 🏠 Top entity visualization

### 2. **Web-Based Debugger** (`workflow_debugger_web.py`)

Browser-based interface for workflow debugging.

```bash
# Start web debugger
docker exec -d ha-rag-bridge-bridge-1 python /app/workflow_debugger_web.py

# Access at: http://localhost:8899
```

**Features:**
- 📊 Interactive web interface
- 🔄 Real-time query processing
- 📱 Responsive design
- 📈 Visual node flow representation

### 3. **Phase 3 Integration Test Suite**

Comprehensive testing for all Phase 3 features.

```bash
# Full Phase 3 test suite
docker exec ha-rag-bridge-bridge-1 python /app/test_langgraph_phase3.py

# Individual test components
docker exec ha-rag-bridge-bridge-1 python -c "
from test_langgraph_phase3 import test_conversation_memory_persistence
import asyncio
asyncio.run(test_conversation_memory_persistence())
"
```

## 🎯 What Each Node Does

### 🗣️ **Conversation Analysis Node**
```python
conversation_analysis_node(state: RAGState) -> Dict[str, Any]
```
- **Input**: User query + conversation history
- **Processing**: 
  - Area detection (nappali, konyha, etc.)
  - Domain detection (light, sensor, climate)
  - Intent classification (read/control)
  - Follow-up detection
- **Output**: ConversationContext with metadata

**Debug info shows:**
- Areas mentioned: `['nappali']`
- Intent: `read` (confidence: 0.8)
- Is follow-up: `False`

### 🎯 **Scope Detection Node** 
```python
llm_scope_detection_node(state: RAGState) -> Dict[str, Any]
```
- **Input**: Query + conversation context
- **Processing**:
  - MICRO: Specific device actions (k=5-10)
  - MACRO: Area-specific queries (k=15-30) 
  - OVERVIEW: House-wide queries (k=30-50)
- **Output**: Detected scope + optimal k + reasoning

**Debug info shows:**
- Scope: `QueryScope.MACRO`
- Confidence: `0.8`
- Optimal K: `22`
- Reasoning: `"Single area-specific query"`

### 🔍 **Entity Retrieval Node**
```python
entity_retrieval_node(state: RAGState) -> Dict[str, Any]
```
- **Input**: Query vector + scope config + cluster types
- **Processing**:
  1. **Memory lookup**: Previous conversation entities
  2. **Cluster search**: Semantic entity clusters  
  3. **Vector search**: ArangoDB hybrid search
  4. **Memory boosting**: Enhance previously seen entities
- **Output**: Combined entity list with metadata

**Debug info shows:**
- Total entities: `66`
- From clusters: `0` (clusters not populated yet)
- From memory: `0` (first query)
- Memory boosted: `0`

### 📝 **Context Formatting Node**
```python
context_formatting_node(state: RAGState) -> Dict[str, Any]
```
- **Input**: Retrieved entities + query context
- **Processing**:
  - Entity scoring and ranking
  - Formatter selection (compact/detailed/grouped_by_area/tldr)
  - Hierarchical system prompt generation
- **Output**: Formatted context ready for LLM

**Debug info shows:**
- Formatter type: `compact`
- Context length: `2509` characters
- Primary/related entity split

## 🔬 Quality Diagnostics

The workflow automatically assesses its own performance:

```python
diagnostics = {
    "overall_quality": 0.42,  # 0-1 scale
    "conversation_analysis_quality": 0.48,
    "scope_detection_quality": 0.50,
    "entity_retrieval_quality": 0.00,  # Low due to missing clusters
    "context_formatting_quality": 1.00,
    "recommendations": [
        "Consider tuning similarity thresholds",
        "Review cluster definitions and entity relationships", 
        "Check cluster-entity mappings for query domain"
    ]
}
```

## 🛠️ Common Debugging Scenarios

### Scenario 1: Low Entity Retrieval Quality

**Symptoms**: `entity_retrieval_quality: 0.00`

**Debug steps:**
1. Check cluster population: `docker exec ha-rag-bridge-bridge-1 python -c "from app.services.cluster_manager import cluster_manager; print(cluster_manager.get_cluster_stats())"`
2. Verify entity embeddings: Check ArangoDB `entity` collection
3. Test vector search directly: Use `/process-request` endpoint

### Scenario 2: Wrong Scope Detection

**Symptoms**: MICRO detected for area queries, OVERVIEW for specific queries

**Debug steps:**
1. Check conversation analysis: Are areas being detected properly?
2. Review scope detection logic in `llm_scope_detection_node`
3. Test with different query patterns

### Scenario 3: Memory Not Working

**Symptoms**: `memory_entities: 0` for follow-up queries

**Debug steps:**
1. Check session ID consistency
2. Verify conversation memory TTL (15 minutes)
3. Check ArangoDB `conversation_memory` collection

## 📊 Example Debug Session

```bash
docker exec ha-rag-bridge-bridge-1 python /app/debug_workflow.py "termel a napelem?"
```

Expected output flow:
```
🚀 LangGraph Phase 3 Workflow Debugger
============================================================
Query: 'termel a napelem?'
Session ID: debug_session
============================================================

⏱️  Total execution time: 8.45s

🗣️ Conversation Context
------------------------
  areas_mentioned: ['inverter']
  domains_mentioned: ['sensor']  
  is_follow_up: False
  intent: read
  confidence: 0.9

🎯 Scope Detection
-----------------
  scope: QueryScope.MICRO
  confidence: 0.8
  optimal_k: 20
  reasoning: "Specific value query without area context"

🔍 Entity Retrieval
------------------
  total_entities: 45
  cluster_entities: 12
  memory_entities: 0
  memory_boosted: 0

🏠 Top 5 Retrieved Entities:
------------------------------
  1. sensor.solax_today_yield_kwh (score: 0.892) - inverter [CLUSTER]
  2. sensor.solax_power_generation (score: 0.845) - inverter [CLUSTER]  
  3. sensor.solax_battery_soc (score: 0.723) - inverter
  4. sensor.grid_power_consumption (score: 0.689) - no area
  5. light.nappali_jobb_falikar (score: 0.234) - no area

✅ Workflow completed successfully!
```

## 🚀 Next Steps

1. **Populate Semantic Clusters**: Run cluster bootstrap to improve entity retrieval quality
2. **LangSmith Integration**: Enable tracing for official LangGraph Studio
3. **Custom Metrics**: Add domain-specific performance metrics
4. **A/B Testing**: Compare different scope detection strategies

## 🔗 Related Files

- `app/langgraph_workflow/workflow.py` - Main workflow definition
- `app/langgraph_workflow/nodes.py` - Individual node implementations  
- `app/langgraph_workflow/routing.py` - Conditional routing logic
- `test_langgraph_phase3.py` - Comprehensive test suite
- `litellm_ha_rag_hooks_phase3.py` - Production hook integration

---

**Pro Tip**: Use the command line debugger for quick iterations, and the integration test suite for comprehensive validation of workflow changes.