/**
 * RoleSync In-Page Clipboard Drawer Fallback
 * Renders inside a clean, isolated Shadow DOM at bottom-center when
 * application forms are hosted within cross-origin iframes (where browser
 * same-origin policies prevent automated DOM autofill).
 *
 * Provides high-speed 1-click clipboard copy chips and tailored resume download.
 */

export interface CandidateProfileData {
  personal?: {
    full_name?: string;
    email?: string;
    phone?: string;
    location?: string;
    linkedin?: string;
    github?: string;
    website?: string;
  };
  summary?: string;
  experience?: Array<{ role?: string; company?: string; bullets?: string[] }>;
  skills?: string[] | { technical?: string[]; soft?: string[] };
  [key: string]: any;
}

interface CopyFieldChip {
  id: string;
  label: string;
  value: string;
  icon: string;
}

export class ClipboardDrawer {
  private static instance: ClipboardDrawer | null = null;

  private hostElement: HTMLDivElement | null = null;
  private shadowRoot: ShadowRoot | null = null;
  private isShown: boolean = false;
  private candidateProfile: CandidateProfileData | null = null;
  private resumeDataUri: string | null = null;

  constructor() {
    this.init();
  }

  public static getInstance(): ClipboardDrawer {
    if (!ClipboardDrawer.instance) {
      ClipboardDrawer.instance = new ClipboardDrawer();
    }
    return ClipboardDrawer.instance;
  }

  public static show(candidateProfile?: CandidateProfileData, resumeDataUri?: string): ClipboardDrawer {
    const drawer = ClipboardDrawer.getInstance();
    drawer.open(candidateProfile, resumeDataUri);
    return drawer;
  }

  public static hide(): void {
    if (ClipboardDrawer.instance) {
      ClipboardDrawer.instance.close();
    }
  }

  public static toggle(candidateProfile?: CandidateProfileData, resumeDataUri?: string): void {
    const drawer = ClipboardDrawer.getInstance();
    if (drawer.isShown) {
      drawer.close();
    } else {
      drawer.open(candidateProfile, resumeDataUri);
    }
  }

  public static isVisible(): boolean {
    return ClipboardDrawer.instance ? ClipboardDrawer.instance.isShown : false;
  }

  private init(): void {
    const existing = document.getElementById('rolesync-clipboard-drawer-host');
    if (existing && (existing as any)._rolesync_drawer) {
      this.hostElement = existing as HTMLDivElement;
      this.shadowRoot = this.hostElement.shadowRoot;
      return;
    }

    this.hostElement = document.createElement('div');
    this.hostElement.id = 'rolesync-clipboard-drawer-host';
    (this.hostElement as any)._rolesync_drawer = this;
    this.hostElement.style.position = 'fixed';
    this.hostElement.style.bottom = '0';
    this.hostElement.style.left = '0';
    this.hostElement.style.width = '100%';
    this.hostElement.style.zIndex = '2147483646';
    this.hostElement.style.pointerEvents = 'none';
    this.hostElement.style.display = 'flex';
    this.hostElement.style.justifyContent = 'center';
    this.hostElement.style.alignItems = 'flex-end';
    this.hostElement.style.fontFamily = 'system-ui, -apple-system, sans-serif';

    this.shadowRoot = this.hostElement.attachShadow({ mode: 'open' });
    document.body.appendChild(this.hostElement);
  }

  public open(candidateProfile?: CandidateProfileData, resumeDataUri?: string): void {
    if (candidateProfile) {
      this.candidateProfile = candidateProfile;
    }
    if (resumeDataUri) {
      this.resumeDataUri = resumeDataUri;
    }

    this.isShown = true;

    // If profile is missing, attempt to hydrate from session/local storage
    if (!this.candidateProfile) {
      this.hydrateFromStorage().then(() => {
        this.render();
      });
    } else {
      this.render();
    }
  }

  public close(): void {
    this.isShown = false;
    this.render();
  }

  private async hydrateFromStorage(): Promise<void> {
    try {
      if (typeof chrome !== 'undefined' && chrome.storage) {
        if (chrome.storage.session) {
          const session = await chrome.storage.session.get(['rolesync_session_checkpoint', 'rolesync_user_profile']);
          if (session?.rolesync_user_profile) {
            this.candidateProfile = session.rolesync_user_profile;
            return;
          }
          if (session?.rolesync_session_checkpoint?.candidateProfile) {
            this.candidateProfile = session.rolesync_session_checkpoint.candidateProfile;
            return;
          }
        }
        if (chrome.storage.local) {
          const local = await chrome.storage.local.get(['rolesync_master_profile', 'rolesync_profile']);
          if (local?.rolesync_master_profile) {
            this.candidateProfile = local.rolesync_master_profile;
            return;
          }
          if (local?.rolesync_profile) {
            this.candidateProfile = local.rolesync_profile;
            return;
          }
        }
      }
    } catch (err) {
      console.debug('[RoleSync] Error hydrating profile for clipboard drawer:', err);
    }
  }

  private getFieldChips(): CopyFieldChip[] {
    const profile = this.candidateProfile || {};
    const personal = profile.personal || {};

    const fullName = personal.full_name || (profile as any).full_name || '';
    const email = personal.email || (profile as any).email || '';
    const phone = personal.phone || (profile as any).phone || '';
    const location = personal.location || (profile as any).location || '';

    let linkedin = personal.linkedin || (profile as any).linkedin || '';
    if (linkedin && !linkedin.startsWith('http')) {
      linkedin = `https://${linkedin}`;
    }

    let github = personal.github || (profile as any).github || '';
    if (github && !github.startsWith('http')) {
      github = `https://${github}`;
    }

    // Experience / Headline
    let experience = '';
    const exp0 = profile.experience?.[0];
    if (exp0?.role && exp0?.company) {
      experience = `${exp0.role} at ${exp0.company}`;
    } else if (exp0?.role || exp0?.company) {
      experience = exp0.role || exp0.company || '';
    } else if (profile.summary) {
      experience = profile.summary;
    }

    // Skills
    let skills = '';
    if (Array.isArray(profile.skills)) {
      skills = profile.skills.join(', ');
    } else if (profile.skills && typeof profile.skills === 'object') {
      const tech = (profile.skills as any).technical || [];
      const soft = (profile.skills as any).soft || [];
      skills = [...tech, ...soft].join(', ');
    }

    const chips: CopyFieldChip[] = [];

    if (fullName) chips.push({ id: 'chip-fullname', label: 'Full Name', value: fullName, icon: '👤' });
    if (email) chips.push({ id: 'chip-email', label: 'Email', value: email, icon: '✉️' });
    if (phone) chips.push({ id: 'chip-phone', label: 'Phone', value: phone, icon: '📞' });
    if (location) chips.push({ id: 'chip-location', label: 'Location', value: location, icon: '📍' });
    if (linkedin) chips.push({ id: 'chip-linkedin', label: 'LinkedIn', value: linkedin, icon: '🔗' });
    if (github) chips.push({ id: 'chip-github', label: 'GitHub', value: github, icon: '🐙' });
    if (experience) chips.push({ id: 'chip-experience', label: 'Experience/Role', value: experience, icon: '💼' });
    if (skills) chips.push({ id: 'chip-skills', label: 'Skills', value: skills, icon: '⚡' });

    // Fallbacks if profile is completely empty
    if (chips.length === 0) {
      chips.push(
        { id: 'chip-fallback-name', label: 'Full Name', value: 'Candidate Name', icon: '👤' },
        { id: 'chip-fallback-email', label: 'Email', value: 'candidate@example.com', icon: '✉️' }
      );
    }

    return chips;
  }

  private async copyToClipboard(text: string): Promise<boolean> {
    if (!text) return false;
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch {
      // Fall through to textarea execCommand fallback
    }

    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.top = '-9999px';
      textarea.style.left = '-9999px';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const successful = document.execCommand('copy');
      document.body.removeChild(textarea);
      return successful;
    } catch {
      return false;
    }
  }

  private downloadResumePdf(): void {
    const fullName = this.candidateProfile?.personal?.full_name || 'RoleSync';
    const cleanName = fullName.trim().replace(/\s+/g, '_');
    const fileName = `${cleanName}_Tailored_Resume.pdf`;

    if (this.resumeDataUri) {
      const link = document.createElement('a');
      link.href = this.resumeDataUri;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else {
      try {
        chrome.runtime.sendMessage({
          action: 'DOWNLOAD_TAILORED_RESUME',
          payload: { fileName },
        });
      } catch {}
      // Open sidepanel to trigger compilation if resume not ready
      try {
        chrome.runtime.sendMessage({ action: 'OPEN_SIDEPANEL_REQUEST' });
      } catch {}
    }
  }

  public render(): void {
    if (!this.shadowRoot) return;

    if (!this.isShown) {
      this.shadowRoot.innerHTML = '';
      return;
    }

    const chips = this.getFieldChips();

    const html = `
      <style>
        .drawer-card {
          pointer-events: auto;
          margin-bottom: 24px;
          width: calc(100% - 32px);
          max-width: 680px;
          background: #0f172a;
          color: #f8fafc;
          border: 1px solid #334155;
          border-radius: 16px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.55), 0 0 20px rgba(99, 102, 241, 0.2);
          overflow: hidden;
          animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          display: flex;
          flex-direction: column;
        }

        @keyframes slideUp {
          from {
            transform: translateY(40px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        .drawer-header {
          padding: 14px 18px;
          background: #1e293b;
          border-bottom: 1px solid #334155;
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
        }

        .header-left {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .title-row {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .shield-badge {
          background: rgba(99, 102, 241, 0.2);
          border: 1px solid #6366f1;
          color: #a5b4fc;
          font-size: 11px;
          font-weight: 700;
          padding: 2px 7px;
          border-radius: 6px;
          display: inline-flex;
          align-items: center;
          gap: 4px;
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }

        .drawer-title {
          font-size: 13px;
          font-weight: 700;
          color: #f8fafc;
          margin: 0;
        }

        .drawer-desc {
          font-size: 11.5px;
          line-height: 1.45;
          color: #94a3b8;
          margin: 0;
          max-width: 580px;
        }

        .btn-close {
          background: transparent;
          border: none;
          color: #94a3b8;
          cursor: pointer;
          font-size: 16px;
          padding: 4px 8px;
          border-radius: 6px;
          line-height: 1;
          transition: background 0.15s, color 0.15s;
        }

        .btn-close:hover {
          background: #334155;
          color: #ffffff;
        }

        .chips-container {
          padding: 14px 18px;
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
          gap: 10px;
          max-height: 260px;
          overflow-y: auto;
        }

        .chip {
          background: #1e293b;
          border: 1px solid #334155;
          border-radius: 8px;
          padding: 8px 10px;
          display: flex;
          flex-direction: column;
          gap: 3px;
          cursor: pointer;
          transition: all 0.15s ease;
          position: relative;
          text-align: left;
        }

        .chip:hover {
          background: #273549;
          border-color: #6366f1;
          transform: translateY(-1px);
        }

        .chip:active {
          transform: translateY(0);
        }

        .chip-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-size: 10px;
          color: #94a3b8;
          text-transform: uppercase;
          font-weight: 600;
          letter-spacing: 0.03em;
        }

        .chip-val {
          font-size: 12px;
          font-weight: 500;
          color: #f1f5f9;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .chip.copied {
          background: rgba(16, 185, 129, 0.15);
          border-color: #10b981;
        }

        .chip.copied .chip-val {
          color: #34d399;
          font-weight: 600;
        }

        .drawer-footer {
          padding: 12px 18px;
          background: #172033;
          border-top: 1px solid #334155;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          flex-wrap: wrap;
        }

        .footer-hint {
          font-size: 11px;
          color: #64748b;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .footer-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-left: auto;
        }

        .btn-cta {
          background: #4f46e5;
          color: #ffffff;
          border: none;
          padding: 7px 13px;
          border-radius: 7px;
          font-size: 11.5px;
          font-weight: 600;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 5px;
          transition: background 0.15s;
        }

        .btn-cta:hover {
          background: #4338ca;
        }

        .btn-secondary {
          background: #334155;
          color: #e2e8f0;
          border: none;
          padding: 7px 11px;
          border-radius: 7px;
          font-size: 11.5px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s;
        }

        .btn-secondary:hover {
          background: #475569;
        }
      </style>

      <div class="drawer-card" role="dialog" aria-modal="true" aria-label="RoleSync Clipboard Drawer">
        <div class="drawer-header">
          <div class="header-left">
            <div class="title-row">
              <span class="shield-badge">🔒 Frame Guard</span>
              <h3 class="drawer-title">Embedded Application Frame Detected (Cross-Origin Protected)</h3>
            </div>
            <p class="drawer-desc">
              Browser security prevents direct DOM autofill into cross-origin iframes.
              Click any field below to copy to clipboard, then paste (⌘V / Ctrl+V) directly into the job application form.
            </p>
          </div>
          <button class="btn-close" id="btn-drawer-close" title="Dismiss Drawer">✕</button>
        </div>

        <div class="chips-container">
          ${chips
            .map(
              (c) => `
            <div class="chip" data-id="${c.id}" data-val="${encodeURIComponent(c.value)}" title="Click to copy: ${c.value}">
              <div class="chip-top">
                <span>${c.icon} ${c.label}</span>
                <span class="chip-status" style="font-size: 10px;">📋 Copy</span>
              </div>
              <div class="chip-val">${c.value}</div>
            </div>
          `
            )
            .join('')}
        </div>

        <div class="drawer-footer">
          <div class="footer-hint">
            <span>💡 Click chip → Paste into frame input</span>
          </div>
          <div class="footer-actions">
            <button class="btn-cta" id="btn-download-pdf">📄 Download Tailored PDF</button>
            <button class="btn-secondary" id="btn-open-sidepanel">Open Sidepanel ↗</button>
          </div>
        </div>
      </div>
    `;

    this.shadowRoot.innerHTML = html;

    // Attach click listeners to chips
    const chipElements = this.shadowRoot.querySelectorAll<HTMLElement>('.chip');
    chipElements.forEach((chip) => {
      chip.addEventListener('click', async () => {
        const rawVal = chip.getAttribute('data-val');
        if (!rawVal) return;
        const textToCopy = decodeURIComponent(rawVal);
        const success = await this.copyToClipboard(textToCopy);

        if (success) {
          chip.classList.add('copied');
          const statusEl = chip.querySelector('.chip-status');
          if (statusEl) statusEl.textContent = '✓ Copied!';

          setTimeout(() => {
            chip.classList.remove('copied');
            if (statusEl) statusEl.textContent = '📋 Copy';
          }, 1500);
        }
      });
    });

    // Close button
    const btnClose = this.shadowRoot.getElementById('btn-drawer-close');
    if (btnClose) {
      btnClose.addEventListener('click', () => {
        this.close();
      });
    }

    // Download PDF CTA
    const btnDownload = this.shadowRoot.getElementById('btn-download-pdf');
    if (btnDownload) {
      btnDownload.addEventListener('click', () => {
        this.downloadResumePdf();
      });
    }

    // Open sidepanel
    const btnSidepanel = this.shadowRoot.getElementById('btn-open-sidepanel');
    if (btnSidepanel) {
      btnSidepanel.addEventListener('click', () => {
        try {
          chrome.runtime.sendMessage({ action: 'OPEN_SIDEPANEL_REQUEST' });
        } catch {}
      });
    }
  }
}
