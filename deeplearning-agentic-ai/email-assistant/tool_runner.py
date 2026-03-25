from typing import Any
from openai.types.chat import ChatCompletionMessageToolCall

from tool_utils import get_current_time, get_weather_from_ip, get_location_coordinates_from_ip, write_text_file, generate_qr_code
import json


def run_tool(tool_call: ChatCompletionMessageToolCall, user_message: str) -> str:
    tool_args = json.loads(tool_call.function.arguments)

    match tool_call.function.name:
        case "get_current_time":
            return get_current_time()
        case "get_location_coordinates_from_ip":
            lat, lng = get_location_coordinates_from_ip()
            return f"Latitude={lat},Longitude={lng}"
        case "get_weather_from_ip":
            return get_weather_from_ip()
        case "write_text_file":
            return write_text_file(tool_args.get("file_path"), tool_args.get("content"))
        case "generate_qr_code":
            return generate_qr_code(
                tool_args.get("data"), 
                tool_args.get("filename"),
                tool_args.get("image_path")
            )
        case _:
            raise ValueError(f"Tool '{tool_call.function.name}' is not available.")
