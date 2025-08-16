from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import json
import time

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {"status": "ok", "message": "Simple admin router is working"}


@router.get("/overview")
async def get_overview():
    """Simple overview endpoint"""
    return {
        "database": {"name": "test", "status": "ok"},
        "system": {"uptime": "1h", "memory": "512MB"},
    }


@router.get("/test-streaming")
async def test_streaming():
    """Test SSE endpoint for frontend popup validation"""

    async def generate_test_stream():
        """Generate test streaming data"""
        steps = [
            "🚀 Starting test operation...",
            "📊 Initializing components...",
            "🔍 Processing data (step 1/5)...",
            "⚙️ Processing data (step 2/5)...",
            "🔧 Processing data (step 3/5)...",
            "📈 Processing data (step 4/5)...",
            "✅ Processing data (step 5/5)...",
            "🎉 Test operation completed successfully!",
        ]

        for i, step in enumerate(steps):
            # Simulate some processing time
            await asyncio.sleep(0.8)

            # Create SSE-formatted message
            data = {
                "message": step,
                "progress": int((i + 1) / len(steps) * 100),
                "step": i + 1,
                "total": len(steps),
                "timestamp": time.strftime("%H:%M:%S"),
            }

            yield f"data: {json.dumps(data)}\n\n"

        # Send completion event
        yield f"data: {json.dumps({'completed': True, 'message': 'Stream completed'})}\n\n"

    return StreamingResponse(
        generate_test_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )
