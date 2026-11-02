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
chrome.runtime.onMessage.addListener((message: AppExtensionMessage | any, sender, sendResponse) => {
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

    case 'TRIGGER_AUTOFILL_FROM_CAPSULE': {
      (async () => {
        try {
          let targetTabId = sender.tab?.id;
          if (!targetTabId && typeof chrome !== 'undefined' && chrome.tabs) {
            const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
            targetTabId = tabs[0]?.id;
          }
          if (!targetTabId) {
            sendResponse({ status: 'NO_ACTIVE_TAB' });
            return;
          }

          let candidateProfile: any = null;
          let resumeDataUri: string | undefined = undefined;

          if (typeof chrome !== 'undefined' && chrome.storage?.session) {
            try {
              const sessionData = await chrome.storage.session.get(['rolesync_session_checkpoint', 'rolesync_user_profile']);
              if (sessionData?.rolesync_session_checkpoint?.candidateProfile) {
                candidateProfile = sessionData.rolesync_session_checkpoint.candidateProfile;
              } else if (sessionData?.rolesync_user_profile) {
                candidateProfile = sessionData.rolesync_user_profile;
              }
              if (sessionData?.rolesync_session_checkpoint?.tailorResult?.pdfBase64) {
                resumeDataUri = sessionData.rolesync_session_checkpoint.tailorResult.pdfBase64;
              }
            } catch {}
          }

          if (!candidateProfile && typeof chrome !== 'undefined' && chrome.storage?.local) {
            try {
              const localData = await chrome.storage.local.get(['rolesync_master_profile', 'rolesync_profile']);
              candidateProfile = localData?.rolesync_master_profile || localData?.rolesync_profile || null;
            } catch {}
          }

          const autofillMsg: AppExtensionMessage = {
            action: 'EXECUTE_DOM_AUTOFILL',
            correlationId: `autofill_capsule_${Date.now()}`,
            timestamp: Date.now(),
            payload: {
              candidateProfile,
              resumeDataUri,
            },
          } as any;

          if (typeof chrome !== 'undefined' && chrome.tabs) {
            chrome.tabs.sendMessage(targetTabId, autofillMsg, (resp) => {
              sendResponse({ status: 'AUTOFILL_DISPATCHED', response: resp });
            });
          } else {
            sendResponse({ status: 'AUTOFILL_DISPATCHED' });
          }
        } catch (err) {
          console.warn('[RoleSync] Failed to dispatch autofill from capsule:', err);
          sendResponse({ status: 'ERROR', error: String(err) });
        }
      })();
      return true;
    }

    case 'OPEN_SIDEPANEL_REQUEST': {
      (async () => {
        try {
          let windowId = sender.tab?.windowId;
          if (windowId === undefined && typeof chrome !== 'undefined' && chrome.windows) {
            const currWindow = await chrome.windows.getCurrent();
            windowId = currWindow?.id;
          }
          if (typeof chrome !== 'undefined' && chrome.sidePanel && typeof chrome.sidePanel.open === 'function' && windowId !== undefined) {
            await chrome.sidePanel.open({ windowId });
            sendResponse({ status: 'OPENED' });
          } else {
            console.warn('[RoleSync] chrome.sidePanel.open unavailable or windowId missing');
            sendResponse({ status: 'UNSUPPORTED' });
          }
        } catch (err) {
          console.warn('[RoleSync] Error opening sidepanel:', err);
          sendResponse({ status: 'ERROR', error: String(err) });
        }
      })();
      return true;
    }

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

