// RoleSync Framework Prototype Interceptor
// Bypasses React, Angular, and Vue state-fiber shadowing on controlled inputs

export class FrameworkAdapter {
  /**
   * Directly sets the underlying DOM input value by calling the native prototype descriptor,
   * bypassing any setters shadowed by React 16/17/18 synthetic fibers.
   */
  public static setNativeValue(element: HTMLInputElement | HTMLTextAreaElement, value: string): void {
    const prototype = element instanceof HTMLInputElement
      ? window.HTMLInputElement.prototype
      : window.HTMLTextAreaElement.prototype;

    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
    if (descriptor && descriptor.set) {
      descriptor.set.call(element, value);
    } else {
      element.value = value;
    }
  }

  /**
   * Dispatches framework-compliant event chains so that synthetic listeners
   * (e.g. React onChange, Angular ngModelChange) observe state mutation.
   */
  public static dispatchFrameworkEvents(element: HTMLElement): void {
    element.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
    element.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
  }

  /**
   * Checks if an element is currently managed by a React fiber root.
   */
  public static isReactManaged(element: HTMLElement): boolean {
    const keys = Object.keys(element);
    return keys.some(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
  }
}
