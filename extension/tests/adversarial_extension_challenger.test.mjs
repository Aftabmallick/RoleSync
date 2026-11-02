import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionRoot = path.resolve(__dirname, '..');

test('Adversarial Challenge 1: CopilotCapsule Modal Selectors and Boundary Detection', () => {
  const capsuleFile = path.join(extensionRoot, 'src/content/CopilotCapsule.ts');
  const content = fs.readFileSync(capsuleFile, 'utf-8');

  // Assert all 7 modal container selectors exist
  const expectedSelectors = [
    '[aria-modal="true"]',
    '[role="dialog"]',
    'dialog[open]',
    '.jobs-easy-apply-modal',
    'div.artdeco-modal',
    '[data-automation-id="workday-modal"]',
    '.workday-popup',
  ];

  for (const sel of expectedSelectors) {
    assert.ok(
      content.includes(`'${sel}'`),
      `CopilotCapsule MODAL_CONTAINER_SELECTORS missing expected selector: ${sel}`
    );
  }

  // Assert size threshold guards (> 200px) in findActiveModalContainer to ignore tiny dialogs/toasts
  assert.match(
    content,
    /rect\.width\s*>\s*200\s*&&\s*rect\.height\s*>\s*200/,
    'findActiveModalContainer must check width > 200 and height > 200'
  );

  // Assert visibility checks
  assert.match(
    content,
    /window\.getComputedStyle\(el\)\.display\s*!==\s*'none'/,
    'findActiveModalContainer must filter out display: none'
  );
  assert.match(
    content,
    /window\.getComputedStyle\(el\)\.visibility\s*!==\s*'hidden'/,
    'findActiveModalContainer must filter out visibility: hidden'
  );

  // Assert self-exclusion guard (capsule must never detect itself as a modal)
  assert.match(
    content,
    /el\.id\s*===\s*'rolesync-capsule-host'\s*\|\|\s*el\.closest\('#rolesync-capsule-host'\)/,
    'findActiveModalContainer must explicitly ignore capsule host and children'
  );
});

test('Adversarial Challenge 2: Modal Stacking Elevation Math & Boundary Invariants', () => {
  const capsuleFile = path.join(extensionRoot, 'src/content/CopilotCapsule.ts');
  const content = fs.readFileSync(capsuleFile, 'utf-8');

  // Verify zIndex elevation to max 32-bit int
  assert.match(
    content,
    /this\.hostElement\.style\.zIndex\s*=\s*'2147483647';/,
    'Modal elevation must set z-index to 2147483647'
  );

  // Verify Math.max(12, ...) protects against negative top coordinates
  assert.match(
    content,
    /this\.hostElement\.style\.top\s*=\s*`\$\{Math\.max\(12,\s*Math\.round\(modalRect\.top\s*\+\s*8\)\)\}px`;/,
    'style.top must be clamped to min 12px'
  );

  // Verify Math.max(12, ...) protects against overflow on right coordinate
  assert.match(
    content,
    /this\.hostElement\.style\.right\s*=\s*`\$\{Math\.max\(12,\s*Math\.round\(window\.innerWidth\s*-\s*modalRect\.right\s*\+\s*12\)\)\}px`;/,
    'style.right must be clamped to min 12px'
  );

  // Verify bottom and left are explicitly reset to 'auto'
  assert.match(
    content,
    /this\.hostElement\.style\.bottom\s*=\s*'auto';[\s\S]*?this\.hostElement\.style\.left\s*=\s*'auto';/,
    'Modal elevation must clear bottom and left styles to auto'
  );
});

test('Adversarial Challenge 3: Worker Message Dispatch and Cascading Profile Hydration', () => {
  const workerFile = path.join(extensionRoot, 'src/background/worker.ts');
  const content = fs.readFileSync(workerFile, 'utf-8');

  // Verify candidate profile resolution hierarchy:
  // 1. chrome.storage.session -> rolesync_session_checkpoint.candidateProfile
  // 2. chrome.storage.session -> rolesync_user_profile
  // 3. chrome.storage.local -> rolesync_master_profile
  // 4. chrome.storage.local -> rolesync_profile
  assert.match(
    content,
    /sessionData\?\.rolesync_session_checkpoint\?\.candidateProfile/,
    'Must check rolesync_session_checkpoint.candidateProfile first'
  );
  assert.match(
    content,
    /sessionData\?\.rolesync_user_profile/,
    'Must fallback to rolesync_user_profile'
  );
  assert.match(
    content,
    /localData\?\.rolesync_master_profile\s*\|\|\s*localData\?\.rolesync_profile/,
    'Must fallback to local storage master profile'
  );

  // Verify EXECUTE_DOM_AUTOFILL payload packaging
  assert.match(
    content,
    /action:\s*'EXECUTE_DOM_AUTOFILL'/,
    'Must emit EXECUTE_DOM_AUTOFILL'
  );
  assert.match(
    content,
    /payload:\s*\{\s*candidateProfile,\s*resumeDataUri,\s*\}/,
    'Must pass candidateProfile and resumeDataUri in payload'
  );

  // Verify OPEN_SIDEPANEL_REQUEST has windowId fallback
  assert.match(
    content,
    /const\s+currWindow\s*=\s*await\s+chrome\.windows\.getCurrent\(\);/,
    'OPEN_SIDEPANEL_REQUEST must fall back to chrome.windows.getCurrent() if sender.tab.windowId is missing'
  );
});

test('Adversarial Challenge 4: ResumeMatcher Checkbox Invariants and Opt-in Filtration', () => {
  const matcherFile = path.join(extensionRoot, 'src/sidepanel/components/ResumeMatcher.tsx');
  const content = fs.readFileSync(matcherFile, 'utf-8');

  // Verify missing skills initialization
  assert.match(
    content,
    /const\s+initSkills:\s*Record<string,\s*boolean>\s*=\s*\{\};[\s\S]*?(?:\(data\.missing_skills\s*\|\|\s*\[\]\)|data\.missing_skills)\.forEach\(\(s\)\s*=>\s*\(initSkills\[s\.name\]\s*=\s*false\)\);[\s\S]*?setAcceptedSkills\(initSkills\);/,
    'Missing skills must all initialize to false'
  );

  // Verify bullet suggestions initialization
  assert.match(
    content,
    /const\s+initBullets:\s*Record<string,\s*boolean>\s*=\s*\{\};[\s\S]*?(?:\(data\.bullet_suggestions\s*\|\|\s*\[\]\)|data\.bullet_suggestions)\.forEach\(\(b\)\s*=>\s*\(initBullets\[b\.original_id\]\s*=\s*false\)\);[\s\S]*?setAcceptedBullets\(initBullets\);/,
    'Bullet suggestions must all initialize to false'
  );

  // Verify handleAcceptAndSaveVersion strictly filters by truthy accepted keys
  assert.match(
    content,
    /const\s+skillsToApply\s*=\s*Object\.keys\(acceptedSkills\)\.filter\(\(k\)\s*=>\s*acceptedSkills\[k\]\);/,
    'skillsToApply must strictly include only true acceptedSkills'
  );
  assert.match(
    content,
    /const\s+bulletsToApply\s*=\s*matchAnalysis\.bullet_suggestions\s*\.filter\(\(b\)\s*=>\s*acceptedBullets\[b\.original_id\]\)/,
    'bulletsToApply must strictly include only true acceptedBullets'
  );
});
