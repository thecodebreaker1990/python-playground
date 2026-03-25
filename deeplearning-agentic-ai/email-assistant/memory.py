import os
import json
import uuid
from datetime import datetime
from typing import Any, Union
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionToolMessageParam,
)

DB_FILE: str = "db.json"

AIMessage = Union[
    ChatCompletionAssistantMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionToolMessageParam,
]


# AIMessage dict with metadata fields merged in for DB storage
MessageWithMetaData = dict[str, Any]

DBDict = dict[str, Any]


def load_db() -> DBDict:
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data: DBDict) -> None:
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

db = load_db()

def generate_unique_id() -> str:
    return str(uuid.uuid4())


def add_metadata(message: AIMessage) -> MessageWithMetaData:
    msg_dict: dict[str, Any] = message if isinstance(message, dict) else message.model_dump()
    return {
        **msg_dict,
        "id": generate_unique_id(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def remove_metadata(message: MessageWithMetaData) -> AIMessage:
    new_message: MessageWithMetaData = {**message}
    new_message.pop("id", None)
    new_message.pop("created_at", None)
    return new_message


def add_messages(messages: list[AIMessage]) -> None:
    db.setdefault("messages", []).extend(add_metadata(message) for message in messages)
    save_db(db)


def get_messages() -> list[AIMessage]:
    return [remove_metadata(message) for message in db.get("messages", [])]

def save_tool_response(tool_call_id: str, tool_result: str) -> None:
    return add_messages([{
        "role": "tool", 
        "tool_call_id": tool_call_id, 
        "content": tool_result
    }])
