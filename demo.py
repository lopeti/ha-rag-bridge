import argparse
import asyncio
import json
import os
from typing import List, Dict

import httpx
try:
    from colorama import Fore, Style
    _COLOR = True
except Exception:
    class Dummy:
        RESET = ''
    Fore = Style = Dummy()
    _COLOR = False

API_URL = os.getenv("DEMO_API_URL", "http://localhost:8000")


def _color(text: str, color: str) -> str:
    if _COLOR:
        return f"{color}{text}{Style.RESET_ALL}"
    return text


def _parse_first_entity(system_prompt: str) -> str | None:
    for line in system_prompt.splitlines():
        if line.lower().startswith("relevant entities:"):
            parts = line.split(":", 1)[1].strip().split(",")
            return parts[0].strip() if parts else None
    return None


def stub_llm(messages: List[Dict], tools: List[Dict]) -> Dict:
    """Return a dummy LLM response."""
    reply_content = messages[-1]["content"]
    if not tools:
        return {"role": "assistant", "content": reply_content}

    tool = tools[0]
    func = tool["function"]
    args: Dict[str, str] = {}
    params = func.get("parameters", {}).get("properties", {})
    if params:
        first_param = next(iter(params))
        if first_param == "entity_id":
            ent = _parse_first_entity(messages[0]["content"])
            if ent:
                args[first_param] = ent
    tool_calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {
                "name": func["name"],
                "arguments": json.dumps(args),
            },
        }
    ]
    return {"role": "assistant", "content": reply_content, "tool_calls": tool_calls}


async def run_demo(question: str, llm: str = "stub") -> str:
    print(_color(f"> USER: {question}", Fore.GREEN))
    async with httpx.AsyncClient(base_url=API_URL, timeout=10.0) as client:
        r1 = await client.post("/process-request", json={"user_message": question})
    print(_color(f"\u2192 /process-request: {r1.status_code} {r1.reason_phrase}", Fore.CYAN))
    data = r1.json()
    messages = data.get("messages", [])
    tools = data.get("tools", [])

    if llm == "stub":
        assistant = stub_llm(messages, tools)
        if assistant.get("tool_calls"):
            tc = assistant["tool_calls"][0]
            print(_color(
                f"\u2192 Stub-LLM: calling {tc['function']['name']}({tc['function']['arguments']})",
                Fore.MAGENTA,
            ))
    else:
        assistant = {"role": "assistant", "content": messages[-1]["content"], "tool_calls": None}

    payload = {"id": "1", "choices": [{"message": assistant}]}
    async with httpx.AsyncClient(base_url=API_URL, timeout=10.0) as client:
        r2 = await client.post("/process-response", json=payload)
    print(_color(f"\u2192 /process-response: {r2.status_code} {r2.reason_phrase}", Fore.CYAN))
    result = r2.json()
    print(_color(f"< ASSISTANT: {result.get('message')}", Fore.YELLOW))
    return result.get("message", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs=1, help="User question")
    parser.add_argument("--llm", choices=["stub", "openai", "gemini"], default="stub")
    args = parser.parse_args()
    asyncio.run(run_demo(args.question[0], args.llm))


if __name__ == "__main__":
    main()
