const CACHE_NAME = 'genio-hud-v1';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

// استقبال إشعارات الـ Push من سيرفر التحكم
self.addEventListener('push', (e) => {
  const data = e.data ? e.data.json() : { title: 'Genio Alert', body: 'New autonomous event recorded.' };
  const options = {
    body: data.body,
    icon: 'https://img.icons8.com/isometric/512/processor.png',
    badge: 'https://img.icons8.com/isometric/512/processor.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/' }
  };
  e.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data.url));
});
