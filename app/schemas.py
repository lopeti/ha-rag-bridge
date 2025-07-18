from pydantic import BaseModel
from typing import List, Dict


class Request(BaseModel):
    user_message: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ProcessResponse(BaseModel):
    messages: List[ChatMessage]
    tools: List[Dict]


class LLMToolFunction(BaseModel):
    name: str
    arguments: str


class LLMToolCall(BaseModel):
    id: str
    type: str
    function: LLMToolFunction


class LLMMessage(BaseModel):
    role: str
    content: str
    tool_calls: List[LLMToolCall] | None = None


class LLMChoice(BaseModel):
    message: LLMMessage


class LLMResponse(BaseModel):
    id: str
    choices: List[LLMChoice]


class ExecResult(BaseModel):
    status: str
    message: str
