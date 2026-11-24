/* TDMS - tiny service worker: only here so the site can be installed as an app on phones and PCs.
   It never keeps old pages: everything always comes from the server. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => { /* network only */ });
