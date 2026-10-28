// RoleSync MV3 Keepalive & State Lifecycle Manager

export class KeepaliveManager {
  private static activePort: chrome.runtime.Port | null = null;
  public static readonly KEEPALIVE_PORT_NAME = 'rolesync_ui_keepalive';

  public static initialize(): void {
    chrome.runtime.onConnect.addListener((port) => {
      if (port.name === this.KEEPALIVE_PORT_NAME) {
        this.activePort = port;
        console.log('[RoleSync] Keepalive port connected from UI.');

        port.onDisconnect.addListener(() => {
          this.activePort = null;
          console.log('[RoleSync] Keepalive port disconnected.');
        });

        port.onMessage.addListener((msg) => {
          if (msg.type === 'PING') {
            port.postMessage({ type: 'PONG', timestamp: Date.now() });
          }
        });
      }
    });
  }

  public static isConnected(): boolean {
    return this.activePort !== null;
  }

  public static async executeWithLock<T>(taskId: string, operation: () => Promise<T>): Promise<T> {
    if (typeof navigator !== 'undefined' && navigator.locks) {
      return new Promise<T>((resolve, reject) => {
        navigator.locks.request(`rolesync_task_${taskId}`, { mode: 'exclusive' }, async () => {
          try {
            const res = await operation();
            resolve(res);
          } catch (err) {
            reject(err);
          }
        });
      });
    }
    // Fallback if locks are unavailable
    return await operation();
  }

  public static async checkpointState(key: string, data: any): Promise<void> {
    if (chrome && chrome.storage && chrome.storage.session) {
      await chrome.storage.session.set({ [key]: { data, updatedAt: Date.now() } });
    }
  }

  public static async getCheckpointState<T>(key: string): Promise<T | null> {
    if (chrome && chrome.storage && chrome.storage.session) {
      const res = await chrome.storage.session.get(key);
      return res[key]?.data || null;
    }
    return null;
  }

  public static async clearCheckpoint(key: string): Promise<void> {
    if (chrome && chrome.storage && chrome.storage.session) {
      await chrome.storage.session.remove(key);
    }
  }
}

