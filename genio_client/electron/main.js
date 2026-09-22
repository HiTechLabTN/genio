const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { autoUpdater } = (() => {
  try {
    return require('electron-updater');
  } catch {
    return { autoUpdater: null };
  }
})();

let mainWindow = null;
let updaterAvailable = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    backgroundColor: '#0a0e1a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
    icon: path.join(__dirname, '../public/icon.png'),
    autoHideMenuBar: true,
  });
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });
  mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  mainWindow.removeMenu();
}

function setupAutoUpdater() {
  if (!autoUpdater) {
    console.log('[electron-updater] not available — skipping auto-update setup');
    return;
  }
  try {
    updaterAvailable = true;
    autoUpdater.autoDownload = true;
    autoUpdater.autoInstallOnAppQuit = true;
    // GitHub provider uses package.json build.publish config; no setFeedURL needed
    autoUpdater.logger = console;

    autoUpdater.on('checking-for-update', () => {
      console.log('[updater] checking-for-update');
      mainWindow?.webContents.send('updater:checking');
    });
    autoUpdater.on('update-available', (info) => {
      console.log('[updater] update-available', info.version);
      mainWindow?.webContents.send('updater:available', info);
    });
    autoUpdater.on('update-not-available', () => {
      console.log('[updater] update-not-available');
      mainWindow?.webContents.send('updater:not-available');
    });
    autoUpdater.on('download-progress', (p) => {
      console.log(`[updater] download-progress ${Math.round(p.percent)}%`);
      mainWindow?.webContents.send('updater:progress', p);
    });
    autoUpdater.on('update-downloaded', (info) => {
      console.log('[updater] update-downloaded', info.version);
      mainWindow?.webContents.send('updater:downloaded', info);
      // Optionally auto-install on quit; user can trigger via IPC
    });
    autoUpdater.on('error', (err) => {
      console.error('[updater] error', err);
      mainWindow?.webContents.send('updater:error', err?.message || String(err));
    });

    // IPC handlers exposed to renderer (UpdaterModal / updater.ts fallback)
    ipcMain.handle('updater:check', async () => {
      try {
        const result = await autoUpdater.checkForUpdates();
        return { ok: true, updateInfo: result?.updateInfo ?? null };
      } catch (e) {
        return { ok: false, error: e?.message || String(e) };
      }
    });

    ipcMain.handle('updater:download', async () => {
      try {
        await autoUpdater.downloadUpdate();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: e?.message || String(e) };
      }
    });

    ipcMain.handle('updater:quitAndInstall', () => {
      try {
        autoUpdater.quitAndInstall(false, true);
        return { ok: true };
      } catch (e) {
        return { ok: false, error: e?.message || String(e) };
      }
    });

    // Defer check slightly to ensure window ready
    setTimeout(() => {
      autoUpdater.checkForUpdatesAndNotify().catch((e) => console.error('[updater] checkForUpdatesAndNotify failed', e));
    }, 3000);
  } catch (e) {
    console.error('[updater] setup failed', e);
  }
}

app.whenReady().then(() => {
  createWindow();
  setupAutoUpdater();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
