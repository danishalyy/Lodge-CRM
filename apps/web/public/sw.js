/* Public app shell/static assets only. Authenticated documents and API data are network-only. */
const CACHE = 'safarios-static-v2';
const PUBLIC = ['/offline.html', '/manifest.webmanifest', '/branding/safarios-mark.svg', '/icons/icon-192.png', '/icons/icon-512.png'];
function binding(clear = false, expected = null) {
  return new Promise(resolve => {
    const r = indexedDB.open('safarios-device', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('binding');
    r.onerror = () => resolve(null);
    r.onsuccess = () => {
      const db = r.result, tx = db.transaction('binding', clear ? 'readwrite' : 'readonly'), store = tx.objectStore('binding'), get = store.get('push');
      if (clear) get.onsuccess = () => { if (!get.result || get.result.id === expected) store.delete('push'); };
      tx.oncomplete = () => { db.close(); resolve(clear ? null : get.result || null); };
      tx.onerror = tx.onabort = () => { db.close(); resolve(null); };
    };
  });
}
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC)).catch(() => {})); self.skipWaiting(); });
self.addEventListener('activate', event => event.waitUntil((async () => { try { for (const key of await caches.keys()) if (key.startsWith('safarios-static-') && key !== CACHE) await caches.delete(key); } catch {} await self.clients.claim(); })()));
// Cache storage is optional. Quota, eviction and browser storage failures must
// never turn a successful public bundle download into a ChunkLoadError.
async function publicCached(request) {
  try { return await caches.match(request); } catch { return undefined; }
}
async function rememberPublic(request, response) {
  try {
    const cache = await caches.open(CACHE);
    await cache.put(request, response);
  } catch { /* Keep the network response available when local storage fails. */ }
}
self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request, { cache: 'no-store' }).catch(async () => (await publicCached('/offline.html')) || new Response('<!doctype html><title>SafariOS offline</title><h1>You are offline</h1><p>Reconnect to sign in. Private pages are never cached.</p>', { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } })));
  } else if (PUBLIC.includes(url.pathname)) {
    event.respondWith((async () => {
      const cached = await publicCached(request);
      if (cached) return cached;
      const response = await fetch(request);
      if (response.ok && response.type === 'basic' && !url.search)
        event.waitUntil(rememberPublic(request, response.clone()));
      return response;
    })());
  }
  // Hashed application bundles use the browser HTTP cache, not a second worker
  // cache/stream. Private offline navigation is deliberately a public fallback;
  // an already loaded tab retains its scoped IndexedDB work queue.
  // API calls, RSC responses, media and non-public documents are never cached.
});
self.addEventListener('message', event => {
  if (event.data?.type === 'CLEAR_SESSION') event.waitUntil((async () => { await binding(true, event.data.binding); const notices = await self.registration.getNotifications(); notices.forEach(n => n.close()); })());
});
self.addEventListener('push', event => event.waitUntil((async () => {
  let data; try { data = event.data?.json(); } catch { return; }
  const active = await binding();
  if (!active || data?.binding !== active.id || data?.type !== 'notification') return;
  // A vendor may deliver after logout/session expiry. Recheck the current cookie
  // before presenting even a generic alert; never cache this response.
  try {
    const response = await fetch('/api/v1/auth/me', { credentials: 'include', cache: 'no-store', headers: { 'X-Expected-User-Id': active.userId, 'X-Lodge-Context': active.lodgeId }, signal: AbortSignal.timeout(8000) });
    if (!response.ok) return;
    const user = await response.json(), membership = user.memberships?.find(row => row.lodge_id === active.lodgeId);
    if (user.id !== active.userId || user.is_super_admin || !membership?.permissions?.includes('notifications.view') || !membership?.entitlements?.includes('notifications') || ['Pending','Suspended'].includes(membership.subscription_status)) return;
    const latest = await binding(); if (!latest || latest.id !== active.id) return;
  } catch { return; }
  await self.registration.showNotification('SafariOS', { body: 'You have an update. Open SafariOS to view it.', icon: '/icons/icon-192.png', badge: '/icons/icon-192.png', tag: 'safarios-updates', data: { binding: active.id } });
})()));
self.addEventListener('notificationclick', event => { event.notification.close(); event.waitUntil((async () => {
  const active = await binding(); if (!active || active.id !== event.notification.data?.binding) return;
  const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  const current = windows.find(client => new URL(client.url).origin === self.location.origin);
  if (current) { await current.navigate('/notifications'); await current.focus(); } else await self.clients.openWindow('/notifications');
})()); });
