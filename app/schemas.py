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
