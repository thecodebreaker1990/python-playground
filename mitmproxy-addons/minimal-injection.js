//START SHIELD MINIMUM SCRIPT
(() => {
  if (window.self !== window.top) return; // Ensure it runs only on top-frame

  console.log("[top-frame] Minimal Script Running");

  // Retrieve UUID from sessionStorage
  const sessionID = sessionStorage.getItem("shieldSessionID");
  if (!sessionID) {
    console.error("No session ID found in sessionStorage.");
    return;
  }
  window.shieldSessionID = sessionID;

  // Setup minimal listener for iframe requests
  window.addEventListener("message", function (event) {
    if (event.data === "SHIELD_GET_UID") {
      console.log("Minimal Script: Sending UID to sub-frame");
      event.source.postMessage(
        JSON.stringify(["SHIELD_SET_UID", window.shieldSessionID]),
        event.origin
      );
    }
  });
})();
//END SHIELD MINIMUM SCRIPT
