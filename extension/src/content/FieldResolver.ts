// RoleSync Heuristic Field Resolution Engine
// Resolves input targets using multi-strategy cascading heuristics

export interface ResolvedField {
  element: HTMLElement;
  fieldType: 'TEXT' | 'SELECT' | 'RADIO' | 'CHECKBOX' | 'FILE' | 'COMBOBOX';
  confidence: number;
}

export class FieldResolver {
  public static resolveInput(targetKey: string): ResolvedField | null {
    const keyClean = targetKey.toLowerCase().trim();

    // Strategy 1: Explicit label[for] match
    const labels = Array.from(document.querySelectorAll('label'));
    for (const label of labels) {
      const text = label.textContent?.toLowerCase().trim() || '';
      if (text.includes(keyClean)) {
        const forId = label.getAttribute('for');
        if (forId) {
          const el = document.getElementById(forId);
          if (el) return this.classifyElement(el, 0.95);
        }
        // Subtree input inside label
        const nested = label.querySelector('input, select, textarea');
        if (nested) return this.classifyElement(nested as HTMLElement, 0.90);
      }
    }

    // Strategy 2: aria-label / aria-labelledby
    const ariaElements = Array.from(document.querySelectorAll<HTMLElement>('[aria-label], [aria-labelledby]'));
    for (const el of ariaElements) {
      const labelText = el.getAttribute('aria-label')?.toLowerCase() || '';
      if (labelText.includes(keyClean)) {
        return this.classifyElement(el, 0.90);
      }
    }

    // Strategy 3: Name, id, or placeholder attribute match
    const inputs = Array.from(document.querySelectorAll<HTMLInputElement>('input, textarea, select, [role="combobox"]'));
    for (const input of inputs) {
      const name = (input.getAttribute('name') || '').toLowerCase();
      const id = (input.id || '').toLowerCase();
      const placeholder = (input.getAttribute('placeholder') || '').toLowerCase();

      if (name.includes(keyClean) || id.includes(keyClean) || placeholder.includes(keyClean)) {
        return this.classifyElement(input, 0.85);
      }
    }

    return null;
  }

  private static classifyElement(el: HTMLElement, confidence: number): ResolvedField {
    if (el.tagName === 'SELECT') {
      return { element: el, fieldType: 'SELECT', confidence };
    }
    if (el.getAttribute('role') === 'combobox' || el.classList.contains('select__control')) {
      return { element: el, fieldType: 'COMBOBOX', confidence };
    }
    if (el instanceof HTMLInputElement) {
      const type = (el.type || 'text').toUpperCase();
      if (type === 'FILE') return { element: el, fieldType: 'FILE', confidence };
      if (type === 'RADIO') return { element: el, fieldType: 'RADIO', confidence };
      if (type === 'CHECKBOX') return { element: el, fieldType: 'CHECKBOX', confidence };
    }
    return { element: el, fieldType: 'TEXT', confidence };
  }
}
