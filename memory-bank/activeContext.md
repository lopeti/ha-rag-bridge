# Active Context

## Current Goals

**Sprint 1: Context-Aware Entity Prioritization (2-3 weeks)**
- Fix core issue: "Mekkora a nedveség a kertben?" should return kerti szenzor, not nappali
- Enhanced Request schema with conversation_history support
- Cross-encoder reranking for conversation-aware entity scoring
- Hierarchical system prompt with primary/contextual entity separation

## Current Focus Areas

1. **Entity Relevance Scoring**: Area-based boost, domain priority, conversation context integration
2. **Query Context Analysis**: Hungarian language area/domain detection ("kertben" → area_id boost)
3. **System Prompt Enhancement**: Primary entity highlighted, related entities as context
4. **Multi-turn Support**: "És a házban?" context expansion from conversation history

## Current Blockers

- None yet - ready to start Sprint 1 implementation

## Success Criteria for Current Sprint

- "Mekkora a nedveség a kertben?" → sensor.kert_aqara_szenzor_humidity primary
- "És a házban?" → proper area context expansion
- Cross-encoder reranking <200ms performance
- Hierarchical entity presentation in system prompt

## Next Session Priority

Start with Enhanced Request schema implementation in `/app/app/schemas.py`