from tool_utils import get_current_time
import json

def run_tool(tool_call, user_message):
    input = {
        message: user_message,
        tool_args: json.loads(tool_call.function.argument or {})
    }

    tool_name_to_func_mapping = {
        "get_current_time": get_current_time
    }

    tool_name = tool_call.function.name
    
    if tool_name in tool_name_to_func_mapping:
        tool = tool_name_to_func_mapping[tool_name]
        return tool(input)