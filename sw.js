// Service worker de Metro+Bizkaibus
// Sube el número de versión cuando cambies index.html para forzar la actualización.
const VERSION = 'v2';
const SHELL_CACHE = `shell-${VERSION}`;
const DATA_CACHE = `data-${VERSION}`;

const SHELL_FILES = [
  './',
  './index.html',
  './manifest.webmanifest',
  './img/icon-192.png',
  './img/icon-512.png',
  './img/icon-maskable-512.png'
];

// Orígenes de los datos teóricos (stop_times, calendar, trips...)
const DATA_HOSTS = ['dl.rix.dev', 'raw.githubusercontent.com'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then(cache => cache.addAll(SHELL_FILES)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => ![SHELL_CACHE, DATA_CACHE].includes(k)).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// Red primero; si falla (sin conexión), lo último guardado en caché.
async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;
    throw err;
  }
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Datos teóricos: red primero, caché como respaldo offline
  if (DATA_HOSTS.includes(url.hostname)) {
    event.respondWith(networkFirst(request, DATA_CACHE));
    return;
  }

  // Archivos de la propia app
  if (url.origin === self.location.origin) {
    event.respondWith(
      networkFirst(request, SHELL_CACHE).catch(() => caches.match('./index.html'))
    );
    return;
  }

  // Todo lo demás (API de Metro Bilbao, tiempo real de Bizkaibus...) va directo a la red, sin caché
});
