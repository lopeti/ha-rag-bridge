#!/usr/bin/env python3
"""Web-based LangGraph Phase 3 workflow debugger with real-time node visualization."""

import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

from app.langgraph_workflow.workflow import run_rag_workflow
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)

app = FastAPI(title="LangGraph Phase 3 Workflow Debugger")


@app.get("/", response_class=HTMLResponse)
async def workflow_debugger_ui():
    """Serve the workflow debugger UI."""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>🚀 LangGraph Phase 3 Workflow Debugger</title>
    <style>
        body { font-family: monospace; background: #1a1a1a; color: #ffffff; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .query-form { background: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .query-input { width: 70%; padding: 10px; font-size: 16px; background: #3a3a3a; border: 1px solid #555; color: #fff; }
        .debug-btn { padding: 10px 20px; font-size: 16px; background: #007acc; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .debug-btn:hover { background: #005a9e; }
        .results { background: #2a2a2a; padding: 20px; border-radius: 8px; margin-top: 20px; }
        .node-section { background: #3a3a3a; margin: 10px 0; padding: 15px; border-left: 4px solid #007acc; }
        .node-title { color: #00ff88; font-weight: bold; font-size: 18px; }
        .node-details { margin-left: 20px; color: #cccccc; }
        .error { color: #ff6b6b; }
        .success { color: #00ff88; }
        .warning { color: #ffa500; }
        .entity-list { max-height: 300px; overflow-y: auto; }
        .entity { padding: 5px; border-left: 2px solid #555; margin-left: 10px; }
        .loading { color: #ffa500; font-style: italic; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 LangGraph Phase 3 Workflow Debugger</h1>
            <p>Real-time node visualization and debugging</p>
        </div>
        
        <div class="query-form">
            <h3>📝 Enter Query:</h3>
            <input type="text" id="queryInput" class="query-input" placeholder="mi van a nappaliban? / kapcsold fel a lámpát / termel a napelem?" />
            <button class="debug-btn" onclick="debugWorkflow()">🔍 Debug Workflow</button>
        </div>
        
        <div id="results" class="results" style="display: none;">
            <h3>📊 Workflow Execution Results:</h3>
            <div id="workflowSteps"></div>
        </div>
    </div>

    <script>
        async function debugWorkflow() {
            const query = document.getElementById('queryInput').value.trim();
            if (!query) {
                alert('Please enter a query!');
                return;
            }
            
            const resultsDiv = document.getElementById('results');
            const stepsDiv = document.getElementById('workflowSteps');
            
            resultsDiv.style.display = 'block';
            stepsDiv.innerHTML = '<div class="loading">🔄 Running workflow...</div>';
            
            try {
                const response = await fetch('/debug', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    displayWorkflowResults(result.data);
                } else {
                    stepsDiv.innerHTML = `<div class="error">❌ Error: ${result.error}</div>`;
                }
            } catch (error) {
                stepsDiv.innerHTML = `<div class="error">❌ Network Error: ${error.message}</div>`;
            }
        }
        
        function displayWorkflowResults(data) {
            const stepsDiv = document.getElementById('workflowSteps');
            
            let html = `
                <div class="node-section">
                    <div class="node-title">⏱️ Execution Summary</div>
                    <div class="node-details">
                        Duration: ${data.duration.toFixed(2)}s<br>
                        Total Entities: ${data.entity_count}<br>
                        Quality Score: ${data.quality_score.toFixed(2)}
                    </div>
                </div>
            `;
            
            // Conversation Analysis Node
            const conv = data.conversation_context;
            html += `
                <div class="node-section">
                    <div class="node-title">🗣️ Conversation Analysis Node</div>
                    <div class="node-details">
                        Areas: ${conv.areas_mentioned.join(', ') || 'none'}<br>
                        Domains: ${conv.domains_mentioned.join(', ') || 'none'}<br>
                        Intent: ${conv.intent} (confidence: ${conv.confidence})<br>
                        Follow-up: ${conv.is_follow_up ? 'Yes' : 'No'}
                    </div>
                </div>
            `;
            
            // Scope Detection Node
            html += `
                <div class="node-section">
                    <div class="node-title">🎯 Scope Detection Node</div>
                    <div class="node-details">
                        Detected Scope: <strong>${data.detected_scope}</strong><br>
                        Confidence: ${data.scope_confidence.toFixed(2)}<br>
                        Optimal K: ${data.optimal_k}<br>
                        Reasoning: ${data.scope_reasoning || 'N/A'}
                    </div>
                </div>
            `;
            
            // Entity Retrieval Node
            html += `
                <div class="node-section">
                    <div class="node-title">🔍 Entity Retrieval Node</div>
                    <div class="node-details">
                        Total Retrieved: ${data.entity_counts.total}<br>
                        From Clusters: ${data.entity_counts.cluster}<br>
                        From Memory: ${data.entity_counts.memory}<br>
                        Memory Boosted: ${data.entity_counts.memory_boosted}
                    </div>
                </div>
            `;
            
            // Context Formatting Node
            html += `
                <div class="node-section">
                    <div class="node-title">📝 Context Formatting Node</div>
                    <div class="node-details">
                        Formatter Type: ${data.formatter_type}<br>
                        Context Length: ${data.context_length} characters<br>
                        <details>
                            <summary>Context Preview</summary>
                            <pre style="white-space: pre-wrap; color: #aaa;">${data.context_preview}</pre>
                        </details>
                    </div>
                </div>
            `;
            
            // Top Entities
            if (data.top_entities.length > 0) {
                html += `
                    <div class="node-section">
                        <div class="node-title">🏠 Top Retrieved Entities</div>
                        <div class="node-details entity-list">
                `;
                data.top_entities.forEach((entity, i) => {
                    const badges = [];
                    if (entity.memory_boosted) badges.push('MEMORY');
                    if (entity.cluster_context) badges.push('CLUSTER');
                    const badgeStr = badges.length > 0 ? ` [${badges.join(', ')}]` : '';
                    
                    html += `
                        <div class="entity">
                            ${i + 1}. <strong>${entity.entity_id}</strong> (score: ${entity.score.toFixed(3)})<br>
                            &nbsp;&nbsp;&nbsp;&nbsp;Area: ${entity.area || 'no area'}${badgeStr}
                        </div>
                    `;
                });
                html += `
                        </div>
                    </div>
                `;
            }
            
            // Errors and Diagnostics
            if (data.errors.length > 0 || data.diagnostics) {
                html += `
                    <div class="node-section">
                        <div class="node-title">⚠️ Diagnostics & Issues</div>
                        <div class="node-details">
                `;
                
                if (data.errors.length > 0) {
                    html += '<div class="error">Errors:</div>';
                    data.errors.forEach(error => {
                        html += `<div class="error">• ${error}</div>`;
                    });
                }
                
                if (data.diagnostics) {
                    html += `
                        <div class="success">Diagnostics:</div>
                        <div>Overall Quality: ${data.diagnostics.overall_quality.toFixed(2)}</div>
                        <div>Components:</div>
                        <div>&nbsp;&nbsp;- Conversation: ${data.diagnostics.conversation_analysis_quality.toFixed(2)}</div>
                        <div>&nbsp;&nbsp;- Scope Detection: ${data.diagnostics.scope_detection_quality.toFixed(2)}</div>
                        <div>&nbsp;&nbsp;- Entity Retrieval: ${data.diagnostics.entity_retrieval_quality.toFixed(2)}</div>
                        <div>&nbsp;&nbsp;- Context Formatting: ${data.diagnostics.context_formatting_quality.toFixed(2)}</div>
                    `;
                    
                    if (data.diagnostics.recommendations && data.diagnostics.recommendations.length > 0) {
                        html += '<div class="warning">Recommendations:</div>';
                        data.diagnostics.recommendations.forEach(rec => {
                            html += `<div class="warning">• ${rec}</div>`;
                        });
                    }
                }
                
                html += '</div></div>';
            }
            
            stepsDiv.innerHTML = html;
        }
        
        // Allow Enter key to trigger debug
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('queryInput').addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    debugWorkflow();
                }
            });
        });
    </script>
</body>
</html>
    """
    return html_content


@app.post("/debug")
async def debug_workflow_endpoint(request: Request):
    """Debug workflow endpoint."""
    try:
        data = await request.json()
        query = data.get("query", "").strip()

        if not query:
            return {"success": False, "error": "Query is required"}

        logger.info(f"Debugging workflow for query: {query}")

        session_id = f"web_debug_{int(time.time())}"
        start_time = time.time()

        # Run the workflow
        result = await run_rag_workflow(
            user_query=query, session_id=session_id, conversation_history=[]
        )

        end_time = time.time()
        duration = end_time - start_time

        # Extract and structure the results
        entities = result.get("retrieved_entities", [])
        diagnostics = result.get("diagnostics", {})

        # Process top entities
        top_entities = []
        for entity in entities[:8]:  # Top 8 entities
            top_entities.append(
                {
                    "entity_id": entity.get("entity_id", "unknown"),
                    "score": entity.get("_score", 0.0),
                    "area": entity.get("area_name", "no area"),
                    "memory_boosted": entity.get("_memory_boosted", False),
                    "cluster_context": bool(entity.get("_cluster_context")),
                }
            )

        # Structure the response
        response_data = {
            "duration": duration,
            "entity_count": len(entities),
            "quality_score": diagnostics.get("overall_quality", 0.0),
            "conversation_context": result.get("conversation_context", {}),
            "detected_scope": str(result.get("detected_scope", "unknown")).replace(
                "QueryScope.", ""
            ),
            "scope_confidence": result.get("scope_confidence", 0.0),
            "optimal_k": result.get("optimal_k", 0),
            "scope_reasoning": result.get("scope_reasoning", ""),
            "entity_counts": {
                "total": len(entities),
                "cluster": len(result.get("cluster_entities", [])),
                "memory": len(result.get("memory_entities", [])),
                "memory_boosted": len(
                    [e for e in entities if e.get("_memory_boosted")]
                ),
            },
            "formatter_type": result.get("formatter_type", "unknown"),
            "context_length": len(result.get("formatted_context", "")),
            "context_preview": result.get("formatted_context", "")[:500]
            + ("..." if len(result.get("formatted_context", "")) > 500 else ""),
            "top_entities": top_entities,
            "errors": result.get("errors", []),
            "diagnostics": diagnostics if diagnostics else None,
        }

        return {"success": True, "data": response_data}

    except Exception as e:
        logger.error(f"Debug workflow error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("🚀 Starting LangGraph Phase 3 Workflow Debugger Web UI...")
    print("📍 Access at: http://localhost:8899")
    uvicorn.run(app, host="0.0.0.0", port=8899, log_level="info")
