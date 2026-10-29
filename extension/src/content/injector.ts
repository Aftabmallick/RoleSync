// RoleSync Content Script Injector Orchestrator
import { HistoryInterceptor } from './HistoryInterceptor';
import { JobExtractorEngine } from './JobExtractorEngine';
import { DOMAutofillEngine } from './DOMAutofillEngine';
import { AppExtensionMessage } from '../types/messages';

console.log('[RoleSync] Content script orchestrator initializing on host:', window.location.hostname);

const extractor = new JobExtractorEngine();
const autofillEngine = new DOMAutofillEngine();

async function runExtraction(): Promise<void> {
  try {
    const extracted = await extractor.extract();
    console.log('[RoleSync] Extracted job details:', extracted);

    chrome.runtime.sendMessage({
      action: 'JD_EXTRACTED',
      correlationId: `ext_${Date.now()}`,
      timestamp: Date.now(),
      payload: {
        atsProvider: extracted.atsProvider,
        jobTitle: extracted.title,
        companyName: extracted.company,
        rawText: extracted.rawTextContent,
        cleanedHtml: extracted.cleanedHtmlContent,
        pageUrl: extracted.sourceUrl
      }
    } as AppExtensionMessage);
  } catch (err) {
    console.error('[RoleSync] Error extracting job details:', err);
  }
}

// 1. Initial extraction on document_idle
if (document.readyState === 'complete' || document.readyState === 'interactive') {
  runExtraction();
} else {
  window.addEventListener('DOMContentLoaded', () => runExtraction());
}

// 2. Install SPA dynamic navigation interceptor
HistoryInterceptor.install((newUrl) => {
  console.log('[RoleSync] Location change detected by interceptor:', newUrl);
  // Debounce to allow new SPA view DOM tree to mount
  setTimeout(() => runExtraction(), 1500);
});

// 3. Listen for autofill execution commands from background / sidepanel
chrome.runtime.onMessage.addListener((message: AppExtensionMessage, sender, sendResponse) => {
  if (message.action === 'EXECUTE_DOM_AUTOFILL') {
    const { mappings } = message.payload;
    console.log('[RoleSync] Executing DOM autofill with mappings:', mappings);

    autofillEngine.executeAutofill(mappings, (completed, total, current) => {
      chrome.runtime.sendMessage({
        action: 'AUTOFILL_PROGRESS',
        correlationId: message.correlationId,
        timestamp: Date.now(),
        payload: {
          taskId: message.correlationId,
          fieldsCompleted: completed,
          totalFields: total,
          currentFieldSelector: current,
          status: completed === total ? 'COMPLETED' : 'IN_PROGRESS'
        }
      } as AppExtensionMessage);
    }).then((res) => {
      sendResponse({ status: 'COMPLETED', result: res });
    }).catch((err) => {
      sendResponse({ status: 'FAILED', error: String(err) });
    });

    return true; // Keep message channel open for async response
  }
});
