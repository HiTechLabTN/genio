const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Auto-updater bridge for updater.ts desktop fallback (Electron)
  checkForUpdate: () => ipcRenderer.invoke('updater:check'),
  downloadUpdate: () => ipcRenderer.invoke('updater:download').then((r) => r?.ok === true),
  quitAndInstall: () => ipcRenderer.invoke('updater:quitAndInstall'),
  onUpdaterEvent: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('updater:available', handler);
    ipcRenderer.on('updater:downloaded', handler);
    ipcRenderer.on('updater:progress', handler);
    ipcRenderer.on('updater:error', handler);
    return () => {
      ipcRenderer.removeListener('updater:available', handler);
      ipcRenderer.removeListener('updater:downloaded', handler);
      ipcRenderer.removeListener('updater:progress', handler);
      ipcRenderer.removeListener('updater:error', handler);
    };
  },
});

window.addEventListener('DOMContentLoaded', () => {
  console.log('Genio Electron app loaded — electronAPI exposed, updater bridge ready');
});
