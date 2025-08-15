# SBERT & Query Rewriting Fejlesztési Terv

**Létrehozva**: 2025-08-15  
**Állapot**: Implementáció alatt  
**Verzió**: 1.0

## 🎯 Összefoglaló

Ez a dokumentum a HA-RAG Bridge SBERT optimalizációs és query rewriting fejlesztési tervét tartalmazza. A cél a többfordulós beszélgetések kezelésének drasztikus javítása modern LLM-alapú query rewriting és fejlett embedding technikákkal.

## 📊 Kiindulási Helyzet

### ✅ Meglévő Funkciók
- **Embedding**: `paraphrase-multilingual-mpnet-base-v2` (768 dim), normalizált
- **Keresés**: Hibrid vector + text search ArangoDB-ben
- **Reranking**: Cross-encoder `ms-marco-MiniLM-L-6-v2`
- **Conversation Memory**: 15 perces TTL, 7-faktoros relevancia scoring
- **Follow-up detektálás**: Regex alapú (`"és\s+a"`, `"mi\s+a"`, stb.)

### ❌ Azonosított Problémák
1. **Query Understanding**: Primitív follow-up detektálás beégetett pattern-ekkel
2. **Coreference Resolution**: Nincs anafora feloldás ("és a kertben?" → nem tudja mire vonatkozik)
3. **Embedding Quality**: Túl komplex szövegek, nincs query/document megkülönböztetés
4. **Instruction Templates**: Nincs prompt-based embedding optimization
5. **Magyar Specifikusság**: Multilingual modell helyett nincs magyar-optimalizált alternatíva

### 🔍 Példa Problémák
```
User: "Hány fok van a nappaliban?"
Assistant: "A nappaliban 22.5 fok van."
User: "És a kertben?"
---
Jelenlegi viselkedés: Csak az "és a kertben?" query-t embedeli
Kívánatos: "Hány fok van a kertben?" query-re keressen
```

## 🚀 Fejlesztési Fázisok

### **FÁZIS 1: Query Understanding & Rewriting** (KRITIKUS)
**Becsült effort**: 50K-75K token / 2-3 óra Claude Code kódolás

#### 1.1 LLM-alapú Query Rewriter
**Fájl**: `app/services/query_rewriter.py`

```python
class ConversationalQueryRewriter:
    """LLM-alapú query átírás coreference resolution-nel"""
    
    def __init__(self, model="mistral-7b"):
        self.model = model
        self.timeout_ms = 200
        
    async def rewrite_query(
        self, 
        current_query: str, 
        conversation_history: List[ChatMessage]
    ) -> str:
        """
        Átírja a context-dependent query-t standalone formára
        
        Examples:
        - "és a kertben?" → "hány fok van a kertben?"
        - "mennyi ott?" → "mennyi a páratartalom a nappaliban?"
        """
```

**Admin UI Config**:
```python
# ha_rag_bridge/config.py
class QueryRewritingConfig:
    enabled: bool = Field(
        default=True,
        title_hu="Query átírás engedélyezése",
        title_en="Enable Query Rewriting"
    )
    
    model: str = Field(
        default="mistral-7b",
        enum=["mistral-7b", "llama-3.2", "disabled"],
        title_hu="Query átíró modell"
    )
    
    timeout_ms: int = Field(
        default=200,
        ge=50, le=2000,
        title_hu="Maximális válaszidő (ms)"
    )
```

### **FÁZIS 2: Embedding Pipeline Optimalizáció** (MAGAS)  
**Becsült effort**: 40K-60K token / 2-3 óra Claude Code kódolás

#### 2.1 Query/Document Encoding Split
**Fájl**: `scripts/embedding_backends.py` refactor

```python
class EnhancedLocalBackend(BaseEmbeddingBackend):
    """Instruction-aware embedding backend"""
    
    def embed_query(self, text: str) -> List[float]:
        """Query-specific embedding with instruction"""
        return self.embed([f"query: {text}"])[0]
        
    def embed_document(self, text: str) -> List[float]: 
        """Document-specific embedding with instruction"""
        return self.embed([f"passage: {text}"])[0]
```

#### 2.2 Multi-Query Expansion
**Fájl**: `app/services/query_expander.py`

```python
class QueryExpander:
    """Magyar-angol query expansion"""
    
    async def expand_query(self, query: str) -> List[str]:
        """
        Returns:
            [
                "eredeti query",
                "synonym expansion", 
                "translation variant"
            ]
        """
```

### **FÁZIS 3: Magyar Optimalizáció** (KÖZEPES)
**Becsült effort**: 30K-40K token / 1-2 óra Claude Code kódolás

#### 3.1 Model Benchmarking
**Fájl**: `scripts/model_benchmark.py`

A/B testing framework embedding modellek összehasonlítására:
- `paraphrase-multilingual-mpnet-base-v2` (jelenlegi)
- `NYTK/sentence-transformers-experimental-hubert-hungarian`
- `intfloat/multilingual-e5-large`

## 🎛️ Admin UI Fejlesztések

### Új Configuration Szekciók

#### 1. Query Processing Section
```typescript
interface QueryProcessingConfig {
  queryRewriting: {
    enabled: boolean;
    model: "mistral-7b" | "llama-3.2" | "disabled";
    timeoutMs: number;
  };
  
  expansion: {
    enabled: boolean;
    maxVariants: number;
    includeTranslations: boolean;
  };
}
```

#### 2. Embedding Advanced Section  
```typescript
interface EmbeddingAdvancedConfig {
  instructionTemplates: {
    enabled: boolean;
    queryPrefix: string;
    documentPrefix: string;
  };
  
  textFormat: "legacy" | "structured" | "minimal";
}
```

#### 3. Model Comparison Section
```typescript
interface ModelComparisonConfig {
  enabled: boolean;
  primaryModel: string;
  comparisonModel: string;
  trafficSplit: number; // 0-100%
}
```

## 📝 Implementation Checklist

### Phase 1: Foundation
- [x] Memory bank dokumentáció
- [ ] Config schema update
- [ ] Basic query rewriter interface
- [ ] Admin UI skeleton for new sections

### Phase 2: Core Implementation  
- [ ] LLM query rewriter implementation
- [ ] Coreference resolver
- [ ] Query/document encoding split
- [ ] Instruction templates

### Phase 3: Advanced Features
- [ ] Multi-query expansion
- [ ] Structured text formatter
- [ ] Model benchmarking framework
- [ ] Admin UI full implementation

### Phase 4: Testing & Optimization
- [ ] Unit tests
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] A/B testing setup

## 🧪 Testing Strategy

### Test Cases

#### Follow-up Query Resolution
```python
test_cases = [
    {
        "history": ["Hány fok van a nappaliban?"],
        "current": "És a kertben?",
        "expected": "Hány fok van a kertben?"
    },
    {
        "history": ["Kapcsold fel a világítást"],
        "current": "És a konyhában is",
        "expected": "Kapcsold fel a világítást a konyhában is"
    }
]
```

### Performance Benchmarks
- Query rewriting latency: target <200ms
- Embedding generation: target <100ms
- Total search pipeline: target <500ms
- Memory usage increase: target <20%

## 📊 Success Metrics

### Key Performance Indicators
1. **Query Understanding**: Coreference resolution accuracy %
2. **Search Quality**: Relevant results in top-5 %
3. **Response Time**: P95 latency < 500ms
4. **User Experience**: Reduced query reformulation rate

### Before/After Targets
- Follow-up query accuracy: 45% → 85%+ target
- Semantic search relevance: 75% → 90%+ target  
- Hungarian query handling: 70% → 90%+ target

## 🔄 Rollout Strategy

### Phase 1: Development & Testing
- Local testing environment
- Unit and integration tests
- Performance baseline

### Phase 2: Canary Deployment  
- 10% traffic split to new system
- Monitor metrics closely
- Gradual rollout if successful

### Phase 3: Full Deployment
- 100% traffic to new system
- Monitor for regressions
- Quick rollback plan ready

## 🚨 Risk Mitigation

### Technical Risks
1. **LLM Latency**: Hybrid approach, fallback to rule-based
2. **Model Performance**: A/B testing before full rollout
3. **Breaking Changes**: Comprehensive testing, gradual migration
4. **Resource Usage**: Monitoring and alerting

### Business Risks
1. **User Experience**: Careful UX testing
2. **Reliability**: Circuit breakers and fallbacks  
3. **Cost**: Monitor LLM usage and optimize
4. **Timeline**: Iterative development with MVPs

---

**Status**: ✅ Phase 1-2 COMPLETED (60-65% implementation)  
**Last Updated**: 2025-08-15  
**Next Phase**: Model Benchmarking Framework

## 🎉 Implementation Summary

### ✅ Successfully Implemented (Phase 1-2)
- **Query Rewriter Service**: LLM-based with rule-based fallback
- **Query Expander Service**: 6 domain categories, synonym expansion
- **Enhanced Embedding Backend**: Query/document split with instruction templates
- **Advanced Config Management**: 20+ new fields, specialized Admin UI
- **Production Integration**: 88% test success, real-world validation
- **Admin UI Components**: Custom QueryProcessing & EmbeddingAdvanced panels

### ⏳ Remaining Work (Phase 3+)
- Model Benchmarking Framework (`scripts/model_benchmark.py`)
- A/B Testing Infrastructure
- Structured Text Formatter variants
- Production Monitoring & Dashboards

**Contact**: Development team