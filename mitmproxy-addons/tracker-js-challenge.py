import logging

from collections import defaultdict
from mitmproxy import http

shield_token_name = "shield_browser_token"

class NetworkRequestTracker:
    def __init__(self):
        self.client_requests = defaultdict(list)

    def client_connected(self, client):
        logging.info("-----Client connected-----")
        client_info = f'''
Client Address: {client.peername}
Local Address: {client.sockname}
Transport Protocol: {client.transport_protocol}
TLS Version: {client.tls_version}'''
        logging.info(client_info)

    def request(self, flow: http.HTTPFlow):
        """
        Called when a client request is received.
        We cannot directly return a custom response here if we also need to
        forward the request in other cases. Instead, we set a flag in flow.metadata
        and handle it in the response() hook.
        """
        client_address = flow.client_conn.peername
        request_info = {
            "url": flow.request.pretty_url,
            "method": flow.request.method,
            "headers": dict(flow.request.headers),
            "user_agent": flow.request.headers.get("User-Agent", "N/A"),
            "accept": flow.request.headers.get("Accept", "N/A")
        }
        self.client_requests[client_address].append(request_info)

        if flow.request.path == "/set_cookie":
            # Mark this request to be handled with a special response
            flow.metadata["set_cookie_request"] = True

        # Log request info
        logging.info("-----Request-----")
        logging.info(f"URL: {request_info['url']}")
        logging.info(f"Accept: {request_info['accept']}")

        # Decide if it's an HTML doc request
        is_html_doc_requested = request_info["accept"].startswith("text/html")
        if is_html_doc_requested:
            cookies = flow.request.headers.get_all("Cookie")
            for cookie in cookies:
                logging.info(f"Cookie: {cookie}")
            logging.info(f"Method: {request_info['method']}")
            logging.info(f"User-Agent: {request_info['user_agent']}")

            browser_token = check_for_browser_token(cookies)
            if browser_token is None:
                logging.info("No browser token found; scheduling custom HTML response.")
                # Instead of directly creating a flow.response here,
                # we set a flag in flow.metadata to handle it in the response() hook.
                flow.metadata["serve_custom_html"] = True
            else:
                logging.info(f"Browser token found: {browser_token}")

    def response(self, flow: http.HTTPFlow):
        """
        Called when a server response is received (or immediately if we create one).
        If our 'serve_custom_html' flag is set, we replace the response entirely
        with our custom HTML.
        """
        # Handle `/set_cookie` URL
        # Handle `/set_cookie` URL
        if flow.metadata.get("set_cookie_request"):
            # Respond with a JSON body and set the cookie in the browser
            json_response = '{"ok": true, "message": "Cookie set successfully."}'
            flow.response = http.Response.make(
                200,
                json_response.encode("utf-8"),  # Encode JSON data to bytes
                {
                    "Content-Type": "application/json",  # Indicate JSON response
                    "Set-Cookie": "shield_browser_token=verified; Path=/; Secure; HttpOnly; SameSite=Strict"
                }
            )
            return


        if flow.metadata.get("serve_custom_html"):
            # We can build the custom HTML response here.
            html_content = """
            <html>
            <head>
                <script>
                    async function setCookie() {
                        try {
                            let response = await fetch('/set_cookie');
                            if (response.ok) {
                                // Redirect back or anywhere you wish:
                                window.location.reload();
                            }
                        } catch (error) {
                            console.error('Error setting cookie:', error);
                        }
                    }
                    window.onload = setCookie;
                </script>
            </head>
            <body>
                <p>Setting up your session, please wait...</p>
            </body>
            </html>
            """

            # Replace the real server response with our own
            flow.response = http.Response.make(
                200,  # status code
                html_content,
                {"Content-Type": "text/html"}
            )
            # Optionally clear the flag so we don't do it again.
            flow.metadata["serve_custom_html"] = False

    def get_requests_from_client(self, client_address):
        """Retrieve all requests from a specific client."""
        return self.client_requests.get(client_address, [])

def check_for_browser_token(cookies):
    """
    If the shield token is present in any cookie, return it; else None.
    """
    for cookie in cookies:
        if shield_token_name in cookie:
            # e.g., "shield_browser_token=abc123"
            parts = cookie.split("=")
            if len(parts) == 2 and parts[0].strip() == shield_token_name:
                return parts[1].strip()
    return None

addons = [NetworkRequestTracker()]
