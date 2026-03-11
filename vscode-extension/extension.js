const vscode = require("vscode");

const SERVER = "http://127.0.0.1:27182/heartbeat";
const INTERVAL_MS = 5000;

let intervalHandle = null;
let lastTickTime = null;

async function sendHeartbeat(seconds) {
  try {
    await fetch(SERVER, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ site: "VSCode", seconds }),
    });
  } catch (_) {
    // daemon not running, ignore
  }
}

function tick() {
  const now = Date.now();
  if (!vscode.window.state.focused) {
    lastTickTime = null;
    return;
  }
  if (lastTickTime !== null) {
    const elapsed = Math.round((now - lastTickTime) / 1000);
    if (elapsed > 0) sendHeartbeat(elapsed);
  }
  lastTickTime = now;
}

function activate(context) {
  intervalHandle = setInterval(tick, INTERVAL_MS);

  // Reset timer when window gains focus
  vscode.window.onDidChangeWindowState((state) => {
    if (state.focused) {
      lastTickTime = Date.now();
    } else {
      lastTickTime = null;
    }
  }, null, context.subscriptions);
}

function deactivate() {
  if (intervalHandle) clearInterval(intervalHandle);
}

module.exports = { activate, deactivate };
