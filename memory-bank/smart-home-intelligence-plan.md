# Smart Home Intelligence - Sprint-Based Implementation Plan

## Vision
Transform ha-rag-bridge from simple Q&A automation into **AI-powered home intelligence system** that provides:
- **Pattern recognition**: "3 zuhanyzás ma" from humidity data
- **Anomaly detection**: Nyitott ablak télen, energia pazarlás detection  
- **Proactive recommendations**: Maintenance alerts, comfort optimization
- **Context-aware conversations**: Multi-turn dialogue with memory
- **Natural language reasoning**: "Mi újság otthon?" comprehensive reports

## Technical Architecture Overview

### Current Stack Enhancement
```
Home Assistant → Extended OpenAI → LiteLLM Proxy → ha-rag-bridge
                                                      ↓
                                               ArangoDB (graph + vector + time-series)
                                                      ↓  
                                               MindsDB (ML pattern recognition)
                                                      ↓
                                               LlamaCPP + Mistral 7B (local reasoning)
```

### Key Components
- **ArangoDB**: Graph-based conversation tracking, entity relationships, temporal patterns
- **MindsDB**: ML models for activity detection, anomaly recognition, behavioral learning
- **LlamaCPP**: Local AI reasoning (15 tok/sec Mistral 7B Q5) for pattern explanation
- **Cross-encoder**: Conversation-aware entity reranking
- **Enhanced RAG**: Context-aware system prompt generation

## Sprint-Based Implementation

### Sprint 1: Context-Aware Entity Prioritization ✅ COMPLETED
**Problem Solved**: "Mekkora a nedveség a kertben?" → nappali szenzor értéke (hardcoded results[0] logic)
**Goal**: Fix entity relevance scoring and prioritization

#### ✅ Completed Deliverables:
1. **Enhanced Request Schema** ✅
   ```python
   class Request(BaseModel):
       user_message: str
       conversation_history: Optional[List[ChatMessage]] = None
       conversation_id: Optional[str] = None
   ```

2. **Hungarian Conversation Analyzer** ✅
   - Area detection with aliases: "kertben", "kint", "outside" → "kert" area boost
   - Domain detection: "nedveség" → humidity device_class priority
   - Intent detection: control vs read operations
   - Follow-up detection: "És a házban?" context inheritance
   - Multi-language Hungarian/English processing

3. **Cross-encoder Entity Reranker** ✅
   - Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
   - Conversation context-aware scoring with TTL caching
   - Area/domain relevance boost integration
   - Fallback logic for compatibility

4. **Hierarchical System Prompt Generation** ✅
   ```
   Primary entity: sensor.kert_aqara_szenzor_humidity [kert]
   Current value: 59.2%
   
   Related entities:
   - sensor.lumi_lumi_weather_humidity [nappali]: 59.35%
   - sensor.lumi_lumi_weather_humidity_3 [hálószoba]: 58.1%
   
   Relevant domains: sensor
   ```

#### ✅ Success Criteria Achieved:
- "Mekkora a nedveség a kertben?" → kerti szenzor primary position ✅
- "Mekkora a hőmérséklet kint?" → kerti szenzor prioritized correctly ✅  
- "És a házban?" → area context expansion working ✅
- Hierarchical entity presentation with current values ✅
- Performance targets: <10ms analysis, <200ms ranking ✅
- Sprint 1 validation script: 100% success rate ✅

#### ✅ Files Implemented:
- `/app/app/schemas.py` - Request schema enhanced ✅
- `/app/app/main.py` - process_request logic completely overhauled ✅
- `/app/app/services/conversation_analyzer.py` - New service ✅
- `/app/app/services/entity_reranker.py` - New service ✅
- Comprehensive test suite and validation scripts ✅

#### Technical Implementation Details:
- **Dependencies**: transformers ^4.44, types-cachetools
- **Performance**: TTL caching (5min), CPU-optimized cross-encoder
- **Error Handling**: Graceful degradation with structured logging
- **Alias System**: Extensible area/domain pattern matching
- **Testing**: Unit, integration, and performance validation

#### Commit: `424a176` - Ready for deployment

### Sprint 2: ArangoDB Conversation Tracking (2-3 weeks)
**Goal**: Graph-based conversation memory foundation

#### Deliverables:
1. **Conversation Graph Schema**
   ```aql
   // Collections
   conversation: {_key, user_id, started_at, last_activity}
   conversation_turn: {_key, conversation_id, turn_number, timestamp, user_message, entities_mentioned}
   
   // Edges  
   turn_follows: conversation_turn -> conversation_turn
   turn_mentions: conversation_turn -> entity
   context_transition: conversation_turn -> conversation_turn (area_shift, topic_change)
   ```

2. **Session Tracking**
   - conversation_id generation and persistence
   - Turn sequence management
   - Context transition detection

3. **Context-Aware Queries**
   ```aql
   // Recent entity mentions
   FOR turn IN conversation_turn
     FILTER turn.conversation_id == @conv_id
     SORT turn.timestamp DESC LIMIT 3
     FOR entity IN 1..1 OUTBOUND turn turn_mentions
       RETURN DISTINCT entity
   ```

4. **LiteLLM Hook Enhancement**
   - Full conversation context extraction
   - Context summary generation
   - Bridge API integration

#### Success Criteria:
- Multi-turn conversations preserve context
- "És a házban?" properly resolved with conversation history
- Graph queries for conversation analysis work

### Sprint 3: Basic Pattern Recognition (3-4 weeks)
**Goal**: MindsDB foundation + first ML models

#### Deliverables:
1. **MindsDB Integration**
   - ArangoDB connector setup
   - Time-series data pipeline from HA
   - Model training/prediction workflow

2. **Shower Activity Detection Model**
   ```sql
   CREATE MODEL shower_activity_detector
   FROM arangodb.humidity_timeseries
   PREDICT activity_type, confidence, duration
   WHERE area_id = 'furdoszoba'
   USING engine='time_series'
   ```

3. **LlamaCPP Integration**
   - Mistral 7B API wrapper
   - Pattern explanation prompts
   - Natural language anomaly descriptions

4. **Basic Anomaly Reporting**
   - ML predictions in system prompts
   - Confidence scoring
   - Activity summaries for "Mi újság otthon?"

#### Success Criteria:
- Zuhanyzás detection működik humidity data alapján
- Mistral explains patterns naturally: "Likely someone took a shower..."
- "Mi újság otthon?" includes detected activities

### Sprint 4: Advanced Anomaly Detection (3-4 weeks)
**Goal**: Multi-sensor correlation analysis

#### Deliverables:
1. **Window Opening Detection**
   ```sql
   CREATE MODEL window_opening_detector
   FROM arangodb.multi_sensor_patterns
   PREDICT window_state, opening_type, confidence
   -- Patterns: temperature drop + humidity change + heating spike
   ```

2. **Energy Waste Detection**
   - Heating + open window conflicts
   - Cross-area sensor correlation
   - Cost impact estimation

3. **Enhanced Conversation Intelligence**
   - Comprehensive anomaly reporting
   - Priority-based information hierarchy
   - Actionable recommendations

4. **Confidence & Feedback System**
   - Model uncertainty handling
   - User feedback collection for improvement
   - Continuous learning integration

#### Success Criteria:
- Nyitott ablak detection télen (indirect sensor inference)
- "Mi újság otthon?" → comprehensive anomaly report
- Energy waste patterns identified and reported

### Sprint 5: Proactive Intelligence (2-3 weeks)  
**Goal**: Predictive recommendations and behavioral learning

#### Deliverables:
1. **Behavioral Pattern Learning**
   ```sql
   CREATE MODEL user_routine_model
   FROM arangodb.user_interactions
   PREDICT next_likely_action, optimal_timing
   ```

2. **Predictive Maintenance**
   - Device health models from sensor telemetry
   - Failure probability estimation
   - Maintenance scheduling recommendations

3. **Smart Recommendations Engine**
   - Comfort optimization suggestions
   - Energy efficiency recommendations
   - Security pattern analysis

4. **Performance Optimization**
   - Query optimization
   - Model performance tuning
   - Response time improvements

#### Success Criteria:
- Proactive maintenance alerts
- "Mi újság otthon?" includes predictive insights
- User routine optimization suggestions

## MVP Definition

### Phase 1 MVP (Sprint 1-2): **Context-Aware Conversation**
- Multi-turn conversations work properly
- Entity relevance scoring accurate
- Basic conversation memory

### Phase 2 MVP (Sprint 3): **Pattern Recognition Foundation**
- Basic activity detection (zuhanyzás)
- Natural language pattern explanation
- Simple anomaly reporting

### Phase 3 Complete (Sprint 4-5): **Advanced Intelligence**
- Multi-sensor anomaly detection
- Predictive recommendations
- Comprehensive home monitoring

## Technical Considerations

### Performance Requirements
- Cross-encoder reranking: <200ms per query
- MindsDB predictions: <500ms per model
- LlamaCPP reasoning: <2s per explanation
- Total response time: <3s for complex queries

### Privacy & Security
- Sensitive reasoning stays local (LlamaCPP)
- Conversation data encrypted in ArangoDB
- User consent for behavioral learning
- Data retention policies

### Scalability
- ArangoDB sharding for large conversation history
- MindsDB model versioning and A/B testing
- Caching strategies for frequent patterns
- Load balancing for multiple users

## Success Metrics

### Sprint 1 Metrics:
- Entity relevance accuracy: >90% correct primary entity
- Response time: <1s for context-aware queries
- User satisfaction: Qualitative feedback on relevance

### Sprint 3 Metrics:
- Pattern detection accuracy: >85% shower activity detection
- False positive rate: <10% for anomaly detection
- Natural language quality: Readable explanations

### Sprint 5 Metrics:
- Proactive recommendation acceptance: >60% user action rate
- Energy optimization impact: Measurable consumption reduction
- Overall system intelligence: "Mi újság otthon?" comprehensive score

## Next Steps
1. **Start Sprint 1**: Enhanced Request schema implementation
2. **Set up development environment**: Cross-encoder model testing
3. **Create test datasets**: Conversation scenarios for validation
4. **Establish feedback loops**: User testing and iteration cycles