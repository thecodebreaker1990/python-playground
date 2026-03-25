from typing import Any
from openai.types.chat import ChatCompletionMessageToolCall

from tool_utils import get_current_time
import json


def run_tool(tool_call: ChatCompletionMessageToolCall, user_message: str) -> str:
    input: dict[str, Any] = {
        "message": user_message,
        "tool_args": json.loads(tool_call.function.arguments)
    }

    match tool_call.function.name:
        case "get_current_time":
            return get_current_time()
        case _:
            raise ValueError(f"Tool '{tool_call.function.name}' is not available.")
