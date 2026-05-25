const CACHE_NAME = 'xenda-v1';

const ARCHIVOS_CACHE = [
    '/',
    '/static/gob_mex.jpeg',
    '/static/fondo_index_movil.png',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png'
];

// =====================================
// INSTALACIÓN — cachea archivos
// =====================================

self.addEventListener('install', function(e) {
    e.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(ARCHIVOS_CACHE);
        })
    );
    self.skipWaiting();
});

// =====================================
// ACTIVACIÓN — limpia cachés viejos
// =====================================

self.addEventListener('activate', function(e) {
    e.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// =====================================
// FETCH — sirve desde caché si no hay red
// =====================================

self.addEventListener('fetch', function(e) {

    if (e.request.method !== 'GET') return;

    e.respondWith(
        fetch(e.request)
            .then(function(response) {
                const copia = response.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(e.request, copia);
                });
                return response;
            })
            .catch(function() {
                return caches.match(e.request);
            })
    );
});

// =====================================
// SYNC — sincroniza registros pendientes
// =====================================

self.addEventListener('sync', function(e) {
    if (e.tag === 'sync-registros') {
        e.waitUntil(sincronizarRegistros());
    }
});

async function sincronizarRegistros() {

    const db = await abrirDB();
    const registros = await obtenerPendientes(db);

    for (const registro of registros) {
        try {
            const response = await fetch('/', {
                method: 'POST',
                body: registro.formData,
                credentials: 'same-origin'
            });
            if (response.ok) {
                await eliminarPendiente(db, registro.id);
            }
        } catch (e) {
            console.log('Sin conexión, reintentando después');
        }
    }
}

// =====================================
// INDEXEDDB — almacén local
// =====================================

function abrirDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open('xenda-offline', 1);
        req.onupgradeneeded = function(e) {
            e.target.result.createObjectStore(
                'pendientes',
                { keyPath: 'id', autoIncrement: true }
            );
        };
        req.onsuccess = e => resolve(e.target.result);
        req.onerror = e => reject(e);
    });
}

function obtenerPendientes(db) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction('pendientes', 'readonly');
        const req = tx.objectStore('pendientes').getAll();
        req.onsuccess = e => resolve(e.target.result);
        req.onerror = e => reject(e);
    });
}

function eliminarPendiente(db, id) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction('pendientes', 'readwrite');
        const req = tx.objectStore('pendientes').delete(id);
        req.onsuccess = () => resolve();
        req.onerror = e => reject(e);
    });
}