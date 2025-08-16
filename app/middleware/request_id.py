from uuid import uuid4
import structlog


async def request_id_middleware(request, call_next):
    req_id = uuid4().hex
    request.state.req_id = req_id
    with structlog.contextvars.bound_contextvars(req_id=req_id):
        return await call_next(request)
