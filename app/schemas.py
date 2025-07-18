from pydantic import BaseModel, field_validator, ConfigDict, Field
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

class EdgeCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="_from")
    to: str = Field(alias="_to")
    label: str
    weight: float = 1.0
    source: str | None = None
    ts_created: str | None = None

    @field_validator('label')
    @classmethod
    def _valid_label(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('label must not be empty')
        if len(v) > 30:
            raise ValueError('label too long')
        return v


class EdgeResult(BaseModel):
    status: str
    edge_key: str
    action: str

