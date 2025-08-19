"""RAG workflow state definition for LangGraph."""

from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum


class QueryScope(Enum):
    """Query scope levels for adaptive RAG retrieval."""

    MICRO = "micro"  # k=5-10, specific actions
    MACRO = "macro"  # k=15-30, area-based
    OVERVIEW = "overview"  # k=30-50, house-wide


class RAGState(TypedDict):
    """Complete state schema for the RAG workflow."""

    # Input
    user_query: str
    session_id: str
    conversation_history: List[Dict[str, Any]]

    # Analysis Results
    conversation_context: Optional[Dict[str, Any]]
    detected_scope: Optional[QueryScope]
    scope_confidence: float
    optimal_k: Optional[int]

    # Entity Retrieval
    retrieved_entities: List[Dict[str, Any]]
    cluster_entities: List[Dict[str, Any]]
    memory_entities: List[Dict[str, Any]]
    reranked_entities: List[Dict[str, Any]]

    # Context Building
    formatted_context: str
    formatter_type: str
    _force_formatter: Optional[str]

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

    # Tracing
    trace_id: Optional[str]
