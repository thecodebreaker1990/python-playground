import logging
import re

from collections import defaultdict
from mitmproxy import http
from utilsmodule import custom_header_name, convert_list_values_to_string, load_worker_script, check_for_browser_token, delete_unwanted_headers, get_new_headers

# Load the Service Worker related injection scripts from an external file
SW_SCRIPT = load_worker_script("sw.js")
SW_REGISTRATION_SCRIPT = load_worker_script("sw-registration.js")
MINIMAL_INJECTION_SCRIPT = load_worker_script("minimal-injection.js")

class NetworkRequestTracker:
    def __init__(self):
        self.client_requests = defaultdict(list)

    def requestheaders(self, flow: http.HTTPFlow):
        if flow.request.method == "OPTIONS":
            logging.info(f"Pre-flight request intercepted for URL = {flow.request.pretty_url}")
            flow.metadata["modify_response_header"] = True
            delete_unwanted_headers(flow.request, "request")
        
        # Check for the custom header in the request
        shield_token = check_for_browser_token(flow.request.headers)
        if shield_token is not None:
            #logging.info(f"Web Traffic detected for URL = {flow.request.pretty_url}, Token = {shield_token}")
            #flow.metadata["modify_response_header"] = True
            flow.metadata["shield_token"] = shield_token
            del flow.request.headers[custom_header_name]
  
    def request(self, flow: http.HTTPFlow):
        """
        Called when a client request is received.
        We cannot directly return a custom response here if we also need to
        forward the request in other cases. Instead, we set a flag in flow.metadata
        and handle it in the response() hook.
        """
        #client_address = flow.client_conn.peername
        request_info = {
            "url": flow.request.pretty_url,
            "method": flow.request.method,
            "headers": dict(flow.request.headers),
            "user_agent": flow.request.headers.get("User-Agent", "N/A"),
            "accept": flow.request.headers.get("Accept", "N/A")
        }
        self.client_requests[flow.request.pretty_url].append(request_info)

        shield_token = flow.metadata.get("shield_token")

        # Check if this is the request for the SW script:
        if "/shield-proxy-sw.js" in flow.request.path:
            # Parse the query parameter for shield-session-id
            query_params = flow.request.query
            shield_session_id = query_params.get("shield-session-id", None)

            logging.info("-----Service Worker Request-----")
            if shield_session_id:
                logging.info(f"Intercepted SW request with Shield-Session-ID: {shield_session_id} for URL = {request_info['url']}")
                flow.metadata["serve_service_worker"] = True
            else:
                logging.error("SW request intercepted but missing Shield-Session-ID!")

        # Decide if it's an HTML doc request
        is_html_doc_requested = request_info["accept"].startswith("text/html")
        if is_html_doc_requested:
            # Log request info
            logging.info("-----HTML Request-----")
            logging.info(f"URL: {request_info['url']}")
            logging.info(f"Accept: {request_info['accept']}")
            cookies = flow.request.headers.get_all("Cookie")
            for cookie in cookies:
                logging.info(f"Cookie: {cookie}")
            logging.info(f"Method: {request_info['method']}")
            logging.info(f"User-Agent: {request_info['user_agent']}")

            if shield_token is None:
                logging.warning("No Shield-Session-ID found; scheduling custom HTML response.")
                # We'll inject a custom HTML that registers the SW
                flow.metadata["serve_custom_html"] = True
            else:
                logging.info(f"Shield Token detected for URL = {request_info['url']}, Token = {shield_token}")
                logging.warning("Injecting minimum script")
                # We'll inject a minimal script
                flow.metadata["inject_minimum_script"] = True
                
    def responseheaders(self, flow: http.HTTPFlow):
        if flow.metadata.get("modify_response_header") and flow.request.method == "OPTIONS":
            logging.warning("Modifying response headers to overcome CORS issues")
            
            new_headers = get_new_headers(flow.response, flow.request)
            new_headers["Cache-Control"] = "no-cache"
            new_headers = convert_list_values_to_string(new_headers)

            delete_unwanted_headers(flow.response, "response")
            
            flow.response.headers.update(new_headers)

    def response(self, flow: http.HTTPFlow):
        """
        Called when a server response is received (or immediately if we create one).
        If our 'serve_custom_html' flag is set, we replace the response entirely
        with our custom HTML.
        """

        # 2. Serve the Service Worker script at /my-proxy-sw.js
        if flow.metadata.get("serve_service_worker"):
            shield_session_id = flow.request.query.get("shield-session-id", "")
            modified_sw_script = SW_SCRIPT.replace("{{SHIELD_SESSION_ID}}", shield_session_id)
            
            logging.info("-----Service Worker Response-----")
            logging.info(f"Sent SW response with Shield-Session-ID: {shield_session_id} for URL = {flow.request.pretty_url}")

            flow.response = http.Response.make(
                200,
                modified_sw_script.encode("utf-8"),
                {"Content-Type": "application/javascript"}
            )
            return

        # Check if we are modifying an HTML document
        content_type = flow.response.headers.get("Content-Type", "")
        if "text/html" in content_type and flow.metadata.get("serve_custom_html"):
            # Inject script before the closing <head> tag
            html_content = self.handle_html_request(flow.request, flow.response)
            
            logging.info("-----HTML Response-----")
            logging.info(f"Sent HTML response for URL = {flow.request.pretty_url}")

            # Replace the real server response with our own
            flow.response = http.Response.make(
                200,  # status code
                html_content,
                {"Content-Type": "text/html"}
            )

            # Optionally clear the flag so we don't do it again.
            flow.metadata["serve_custom_html"] = False
        elif "text/html" in content_type and flow.metadata.get("inject_minimum_script"):
            # Inject script before the closing <head> tag
            html_content = self.handle_html_request(flow.request, flow.response, True)

            # Replace the real server response with our own
            flow.response = http.Response.make(
                200,  # status code
                html_content,
                {"Content-Type": "text/html"}
            )

            flow.metadata["inject_minimum_script"] = False

    def get_requests_from_client(self, url):
        """Retrieve all requests from a specific client."""
        return self.client_requests.get(url, [])
    
    def handle_html_request(self, req, res, inject_minimal_script = False):
        print(f'Content Encoding = {res.headers.get('Content-Encoding', '')}')
        html_content = res.text  # Get the original HTML content

        if inject_minimal_script:
            html_content = self.inject_minimal_script(html_content)
        else:
            additional_params = [("SHIELD_SESSION_URL", req.pretty_url)]
            
            # Remove or comment out iframes before injecting the shield script
            html_content = self.remove_iframes(html_content)
            html_content = self.add_shield_scripts(html_content, additional_params, '')

        return html_content
    
    def remove_iframes(self, html_content):
        """
        Finds and comments out all <iframe>...</iframe> elements in the HTML content.
        
        This function uses a regular expression to locate iframes and replaces them
        with an HTML comment that contains the original iframe markup.
        
        Note: This approach is not 100% robust against malformed or deeply nested HTML,
        but it works for many standard cases.
        """
        # The regex pattern is case-insensitive and DOTALL-enabled so that '.' matches newlines.
        # It captures any <iframe ...> ... </iframe> block.
        pattern = re.compile(r'(?is)(<iframe\b.*?>.*?</iframe>)')
        
        # Replace each iframe block with a commented version.
        # If you prefer to remove the iframe entirely, you could return an empty string instead.
        new_html = pattern.sub(r'<!-- \1 -->', html_content)
    
        return new_html
    
    def add_shield_scripts(self, body, params, nonce=None):
        """
        Adds a shield script tag to the HTML head and encodes the content.

        :param body: The content body as a byte string.
        :param nonce: An optional nonce value to include in the script tag.
        :return: The encoded content body with the shield script added.
        """
        modified_sw_reg_script = SW_REGISTRATION_SCRIPT
        for param in params:
            (key, value) = param
            modified_sw_reg_script = modified_sw_reg_script.replace("{{" + key + "}}", value)
        
        shield_script = f'<script {"nonce=" + repr(nonce) if nonce else ""}>{modified_sw_reg_script}</script>'
        return body.replace('<head>', f'<head>\n{shield_script}')
    
    def inject_minimal_script(self, body, nonce=None):
        # Check if minimal script is already present
        if "//START SHIELD MINIMUM SCRIPT" in body:
            logging.warning("Minimal script already present. No injection needed.")
            return body
        
        modified_html = body
        
        # Inject minimal script before closing </head> tag
        if re.search(r'</head>', body, re.IGNORECASE):
            minimal_script = f'<script {"nonce=" + repr(nonce) if nonce else ""}>{MINIMAL_INJECTION_SCRIPT}</script>'
            modified_html = re.sub(r'</head>', minimal_script + '\n</head>', body, flags=re.IGNORECASE)
            logging.info("Minimal script injected successfully.")
        
        return modified_html



addons = [NetworkRequestTracker()]
