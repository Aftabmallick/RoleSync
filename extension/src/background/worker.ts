import { KeepaliveManager } from './KeepaliveManager';
import { AppExtensionMessage } from '../types/messages';

console.log('[RoleSync] Service Worker initializing...');

// Initialize Port Keepalive listener to defeat 30s MV3 dormancy
KeepaliveManager.initialize();

// Enable Side Panel opening on action click
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error('[RoleSync] Error setting panel behavior:', error));

// Allow extension pages (Side Panel) to access chrome.storage.session
if (chrome.storage && chrome.storage.session && (chrome.storage.session as any).setAccessLevel) {
  (chrome.storage.session as any)
    .setAccessLevel({ accessLevel: 'TRUSTED_AND_UNTRUSTED_CONTEXTS' })
    .catch((err: any) => console.warn('[RoleSync] Error configuring session access level:', err));
}

// Central Extension Message Bus
chrome.runtime.onMessage.addListener((message: AppExtensionMessage, _sender, sendResponse) => {
  console.log(`[RoleSync] Message received: ${message.action}`, message);

  switch (message.action) {
    case 'JD_EXTRACTED':
      // Store current JD in session storage so sidepanel can read immediately
      KeepaliveManager.checkpointState('current_jd', message.payload).then(() => {
        sendResponse({ status: 'ACKNOWLEDGED' });
      });
      return true; // Keep message channel open for async response

    case 'AUTOFILL_PROGRESS':
      KeepaliveManager.checkpointState('autofill_progress', message.payload).then(() => {
        sendResponse({ status: 'PROGRESS_RECORDED' });
      });
      return true;

    case 'TELEMETRY_REPORT' as any:
      fetch('http://localhost:8000/api/v1/telemetry/selector-failure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(message.payload),
      }).catch((err) => console.log('[RoleSync] Telemetry forward error:', err));
      sendResponse({ status: 'REPORTED' });
      return true;

    default:
      sendResponse({ status: 'UNKNOWN_ACTION' });
      return false;
  }
});

