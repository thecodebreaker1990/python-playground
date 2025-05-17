self.addEventListener("install", (event) => {
  self.skipWaiting();
  self.shieldSessionID = "{{SHIELD_SESSION_ID}}";
  console.log("Service worker installed");
});

self.addEventListener("activate", (event) => {
  event.waitUntil(clients.claim());
  console.log("Service worker activated");
});

self.addEventListener("fetch", function (event) {
  if (event.request.method === "OPTIONS") return;
  // Clone the request to ensure it's mutable
  let modifiedRequest = event.request.clone();
  const headers = addHeaders(modifiedRequest);
  modifiedRequest = createRequest(modifiedRequest, headers);
  event.respondWith(fetch(modifiedRequest));
});

function addHeaders(modifiedRequest) {
  const headers = new Headers(
    [
      ...modifiedRequest.headers.entries(),
      ["shield-session-id", self.shieldSessionID],
      ["access-control-allow-origin", modifiedRequest.referrer]
    ].filter(
      ([name, value]) => name.toLowerCase() !== "access-control-allow-origin"
    )
  );
  return headers;
}

function createRequest(modifiedRequest, headers) {
  const newRequest = new Request(modifiedRequest, {
    mode: "cors",
    credentials: "same-origin",
    headers: headers
  });
  return newRequest;
}
