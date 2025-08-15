# SBERT & Query Rewriting - Implementation Checklist

**Létrehozva**: 2025-08-15  
**Állapot**: Implementáció alatt  

## 📋 Phase 1: Foundation & Config Setup

### ✅ Dokumentáció
- [x] Memory bank főterv (`sbert-query-rewriting-plan.md`)
- [x] Implementation checklist (ez a dokumentum)
- [ ] Config schema changes dokumentáció
- [ ] Admin UI mockups dokumentáció

### 🎛️ Config Schema Update
**Target files**: `ha_rag_bridge/config.py`

```python
# Új config blokkok hozzáadása
class QueryRewritingConfig(BaseModel):
    enabled: bool = Field(default=True)
    model: str = Field(default="mistral-7b")
    timeout_ms: int = Field(default=200)
    coreference_resolution: bool = Field(default=True)

class EmbeddingAdvancedConfig(BaseModel):
    use_instruction_templates: bool = Field(default=True)
    query_prefix: str = Field(default="query: ")
    document_prefix: str = Field(default="passage: ")
    text_format: str = Field(default="structured")
    
class ModelComparisonConfig(BaseModel):
    enabled: bool = Field(default=False)
    primary_model: str = Field(default="multilingual")
    comparison_model: str = Field(default="hungarian")
    traffic_split: int = Field(default=10)  # %
```

**Checklist**:
- [ ] `QueryRewritingConfig` class hozzáadása
- [ ] `EmbeddingAdvancedConfig` class hozzáadása  
- [ ] `ModelComparisonConfig` class hozzáadása
- [ ] Főconfig-ba integrálás
- [ ] Validation logic
- [ ] Default értékek beállítása
- [ ] Hungarian/English mezőnevek
- [ ] Restart required flags

### 🖥️ Admin UI Skeleton
**Target files**: `apps/admin-ui/src/components/`

**Új komponensek**:
- [ ] `QueryProcessingConfig.tsx`
- [ ] `EmbeddingAdvancedConfig.tsx`
- [ ] `ModelComparisonConfig.tsx`
- [ ] `QueryRewritingTestPanel.tsx` (debug célra)

**Checklist**:
- [ ] Új config szekciók a main config page-en
- [ ] Form validation
- [ ] Real-time save functionality
- [ ] Connection test buttons
- [ ] Reset to defaults opció

---

## 📋 Phase 2: Core Implementation

### 🧠 Query Rewriter Service
**Target file**: `app/services/query_rewriter.py`

```python
class ConversationalQueryRewriter:
    """LLM-alapú conversational query rewriting"""
    
    def __init__(self):
        self.settings = get_settings()
        self.model = self._initialize_model()
        
    async def rewrite_query(
        self, 
        current_query: str, 
        conversation_history: List[ChatMessage]
    ) -> QueryRewriteResult:
        """Main rewriting method"""
        
    def _build_rewrite_prompt(self, query: str, history: List[ChatMessage]) -> str:
        """Few-shot prompt building"""
        
    async def _call_llm(self, prompt: str) -> str:
        """LLM API call with timeout"""
```

**Checklist**:
- [ ] Base class és interface definiálás
- [ ] Prompt template rendszer
- [ ] LLM integration (Mistral/Llama)
- [ ] Error handling és timeout
- [ ] Caching layer (TTL 5 perc)
- [ ] Metrics collection
- [ ] Fallback mechanizmus

### 🔗 Coreference Resolver
**Target file**: `app/services/coreference_resolver.py`

```python
class CoreferenceResolver:
    """Anafora és ellipszis feloldás conversational context-ben"""
    
    PRONOUNS = {
        "spatial": ["ott", "itt", "there", "here"],
        "entity": ["az", "azt", "annak", "it", "that"],
        "additive": ["és", "is", "szintén", "and", "also"]
    }
    
    def resolve_references(
        self, 
        query: str, 
        memory: ConversationMemory
    ) -> CoreferenceResult:
        """Referencia feloldás"""
```

**Checklist**:
- [ ] Pronoun detection patterns
- [ ] Antecedent matching algoritmus
- [ ] Context entity tracking
- [ ] Intent inheritance logic
- [ ] Magyar nyelvi szabályok
- [ ] Test cases kidolgozása

### 🔄 Enhanced Embedding Backend
**Target file**: `scripts/embedding_backends.py` (refactor)

```python
class EnhancedLocalBackend(BaseEmbeddingBackend):
    """Instruction-aware és multi-query támogatással"""
    
    def __init__(self):
        super().__init__()
        self.config = get_settings().embedding_advanced
        
    def embed_query(self, text: str) -> List[float]:
        """Query-specific encoding"""
        
    def embed_document(self, text: str) -> List[float]:
        """Document-specific encoding"""
        
    def embed_multi_query(self, queries: List[str]) -> List[List[float]]:
        """Batch multi-query embedding"""
```

**Checklist**:
- [ ] Query/document encoding split
- [ ] Instruction template support
- [ ] Multi-query batch processing
- [ ] Config integration
- [ ] Backward compatibility
- [ ] Performance optimization

---

## 📋 Phase 3: Advanced Features

### 🔍 Query Expander Service
**Target file**: `app/services/query_expander.py`

```python
class QueryExpander:
    """Semantic query expansion magyar nyelvre optimalizálva"""
    
    DOMAIN_SYNONYMS = {
        "temperature": ["hőmérséklet", "hőfok", "meleg", "hideg"],
        "humidity": ["páratartalom", "nedvesség"],
        "light": ["világítás", "lámpa", "fény"],
        # ...
    }
    
    async def expand_query(
        self, 
        query: str, 
        context: ConversationContext
    ) -> List[str]:
        """Query expansion with synonyms and translations"""
```

**Checklist**:
- [ ] Domain-specific synonym dictionaries
- [ ] Magyar-angol fordítási párok
- [ ] Context-aware expansion
- [ ] Configurable expansion limit
- [ ] Quality scoring
- [ ] Performance optimization

### 📊 Model Benchmark Framework  
**Target file**: `scripts/model_benchmark.py`

```python
class EmbeddingModelBenchmark:
    """A/B testing és model összehasonlítás"""
    
    MODELS = {
        "multilingual": "paraphrase-multilingual-mpnet-base-v2",
        "hungarian": "NYTK/sentence-transformers-experimental-hubert-hungarian",
        "e5": "intfloat/multilingual-e5-large"
    }
    
    async def run_benchmark(
        self, 
        test_queries: List[str]
    ) -> BenchmarkResult:
        """Comprehensive model benchmark"""
```

**Checklist**:
- [ ] Test query dataset
- [ ] Multiple model support
- [ ] Performance metrics collection
- [ ] Statistical significance testing  
- [ ] Results storage
- [ ] Admin UI integration

### 📝 Structured Text Formatter
**Target file**: `scripts/ingest.py` (refactor)

```python
def build_structured_text(
    entity: dict, 
    format_type: str = "structured"
) -> str:
    """
    Optimalizált embedding szöveg generálás
    
    Args:
        format_type: "legacy", "structured", "minimal"
    """
```

**Checklist**:
- [ ] Legacy format megtartása
- [ ] Structured format (pipe-separated)
- [ ] Minimal format (space-separated)
- [ ] Config-driven választás
- [ ] Backward compatibility testing
- [ ] Performance measurement

---

## 📋 Phase 4: Admin UI Integration

### 🎛️ Configuration Panels

#### Query Processing Config
**File**: `apps/admin-ui/src/components/QueryProcessingConfig.tsx`

```typescript
interface QueryProcessingProps {
  config: QueryRewritingConfig;
  onSave: (config: QueryRewritingConfig) => void;
}
```

**Features**:
- [ ] Enable/disable toggles
- [ ] Model selection dropdown
- [ ] Timeout slider
- [ ] Real-time validation
- [ ] Test query panel

#### Embedding Advanced Config
**File**: `apps/admin-ui/src/components/EmbeddingAdvancedConfig.tsx`

```typescript
interface EmbeddingAdvancedProps {
  config: EmbeddingAdvancedConfig;
  onSave: (config: EmbeddingAdvancedConfig) => void;
}
```

**Features**:
- [ ] Instruction template editor
- [ ] Text format selector
- [ ] Query expansion controls
- [ ] Preview panel
- [ ] Performance indicators

#### Model Comparison Panel
**File**: `apps/admin-ui/src/components/ModelComparisonConfig.tsx`

**Features**:
- [ ] A/B testing toggle
- [ ] Traffic split slider
- [ ] Model selection
- [ ] Live metrics display
- [ ] Benchmark trigger

### 📊 Monitoring Dashboard

#### Query Rewriting Metrics
**Component**: `QueryRewritingMetrics.tsx`

**Metrics**:
- [ ] Rewriting success rate
- [ ] Average latency
- [ ] Coreference resolution accuracy
- [ ] Most common patterns

#### Embedding Quality Metrics  
**Component**: `EmbeddingQualityMetrics.tsx`

**Metrics**:
- [ ] Search relevance scores
- [ ] Follow-up success rate
- [ ] Model comparison results
- [ ] Performance trends

---

## 📋 Phase 5: Testing & Validation

### 🧪 Unit Tests

#### Query Rewriter Tests
**File**: `tests/test_query_rewriter.py`

```python
class TestQueryRewriter:
    def test_basic_follow_up_rewriting(self):
        """Test: 'és a kertben?' -> 'hány fok van a kertben?'"""
        
    def test_coreference_resolution(self):
        """Test pronoun resolution"""
        
    def test_intent_inheritance(self):
        """Test context inheritance"""
```

**Test Coverage**:
- [ ] Basic rewriting scenarios
- [ ] Edge cases (empty history, malformed queries)
- [ ] Error handling
- [ ] Performance benchmarks
- [ ] Magyar nyelvi specifikus esetek

#### Embedding Tests
**File**: `tests/test_enhanced_embedding.py`

```python
class TestEnhancedEmbedding:
    def test_query_document_split(self):
        """Test query vs document encoding differences"""
        
    def test_instruction_templates(self):
        """Test instruction prefix impact"""
        
    def test_multi_query_expansion(self):
        """Test query expansion quality"""
```

**Test Coverage**:
- [ ] Query/document encoding differences
- [ ] Instruction template effectiveness
- [ ] Multi-query consistency
- [ ] Performance comparison
- [ ] Backward compatibility

### 🔄 Integration Tests

#### End-to-End Pipeline
**File**: `tests/test_e2e_query_processing.py`

```python
class TestE2EQueryProcessing:
    async def test_full_pipeline(self):
        """Test: user query -> rewriting -> embedding -> search -> results"""
        
    async def test_follow_up_scenario(self):
        """Test complete follow-up conversation flow"""
        
    async def test_fallback_mechanisms(self):
        """Test error scenarios and fallbacks"""
```

**Test Scenarios**:
- [ ] Normal query processing
- [ ] Follow-up conversations
- [ ] Error conditions
- [ ] Performance under load
- [ ] Memory usage patterns

### 📊 Performance Benchmarks

#### Latency Benchmarks
```python
class PerformanceBenchmarks:
    def test_query_rewriting_latency(self):
        """Target: <200ms P95"""
        
    def test_embedding_generation_latency(self):
        """Target: <100ms P95"""
        
    def test_total_pipeline_latency(self):
        """Target: <500ms P95"""
```

**Benchmark Targets**:
- [ ] Query rewriting: <200ms P95
- [ ] Embedding generation: <100ms P95  
- [ ] Total pipeline: <500ms P95
- [ ] Memory usage: <20% increase
- [ ] CPU usage: <30% increase

---

## 📋 Phase 6: Deployment & Monitoring

### 🚀 Deployment Strategy

#### Feature Flags
- [ ] `QUERY_REWRITING_ENABLED` environment variable
- [ ] `EMBEDDING_ADVANCED_ENABLED` flag
- [ ] `MODEL_COMPARISON_ENABLED` flag
- [ ] Gradual rollout percentages

#### Database Migrations
- [ ] Conversation memory schema updates
- [ ] New metrics collection tables
- [ ] Index optimizations
- [ ] Cleanup procedures

#### Configuration Migration
- [ ] Existing config preservation  
- [ ] Default value population
- [ ] Validation during startup
- [ ] Migration scripts

### 📈 Monitoring & Alerting

#### Key Metrics
- [ ] Query rewriting success rate
- [ ] Search relevance improvement
- [ ] User query reformulation rate
- [ ] System resource usage

#### Alerts
- [ ] High latency alert (>500ms)
- [ ] Low success rate alert (<80%)
- [ ] Error rate spike alert
- [ ] Resource usage alert

#### Dashboards
- [ ] Query processing performance
- [ ] Embedding quality trends
- [ ] Model comparison results
- [ ] User experience metrics

---

## 🎯 Success Criteria

### Functional Requirements
- [ ] Follow-up queries properly resolved (85%+ accuracy)
- [ ] Coreference resolution working (80%+ accuracy)  
- [ ] Query expansion improving results (15%+ relevance boost)
- [ ] Multiple models comparable (A/B testing working)

### Performance Requirements  
- [ ] Latency targets met (<500ms total)
- [ ] Resource usage acceptable (<20% increase)
- [ ] Reliability maintained (99.5%+ uptime)
- [ ] Scalability proven (load testing passed)

### User Experience Requirements
- [ ] Improved conversation flow
- [ ] Reduced query reformulation
- [ ] Better Hungarian language support
- [ ] Seamless admin configuration

---

## 📝 Next Steps

### Immediate Actions (Today)
1. [x] Memory bank documentation
2. [ ] Config schema implementation
3. [ ] Basic query rewriter skeleton
4. [ ] Admin UI mockups

### This Week
1. [ ] Core query rewriter implementation
2. [ ] Coreference resolver
3. [ ] Enhanced embedding backend
4. [ ] Basic admin UI integration

### Next Week  
1. [ ] Query expansion service
2. [ ] Model benchmarking framework
3. [ ] Complete admin UI
4. [ ] Testing suite

### Following Weeks
1. [ ] Performance optimization
2. [ ] A/B testing setup
3. [ ] Production deployment
4. [ ] Monitoring & alerting

---

**Status**: ✅ Phase 1-2 COMPLETED | ⏳ Phase 3+ Pending  
**Last Updated**: 2025-08-15  
**Implementation Progress**: 60-65%  
**Responsible**: Development team

## 🎯 Phase Completion Status

### ✅ Phase 1: Foundation & Config Setup - COMPLETED
- [x] Memory bank főterv dokumentáció  
- [x] Config schema update (20+ új mező)
- [x] Admin UI skeleton komponensek
- [x] Field categorization és metadata

### ✅ Phase 2: Core Implementation - COMPLETED  
- [x] Query Rewriter Service (rule-based + LLM)
- [x] Coreference Resolver (beépítve)
- [x] Enhanced Embedding Backend
- [x] Query Expander Service

### ✅ Phase 4: Admin UI Integration - COMPLETED
- [x] QueryProcessingConfig.tsx specializált komponens
- [x] EmbeddingAdvancedConfig.tsx specializált komponens  
- [x] Settings.tsx integráció
- [x] Magyar/angol lokalizáció

### ✅ Phase 5: Testing & Validation - PARTIAL (60%)
- [x] Unit tests (15/17 sikeres)
- [x] Integration tests  
- [x] Real-world validation
- [ ] Performance benchmarks
- [ ] Load testing

### ⏳ Phase 3: Advanced Features - PENDING (20%)
- [ ] Model Benchmark Framework
- [ ] A/B Testing Setup  
- [ ] Structured Text Formatter variants
- [x] Query Expander Service ✅

### ⏳ Phase 6: Production Deployment - PENDING (30%)
- [x] Feature flags (basic)
- [ ] Canary deployment
- [ ] Monitoring & alerting  
- [ ] Performance dashboards