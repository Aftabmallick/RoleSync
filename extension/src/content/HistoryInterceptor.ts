// RoleSync SPA Dynamic Navigation Interceptor
// Detects page transitions on client-side routing applications (LinkedIn, Workday, Lever)

export class HistoryInterceptor {
  private static installed = false;

  public static install(onRouteChange: (url: string) => void): void {
    if (this.installed) return;
    this.installed = true;

    const wrapHistoryMethod = (type: 'pushState' | 'replaceState') => {
      const original = history[type];
      return function (this: History, ...args: any[]) {
        const result = original.apply(this, args);
        window.dispatchEvent(new Event('rolesync:location_change'));
        return result;
      };
    };

    history.pushState = wrapHistoryMethod('pushState');
    history.replaceState = wrapHistoryMethod('replaceState');

    window.addEventListener('popstate', () => {
      onRouteChange(window.location.href);
    });

    window.addEventListener('rolesync:location_change', () => {
      onRouteChange(window.location.href);
    });

    console.log('[RoleSync] SPA HistoryInterceptor successfully installed.');
  }
}
