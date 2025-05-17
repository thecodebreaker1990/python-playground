import logging
from urllib.parse import urlparse

custom_header_name = "shield-session-id"

def check_for_browser_token(headers):
    """
    Check if the request contains the custom header 'Shield-Session-ID'.
    Returns the header value if found, else None.
    """
    if custom_header_name in headers:
        return headers[custom_header_name]
    return None

def delete_unwanted_headers(networkFlow, flowType):
    res_headers = ['access-control-allow-headers', 'access-control-allow-origin', 'Content-Security-Policy',  'Content-Length', 'Content-Security-Policy-Report-Only']
    req_headers = ['access-control-request-headers', 'access-control-request-method']

    final_headers = req_headers if flowType == "request" else res_headers

    for header in final_headers:
        if header in networkFlow.headers:
            del networkFlow.headers[header]

def get_new_headers(res, req):
    return {
        'Custom-Header-Received': req.headers.get(custom_header_name, '-'),
        'Access-Control-Allow-Headers': modify_header_values(
            res.headers.get('Access-Control-Allow-Headers') or res.headers.get('access-control-allow-headers'),
            custom_header_name
        ),
        'Access-Control-Allow-Methods': modify_header_values(
            res.headers.get('Access-Control-Allow-Methods') or res.headers.get('access-control-allow-methods'),
            'PUT,PATCH,DELETE'
        ),
        'Access-Control-Allow-Origin': modify_header_values(
            res.headers.get('Access-Control-Allow-Origin') or res.headers.get('access-control-allow-origin'),
            urlparse(req.headers.get('Referer', '*')).scheme + '://' + urlparse(req.headers.get('Referer', '*')).netloc
            if 'Referer' in req.headers else '*'
        ),
    }

def convert_list_values_to_string(input_dict):
    """
    Converts list values in a dictionary to a string representation.

    :param input_dict: Dictionary with possible list values
    :return: Updated dictionary with lists converted to strings
    """
    updated_dict = {
        key: ', '.join(map(str, value)) if isinstance(value, list) else value
        for key, value in input_dict.items()
    }
    return updated_dict

def load_worker_script(file_path):
    """
    Reads the content of the Service Worker script from a file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Failed to load script: {e}")
        return

def modify_header_values(header, value):
    if header == '*' or value == '*':
        return '*'
    if not header:
        return [value]
    if isinstance(header, list):
        return list(set(header + [value]))
    return list(set([header, value]))
    
def capitalize_str_by_separator(strel, separator = '-'):
    str_arr = strel.split(separator)
    str_arr = [x.capitalize() for x in str_arr]
    return separator.join(str_arr)

def modify_iframe_tag(html_content):
    """Modify the iframe tag to include the 'sandbox' attribute."""
    return html_content.replace('<iframe', '<iframe sandbox="allow-scripts"')