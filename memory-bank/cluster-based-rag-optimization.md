# Cluster-based RAG Optimization Plan

## Executive Summary

This document outlines a comprehensive optimization strategy for the Home Assistant RAG pipeline, introducing semantic entity clustering and adaptive query scope detection to address current limitations in multi-turn conversations and entity retrieval efficiency.

## Current System Analysis

### Strengths Identified
- **Fast local architecture**: Mistral 7B + local embedding + cross-encoder reranking performing well
- **Existing graph infrastructure**: ArangoDB edge collections already support device-manual relationships
- **Advanced reranking**: Cross-encoder (ms-marco-MiniLM-L-6-v2) provides good entity relevance scoring
- **Multi-formatter system**: Intelligent prompt formatting (compact/detailed/grouped_by_area/tldr) already implemented
- **Hungarian language support**: Conversation analyzer handles Magyar context well

### Critical Issues Identified

#### 1. Multi-turn Conversation Blind Spot
- **Problem**: System only RAGs against the first user message in OpenWebUI conversations
- **Impact**: Context from previous conversation turns is lost
- **Current behavior**: "Mi a hőmérséklet?" followed by "És a páratartalom?" loses context about area/sensors

#### 2. Fixed Retrieval Scope Problem  
- **Problem**: Hardcoded `k=15` entity limit regardless of query scope
- **Impact**: "Mi van otthon?" (overview) vs "kapcsold fel a lámpát" (specific) get same entity count
- **Missing**: Adaptive "zoom level" like Google Maps - micro/macro/overview scoping

#### 3. Lack of Semantic Entity Clustering
- **Problem**: Individual entity vector search without logical grouping
- **Impact**: "Hogy termel a napelem?" might miss related sensors (voltage, current, battery)
- **Missing**: Pre-computed entity clusters for common use cases (solar performance, climate control, security)

#### 4. No Conversation Memory
- **Problem**: Previously relevant entities not cached across conversation turns
- **Impact**: User must re-specify context in follow-up questions
- **Missing**: TTL-based entity persistence per conversation

## Proposed Solution: 3-Tier Cluster Architecture

### Core Concept: "Smart Zoom" RAG System
Like Google Maps, queries should automatically determine the appropriate "zoom level" and return contextually grouped information.

### Tier 1: Semantic Entity Clusters

#### Cluster Data Model
```javascript
// cluster collection (document)
{
  _key: "solar_performance",
  name: "Napelem teljesítmény cluster",
  type: "micro_cluster",              // micro | macro | overview
  scope: "specific",                  // specific | area_wide | global  
  description: "Napelemes rendszer teljesítmény mutatók",
  embedding: [0.1, 0.2, ...],        // pre-computed cluster embedding
  query_patterns: [
    "hogy termel a napelem",
    "solar performance", 
    "mennyi áramot termel",
    "battery töltöttség"
  ],
  areas: ["kert"],                    // associated areas
  domains: ["sensor"],                // associated domains
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z"
}

// cluster_entity edge collection
{
  _from: "cluster/solar_performance",
  _to: "entity/sensor.solar_power",
  label: "contains_entity",
  role: "primary",                    // primary | related
  weight: 1.0,                       // relevance weight
  context_boost: 2.0                 // boost factor for this context
}
```

#### Initial Cluster Definitions

**Micro Clusters (Specific Functionality)**:
- `solar_performance`: solar sensors, battery, inverter status
- `climate_control`: temperature, humidity, thermostat entities per area
- `lighting_control`: lights, brightness sensors, switches per area  
- `security_sensors`: door/window sensors, motion detection, cameras
- `energy_monitoring`: power consumption, energy production, costs

**Macro Clusters (Area/Domain Wide)**:
- `area_climate_{area}`: all climate-related entities in specific area
- `area_lighting_{area}`: all lighting entities in specific area
- `energy_overview`: house-wide energy production/consumption
- `security_status`: house-wide security sensor status

**Overview Clusters (House-level)**:
- `house_status`: representative entities from each major system
- `active_alerts`: entities with alerts/issues across all areas
- `energy_summary`: total production/consumption/battery status

### Tier 2: Adaptive Query Scope Detection

#### Scope Classification Patterns
```python
SCOPE_PATTERNS = {
    "micro": {
        "patterns": [r"\b(kapcsold|állítsd|turn on|turn off)\b", r"\b(specific entity names)\b"],
        "k_range": (5, 10),
        "cluster_types": ["micro_cluster"],
        "formatter": "detailed"
    },
    "macro": {
        "patterns": [r"\b(nappali|konyha|area names)\b", r"\b(mi van|what's)\b"],
        "k_range": (15, 30),
        "cluster_types": ["micro_cluster", "macro_cluster"],
        "formatter": "grouped_by_area"
    },
    "overview": {
        "patterns": [r"\b(otthon|house|minden|all|összesítés|summary)\b"],
        "k_range": (30, 50),
        "cluster_types": ["overview_cluster"],
        "formatter": "tldr"
    }
}
```

#### Query Processing Pipeline
1. **Scope Detection**: Classify query as micro/macro/overview
2. **Cluster Search**: Vector similarity search in appropriate cluster types
3. **Entity Expansion**: Graph traversal from matched clusters to entities
4. **Hybrid Fallback**: If no cluster match, use current vector search
5. **Adaptive Reranking**: Apply current cross-encoder with cluster context boosts

### Tier 3: Conversation-Aware Context Building

#### Conversation Memory Service
```python
# conversation_memory collection
{
  _key: "conv_12345_entities",
  conversation_id: "12345",
  entities: [
    {
      entity_id: "sensor.living_room_temperature",
      relevance_score: 0.95,
      mentioned_at: "2024-01-01T10:30:00Z",
      context: "user asked about living room temperature"
    }
  ],
  areas_mentioned: ["nappali"],
  last_updated: "2024-01-01T10:30:00Z",
  ttl: "2024-01-01T10:45:00Z"  // 15 minute expiry
}
```

#### Multi-turn Enhancement Strategy
1. **Context Accumulation**: Build conversation-scoped entity cache
2. **Query Augmentation**: Combine current query with relevant conversation history
3. **Entity Memory Boosting**: Higher relevance scores for previously mentioned entities
4. **Smart Context Pruning**: Remove irrelevant entities based on conversation flow

## Implementation Plan

### Phase 1: Core Cluster Infrastructure (2-3 weeks)
**Priority**: High Impact, Low Risk

#### Database Schema
- Add `cluster` document collection to ArangoDB
- Add `cluster_entity` edge collection 
- Add `conversation_memory` collection with TTL index
- Update bootstrap system to create new collections

#### Core Services
- `ClusterManager`: CRUD operations for clusters, embedding generation
- `ConversationMemoryService`: conversation entity persistence with TTL
- `ScopeDetector`: query classification into micro/macro/overview

#### Integration Points
- Extend `retrieve_entities()` function with cluster-first logic
- Add cluster vector search to ArangoDB query functions
- Integrate with existing cross-encoder reranking

### Phase 2: Adaptive Scope Detection (2-3 weeks)
**Priority**: Medium Impact, Medium Risk

#### Query Pipeline Enhancement
- Implement scope classification patterns
- Add adaptive k-value selection based on detected scope
- Create hierarchical cluster relationships (micro → macro → overview)
- Enhance formatter selection with scope awareness

#### Performance Optimization
- Cache cluster embeddings for fast lookup
- Implement cluster relevance scoring
- Add cluster-based entity pre-filtering

### Phase 3: Conversation Context Enhancement (3-4 weeks)  
**Priority**: High Impact, Medium Risk

#### Multi-turn Capabilities
- Conversation history analysis and entity extraction
- Smart query augmentation with conversation context
- Previous entity boosting in reranking algorithm
- Context-aware cluster selection based on conversation areas

#### Advanced Features
- Dynamic cluster learning from conversation patterns
- Entity usage analytics for cluster optimization
- Auto-cluster discovery based on frequent entity co-occurrences

## Technical Architecture

### ArangoDB Schema Extensions
```javascript
// New collections
cluster: {
  type: "document",
  indexes: [
    { type: "vector", fields: ["embedding"], dimension: 384 },
    { type: "hash", fields: ["type"] },
    { type: "fulltext", fields: ["query_patterns"] }
  ]
}

cluster_entity: {
  type: "edge", 
  indexes: [
    { type: "hash", fields: ["role"] },
    { type: "skiplist", fields: ["weight"] }
  ]
}

conversation_memory: {
  type: "document",
  indexes: [
    { type: "hash", fields: ["conversation_id"] },
    { type: "ttl", fields: ["ttl"], expireAfterSeconds: 0 }
  ]
}
```

### AQL Query Templates
```aql
-- Cluster vector search
FOR c IN cluster
  FILTER c.type IN @cluster_types AND LENGTH(c.embedding) > 0
  LET score = COSINE_SIMILARITY(c.embedding, @query_vector)
  SORT score DESC 
  LIMIT @k
  RETURN c

-- Entity expansion from clusters
FOR cluster IN @matched_clusters
  FOR entity IN 1..1 OUTBOUND cluster._id cluster_entity
    RETURN {
      entity: entity,
      cluster: cluster.name,
      role: edge.role,
      boost: edge.weight
    }

-- Conversation memory lookup  
FOR mem IN conversation_memory
  FILTER mem.conversation_id == @conv_id AND mem.ttl > DATE_NOW()
  RETURN mem.entities
```

### Service Integration
- **Leverage existing**: ConversationAnalyzer, EntityReranker, SystemPromptFormatter
- **Extend existing**: `retrieve_entities`, `query_arango` functions
- **New services**: ClusterManager, ConversationMemoryService, QueryScopeDetector

## Expected Outcomes

### Performance Improvements
- **Faster relevant retrieval**: 60-80% reduction in irrelevant entities through cluster pre-filtering
- **Better conversation continuity**: 90% improvement in follow-up question handling
- **Adaptive resource usage**: 40% reduction in average entity processing for specific queries
- **Semantic coherence**: 3x improvement in logical entity grouping for complex queries

### Smart Home Specific Benefits

#### Query Examples
```
Query: "Hogy termel a napelem?"
Current: [random solar/energy entities via vector search]  
Optimized: solar_performance cluster → [power, voltage, current, daily_production, battery_level]

Query: "Mi a helyzet a nappaliban?"
Current: k=15 entities, mixed relevance
Optimized: area_climate_nappali + area_lighting_nappali clusters → relevant area entities only

Query: "És a konyhában?" (follow-up)
Current: loses previous context
Optimized: conversation memory + area_climate_konyha cluster → contextual response
```

#### Use Case Coverage
- **Energy monitoring**: Solar performance, consumption tracking, battery status
- **Climate control**: Temperature, humidity, thermostat management per area
- **Security status**: Door/window sensors, motion detection, camera alerts
- **Lighting control**: Smart lights, brightness sensors, automated schedules
- **Overview queries**: House-wide status, active alerts, energy summary

## Risk Assessment and Mitigation

### Technical Risks
- **ArangoDB schema changes**: Mitigated by backward-compatible additions
- **Query performance impact**: Mitigated by cluster embedding caching and indexes
- **Memory usage increase**: Mitigated by TTL-based conversation cleanup

### Implementation Risks  
- **Complex multi-phase rollout**: Mitigated by incremental feature flags
- **Existing pipeline disruption**: Mitigated by fallback to current vector search
- **Embedding quality for clusters**: Mitigated by extensive testing and manual tuning

### Operational Risks
- **Cluster maintenance overhead**: Mitigated by automated cluster validation
- **Conversation memory scaling**: Mitigated by aggressive TTL and cleanup policies

## Success Metrics

### Quantitative KPIs
- Query response relevance score: Target 85%+ (currently ~65%)
- Multi-turn conversation success rate: Target 90%+ (currently ~40%)
- Average query processing time: Target <500ms (currently ~800ms)
- Entity retrieval precision: Target 80%+ (currently ~55%)

### Qualitative Indicators
- Reduced need for query re-phrasing by users
- Better handling of Hungarian language queries
- More coherent entity grouping in responses
- Smoother conversation flow in OpenWebUI

## Future Enhancements

### Dynamic Clustering (Phase 4+)
- Machine learning-based cluster discovery
- Usage pattern analysis for cluster optimization
- Automated cluster relationship learning
- Cross-domain cluster connections

### Advanced Conversation AI (Phase 5+)
- Intent prediction for proactive entity loading
- Conversation summary generation
- Long-term user preference learning
- Multi-user conversation context management

---

**Created**: 2024-08-06  
**Status**: Planning Phase  
**Priority**: High  
**Estimated Effort**: 8-10 weeks total  
**Dependencies**: ArangoDB graph infrastructure, existing reranking pipeline