// Utility UUID Generation Function
function generateUUID() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
    /[xy]/g,
    function (char) {
      const random = (Math.random() * 16) | 0;
      const value = char === "x" ? random : (random & 0x3) | 0x8;
      return value.toString(16);
    }
  );
}

(async () => {
  let url = "{{SHIELD_SESSION_URL}}";
  if (url.endsWith("/")) {
    url = url.slice(0, -1);
  }

  const isTopFrame = window.self === window.top;
  console.log(
    `[${isTopFrame ? "top-frame" : "sub-frame"}] Full Script Running`
  );

  if (isTopFrame) {
    // Generate or retrieve unique ID
    let sessionID = sessionStorage.getItem("shieldSessionID");
    if (!sessionID) {
      sessionID = generateUUID();
      sessionStorage.setItem("shieldSessionID", sessionID);
    }
    window.shieldSessionID = sessionID;
    await setServiceWorker(url);
  } else {
    // For sub-frames, request UID from top frame
    window.top.postMessage("SHIELD_GET_UID", "*");
  }

  setListeners(url);
})();

function setListeners(url) {
  const isTopFrame = window.self === window.top;
  window.addEventListener("message", function (event) {
    if (isTopFrame && event.data === "SHIELD_GET_UID") {
      event.source.postMessage(
        JSON.stringify(["SHIELD_SET_UID", window.shieldSessionID]),
        event.origin
      );
    }

    if (!isTopFrame && event.data?.includes("SHIELD_SET_UID")) {
      const data = JSON.parse(event.data);
      window.shieldSessionID = data[1];
      setServiceWorker(url);
    }
  });
}

async function setServiceWorker(url) {
  if ("serviceWorker" in navigator) {
    try {
      const urlObj = new URL(url);
      let pathname = urlObj.pathname;
      if (pathname.endsWith("/")) {
        pathname = pathname.slice(0, -1);
      }
      // pathname = pathname.split("/").pop();

      const reg = await navigator.serviceWorker.register(
        `${url}/shield-proxy-sw.js?shield-session-id=${window.shieldSessionID}`,
        pathname ? { scope: `/${pathname}/` } : {}
      );

      const sw = reg.installing || reg.waiting || reg.active;

      sw.addEventListener("statechange", function (e) {
        if (e.target.state === "installed") {
          console.log(
            `Reloading [${
              window.self === window.top ? "top-frame" : "sub-frame"
            }]`
          );
          window.location.reload();
        }
      });
    } catch (error) {
      console.error("SW registration failed:", error);
    }
  }
}
