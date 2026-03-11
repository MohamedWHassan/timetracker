const api = typeof browser !== "undefined" ? browser : chrome;

const SITES = {
  "youtube.com": "YouTube",
  "facebook.com": "Facebook",
  "instagram.com": "Instagram",
};

const SERVER = "http://127.0.0.1:27182";
const INTERVAL_SECONDS = 5;

// Map site name -> accumulated seconds not yet sent
let pending = {};
let lastActiveUrl = null;
let lastTickTime = null;

function getSite(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    for (const [domain, name] of Object.entries(SITES)) {
      if (host === domain || host.endsWith("." + domain)) return name;
    }
  } catch (_) {}
  return null;
}

async function tick() {
  // Get the currently focused tab
  const [tab] = await api.tabs.query({ active: true, lastFocusedWindow: true });
  const now = Date.now();

  if (tab && tab.url && lastActiveUrl !== null && lastTickTime !== null) {
    const site = getSite(lastActiveUrl);
    if (site) {
      const elapsed = Math.round((now - lastTickTime) / 1000);
      pending[site] = (pending[site] || 0) + elapsed;
    }
  }

  lastActiveUrl = tab?.url ?? null;
  lastTickTime = now;

  // Send all pending data
  for (const [site, seconds] of Object.entries(pending)) {
    if (seconds > 0) {
      try {
        await fetch(`${SERVER}/heartbeat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ site, seconds }),
        });
        delete pending[site];
      } catch (_) {
        // Server not running, keep pending
      }
    }
  }

  // Check for blocked sites and close their tabs
  try {
    const res = await fetch(`${SERVER}/status`);
    const { blocked } = await res.json();
    if (blocked && blocked.length > 0) {
      const allTabs = await api.tabs.query({});
      for (const tab of allTabs) {
        const site = getSite(tab.url || "");
        if (site && blocked.includes(site)) {
          api.tabs.remove(tab.id);
        }
      }
    }
  } catch (_) {}
}

// Run every INTERVAL_SECONDS seconds
api.alarms.create("tick", { periodInMinutes: INTERVAL_SECONDS / 60 });
api.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "tick") tick();
});

// Also tick immediately on tab/window focus changes
api.tabs.onActivated.addListener(() => tick());
api.windows.onFocusChanged.addListener(() => tick());
