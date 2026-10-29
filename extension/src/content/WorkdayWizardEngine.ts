import { DOMAutofillEngine, FormMapping } from './DOMAutofillEngine';
import { StatefulTaskRunner, AutopilotCheckpoint } from './StatefulTaskRunner';

export type WorkdayStage =
  | 'MY_INFORMATION'
  | 'MY_EXPERIENCE'
  | 'APPLICATION_QUESTIONS'
  | 'VOLUNTARY_DISCLOSURES'
  | 'REVIEW'
  | 'UNKNOWN';

export interface WorkdayAutopilotOptions {
  autoAdvance?: boolean;
  maxWaitPerStepMs?: number;
  pauseBeforeReviewSubmit?: boolean;
}

export class WorkdayWizardEngine {
  private autofillEngine: DOMAutofillEngine;
  private taskRunner: StatefulTaskRunner;
  private options: Required<WorkdayAutopilotOptions>;

  private static STAGE_SEQUENCE: WorkdayStage[] = [
    'MY_INFORMATION',
    'MY_EXPERIENCE',
    'APPLICATION_QUESTIONS',
    'VOLUNTARY_DISCLOSURES',
    'REVIEW',
  ];

  constructor(options?: WorkdayAutopilotOptions) {
    this.autofillEngine = new DOMAutofillEngine();
    this.taskRunner = new StatefulTaskRunner();
    this.options = {
      autoAdvance: options?.autoAdvance ?? true,
      maxWaitPerStepMs: options?.maxWaitPerStepMs ?? 10000,
      pauseBeforeReviewSubmit: options?.pauseBeforeReviewSubmit ?? true,
    };
  }

  /**
   * Identifies current Workday wizard stage from progress indicators or DOM headings.
   */
  public detectCurrentStage(): WorkdayStage {
    // 1. Check data-automation-id on active step or heading
    const activeStepEl = document.querySelector(
      '[data-automation-id="progressBar"] [aria-current="step"], [data-automation-id="progressBar"] [class*="active"], [data-automation-id="pageHeader"]'
    );
    const bodyText = (activeStepEl?.textContent || document.body.innerText).toLowerCase();

    if (bodyText.includes('my information') || document.querySelector('[data-automation-id="legalNameSection"]')) {
      return 'MY_INFORMATION';
    }
    if (bodyText.includes('my experience') || document.querySelector('[data-automation-id="resumeSection"]')) {
      return 'MY_EXPERIENCE';
    }
    if (bodyText.includes('application questions') || document.querySelector('[data-automation-id="questionnaireSection"]')) {
      return 'APPLICATION_QUESTIONS';
    }
    if (bodyText.includes('voluntary disclosures') || bodyText.includes('self-identify') || document.querySelector('[data-automation-id="eeoSection"]')) {
      return 'VOLUNTARY_DISCLOSURES';
    }
    if (bodyText.includes('review') || document.querySelector('[data-automation-id="reviewSection"]')) {
      return 'REVIEW';
    }

    return 'UNKNOWN';
  }

  /**
   * Executes autofill for the current detected Workday stage, updates session checkpoint,
   * and optionally triggers the 'Save and Continue' advance button.
   */
  public async processCurrentStage(
    candidateData: Record<string, any>,
    pdfBase64?: string
  ): Promise<{ stage: WorkdayStage; completed: number; failed: number; nextStageReady: boolean }> {
    const stage = this.detectCurrentStage();
    console.log(`[RoleSync] Processing Workday stage: ${stage}`);

    if (stage === 'UNKNOWN') {
      return { stage, completed: 0, failed: 0, nextStageReady: false };
    }

    const mappings = this.buildMappingsForStage(stage, candidateData, pdfBase64);
    const fillResult = await this.autofillEngine.executeAutofill(mappings);

    const stageIndex = WorkdayWizardEngine.STAGE_SEQUENCE.indexOf(stage);
    await this.taskRunner.advanceStage(stageIndex, stage, { [stage]: fillResult });

    // Review stage requires explicit user confirmation before final submission
    if (stage === 'REVIEW' && this.options.pauseBeforeReviewSubmit) {
      console.log('[RoleSync] Reached REVIEW stage. Pausing autopilot for candidate review.');
      return {
        stage,
        completed: fillResult.completed,
        failed: fillResult.failed,
        nextStageReady: false,
      };
    }

    let nextStageReady = false;
    if (this.options.autoAdvance) {
      nextStageReady = await this.advanceToNextStage();
    }

    return {
      stage,
      completed: fillResult.completed,
      failed: fillResult.failed,
      nextStageReady,
    };
  }

  /**
   * Generates form mappings tailored to Workday DOM conventions for the current stage.
   */
  public buildMappingsForStage(
    stage: WorkdayStage,
    data: Record<string, any>,
    pdfBase64?: string
  ): FormMapping[] {
    const mappings: FormMapping[] = [];

    switch (stage) {
      case 'MY_INFORMATION':
        if (data.firstName) {
          mappings.push({
            selector: 'input[data-automation-id="legalNameSection_firstName"]',
            value: data.firstName,
            type: 'TEXT',
          });
        }
        if (data.lastName) {
          mappings.push({
            selector: 'input[data-automation-id="legalNameSection_lastName"]',
            value: data.lastName,
            type: 'TEXT',
          });
        }
        if (data.addressLine1) {
          mappings.push({
            selector: 'input[data-automation-id="addressSection_addressLine1"]',
            value: data.addressLine1,
            type: 'TEXT',
          });
        }
        if (data.city) {
          mappings.push({
            selector: 'input[data-automation-id="addressSection_city"]',
            value: data.city,
            type: 'TEXT',
          });
        }
        if (data.postalCode) {
          mappings.push({
            selector: 'input[data-automation-id="addressSection_postalCode"]',
            value: data.postalCode,
            type: 'TEXT',
          });
        }
        if (data.phone) {
          mappings.push({
            selector: 'input[data-automation-id="phone-number"]',
            value: data.phone,
            type: 'TEXT',
          });
        }
        break;

      case 'MY_EXPERIENCE':
        if (pdfBase64) {
          mappings.push({
            selector: 'input[type="file"][data-automation-id*="file-upload-input-drop-zone"], input[type="file"]',
            value: pdfBase64,
            type: 'FILE',
            fileName: data.resumeFileName || 'Alex_Mercer_Resume.pdf',
          });
        }
        if (data.linkedinUrl) {
          mappings.push({
            selector: 'input[data-automation-id="website"]',
            value: data.linkedinUrl,
            type: 'TEXT',
          });
        }
        break;

      case 'APPLICATION_QUESTIONS':
        // Common Workday work authorization radio inputs
        if (data.legallyAuthorized !== undefined) {
          mappings.push({
            selector: 'input[name*="legallyAuthorized"]',
            value: data.legallyAuthorized ? 'yes' : 'no',
            type: 'RADIO',
          });
        }
        if (data.requiresSponsorship !== undefined) {
          mappings.push({
            selector: 'input[name*="sponsorship"]',
            value: data.requiresSponsorship ? 'yes' : 'no',
            type: 'RADIO',
          });
        }
        break;

      case 'VOLUNTARY_DISCLOSURES':
        // EEO gender / veteran / disability dropdowns
        if (data.gender) {
          mappings.push({
            selector: '[data-automation-id="gender"]',
            value: data.gender,
            type: 'COMBOBOX',
          });
        }
        if (data.veteranStatus) {
          mappings.push({
            selector: '[data-automation-id="veteranStatus"]',
            value: data.veteranStatus,
            type: 'COMBOBOX',
          });
        }
        if (data.disabilityStatus) {
          mappings.push({
            selector: '[data-automation-id="disabilityStatus"]',
            value: data.disabilityStatus,
            type: 'COMBOBOX',
          });
        }
        break;

      case 'REVIEW':
        // Acknowledgment checkbox
        mappings.push({
          selector: 'input[type="checkbox"][data-automation-id*="agree"]',
          value: 'true',
          type: 'CHECKBOX',
        });
        break;
    }

    return mappings;
  }

  /**
   * Locates and triggers Workday's 'Save and Continue' or 'Next' button,
   * then verifies the transition to the next page view.
   */
  public async advanceToNextStage(): Promise<boolean> {
    const nextBtnSelectors = [
      'button[data-automation-id="bottom-navigation-next-button"]',
      'button[data-automation-id="page-navigation-save-and-continue"]',
      'button[data-automation-id="next-button"]',
    ];

    let button: HTMLElement | null = null;
    for (const sel of nextBtnSelectors) {
      const el = document.querySelector(sel) as HTMLElement;
      if (el && !el.hasAttribute('disabled')) {
        button = el;
        break;
      }
    }

    if (!button) {
      // Fallback search by text
      const buttons = Array.from(document.querySelectorAll('button'));
      button =
        buttons.find(
          b => /save and continue|save & continue|next step|continue/i.test(b.textContent || '') &&
               !b.hasAttribute('disabled')
        ) || null;
    }

    if (!button) {
      console.warn('[RoleSync] Next/Save and Continue button not found or disabled.');
      return false;
    }

    const currentUrl = window.location.href;
    button.scrollIntoView({ behavior: 'smooth', block: 'center' });
    button.click();

    // Wait for transition or DOM mutation
    return new Promise((resolve) => {
      let timeoutId: NodeJS.Timeout;
      const observer = new MutationObserver(() => {
        const newStage = this.detectCurrentStage();
        if (newStage !== 'UNKNOWN') {
          clearTimeout(timeoutId);
          observer.disconnect();
          resolve(true);
        }
      });

      timeoutId = setTimeout(() => {
        observer.disconnect();
        resolve(window.location.href !== currentUrl);
      }, this.options.maxWaitPerStepMs);

      observer.observe(document.body, { childList: true, subtree: true });
    });
  }
}
