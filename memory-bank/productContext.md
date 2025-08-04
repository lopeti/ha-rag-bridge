# Product Context

## Vision: AI-Powered Smart Home Intelligence

Transform traditional home automation from simple device control into **intelligent home monitoring and proactive assistance**. Beyond "turn on lights" and "what's the temperature", enable conversations like "Mi újság otthon?" with comprehensive, insightful responses about home patterns, anomalies, and recommendations.

## Overview

**ha-rag-bridge** evolution from basic RAG system to **multi-modal AI home intelligence platform** combining:
- **Semantic understanding** of natural language home queries
- **Pattern recognition** from sensor data (zuhanyzás detection, nyitott ablak inference)
- **Anomaly detection** and energy waste identification  
- **Contextual conversations** with memory and reasoning
- **Proactive recommendations** for comfort, security, and efficiency

## Core Intelligence Capabilities

### **Context-Aware Conversations**
- Multi-turn dialogue with conversation memory
- "És a házban?" context expansion from previous questions
- Hungarian language understanding and area/domain detection
- Hierarchical entity prioritization (primary vs contextual information)

### **Pattern Recognition & Inference**
- **Activity detection**: Zuhanyzás from humidity patterns, főzés from kitchen sensors
- **Indirect monitoring**: Nyitott ablak detection from temperature/humidity/heating correlation
- **Behavioral learning**: User routine patterns and optimal timing suggestions
- **Cross-sensor analysis**: Multi-room pattern correlation

### **Proactive Home Monitoring**
- **"Mi újság otthon?" intelligence**: Comprehensive status reports since last conversation
- **Anomaly alerts**: Energy waste (klíma + nyitott teraszajtó), unusual patterns
- **Predictive maintenance**: Device health monitoring from sensor telemetry
- **Security awareness**: Motion pattern analysis, unusual activity detection

## Technical Architecture

### **Enhanced Stack**
```
Home Assistant → Extended OpenAI → LiteLLM Proxy → ha-rag-bridge
                                                      ↓
                                               ArangoDB (graph + vector + time-series)
                                                      ↓  
                                               MindsDB (ML pattern recognition)
                                                      ↓
                                               LlamaCPP + Mistral 7B (local reasoning)
```

### **Core Components**
- **ArangoDB**: Graph-based conversation tracking, entity relationships, temporal patterns
- **MindsDB**: ML models for activity detection, anomaly recognition, behavioral learning  
- **LlamaCPP**: Local AI reasoning (Mistral 7B Q5) for pattern explanation and privacy
- **Cross-encoder**: Conversation-aware entity reranking for relevance
- **Enhanced RAG**: Context-aware system prompt generation with hierarchy

## Project Description

**Next-generation home automation intelligence** that transforms sensor data into actionable insights through AI. Combines traditional RAG with graph-based conversation memory, ML pattern recognition, and local AI reasoning to create a truly intelligent home assistant capable of understanding context, detecting patterns, and providing proactive recommendations.



## Technologies

- Python 3.13+
- FastAPI
- ArangoDB
- Docker
- Poetry
- WebSockets
- Vector Search
- Embeddings
- OpenAI API
- Google Gemini
- Home Assistant
- REST API



## Libraries and Dependencies

- fastapi
- uvicorn
- httpx
- openai
- python-arango
- sentence-transformers
- websockets
- influxdb-client
- cachetools
- colorama
- pdfminer.six
- structlog
- pydantic
- google-genai
- typer
- rouge-score

