// RoleSync Content Script Injector Orchestrator
import { HistoryInterceptor } from './HistoryInterceptor';
import { JobExtractorEngine } from './JobExtractorEngine';
import { DOMAutofillEngine, FormMapping } from './DOMAutofillEngine';
import { WorkdayWizardEngine } from './WorkdayWizardEngine';
import { AppExtensionMessage } from '../types/messages';
import { FrameworkAdapter } from './FrameworkAdapter';

console.log('[RoleSync] Content script orchestrator initializing on host:', window.location.hostname);

const extractor = new JobExtractorEngine();
const autofillEngine = new DOMAutofillEngine();
let workdayWizard: WorkdayWizardEngine | null = null;

function getWorkdayWizard(): WorkdayWizardEngine {
  if (!workdayWizard) {
    workdayWizard = new WorkdayWizardEngine({
      autoAdvance: true,
      pauseBeforeReviewSubmit: true,
      maxWaitPerStepMs: 12000,
    });
  }
  return workdayWizard;
}

async function runExtraction(): Promise<void> {
  try {
    const extracted = await extractor.extract();
    console.log('[RoleSync] Extracted job details:', extracted);

    chrome.runtime.sendMessage({
      action: 'JD_EXTRACTED',
      correlationId: `ext_${Date.now()}`,
      timestamp: Date.now(),
      payload: {
        atsProvider: extracted.atsProvider,
        jobTitle: extracted.title,
        companyName: extracted.company,
        rawText: extracted.rawTextContent,
        cleanedHtml: extracted.cleanedHtmlContent,
        pageUrl: extracted.sourceUrl,
      },
    } as AppExtensionMessage);
  } catch (err) {
    console.error('[RoleSync] Error extracting job details:', err);
  }
}

// 1. Initial extraction on document_idle
if (document.readyState === 'complete' || document.readyState === 'interactive') {
  runExtraction();
} else {
  window.addEventListener('DOMContentLoaded', () => runExtraction());
}

// 2. Install SPA dynamic navigation interceptor
HistoryInterceptor.install((newUrl) => {
  console.log('[RoleSync] Location change detected by interceptor:', newUrl);
  // Debounce to allow new SPA view DOM tree to mount
  setTimeout(() => runExtraction(), 1500);
});

/**
 * Builds universal comprehensive form mappings from candidate profile data.
 */
function buildUniversalMappings(profile: any, resumeDataUri?: string): FormMapping[] {
  const mappings: FormMapping[] = [];
  if (!profile) return mappings;

  const personal = profile.personal || {};
  const fullName = personal.full_name || '';
  const nameParts = fullName.trim().split(/\s+/);
  const firstName = nameParts[0] || '';
  const lastName = nameParts.length > 1 ? nameParts.slice(1).join(' ') : '';
  const email = personal.email || '';
  const phone = personal.phone || '';
  const location = personal.location || '';
  const linkedin = personal.linkedin || '';
  const github = personal.github || '';
  const website = personal.website || '';
  const summary = profile.summary || '';

  // Name
  if (firstName) {
    mappings.push({
      selector: 'input[name*="first_name" i], input[id*="first_name" i], input[autocomplete="given-name"], input[placeholder*="first name" i]',
      value: firstName,
      type: 'TEXT',
    });
  }
  if (lastName) {
    mappings.push({
      selector: 'input[name*="last_name" i], input[id*="last_name" i], input[autocomplete="family-name"], input[placeholder*="last name" i]',
      value: lastName,
      type: 'TEXT',
    });
  }
  if (fullName) {
    mappings.push({
      selector: 'input[name="name"], #name, input[id="name"], input[name*="full_name" i], input[id*="full_name" i], input[autocomplete="name"]',
      value: fullName,
      type: 'TEXT',
    });
  }

  // Contact
  if (email) {
    mappings.push({
      selector: 'input[name*="email" i], #email, input[id*="email" i], input[type="email"], input[autocomplete="email"]',
      value: email,
      type: 'TEXT',
    });
  }
  if (phone) {
    mappings.push({
      selector: 'input[name*="phone" i], #phone, input[id*="phone" i], input[type="tel"], input[autocomplete="tel"]',
      value: phone,
      type: 'TEXT',
    });
  }

  // Location / Address
  if (location) {
    mappings.push({
      selector: 'input[name*="location" i], input[id*="location" i], input[name*="city" i], input[id*="city" i], input[name*="address" i]',
      value: location,
      type: 'TEXT',
    });
  }

  // Headline / Summary
  if (summary) {
    mappings.push({
      selector: 'textarea[name*="summary" i], textarea[id*="summary" i], input[name*="headline" i], textarea[placeholder*="summary" i]',
      value: summary,
      type: 'TEXT',
    });
  }

  // URLs
  if (linkedin) {
    const fullLinkedin = linkedin.startsWith('http') ? linkedin : `https://${linkedin}`;
    mappings.push({
      selector: 'input[name*="linkedin" i], input[id*="linkedin" i], input[placeholder*="linkedin" i]',
      value: fullLinkedin,
      type: 'TEXT',
    });
  }
  if (github) {
    const fullGithub = github.startsWith('http') ? github : `https://${github}`;
    mappings.push({
      selector: 'input[name*="github" i], input[id*="github" i], input[placeholder*="github" i]',
      value: fullGithub,
      type: 'TEXT',
    });
  }
  if (website) {
    mappings.push({
      selector: 'input[name*="website" i], input[id*="website" i], input[name*="portfolio" i], input[id*="portfolio" i]',
      value: website,
      type: 'TEXT',
    });
  }

  // Current Company / Title
  const exp0 = profile.experience?.[0];
  if (exp0?.company) {
    mappings.push({
      selector: 'input[name*="current_company" i], input[id*="current_company" i], input[name*="company" i]:not([name*="address"])',
      value: exp0.company,
      type: 'TEXT',
    });
  }
  if (exp0?.role) {
    mappings.push({
      selector: 'input[name*="current_title" i], input[id*="current_title" i], input[name*="title" i]:not([name*="job_title"])',
      value: exp0.role,
      type: 'TEXT',
    });
  }

  // Resume File Upload
  if (resumeDataUri) {
    mappings.push({
      selector: 'input[type="file"][name*="resume" i], input[type="file"][id*="resume" i], input[type="file"][data-automation-id*="resume" i], input[type="file"][data-automation-id*="file" i], input[type="file"]',
      value: resumeDataUri,
      type: 'FILE',
      fileName: `${fullName ? fullName.replace(/\s+/g, '_') : 'RoleSync'}_Tailored_Resume.pdf`,
    });
  }

  return mappings;
}

// 3. Listen for commands from background / sidepanel
chrome.runtime.onMessage.addListener((message: any, _sender, sendResponse) => {
  if (message.action === 'TRIGGER_PAGE_EXTRACTION') {
    console.log('[RoleSync] Manual trigger page extraction received.');
    runExtraction()
      .then(() => sendResponse({ status: 'EXTRACTION_TRIGGERED' }))
      .catch((err) => sendResponse({ status: 'FAILED', error: String(err) }));
    return true;
  }

  // --- COPILOT AUTOFILL ---
  if (message.action === 'EXECUTE_DOM_AUTOFILL') {
    const { mappings: customMappings, resumeDataUri, candidateProfile } = message.payload || {};
    console.log('[RoleSync] Executing DOM autofill.');

    let effectiveMappings: FormMapping[] = [];
    if (candidateProfile) {
      effectiveMappings = buildUniversalMappings(candidateProfile, resumeDataUri);
    }

    if (customMappings && Array.isArray(customMappings)) {
      effectiveMappings = [...effectiveMappings, ...customMappings];
    }

    autofillEngine
      .executeAutofill(effectiveMappings, (completed, total, current) => {
        chrome.runtime.sendMessage({
          action: 'AUTOFILL_PROGRESS',
          correlationId: message.correlationId,
          timestamp: Date.now(),
          payload: {
            taskId: message.correlationId,
            fieldsCompleted: completed,
            totalFields: total,
            currentFieldSelector: current,
            status: completed === total ? 'COMPLETED' : 'IN_PROGRESS',
          },
        } as AppExtensionMessage);
      })
      .then((res) => {
        sendResponse({ status: 'COMPLETED', result: res });
      })
      .catch((err) => {
        sendResponse({ status: 'FAILED', error: String(err) });
      });

    return true;
  }

  // --- AUTOPILOT MULTI-STAGE TRAVERSAL (WORKDAY & ATS) ---
  if (message.action === 'EXECUTE_AUTOPILOT') {
    const { candidateProfile, resumeDataUri, autoAdvance = true } = message.payload || {};
    const isWorkday = window.location.hostname.includes('workday') || window.location.hostname.includes('myworkdayjobs');

    console.log(`[RoleSync] Executing Autopilot. Is Workday: ${isWorkday}`);

    if (isWorkday) {
      const wizard = getWorkdayWizard();
      const currentStage = wizard.detectCurrentStage();
      console.log(`[RoleSync] Current Workday stage detected: ${currentStage}, autoAdvance=${autoAdvance}`);

      const candidateData = {
        firstName: candidateProfile?.personal?.full_name?.split(' ')[0] || 'Alex',
        lastName: candidateProfile?.personal?.full_name?.split(' ').slice(1).join(' ') || 'Mercer',
        addressLine1: candidateProfile?.personal?.location || '100 Market St',
        city: candidateProfile?.personal?.location?.split(',')[0] || 'San Francisco',
        postalCode: '94105',
        phone: candidateProfile?.personal?.phone || '+1 555-019-2834',
        linkedinUrl: candidateProfile?.personal?.linkedin || 'https://linkedin.com/in/alex-mercer',
        resumeFileName: `${candidateProfile?.personal?.full_name?.replace(/\s+/g, '_') || 'RoleSync'}_Resume.pdf`,
        legallyAuthorized: candidateProfile?.preferences?.legally_authorized ?? true,
        requiresSponsorship: candidateProfile?.preferences?.requires_sponsorship ?? false,
        gender: candidateProfile?.preferences?.gender || 'Decline to self-identify',
        veteranStatus: candidateProfile?.preferences?.veteran_status || 'I am not a protected veteran',
        disabilityStatus: candidateProfile?.preferences?.disability_status || 'No, I do not have a disability',
      };

      wizard
        .processCurrentStage(candidateData, resumeDataUri)
        .then((result) => {
          const isReview = result.stage === 'REVIEW';
          chrome.runtime.sendMessage({
            action: 'AUTOPILOT_PROGRESS',
            correlationId: message.correlationId,
            timestamp: Date.now(),
            payload: {
              taskId: message.correlationId,
              stage: result.stage,
              fieldsCompleted: result.completed,
              fieldsFailed: result.failed,
              nextStageReady: result.nextStageReady,
              isPausedForReview: isReview,
              message: isReview
                ? 'Reached Review Stage. Paused for your final review before submission.'
                : `Stage '${result.stage}' completed (${result.completed} fields filled). Ready for next step.`,
            },
          } as AppExtensionMessage);
          sendResponse({ status: 'COMPLETED', result });
        })
        .catch((err) => {
          sendResponse({ status: 'FAILED', error: String(err) });
        });
    } else {
      // General ATS portal
      const mappings = buildUniversalMappings(candidateProfile, resumeDataUri);
      autofillEngine
        .executeAutofill(mappings, (completed, total, current) => {
          chrome.runtime.sendMessage({
            action: 'AUTOFILL_PROGRESS',
            correlationId: message.correlationId,
            timestamp: Date.now(),
            payload: {
              taskId: message.correlationId,
              fieldsCompleted: completed,
              totalFields: total,
              currentFieldSelector: current,
              status: completed === total ? 'COMPLETED' : 'IN_PROGRESS',
            },
          } as AppExtensionMessage);
        })
        .then((res) => {
          sendResponse({ status: 'COMPLETED', result: res });
        })
        .catch((err) => {
          sendResponse({ status: 'FAILED', error: String(err) });
        });
    }

    return true;
  }

  // --- AUTOFILL COVER LETTER ---
  if (message.action === 'AUTOFILL_COVER_LETTER') {
    const { coverLetterText } = message.payload || {};
    if (!coverLetterText) {
      sendResponse({ status: 'FAILED', error: 'No cover letter text provided' });
      return true;
    }

    const coverSelectors = [
      'textarea[name*="cover" i]',
      'textarea[id*="cover" i]',
      'textarea[placeholder*="cover" i]',
      'textarea[aria-label*="cover" i]',
      'textarea[name*="comment" i]',
      'textarea[id*="comment" i]',
      'textarea[name*="note" i]',
      'textarea[name*="letter" i]',
      'textarea',
    ];

    let foundEl: HTMLTextAreaElement | null = null;
    for (const sel of coverSelectors) {
      const el = document.querySelector<HTMLTextAreaElement>(sel);
      if (el) {
        foundEl = el;
        break;
      }
    }

    if (foundEl) {
      foundEl.focus();
      FrameworkAdapter.setNativeValue(foundEl, coverLetterText);
      FrameworkAdapter.dispatchFrameworkEvents(foundEl);
      sendResponse({ status: 'COMPLETED', selector: foundEl.tagName });
    } else {
      sendResponse({ status: 'NOT_FOUND', message: 'No cover letter textarea detected on page' });
    }
    return true;
  }
});
