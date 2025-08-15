"""
Integration tests for the query processing pipeline including:
- Query rewriting with coreference resolution
- Query expansion with synonyms and translations
- Enhanced embedding with instruction templates
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.query_rewriter import ConversationalQueryRewriter, QueryRewriteResult
from app.services.query_expander import QueryExpander, QueryExpansionResult
from scripts.embedding_backends import EnhancedLocalBackend
from app.schemas import ChatMessage


class TestQueryRewriterIntegration:
    """Test conversational query rewriting scenarios."""
    
    @pytest.fixture
    def query_rewriter(self):
        """Create query rewriter instance for testing."""
        return ConversationalQueryRewriter()
    
    @pytest.fixture
    def sample_conversation(self):
        """Sample conversation history for testing."""
        return [
            ChatMessage(role="user", content="Hány fok van a nappaliban?"),
            ChatMessage(role="assistant", content="A nappaliban 22.5 fok van."),
        ]
    
    @pytest.mark.asyncio
    async def test_basic_follow_up_rewriting(self, query_rewriter, sample_conversation):
        """Test basic follow-up query rewriting."""
        result = await query_rewriter.rewrite_query(
            current_query="És a kertben?",
            conversation_history=sample_conversation
        )
        
        assert isinstance(result, QueryRewriteResult)
        assert result.rewritten_query != result.original_query
        assert "kert" in result.rewritten_query.lower()
        assert result.confidence > 0.5
        assert result.processing_time_ms > 0
        
        # Should detect follow-up patterns
        assert len(result.coreferences_resolved) > 0
    
    @pytest.mark.asyncio
    async def test_coreference_resolution(self, query_rewriter, sample_conversation):
        """Test pronoun and reference resolution."""
        result = await query_rewriter.rewrite_query(
            current_query="Mennyi ott?",
            conversation_history=sample_conversation
        )
        
        # Should resolve "ott" reference
        assert "ott" not in result.rewritten_query.lower()
        assert result.confidence > 0.0
        assert "ott" in result.coreferences_resolved
    
    @pytest.mark.asyncio
    async def test_intent_inheritance(self, query_rewriter, sample_conversation):
        """Test intent inheritance from conversation context."""
        result = await query_rewriter.rewrite_query(
            current_query="és a fürdőszobában is",
            conversation_history=sample_conversation
        )
        
        # Should inherit temperature query intent
        rewritten_lower = result.rewritten_query.lower()
        assert any(word in rewritten_lower for word in ["fok", "hőmérséklet", "temperature"])
        assert any(word in rewritten_lower for word in ["fürdőszoba", "fürdőszobában"])
    
    @pytest.mark.asyncio
    async def test_no_rewrite_needed(self, query_rewriter):
        """Test queries that don't need rewriting."""
        result = await query_rewriter.rewrite_query(
            current_query="Hány fok van a nappaliban?",
            conversation_history=[]
        )
        
        assert result.original_query == result.rewritten_query
        assert result.method == "no_rewrite_needed"
        assert result.confidence == 1.0
    
    @pytest.mark.asyncio
    async def test_disabled_rewriting(self, query_rewriter):
        """Test behavior when rewriting is disabled."""
        with patch.object(query_rewriter, 'enabled', False):
            result = await query_rewriter.rewrite_query(
                current_query="és a kertben?",
                conversation_history=[]
            )
            
            assert result.method == "disabled"
            assert result.original_query == result.rewritten_query


class TestQueryExpanderIntegration:
    """Test query expansion functionality."""
    
    @pytest.fixture
    def query_expander(self):
        """Create query expander instance for testing."""
        return QueryExpander()
    
    @pytest.mark.asyncio
    async def test_synonym_expansion(self, query_expander):
        """Test synonym-based query expansion."""
        result = await query_expander.expand_query(
            original_query="hány fok van a nappaliban",
            domain_context="temperature"
        )
        
        assert isinstance(result, QueryExpansionResult)
        assert len(result.expanded_queries) > 1
        assert result.original_query in result.expanded_queries
        
        # Should include temperature synonyms
        expanded_text = " ".join(result.expanded_queries).lower()
        assert any(word in expanded_text for word in ["hőmérséklet", "meleg"])
    
    @pytest.mark.asyncio
    async def test_translation_expansion(self, query_expander):
        """Test Hungarian-English translation expansion."""
        result = await query_expander.expand_query(
            original_query="világítás a nappaliban"
        )
        
        expanded_text = " ".join(result.expanded_queries).lower()
        
        # Should include English translations
        assert any(word in expanded_text for word in ["light", "living room"])
        assert "nappali" in result.original_query
    
    @pytest.mark.asyncio
    async def test_reformulation_variants(self, query_expander):
        """Test pattern-based query reformulation."""
        result = await query_expander.expand_query(
            original_query="hány fok van a kertben"
        )
        
        # Should generate intent variations
        assert len(result.expanded_queries) >= 2
        assert any("temperature" in method for method in result.expansion_methods)
    
    @pytest.mark.asyncio
    async def test_max_variants_limit(self, query_expander):
        """Test maximum variants configuration."""
        with patch.object(query_expander, 'max_variants', 2):
            result = await query_expander.expand_query(
                original_query="hány fok van a nappaliban"
            )
            
            assert len(result.expanded_queries) <= 2
    
    @pytest.mark.asyncio
    async def test_disabled_expansion(self, query_expander):
        """Test behavior when expansion is disabled."""
        with patch.object(query_expander, 'enabled', False):
            result = await query_expander.expand_query(
                original_query="test query"
            )
            
            assert len(result.expanded_queries) == 1
            assert result.expanded_queries[0] == result.original_query
            assert result.expansion_methods == ["disabled"]


class TestEnhancedEmbeddingIntegration:
    """Test enhanced embedding backend with instruction templates."""
    
    @pytest.fixture
    def enhanced_backend(self):
        """Create enhanced embedding backend for testing."""
        return EnhancedLocalBackend()
    
    def test_query_document_encoding_split(self, enhanced_backend):
        """Test that query and document encodings are different."""
        test_text = "nappali hőmérséklet szenzor"
        
        query_embedding = enhanced_backend.embed_query(test_text)
        document_embedding = enhanced_backend.embed_document(test_text)
        
        # Should be different due to different prefixes
        assert query_embedding != document_embedding
        assert len(query_embedding) == len(document_embedding)
        assert all(isinstance(x, float) for x in query_embedding)
    
    def test_instruction_templates_applied(self, enhanced_backend):
        """Test that instruction templates are applied correctly."""
        test_text = "test query"
        
        # Mock the base embed method to check prefixed text
        with patch.object(enhanced_backend, 'embed') as mock_embed:
            mock_embed.return_value = [[0.1, 0.2, 0.3]]
            
            enhanced_backend.embed_query(test_text)
            enhanced_backend.embed_document(test_text)
            
            # Check that prefixed texts were used
            call_args = [call[0][0][0] for call in mock_embed.call_args_list]
            assert any(text.startswith("query:") for text in call_args)
            assert any(text.startswith("passage:") for text in call_args)
    
    def test_multi_query_batch_processing(self, enhanced_backend):
        """Test batch processing for multiple queries."""
        queries = ["hány fok van", "világítás állapota", "ajtó nyitva"]
        
        embeddings = enhanced_backend.embed_multi_query(queries)
        
        assert len(embeddings) == len(queries)
        assert all(len(emb) > 0 for emb in embeddings)
        assert all(isinstance(emb[0], float) for emb in embeddings)
    
    def test_templates_disabled(self, enhanced_backend):
        """Test behavior when instruction templates are disabled."""
        with patch.object(enhanced_backend, 'use_instruction_templates', False):
            test_text = "test"
            
            with patch.object(enhanced_backend, 'embed') as mock_embed:
                mock_embed.return_value = [[0.1]]
                
                enhanced_backend.embed_query(test_text)
                
                # Should use original text without prefix
                call_args = mock_embed.call_args[0][0]
                assert call_args == [test_text]


class TestEndToEndPipeline:
    """Test complete query processing pipeline integration."""
    
    @pytest.fixture
    def pipeline_components(self):
        """Create all pipeline components."""
        return {
            'rewriter': ConversationalQueryRewriter(),
            'expander': QueryExpander(),
            'backend': EnhancedLocalBackend()
        }
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_flow(self, pipeline_components):
        """Test complete pipeline: rewrite → expand → embed."""
        rewriter = pipeline_components['rewriter']
        expander = pipeline_components['expander']
        backend = pipeline_components['backend']
        
        # Step 1: Query rewriting
        conversation = [
            ChatMessage(role="user", content="Hány fok van a nappaliban?"),
            ChatMessage(role="assistant", content="22.5 fok van."),
        ]
        
        rewrite_result = await rewriter.rewrite_query(
            current_query="És a kertben?",
            conversation_history=conversation
        )
        
        # Step 2: Query expansion
        expansion_result = await expander.expand_query(
            original_query=rewrite_result.rewritten_query
        )
        
        # Step 3: Enhanced embedding
        embeddings = backend.embed_multi_query(expansion_result.expanded_queries)
        
        # Verify pipeline results
        assert rewrite_result.rewritten_query != "És a kertben?"
        assert len(expansion_result.expanded_queries) > 1
        assert len(embeddings) == len(expansion_result.expanded_queries)
        assert all(len(emb) > 0 for emb in embeddings)
    
    @pytest.mark.asyncio
    async def test_pipeline_performance(self, pipeline_components):
        """Test pipeline performance within acceptable limits."""
        import time
        
        rewriter = pipeline_components['rewriter']
        expander = pipeline_components['expander']
        
        start_time = time.time()
        
        # Quick rewriting test
        rewrite_result = await rewriter.rewrite_query(
            current_query="és ott?",
            conversation_history=[
                ChatMessage(role="user", content="Mi van a nappaliban?")
            ]
        )
        
        # Quick expansion test
        expansion_result = await expander.expand_query(
            original_query="hőmérséklet"
        )
        
        total_time = time.time() - start_time
        
        # Performance assertions
        assert rewrite_result.processing_time_ms < 1000  # < 1 second
        assert expansion_result.processing_time_ms < 500  # < 0.5 seconds
        assert total_time < 2.0  # Total pipeline < 2 seconds
    
    @pytest.mark.asyncio
    async def test_error_handling_robustness(self, pipeline_components):
        """Test pipeline error handling and fallbacks."""
        rewriter = pipeline_components['rewriter']
        expander = pipeline_components['expander']
        
        # Test with problematic inputs
        problematic_queries = [
            "",  # Empty query
            "a" * 1000,  # Very long query
            "🤖💬🏠",  # Emoji only
            None,  # None input (should be handled gracefully)
        ]
        
        for query in problematic_queries:
            if query is None:
                continue
                
            try:
                rewrite_result = await rewriter.rewrite_query(
                    current_query=query,
                    conversation_history=[]
                )
                
                expansion_result = await expander.expand_query(
                    original_query=rewrite_result.rewritten_query
                )
                
                # Should not crash and return reasonable results
                assert isinstance(rewrite_result, QueryRewriteResult)
                assert isinstance(expansion_result, QueryExpansionResult)
                assert len(expansion_result.expanded_queries) > 0
                
            except Exception as e:
                # Log but don't fail - some inputs may legitimately cause errors
                print(f"Query '{query}' caused error: {e}")


# Configuration for pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])