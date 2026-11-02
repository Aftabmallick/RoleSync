import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionRoot = path.resolve(__dirname, '..');

test('M1: Dynamic Modal Stacking Elevation & Selectors in CopilotCapsule', () => {
  const capsuleFile = path.join(extensionRoot, 'src/content/CopilotCapsule.ts');
  const content = fs.readFileSync(capsuleFile, 'utf-8');

  // Verify MODAL_CONTAINER_SELECTORS exported
  assert.match(
    content,
    /export\s+const\s+MODAL_CONTAINER_SELECTORS:\s*string\[\]\s*=/,
    'CopilotCapsule must export MODAL_CONTAINER_SELECTORS'
  );

  // Verify modal selectors include standard ATS and dialog patterns
  assert.match(content, /'\[aria-modal="true"\]'/, 'Must include [aria-modal="true"] selector');
  assert.match(content, /'dialog\[open\]'/, 'Must include dialog[open] selector');
  assert.match(content, /'\.jobs-easy-apply-modal'/, 'Must include LinkedIn Easy Apply modal selector');
  assert.match(content, /'\[data-automation-id="workday-modal"\]'/, 'Must include Workday modal selector');

  // Verify findActiveModalContainer method
  assert.match(
    content,
    /findActiveModalContainer\(\):\s*HTMLElement\s*\|\s*null/,
    'CopilotCapsule must implement findActiveModalContainer'
  );

  // Verify evaluateCollision docks to modal header/margin with elevated z-index
  assert.match(
    content,
    /const\s+activeModal\s*=\s*this\.findActiveModalContainer\(\);/,
    'evaluateCollision must query active modal container'
  );
  assert.match(
    content,
    /this\.hostElement\.style\.zIndex\s*=\s*'2147483647';/,
    'evaluateCollision must elevate z-index above modal backdrop'
  );
  assert.match(
    content,
    /Math\.max\(12,\s*Math\.round\(modalRect\.top\s*\+\s*8\)\)/,
    'evaluateCollision must dock adjacent to modal header vertically'
  );

  // Verify Shadow DOM CSS isolation reset
  assert.match(
    content,
    /:host\s*\{\s*all:\s*initial\s*!important;\s*contain:\s*content;\s*\}/,
    'Capsule Shadow DOM must enforce strict CSS isolation with :host { all: initial !important; contain: content; }'
  );

  // Verify third-party collision avoidance remains intact
  assert.match(
    content,
    /this\.hostElement\.style\.left\s*=\s*'24px';/,
    'Capsule must auto-offset to bottom-left when chat widget collision detected'
  );
});

test('M1: Background Service Worker Message Routing in worker.ts', () => {
  const workerFile = path.join(extensionRoot, 'src/background/worker.ts');
  const content = fs.readFileSync(workerFile, 'utf-8');

  // Verify TRIGGER_AUTOFILL_FROM_CAPSULE handler
  assert.match(
    content,
    /case\s+'TRIGGER_AUTOFILL_FROM_CAPSULE':/,
    'worker.ts must handle TRIGGER_AUTOFILL_FROM_CAPSULE'
  );
  assert.match(
    content,
    /action:\s*'EXECUTE_DOM_AUTOFILL'/,
    'worker.ts must dispatch EXECUTE_DOM_AUTOFILL to active tab upon TRIGGER_AUTOFILL_FROM_CAPSULE'
  );
  assert.match(
    content,
    /chrome\.tabs\.sendMessage\(targetTabId,\s*autofillMsg/,
    'worker.ts must send autofill message to target tab'
  );

  // Verify OPEN_SIDEPANEL_REQUEST handler
  assert.match(
    content,
    /case\s+'OPEN_SIDEPANEL_REQUEST':/,
    'worker.ts must handle OPEN_SIDEPANEL_REQUEST'
  );
  assert.match(
    content,
    /chrome\.sidePanel\.open\(\{\s*windowId\s*\}\)/,
    'worker.ts must call chrome.sidePanel.open with windowId'
  );
});

test('M1: Session Checkpoint Hydration in App.tsx', () => {
  const appFile = path.join(extensionRoot, 'src/sidepanel/App.tsx');
  const content = fs.readFileSync(appFile, 'utf-8');

  // Verify candidateProfile is included in rolesync_session_checkpoint persistence
  assert.match(
    content,
    /rolesync_session_checkpoint:\s*\{[\s\S]*?candidateProfile:\s*masterProfile/,
    'rolesync_session_checkpoint must persist candidateProfile'
  );

  // Verify rehydration restores candidateProfile if present
  assert.match(
    content,
    /if\s*\(cp\.candidateProfile\)\s*setMasterProfile/,
    'App.tsx must rehydrate candidateProfile from session checkpoint'
  );
});

test('M1: Demo Profile Sanitization in ProfileEditor.tsx', () => {
  const profileEditorFile = path.join(extensionRoot, 'src/sidepanel/components/ProfileEditor.tsx');
  const content = fs.readFileSync(profileEditorFile, 'utf-8');

  // Extract SAMPLE_DEMO_PROFILE definition
  const match = content.match(/export\s+const\s+SAMPLE_DEMO_PROFILE:\s*MasterProfileData\s*=\s*(\{[\s\S]*?\n\};)/);
  assert.ok(match, 'SAMPLE_DEMO_PROFILE must be defined and exported');

  const demoProfileStr = match[1];

  // Assert neither 'Alex Mercer' nor 'Apex Systems' is present in SAMPLE_DEMO_PROFILE
  assert.doesNotMatch(
    demoProfileStr,
    /Alex Mercer/i,
    'SAMPLE_DEMO_PROFILE must not contain reference to Alex Mercer'
  );
  assert.doesNotMatch(
    demoProfileStr,
    /Apex Systems/i,
    'SAMPLE_DEMO_PROFILE must not contain reference to Apex Systems'
  );

  // Assert valid replacement structure exists
  assert.match(
    demoProfileStr,
    /full_name:\s*'Jordan Hayes'/,
    'SAMPLE_DEMO_PROFILE should have sanitized realistic full_name'
  );
  assert.match(
    demoProfileStr,
    /company:\s*'TechFlow Systems'/,
    'SAMPLE_DEMO_PROFILE should have sanitized realistic company'
  );
});
