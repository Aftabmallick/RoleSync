// RoleSync Dynamic DOM Autofill & Human Emulation Engine
import { FrameworkAdapter } from './FrameworkAdapter';

export interface FormMapping {
  selector: string;
  value: string; // Text value OR base64 dataURI for binary files
  type: 'TEXT' | 'SELECT' | 'RADIO' | 'CHECKBOX' | 'FILE' | 'COMBOBOX';
  fileName?: string;
  required?: boolean;
}

export class DOMAutofillEngine {
  public async executeAutofill(
    mappings: FormMapping[],
    onProgress?: (completed: number, total: number, currentSelector: string) => void
  ): Promise<{ completed: number; failed: number; hasCrossOriginIframes?: boolean }> {
    let completed = 0;
    let failed = 0;

    for (let i = 0; i < mappings.length; i++) {
      const mapping = mappings[i];
      try {
        if (onProgress) {
          onProgress(completed, mappings.length, mapping.selector);
        }

        // Deep query traversing open shadow roots across modern web components
        const el = this.querySelectorDeep(mapping.selector);
        if (!el) {
          console.warn(`[RoleSync] Target element not found: ${mapping.selector}`);
          failed++;
          continue;
        }

        switch (mapping.type) {
          case 'TEXT':
            await this.simulateHumanTyping(el as HTMLInputElement, mapping.value);
            break;
          case 'FILE':
            await this.uploadFileViaDataTransfer(
              el as HTMLInputElement,
              mapping.value,
              mapping.fileName || 'Resume_Tailored.pdf'
            );
            break;
          case 'SELECT':
            await this.selectDropdownOption(el as HTMLSelectElement, mapping.value);
            break;
          case 'COMBOBOX':
            await this.populateAriaCombobox(el, mapping.value);
            break;
          case 'RADIO':
            this.setRadioOption(mapping.selector, mapping.value);
            break;
          case 'CHECKBOX':
            this.setCheckbox(el as HTMLInputElement, mapping.value === 'true');
            break;
        }

        this.highlightElement(el, 'success');
        completed++;
        // Inter-field human pause jitter (100ms - 250ms)
        await this.delay(this.randomInt(100, 250));
      } catch (err) {
        console.error(`[RoleSync] Failed mapping for ${mapping.selector}:`, err);
        const errEl = document.querySelector(mapping.selector) as HTMLElement | null;
        if (errEl) {
          this.highlightElement(errEl, 'warning');
        }
        failed++;
      }
    }

    if (onProgress) {
      onProgress(completed, mappings.length, 'DONE');
    }

    return { completed, failed, hasCrossOriginIframes: this.hasCrossOriginIframes() };
  }

  /**
   * Detects whether any cross-origin iframes exist in the document that are blocked
   * by browser same-origin policies.
   */
  public hasCrossOriginIframes(): boolean {
    try {
      const iframes = Array.from(document.querySelectorAll('iframe'));
      for (const frame of iframes) {
        try {
          if (!frame.contentDocument) {
            return true;
          }
        } catch {
          // Cross-origin SOP boundary encountered
          return true;
        }
      }
    } catch {
      // Ignore errors
    }
    return false;
  }

  /**
   * Recursive tree walker piercing open Shadow DOM roots on modern enterprise web components
   * and traversing same-origin iframes while safely tolerating cross-origin frames.
   */
  public querySelectorDeep(selector: string, root: Document | Element | ShadowRoot = document): HTMLElement | null {
    try {
      const directMatch = root.querySelector(selector);
      if (directMatch) return directMatch as HTMLElement;

      const children = root.querySelectorAll('*');
      for (let i = 0; i < children.length; i++) {
        const child = children[i];
        if (child.shadowRoot) {
          const shadowMatch = this.querySelectorDeep(selector, child.shadowRoot);
          if (shadowMatch) return shadowMatch;
        }
        if (child instanceof HTMLIFrameElement) {
          try {
            if (child.contentDocument) {
              const frameMatch = this.querySelectorDeep(selector, child.contentDocument);
              if (frameMatch) return frameMatch;
            }
          } catch {
            // Sandboxed / cross-origin iframe blocked by SOP
          }
        }
      }
    } catch {
      // Ignore syntax errors in deep query fallback
    }
    return null;
  }

  /**
   * Decoupled coordinate-anchored pulse highlighting for active form inputs.
   * Renders into #rolesync-pulse-overlay-root to avoid mutating ATS DOM nodes directly.
   */
  public highlightElement(el: HTMLElement, status: 'success' | 'warning' | 'error' = 'success'): void {
    try {
      let overlayRoot = document.getElementById('rolesync-pulse-overlay-root');
      if (!overlayRoot) {
        overlayRoot = document.createElement('div');
        overlayRoot.id = 'rolesync-pulse-overlay-root';
        overlayRoot.style.position = 'absolute';
        overlayRoot.style.top = '0';
        overlayRoot.style.left = '0';
        overlayRoot.style.width = '100%';
        overlayRoot.style.height = '100%';
        overlayRoot.style.pointerEvents = 'none';
        overlayRoot.style.zIndex = '2147483640';
        document.body.appendChild(overlayRoot);
      }

      const rect = el.getBoundingClientRect();
      const scrollX = window.scrollX || window.pageXOffset || 0;
      const scrollY = window.scrollY || window.pageYOffset || 0;

      const pulse = document.createElement('div');
      const color = status === 'success' ? '#10b981' : status === 'warning' ? '#f59e0b' : '#ef4444';
      const bgColor = status === 'success' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)';

      pulse.style.position = 'absolute';
      pulse.style.top = `${rect.top + scrollY - 2}px`;
      pulse.style.left = `${rect.left + scrollX - 2}px`;
      pulse.style.width = `${rect.width + 4}px`;
      pulse.style.height = `${rect.height + 4}px`;
      pulse.style.borderRadius = '6px';
      pulse.style.border = `2px solid ${color}`;
      pulse.style.backgroundColor = bgColor;
      pulse.style.boxShadow = `0 0 8px ${color}60`;
      pulse.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
      pulse.style.pointerEvents = 'none';

      overlayRoot.appendChild(pulse);

      setTimeout(() => {
        pulse.style.opacity = '0';
        pulse.style.transform = 'scale(1.02)';
        setTimeout(() => pulse.remove(), 700);
      }, 1200);
    } catch {
      // Non-critical visual highlight failure ignored
    }
  }

  public async uploadFileViaDataTransfer(
    input: HTMLInputElement,
    dataUri: string,
    fileName: string
  ): Promise<void> {
    /**
     * Synthesizes a FileList using the DataTransfer API to safely attach
     * binary PDF blobs to standard file inputs.
     */
    let blob: Blob;
    try {
      const base64Data = dataUri.includes(',') ? dataUri.split(',')[1] : dataUri;
      const byteCharacters = atob(base64Data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      blob = new Blob([byteArray], { type: 'application/pdf' });
    } catch (e) {
      const url = dataUri.startsWith('data:') ? dataUri : `data:application/pdf;base64,${dataUri}`;
      const res = await fetch(url);
      blob = await res.blob();
    }

    const file = new File([blob], fileName, {
      type: 'application/pdf',
      lastModified: Date.now()
    });

    const dt = new DataTransfer();
    dt.items.add(file);

    input.files = dt.files;
    FrameworkAdapter.dispatchFrameworkEvents(input);
    console.log(`[RoleSync] File '${fileName}' bound via DataTransfer to:`, input);
  }

  public async populateAriaCombobox(container: HTMLElement, value: string): Promise<void> {
    /**
     * Handles Workday and modern React-Select ARIA comboboxes and custom listboxes.
     */
    container.focus();
    container.click();
    await this.delay(120);

    const input = container.querySelector('input') || container;
    if (input instanceof HTMLInputElement) {
      await this.simulateHumanTyping(input, value);
    }
    await this.delay(180);

    // Look for popover options
    const option = document.querySelector('[role="option"], .select__option, li[role="option"]');
    if (option) {
      (option as HTMLElement).click();
    }
  }

  private async simulateHumanTyping(input: HTMLInputElement, text: string): Promise<void> {
    input.focus();
    input.dispatchEvent(new FocusEvent('focus', { bubbles: true }));

    // Reset input value through native setter to satisfy React fibers
    FrameworkAdapter.setNativeValue(input, '');
    FrameworkAdapter.dispatchFrameworkEvents(input);

    let currentVal = '';
    for (let i = 0; i < text.length; i++) {
      const char = text[i];

      // Dispatch keyboard events
      input.dispatchEvent(new KeyboardEvent('keydown', { key: char, code: `Key${char.toUpperCase()}`, bubbles: true }));
      input.dispatchEvent(new KeyboardEvent('keypress', { key: char, bubbles: true }));

      // Append character via prototype setter
      currentVal += char;
      FrameworkAdapter.setNativeValue(input, currentVal);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new KeyboardEvent('keyup', { key: char, bubbles: true }));

      // Gaussian typing latency: Mean 45ms, standard deviation 15ms
      const delayMs = Math.max(15, Math.floor(this.gaussianRandom(45, 15)));
      await this.delay(delayMs);

      // 1.5% chance of simulated typo + correction
      if (Math.random() < 0.015 && i < text.length - 1) {
        await this.simulateTypoCorrection(input, currentVal);
      }
    }

    FrameworkAdapter.dispatchFrameworkEvents(input);
    input.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
  }

  private async simulateTypoCorrection(input: HTMLInputElement, currentVal: string): Promise<void> {
    const typoChar = String.fromCharCode(97 + Math.floor(Math.random() * 26));
    FrameworkAdapter.setNativeValue(input, currentVal + typoChar);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await this.delay(this.randomInt(80, 150));

    // Backspace
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', keyCode: 8, bubbles: true }));
    FrameworkAdapter.setNativeValue(input, currentVal);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Backspace', keyCode: 8, bubbles: true }));
    await this.delay(this.randomInt(60, 110));
  }

  private async selectDropdownOption(select: HTMLSelectElement, targetValue: string): Promise<void> {
    select.focus();
    const options = Array.from(select.options);
    const targetNorm = targetValue.toLowerCase().trim();

    const matched = options.find(
      opt => opt.text.toLowerCase().trim().includes(targetNorm) || opt.value.toLowerCase().trim() === targetNorm
    );

    if (matched) {
      select.value = matched.value;
      FrameworkAdapter.dispatchFrameworkEvents(select);
    }
    select.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
  }

  private setRadioOption(selector: string, targetValue: string): void {
    const radios = Array.from(document.querySelectorAll<HTMLInputElement>(selector));
    const targetNorm = targetValue.toLowerCase().trim();

    const match = radios.find(
      r => r.value.toLowerCase().trim() === targetNorm ||
           r.parentElement?.textContent?.toLowerCase().trim().includes(targetNorm)
    );

    if (match) {
      match.checked = true;
      FrameworkAdapter.dispatchFrameworkEvents(match);
      match.click();
    }
  }

  private setCheckbox(checkbox: HTMLInputElement, shouldCheck: boolean): void {
    if (checkbox.checked !== shouldCheck) {
      checkbox.checked = shouldCheck;
      FrameworkAdapter.dispatchFrameworkEvents(checkbox);
      checkbox.click();
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(res => setTimeout(res, ms));
  }

  private randomInt(min: number, max: number): number {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  private gaussianRandom(mean: number, stdDev: number): number {
    const u = 1 - Math.random();
    const v = Math.random();
    const z = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    return mean + z * stdDev;
  }
}
