# Config Schema Changes - SBERT & Query Rewriting

**Létrehozva**: 2025-08-15  
**Állapot**: Implementálva  
**Fájl**: `ha_rag_bridge/config.py`

## 📋 Új Beállítási Kategóriák

### 1. Query Rewriting & Advanced Search Configuration

#### query_rewriting_enabled
- **Típus**: `bool`
- **Default**: `True`
- **Env**: `QUERY_REWRITING_ENABLED`
- **Leírás**: LLM-alapú többfordulós query átírás engedélyezése

#### query_rewriting_model
- **Típus**: `str`
- **Default**: `"mistral-7b"`
- **Env**: `QUERY_REWRITING_MODEL`
- **Enum**: `["mistral-7b", "llama-3.2", "disabled"]`
- **Leírás**: LLM modell a query átíráshoz

#### query_rewriting_timeout_ms
- **Típus**: `int`
- **Default**: `200`
- **Env**: `QUERY_REWRITING_TIMEOUT_MS`
- **Range**: `50-2000`
- **Leírás**: Maximális várakozási idő query átírásra

#### coreference_resolution_enabled
- **Típus**: `bool`
- **Default**: `True`
- **Env**: `COREFERENCE_RESOLUTION_ENABLED`
- **Leírás**: Pronoun és referencia feloldás beszélgetési kontextusban

### 2. Embedding Advanced Configuration

#### use_instruction_templates
- **Típus**: `bool`
- **Default**: `True`
- **Env**: `USE_INSTRUCTION_TEMPLATES`
- **Leírás**: Query és document specifikus embedding prefix-ek használata

#### query_prefix_template
- **Típus**: `str`
- **Default**: `"query: "`
- **Env**: `QUERY_PREFIX_TEMPLATE`
- **Leírás**: Template prefix query embedding-ekhez

#### document_prefix_template
- **Típus**: `str`
- **Default**: `"passage: "`
- **Env**: `DOCUMENT_PREFIX_TEMPLATE`
- **Leírás**: Template prefix document embedding-ekhez

#### embedding_text_format
- **Típus**: `str`
- **Default**: `"structured"`
- **Env**: `EMBEDDING_TEXT_FORMAT`
- **Enum**: `["legacy", "structured", "minimal"]`
- **Leírás**: Embedding szöveg struktúrájának formátuma

### 3. Query Expansion Configuration

#### query_expansion_enabled
- **Típus**: `bool`
- **Default**: `True`
- **Env**: `QUERY_EXPANSION_ENABLED`
- **Leírás**: Többféle query variáns generálása

#### max_query_variants
- **Típus**: `int`
- **Default**: `3`
- **Env**: `MAX_QUERY_VARIANTS`
- **Range**: `1-5`
- **Leírás**: Maximálisan generált query variánsok száma

#### include_query_translations
- **Típus**: `bool`
- **Default**: `True`
- **Env**: `INCLUDE_QUERY_TRANSLATIONS`
- **Leírás**: Magyar-angol fordítási párok a query expansion-ben

#### include_query_synonyms
- **Típus**: `bool`
- **Default**: `True`
- **Env**: `INCLUDE_QUERY_SYNONYMS`
- **Leírás**: Domain-specifikus szinonimák a query expansion-ben

### 4. Model Comparison & Benchmarking

#### model_comparison_enabled
- **Típus**: `bool`
- **Default**: `False`
- **Env**: `MODEL_COMPARISON_ENABLED`
- **Leírás**: A/B testing embedding modellek között

#### primary_embedding_model
- **Típus**: `str`
- **Default**: `"multilingual"`
- **Env**: `PRIMARY_EMBEDDING_MODEL`
- **Enum**: `["multilingual", "hungarian", "e5"]`
- **Leírás**: Fő embedding modell a benchmarking-hez

#### comparison_embedding_model
- **Típus**: `str`
- **Default**: `"hungarian"`
- **Env**: `COMPARISON_EMBEDDING_MODEL`
- **Enum**: `["multilingual", "hungarian", "e5"]`
- **Leírás**: Alternatív modell az összehasonlításhoz

#### model_comparison_traffic_split
- **Típus**: `int`
- **Default**: `10`
- **Env**: `MODEL_COMPARISON_TRAFFIC_SPLIT`
- **Range**: `0-50`
- **Leírás**: Az összehasonlítási modellre irányított forgalom százaléka

#### benchmark_logging_enabled
- **Típus**: `bool`
- **Default**: `True`
- **Env**: `BENCHMARK_LOGGING_ENABLED`
- **Leírás**: Modell összehasonlítási eredmények naplózása

## 🔧 Admin UI Integráció

### Új Szekciók

#### 1. Query Processing
**Komponens**: `QueryProcessingConfig.tsx`
```typescript
interface QueryProcessingConfig {
  queryRewriting: {
    enabled: boolean;
    model: "mistral-7b" | "llama-3.2" | "disabled";
    timeoutMs: number;
    coreferenceResolution: boolean;
  };
}
```

#### 2. Embedding Advanced
**Komponens**: `EmbeddingAdvancedConfig.tsx`
```typescript
interface EmbeddingAdvancedConfig {
  instructionTemplates: {
    enabled: boolean;
    queryPrefix: string;
    documentPrefix: string;
  };
  textFormat: "legacy" | "structured" | "minimal";
  expansion: {
    enabled: boolean;
    maxVariants: number;
    includeTranslations: boolean;
    includeSynonyms: boolean;
  };
}
```

#### 3. Model Comparison
**Komponens**: `ModelComparisonConfig.tsx`
```typescript
interface ModelComparisonConfig {
  enabled: boolean;
  primaryModel: "multilingual" | "hungarian" | "e5";
  comparisonModel: "multilingual" | "hungarian" | "e5";
  trafficSplit: number;
  benchmarkLogging: boolean;
}
```

## 🧪 Tesztelési Példák

### Config Betöltés Teszt
```python
from ha_rag_bridge.config import get_settings

settings = get_settings()

# Query rewriting beállítások
assert settings.query_rewriting_enabled == True
assert settings.query_rewriting_model == "mistral-7b"
assert settings.query_rewriting_timeout_ms == 200

# Embedding beállítások
assert settings.use_instruction_templates == True
assert settings.embedding_text_format == "structured"
assert settings.max_query_variants == 3

# Model comparison
assert settings.model_comparison_enabled == False
assert settings.primary_embedding_model == "multilingual"
```

### Environment Variable Override
```bash
export QUERY_REWRITING_MODEL="llama-3.2"
export EMBEDDING_TEXT_FORMAT="minimal"
export MAX_QUERY_VARIANTS="2"
```

## 📊 Admin UI Features

### Real-time Configuration Testing
- **Query Rewriting Test Panel**: Tesztelni lehet a query átírást élő példákkal
- **Embedding Format Preview**: Előnézet a különböző szöveg formátumokra
- **Model Performance Comparison**: Valós idejű teljesítmény összehasonlítás

### Connection Testing
- Query rewriting service connectivity test
- LLM model availability check
- Performance latency measurement

### Monitoring Integration
- Query rewriting success/failure metrics
- Embedding generation performance
- Model comparison A/B test results

## 🔄 Migration Strategy

### Backward Compatibility
- Minden új beállítás backward compatible
- Default értékek megőrzik a jelenlegi viselkedést
- Fokozatos rollout lehetőség feature flag-ekkel

### Deployment Checklist
- [ ] Config schema validáció
- [ ] Default értékek tesztelése
- [ ] Admin UI form validáció
- [ ] Environment variable override tesztelés
- [ ] Docker container restart tesztelés

### Rollback Plan
- Eredeti config struktúra megtartva
- Új beállítások deaktiválhatók
- Emergency disable flag minden új funkcióhoz

---

**Status**: ✅ Implementálva  
**Tested**: Config betöltés és validáció sikeres  
**Next**: Query Rewriter Service implementálás