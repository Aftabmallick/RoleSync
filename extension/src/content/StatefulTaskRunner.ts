export type AutopilotStatus = 'IDLE' | 'IN_PROGRESS' | 'PAUSED' | 'COMPLETED' | 'ERROR';

export interface AutopilotCheckpoint {
  taskId: string;
  jobUrl: string;
  currentStepIndex: number;
  currentStepName: string;
  status: AutopilotStatus;
  completedSteps: string[];
  stepData: Record<string, any>;
  timestamp: number;
  retryCount: number;
  lastError?: string;
}

export class StatefulTaskRunner {
  private static STORAGE_KEY = 'rolesync_workday_autopilot_checkpoint';
  private memoryFallback: AutopilotCheckpoint | null = null;

  /**
   * Persists task progress to chrome.storage.session or sessionStorage
   * to survive multi-page navigation across wizard stages.
   */
  public async saveCheckpoint(checkpoint: AutopilotCheckpoint): Promise<void> {
    checkpoint.timestamp = Date.now();
    this.memoryFallback = checkpoint;

    try {
      if (typeof chrome !== 'undefined' && chrome?.storage?.session) {
        await chrome.storage.session.set({ [StatefulTaskRunner.STORAGE_KEY]: checkpoint });
        return;
      }
    } catch {
      // Fallback below
    }

    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        window.sessionStorage.setItem(
          StatefulTaskRunner.STORAGE_KEY,
          JSON.stringify(checkpoint)
        );
      }
    } catch (e) {
      console.warn('[RoleSync] Failed to persist checkpoint to sessionStorage:', e);
    }
  }

  /**
   * Restores checkpoint state upon landing on a new wizard page.
   */
  public async loadCheckpoint(): Promise<AutopilotCheckpoint | null> {
    try {
      if (typeof chrome !== 'undefined' && chrome?.storage?.session) {
        const result = await chrome.storage.session.get(StatefulTaskRunner.STORAGE_KEY);
        if (result && result[StatefulTaskRunner.STORAGE_KEY]) {
          return result[StatefulTaskRunner.STORAGE_KEY] as AutopilotCheckpoint;
        }
      }
    } catch {
      // Fallback below
    }

    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        const raw = window.sessionStorage.getItem(StatefulTaskRunner.STORAGE_KEY);
        if (raw) {
          return JSON.parse(raw) as AutopilotCheckpoint;
        }
      }
    } catch (e) {
      console.warn('[RoleSync] Failed to read checkpoint from sessionStorage:', e);
    }

    return this.memoryFallback;
  }

  /**
   * Clears the current active session state upon completion or abandonment.
   */
  public async clearCheckpoint(): Promise<void> {
    this.memoryFallback = null;
    try {
      if (typeof chrome !== 'undefined' && chrome?.storage?.session) {
        await chrome.storage.session.remove(StatefulTaskRunner.STORAGE_KEY);
      }
    } catch {}

    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        window.sessionStorage.removeItem(StatefulTaskRunner.STORAGE_KEY);
      }
    } catch {}
  }

  /**
   * Advances the wizard checkpoint to the next sequential stage.
   */
  public async advanceStage(
    nextStepIndex: number,
    nextStepName: string,
    currentStepData?: Record<string, any>
  ): Promise<AutopilotCheckpoint> {
    const existing = await this.loadCheckpoint();
    const updated: AutopilotCheckpoint = {
      taskId: existing?.taskId || `task_${Date.now()}`,
      jobUrl: window.location.href,
      currentStepIndex: nextStepIndex,
      currentStepName: nextStepName,
      status: 'IN_PROGRESS',
      completedSteps: existing
        ? Array.from(new Set([...existing.completedSteps, existing.currentStepName]))
        : [],
      stepData: { ...(existing?.stepData || {}), ...(currentStepData || {}) },
      timestamp: Date.now(),
      retryCount: 0,
    };

    await this.saveCheckpoint(updated);
    return updated;
  }
}

