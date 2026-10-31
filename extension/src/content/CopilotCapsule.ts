/**
 * RoleSync In-Page Floating Capsule
 * Renders inside a closed/open Shadow DOM on supported ATS portals and job boards.
 * Provides high-agency, low-cognitive-load contextual actions directly on the web page.
 * Features automated third-party chat widget collision avoidance and pointer-based drag repositioning.
 */

export const CHAT_WIDGET_SELECTORS: string[] = [
  '#intercom-container',
  'iframe[name="intercom-launcher-frame"]',
  '#launcher', // Zendesk Web Widget
  'iframe#webWidget',
  '#ze-snippet',
  '.drift-widget',
  '#drift-widget',
  'iframe#drift-widget-container',
  '#crisp-chatbox',
  '.crisp-client',
  '#onetrust-consent-sdk',
  '#onetrust-banner-sdk',
  '#hubspot-messages-iframe-container',
  '#tawk-bubble-container',
];

export class CopilotCapsule {
  private hostElement: HTMLDivElement | null = null;
  private shadowRoot: ShadowRoot | null = null;
  private isExpanded: boolean = true;
  private jobTitle: string = '';
  private companyName: string = '';
  private atsProvider: string = '';

  // Collision avoidance & drag-and-drop state
  private isCustomPositioned: boolean = false;
  private isDragging: boolean = false;
  private dragStartX: number = 0;
  private dragStartY: number = 0;
  private hostStartLeft: number = 0;
  private hostStartTop: number = 0;
  private hasMovedSignificantly: boolean = false;
  private observer: MutationObserver | null = null;
  private resizeListener: (() => void) | null = null;
  private intervalCheckTimers: number[] = [];

  constructor() {
    this.init();
  }

  public updateJobInfo(title: string, company: string, provider: string) {
    this.jobTitle = title;
    this.companyName = company;
    this.atsProvider = provider;
    this.render();
  }

  private init() {
    if (document.getElementById('rolesync-capsule-host')) return;

    this.hostElement = document.createElement('div');
    this.hostElement.id = 'rolesync-capsule-host';
    this.hostElement.style.position = 'fixed';
    this.hostElement.style.bottom = '24px';
    this.hostElement.style.right = '24px';
    this.hostElement.style.zIndex = '2147483647';
    this.hostElement.style.fontFamily = 'system-ui, -apple-system, sans-serif';
    this.hostElement.style.touchAction = 'none';

    this.shadowRoot = this.hostElement.attachShadow({ mode: 'open' });
    document.body.appendChild(this.hostElement);

    // Restore saved position or evaluate collision with chat widgets
    this.restorePosition().then((restored) => {
      if (!restored) {
        this.evaluateCollision();
      }
      this.render();
    });

    this.setupCollisionObserver();
  }

  /**
   * Collision avoidance: detect if any known third-party support/chat widget
   * is visible in the bottom-right viewport quadrant. If so, automatically
   * shift the capsule to bottom-left unless custom positioned by candidate.
   */
  public evaluateCollision(): void {
    if (this.isCustomPositioned || !this.hostElement) return;

    let collided = false;
    for (const sel of CHAT_WIDGET_SELECTORS) {
      try {
        const el = document.querySelector(sel);
        if (el) {
          const rect = el.getBoundingClientRect();
          // Element is visible and in the bottom-right quadrant
          if (
            rect.width > 0 &&
            rect.height > 0 &&
            rect.bottom > window.innerHeight - 180 &&
            rect.right > window.innerWidth - 240
          ) {
            collided = true;
            break;
          }
        }
      } catch {
        // Skip invalid selector or querying error
      }
    }

    if (collided) {
      // Auto-offset to bottom-left
      this.hostElement.style.bottom = '24px';
      this.hostElement.style.left = '24px';
      this.hostElement.style.right = 'auto';
      this.hostElement.style.top = 'auto';
    } else {
      // Default bottom-right
      this.hostElement.style.bottom = '24px';
      this.hostElement.style.right = '24px';
      this.hostElement.style.left = 'auto';
      this.hostElement.style.top = 'auto';
    }
  }

  private setupCollisionObserver(): void {
    try {
      this.observer = new MutationObserver(() => {
        if (!this.isCustomPositioned) {
          this.evaluateCollision();
        }
      });

      if (document.body) {
        this.observer.observe(document.body, { childList: true, subtree: true });
      }

      // Interval checks for late-mounting widgets (1000ms, 2500ms, 5000ms)
      this.intervalCheckTimers.push(
        window.setTimeout(() => this.evaluateCollision(), 1000),
        window.setTimeout(() => this.evaluateCollision(), 2500),
        window.setTimeout(() => this.evaluateCollision(), 5000)
      );

      this.resizeListener = () => {
        if (!this.isCustomPositioned) {
          this.evaluateCollision();
        }
      };
      window.addEventListener('resize', this.resizeListener, { passive: true });
    } catch (err) {
      console.debug('[RoleSync] Failed to setup collision observer:', err);
    }
  }

  private async savePosition(left: number, top: number): Promise<void> {
    try {
      if (typeof chrome !== 'undefined' && chrome.storage?.session) {
        await chrome.storage.session.set({ rolesync_capsule_pos: { left, top } });
      }
    } catch (err) {
      console.debug('[RoleSync] Failed to save capsule position:', err);
    }
  }

  private async restorePosition(): Promise<boolean> {
    try {
      if (typeof chrome !== 'undefined' && chrome.storage?.session) {
        const res = await chrome.storage.session.get('rolesync_capsule_pos');
        if (res?.rolesync_capsule_pos && this.hostElement) {
          const { left, top } = res.rolesync_capsule_pos;
          if (typeof left === 'number' && typeof top === 'number') {
            const hostW = this.hostElement.offsetWidth || 280;
            const hostH = this.hostElement.offsetHeight || 120;
            const clampedX = Math.max(12, Math.min(window.innerWidth - hostW - 12, left));
            const clampedY = Math.max(12, Math.min(window.innerHeight - hostH - 12, top));
            this.hostElement.style.left = `${clampedX}px`;
            this.hostElement.style.top = `${clampedY}px`;
            this.hostElement.style.right = 'auto';
            this.hostElement.style.bottom = 'auto';
            this.isCustomPositioned = true;
            return true;
          }
        }
      }
    } catch (err) {
      console.debug('[RoleSync] Failed to restore capsule position:', err);
    }
    return false;
  }

  /**
   * Configures unified pointer event listeners for drag-and-drop repositioning
   * with viewport boundary clamping and click-vs-drag jitter threshold.
   */
  private setupDragListeners(handle: HTMLElement): void {
    handle.style.cursor = 'grab';
    handle.style.touchAction = 'none';
    handle.style.userSelect = 'none';

    handle.addEventListener('pointerdown', (e: PointerEvent) => {
      // Ignore clicks on actionable child buttons
      const target = e.target as HTMLElement;
      if (
        target.closest('button') ||
        target.id === 'btn-minimize' ||
        target.id === 'btn-expand' ||
        target.closest('#btn-minimize') ||
        target.closest('#btn-expand')
      ) {
        return;
      }

      this.isDragging = true;
      this.hasMovedSignificantly = false;
      this.dragStartX = e.clientX;
      this.dragStartY = e.clientY;

      if (!this.hostElement) return;
      const rect = this.hostElement.getBoundingClientRect();
      this.hostStartLeft = rect.left;
      this.hostStartTop = rect.top;

      try {
        handle.setPointerCapture(e.pointerId);
      } catch {}
      handle.style.cursor = 'grabbing';
      e.preventDefault();
    });

    handle.addEventListener('pointermove', (e: PointerEvent) => {
      if (!this.isDragging || !this.hostElement) return;

      const deltaX = e.clientX - this.dragStartX;
      const deltaY = e.clientY - this.dragStartY;

      // 4px jitter threshold to distinguish clicks from drags
      if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
        this.hasMovedSignificantly = true;
      }

      if (!this.hasMovedSignificantly) return;

      const hostW = this.hostElement.offsetWidth || (this.isExpanded ? 280 : 120);
      const hostH = this.hostElement.offsetHeight || (this.isExpanded ? 160 : 44);

      // Clamping within viewport bounds [12, innerWidth - hostW - 12] and [12, innerHeight - hostH - 12]
      const clampedX = Math.max(12, Math.min(window.innerWidth - hostW - 12, this.hostStartLeft + deltaX));
      const clampedY = Math.max(12, Math.min(window.innerHeight - hostH - 12, this.hostStartTop + deltaY));

      this.hostElement.style.left = `${clampedX}px`;
      this.hostElement.style.top = `${clampedY}px`;
      this.hostElement.style.right = 'auto';
      this.hostElement.style.bottom = 'auto';
    });

    const endDrag = (e: PointerEvent) => {
      if (!this.isDragging) return;
      this.isDragging = false;
      handle.style.cursor = 'grab';
      try {
        handle.releasePointerCapture(e.pointerId);
      } catch {}

      if (this.hasMovedSignificantly && this.hostElement) {
        this.isCustomPositioned = true;
        const rect = this.hostElement.getBoundingClientRect();
        this.savePosition(rect.left, rect.top);
      }
    };

    handle.addEventListener('pointerup', endDrag);
    handle.addEventListener('pointercancel', endDrag);
  }

  public render() {
    if (!this.shadowRoot) return;

    if (!this.jobTitle && !this.companyName) {
      // Don't show capsule if no job detected on page
      this.shadowRoot.innerHTML = '';
      return;
    }

    const html = `
      <style>
        .capsule-container {
          background: #ffffff;
          border: 1px solid #e2e8f0;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
          border-radius: 12px;
          overflow: hidden;
          transition: box-shadow 0.2s ease;
          color: #0f172a;
          font-size: 12px;
          user-select: none;
        }
        .capsule-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          background: #f8fafc;
          border-bottom: 1px solid #f1f5f9;
          cursor: grab;
          touch-action: none;
        }
        .capsule-header:active {
          cursor: grabbing;
        }
        .drag-grip {
          color: #94a3b8;
          font-size: 13px;
          line-height: 1;
          margin-right: -2px;
        }
        .badge {
          font-size: 10px;
          font-weight: 700;
          padding: 2px 6px;
          border-radius: 9999px;
          background: #eef2ff;
          color: #4f46e5;
          text-transform: uppercase;
        }
        .capsule-body {
          padding: 10px 12px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          max-width: 260px;
        }
        .job-title {
          font-weight: 700;
          color: #1e293b;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .company-name {
          color: #64748b;
          font-size: 11px;
        }
        .btn-row {
          display: flex;
          gap: 6px;
          margin-top: 4px;
        }
        .btn-primary {
          flex: 1;
          background: #10b981;
          color: #ffffff;
          border: none;
          padding: 6px 10px;
          border-radius: 6px;
          font-weight: 600;
          font-size: 11px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
          transition: background 0.15s;
        }
        .btn-primary:hover {
          background: #059669;
        }
        .btn-secondary {
          background: #f1f5f9;
          color: #334155;
          border: none;
          padding: 6px 8px;
          border-radius: 6px;
          font-weight: 600;
          font-size: 11px;
          cursor: pointer;
        }
        .btn-secondary:hover {
          background: #e2e8f0;
        }
        .minimized-pill {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 12px;
          background: #4f46e5;
          color: #ffffff;
          border-radius: 9999px;
          box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35);
          cursor: grab;
          font-weight: 700;
          font-size: 12px;
          touch-action: none;
          user-select: none;
          transition: transform 0.15s, box-shadow 0.15s;
        }
        .minimized-pill:hover {
          transform: scale(1.04);
        }
        .minimized-pill:active {
          cursor: grabbing;
        }
      </style>

      ${
        this.isExpanded
          ? `
        <div class="capsule-container">
          <div class="capsule-header" title="Drag to move capsule">
            <span class="drag-grip">⠿</span>
            <span style="font-size: 14px;">⚡</span>
            <span style="font-weight: 700; color: #4338ca;">RoleSync</span>
            <span class="badge">${this.atsProvider || 'ATS'}</span>
            <div style="margin-left: auto; cursor: pointer; color: #94a3b8; padding: 2px;" id="btn-minimize" title="Minimize">✕</div>
          </div>
          <div class="capsule-body">
            <div class="job-title" title="${this.jobTitle}">${this.jobTitle || 'Detected Position'}</div>
            <div class="company-name">${this.companyName || 'Career Portal'}</div>
            <div class="btn-row">
              <button class="btn-primary" id="btn-autofill">⚡ 1-Click Autofill</button>
              <button class="btn-secondary" id="btn-open-panel" title="Open Copilot Side Panel">Sidepanel ↗</button>
            </div>
          </div>
        </div>
      `
          : `
        <div class="minimized-pill" id="btn-expand" title="${this.jobTitle} • ${this.companyName} (Click to expand, drag to move)">
          <span class="drag-grip" style="color: rgba(255, 255, 255, 0.7);">⠿</span>
          <span>⚡</span>
          <span>RoleSync</span>
        </div>
      `
      }
    `;

    this.shadowRoot.innerHTML = html;

    // Attach pointer drag listeners to appropriate handle
    if (this.isExpanded) {
      const header = this.shadowRoot.querySelector<HTMLElement>('.capsule-header');
      if (header) {
        this.setupDragListeners(header);
      }
    } else {
      const pill = this.shadowRoot.querySelector<HTMLElement>('.minimized-pill');
      if (pill) {
        this.setupDragListeners(pill);
      }
    }

    const btnMinimize = this.shadowRoot.getElementById('btn-minimize');
    if (btnMinimize) {
      btnMinimize.addEventListener('click', (e) => {
        if (this.hasMovedSignificantly) return;
        e.stopPropagation();
        this.isExpanded = false;
        this.render();
      });
    }

    const btnExpand = this.shadowRoot.getElementById('btn-expand');
    if (btnExpand) {
      btnExpand.addEventListener('click', (e) => {
        if (this.hasMovedSignificantly) return;
        e.stopPropagation();
        this.isExpanded = true;
        this.render();
      });
    }

    const btnAutofill = this.shadowRoot.getElementById('btn-autofill');
    if (btnAutofill) {
      btnAutofill.addEventListener('click', (e) => {
        e.stopPropagation();
        chrome.runtime.sendMessage({ action: 'TRIGGER_AUTOFILL_FROM_CAPSULE' });
      });
    }

    const btnOpenPanel = this.shadowRoot.getElementById('btn-open-panel');
    if (btnOpenPanel) {
      btnOpenPanel.addEventListener('click', (e) => {
        e.stopPropagation();
        chrome.runtime.sendMessage({ action: 'OPEN_SIDEPANEL_REQUEST' });
      });
    }
  }

  public destroy(): void {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
    if (this.resizeListener) {
      window.removeEventListener('resize', this.resizeListener);
      this.resizeListener = null;
    }
    this.intervalCheckTimers.forEach((timer) => clearTimeout(timer));
    this.intervalCheckTimers = [];
    if (this.hostElement && this.hostElement.parentNode) {
      this.hostElement.parentNode.removeChild(this.hostElement);
      this.hostElement = null;
    }
  }
}
