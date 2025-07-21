import os
import asyncio
import json
import argparse
import logging
import websockets

try:
    from .ingest import ingest        # package run
except ImportError:                    # direct run
    from ingest import ingest

from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)

WS_PATH = "/api/websocket"


async def _handle_messages(ws: websockets.WebSocketClientProtocol) -> None:
    """Process incoming websocket messages."""
    # Wait for auth_ok
    while True:
        msg = await ws.recv()
        data = json.loads(msg)
        if data.get("type") == "auth_required":
            continue
        if data.get("type") == "auth_ok":
            break
        if data.get("type") == "auth_invalid":
            raise RuntimeError("Authentication failed")

    # Subscribe to entity registry updates
    await ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "entity_registry_updated"}))

    while True:
        msg = await ws.recv()
        data = json.loads(msg)
        if data.get("type") != "event":
            continue
        event = data.get("event", {})
        e_data = event.get("data", {})
        entity_id = e_data.get("entity_id")
        if not entity_id:
            continue
        action = e_data.get("action")
        ingest(entity_id)
        logger.info("entity updated", entity_id=entity_id, action=action)


async def watch() -> None:
    url = os.environ["HA_URL"].rstrip("/") + WS_PATH
    token = os.environ["HA_TOKEN"]

    backoffs = [1, 2, 5]
    attempt = 0

    while True:
        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps({"type": "auth", "access_token": token}))
                await _handle_messages(ws)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # pragma: no cover - reconnect
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            logger.warning("websocket error", error=str(exc), wait_s=wait)
            attempt += 1
            await asyncio.sleep(wait)
            continue
        else:
            attempt = 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    try:
        asyncio.run(watch())
    except KeyboardInterrupt:  # pragma: no cover - manual interrupt
        pass


if __name__ == "__main__":
    main()
