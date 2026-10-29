export interface SelectorFailureTelemetry {
  host: string;
  ats_provider: string;
  failed_selectors: string[];
  page_structure_summary: {
    totalElements: number;
    tagCounts: Record<string, number>;
    maxDepth: number;
    hasForm: boolean;
    buttonCount: number;
    inputCount: number;
  };
  client_version: string;
  timestamp: number;
}

export class TelemetryReporter {
  private static API_ENDPOINT = 'http://localhost:8000/api/v1/telemetry/selector-failure';
  private static CLIENT_VERSION = '2.0.0-mv3';

  /**
   * Reports ATS selector drift to backend with sanitized DOM structural metadata.
   * Guaranteed ZERO candidate PII transmitted.
   */
  public static async reportDrift(
    atsProvider: string,
    failedSelectors: string[]
  ): Promise<boolean> {
    try {
      const summary = this.extractSanitizedDomStructure();
      const payload: SelectorFailureTelemetry = {
        host: window.location.hostname,
        ats_provider: atsProvider,
        failed_selectors: failedSelectors,
        page_structure_summary: summary,
        client_version: this.CLIENT_VERSION,
        timestamp: Date.now(),
      };

      // 1. Prefer Chrome MV3 background service worker message bus to bypass page CSP/Mixed-Content blocks
      if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
        try {
          chrome.runtime.sendMessage({
            action: 'TELEMETRY_REPORT',
            correlationId: `tel_${Date.now()}`,
            timestamp: Date.now(),
            payload,
          } as any).catch(() => {});
          return true;
        } catch {
          // Extension context might be disconnected
        }
      }

      // 2. Direct fetch fallback (only when safe)
      if (window.location.protocol === 'http:') {
        const res = await fetch(this.API_ENDPOINT, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        }).catch(() => null);

        if (res && res.ok) {
          console.warn(`[RoleSync] Telemetry reported selector drift on ${window.location.hostname}`);
          return true;
        }
      }

      return false;
    } catch {
      return false;
    }
  }

  /**
   * Summarizes DOM tree structure safely without collecting text or user inputs.
   */
  private static extractSanitizedDomStructure() {
    const allElements = Array.from(document.querySelectorAll('*'));
    const tagCounts: Record<string, number> = {};

    let maxDepth = 0;
    for (const el of allElements) {
      const tag = el.tagName.toLowerCase();
      tagCounts[tag] = (tagCounts[tag] || 0) + 1;

      // Calculate depth
      let depth = 0;
      let curr: Element | null = el;
      while (curr && curr !== document.documentElement) {
        depth++;
        curr = curr.parentElement;
      }
      if (depth > maxDepth) maxDepth = depth;
    }

    return {
      totalElements: allElements.length,
      tagCounts: Object.fromEntries(Object.entries(tagCounts).slice(0, 20)),
      maxDepth,
      hasForm: document.querySelector('form') !== null,
      buttonCount: tagCounts['button'] || 0,
      inputCount: tagCounts['input'] || 0,
    };
  }
}

