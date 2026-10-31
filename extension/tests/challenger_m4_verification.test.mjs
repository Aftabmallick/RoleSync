import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionRoot = path.resolve(__dirname, '..');

test('Gate 2: Suggested bullets and skills default unchecked', () => {
  const matcherFile = path.join(extensionRoot, 'src/sidepanel/components/ResumeMatcher.tsx');
  const content = fs.readFileSync(matcherFile, 'utf-8');

  // Verify missing_skills default unchecked
  assert.match(
    content,
    /data\.missing_skills\.forEach\(\(s\)\s*=>\s*\(initSkills\[s\.name\]\s*=\s*false\)\);/,
    'Missing skills must default to false (unchecked)'
  );

  // Verify bullet_suggestions default unchecked
  assert.match(
    content,
    /data\.bullet_suggestions\.forEach\(\(b\)\s*=>\s*\(initBullets\[b\.original_id\]\s*=\s*false\)\);/,
    'Bullet suggestions must default to false (unchecked)'
  );

  // Verify only accepted bullets are applied in handleAcceptAndSaveVersion
  assert.match(
    content,
    /\.filter\(\(b\)\s*=>\s*acceptedBullets\[b\.original_id\]\)/,
    'Only explicitly accepted bullets may be passed to apply-enhancements'
  );
});

test('Gate 3: Universal fetchWithAuth and WebSocket completion toast', () => {
  const appFile = path.join(extensionRoot, 'src/sidepanel/App.tsx');
  const appContent = fs.readFileSync(appFile, 'utf-8');

  // Verify POST /tailor uses fetchWithAuth
  assert.match(
    appContent,
    /await\s+fetchWithAuth\(`\$\{BACKEND_API_URL\}\/tailor`,\s*\{/,
    'POST /tailor must use fetchWithAuth'
  );

  // Verify GET /tailor/{task_id} uses fetchWithAuth
  assert.match(
    appContent,
    /await\s+fetchWithAuth\(`\$\{BACKEND_API_URL\}\/tailor\/\$\{task_id\}`\)/,
    'GET /tailor/{task_id} must use fetchWithAuth'
  );

  // Verify WebSocket COMPLETED toast matches polling toast
  assert.match(
    appContent,
    /if\s*\(data\.status\s*===\s*'COMPLETED'\)[\s\S]*?showToast\('success',\s*`Tailored single-page resume generated/,
    'WebSocket COMPLETED status must trigger success toast'
  );
});

test('Gate 4: Single consolidated engine pill, 3-stage stepper, and session checkpointing', () => {
  const appFile = path.join(extensionRoot, 'src/sidepanel/App.tsx');
  const appContent = fs.readFileSync(appFile, 'utf-8');

  // Verify keepalive pill removed from visible UI
  assert.doesNotMatch(
    appContent,
    /Chrome Worker Keepalive Port\s*<\/span>/,
    'Redundant Chrome Worker Keepalive Port pill must be eradicated'
  );

  // Verify consolidated pill exists
  assert.match(
    appContent,
    /backendStatus\s*===\s*'online'\s*\?\s*'RoleSync Live'/,
    'Consolidated engine indicator must show RoleSync Live when online'
  );

  // Verify separate Deep AI Tailor card removed
  assert.doesNotMatch(
    appContent,
    /Optional Deep AI Tailor/,
    'Separate Deep AI Tailor card must be removed from App.tsx'
  );

  // Verify chrome.storage.session checkpointing on mount
  assert.match(
    appContent,
    /chrome\.storage\.session\.get\(\['current_jd',\s*'rolesync_session_checkpoint'\]\)/,
    'Sidepanel must rehydrate rolesync_session_checkpoint from chrome.storage.session on mount'
  );

  // Verify chrome.storage.session save on change
  assert.match(
    appContent,
    /chrome\.storage\.session\.set\(\{\s*rolesync_session_checkpoint:/,
    'Sidepanel must persist rolesync_session_checkpoint to chrome.storage.session'
  );
});

test('Gate 4: Amber overflow banner with Auto-Condense & Multi-Page Override in PdfPreview', () => {
  const pdfPreviewFile = path.join(extensionRoot, 'src/sidepanel/components/PdfPreview.tsx');
  const content = fs.readFileSync(pdfPreviewFile, 'utf-8');

  // Inspects numPages
  assert.match(
    content,
    /setNumPages\(pdf\.numPages\);/,
    'PdfPreview must inspect and store pdf.numPages'
  );

  // Renders Amber Overflow Banner conditional on numPages > 1 && !multiPageOverride
  assert.match(
    content,
    /numPages\s*>\s*1\s*&&\s*!multiPageOverride/,
    'Overflow banner must activate when numPages > 1 and multi-page override is inactive'
  );

  // Auto-Condense action
  assert.match(
    content,
    /Auto-Condense\s*\(Smart Prune\)/,
    'Overflow banner must contain Auto-Condense control'
  );

  // Multi-Page Override action
  assert.match(
    content,
    /Allow Multi-Page Resume/,
    'Overflow banner must contain Multi-Page Override control'
  );
});

test('Gate 4: RFC 7807 invalid_params error handling and dirty-state protection', () => {
  const profileEditorFile = path.join(extensionRoot, 'src/sidepanel/components/ProfileEditor.tsx');
  const peContent = fs.readFileSync(profileEditorFile, 'utf-8');

  // Handles invalid_params
  assert.match(
    peContent,
    /errData\?\.invalid_params\s*&&\s*Array\.isArray\(errData\.invalid_params\)/,
    'ProfileEditor must handle RFC 7807 invalid_params'
  );

  // Dirty state tracking
  assert.match(
    peContent,
    /const\s+isDirty\s*=\s*JSON\.stringify\(profile\)\s*!==\s*lastSavedProfileRef\.current;/,
    'ProfileEditor must track dirty state by comparing current profile against lastSavedProfileRef'
  );

  // Tab switch prompt in App.tsx
  const appFile = path.join(extensionRoot, 'src/sidepanel/App.tsx');
  const appContent = fs.readFileSync(appFile, 'utf-8');
  assert.match(
    appContent,
    /if\s*\(activeTab\s*===\s*'profile'\s*&&\s*isProfileDirty\)[\s\S]*?window\.confirm/,
    'App.tsx must prompt before switching tabs when profile is dirty'
  );
});

test('Gate 6: Top-frame guard, collision avoidance, drag-drop, and multi-frame manifest', () => {
  const manifestFile = path.join(extensionRoot, 'manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf-8'));

  // Multi-frame permissions
  assert.ok(manifest.permissions.includes('clipboardWrite'), 'Manifest must include clipboardWrite');
  assert.equal(manifest.content_scripts[0].all_frames, true, 'Content scripts must configure all_frames: true');
  assert.equal(manifest.content_scripts[0].match_about_blank, true, 'Content scripts must configure match_about_blank: true');

  // Subframe guard in injector.ts
  const injectorFile = path.join(extensionRoot, 'src/content/injector.ts');
  const injContent = fs.readFileSync(injectorFile, 'utf-8');
  assert.match(
    injContent,
    /const\s+isTopFrame\s*=\s*window\s*===\s*window\.top;/,
    'Injector must evaluate isTopFrame'
  );
  assert.match(
    injContent,
    /const\s+capsule\s*=\s*isTopFrame\s*\?\s*new\s+CopilotCapsule\(\)\s*:\s*null;/,
    'Capsule must only be instantiated in top frame'
  );

  // ClipboardDrawer fallback in injector.ts
  assert.match(
    injContent,
    /ClipboardDrawer\.show\(candidateProfile,\s*resumeDataUri\);/,
    'Injector must trigger ClipboardDrawer fallback when autofill matches 0 fields with iframes'
  );

  // Collision avoidance and drag in CopilotCapsule.ts
  const capsuleFile = path.join(extensionRoot, 'src/content/CopilotCapsule.ts');
  const capContent = fs.readFileSync(capsuleFile, 'utf-8');
  assert.match(
    capContent,
    /CHAT_WIDGET_SELECTORS/,
    'CopilotCapsule must define known third-party chat widget selectors'
  );
  assert.match(
    capContent,
    /this\.hostElement\.style\.left\s*=\s*'24px';/,
    'CopilotCapsule must auto-offset to bottom-left upon collision'
  );
  assert.match(
    capContent,
    /Math\.max\(12,\s*Math\.min\(window\.innerWidth\s*-\s*hostW\s*-\s*12/,
    'CopilotCapsule must enforce viewport boundary clamping'
  );
  assert.match(
    capContent,
    /rolesync_capsule_pos/,
    'CopilotCapsule must persist position to session storage'
  );
});
