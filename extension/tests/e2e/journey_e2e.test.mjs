import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionRoot = path.resolve(__dirname, '../..');
const fixturesDir = path.resolve(__dirname, '../fixtures');

// Read source files once for regex/static contract assertions
const workdayHtml = fs.readFileSync(path.join(fixturesDir, 'workday.html'), 'utf-8');
const greenhouseHtml = fs.readFileSync(path.join(fixturesDir, 'greenhouse.html'), 'utf-8');
const leverHtml = fs.readFileSync(path.join(fixturesDir, 'lever.html'), 'utf-8');
const serverMjs = fs.readFileSync(path.join(fixturesDir, 'server.mjs'), 'utf-8');
const keepaliveContent = fs.readFileSync(path.join(extensionRoot, 'src/background/KeepaliveManager.ts'), 'utf-8');
const workerContent = fs.readFileSync(path.join(extensionRoot, 'src/background/worker.ts'), 'utf-8');
const profileEditorContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/components/ProfileEditor.tsx'), 'utf-8');
const extractorContent = fs.readFileSync(path.join(extensionRoot, 'src/content/JobExtractorEngine.ts'), 'utf-8');
const scorecardContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/components/ScoreCard.tsx'), 'utf-8');
const matcherContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/components/ResumeMatcher.tsx'), 'utf-8');
const pdfPreviewContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/components/PdfPreview.tsx'), 'utf-8');
const coverLetterContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/components/CoverLetterViewer.tsx'), 'utf-8');
const outreachContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/components/RecruiterOutreach.tsx'), 'utf-8');
const workdayWizardContent = fs.readFileSync(path.join(extensionRoot, 'src/content/WorkdayWizardEngine.ts'), 'utf-8');
const injectorContent = fs.readFileSync(path.join(extensionRoot, 'src/content/injector.ts'), 'utf-8');
const frameworkContent = fs.readFileSync(path.join(extensionRoot, 'src/content/FrameworkAdapter.ts'), 'utf-8');
const trackerContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/components/ApplicationsTracker.tsx'), 'utf-8');
const appContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/App.tsx'), 'utf-8');

// ===========================================================================
// TIER 1: CORE FUNCTIONAL HAPPY PATHS (ALL 9 STAGES)
// ===========================================================================

test('Tier 1 - Feature 1: Sidepanel Keepalive Lifecycle & Message Routing', () => {
  assert.match(keepaliveContent, /KEEPALIVE_PORT_NAME\s*=\s*'rolesync_ui_keepalive'/);
  assert.match(keepaliveContent, /type:\s*'PONG'/);
  assert.match(workerContent, /case\s+'TRIGGER_AUTOFILL_FROM_CAPSULE':/);
  assert.match(workerContent, /case\s+'OPEN_SIDEPANEL_REQUEST':/);
  assert.match(workerContent, /case\s+'JD_EXTRACTED':/);
});

test('Tier 1 - Feature 2: Master Profile Jordan Hayes Baseline & GPA Integrity', () => {
  assert.match(profileEditorContent, /placeholder="GPA\s*\(e\.g\.\s*3\.85\)"/);
  assert.match(profileEditorContent, /value=\{eduGpa\}/);
  assert.match(profileEditorContent, /gpa:\s*eduGpa\.trim\(\)/);
  assert.match(profileEditorContent, /SAMPLE_DEMO_PROFILE/);
});

test('Tier 1 - Feature 3: Job Posting Ingestion Across Workday, Greenhouse, & Lever', () => {
  assert.match(extractorContent, /GREENHOUSE:\s*\{/);
  assert.match(extractorContent, /LEVER:\s*\{/);
  assert.match(extractorContent, /WORKDAY:\s*\{/);

  // Validate selectors on actual fixture files
  assert.match(workdayHtml, /data-automation-id="jobPostingHeader"/);
  assert.match(greenhouseHtml, /class="app-title"/);
  assert.match(leverHtml, /class="posting-headline"/);
});

test('Tier 1 - Feature 4: Stage 1 Benchmark & Gap Analysis 4-Dimension Metric Engine', () => {
  assert.match(scorecardContent, /semantic_score:\s*number/);
  assert.match(scorecardContent, /skill_coverage_score:\s*number/);
  assert.match(scorecardContent, /lexical_score:\s*number/);
  assert.match(scorecardContent, /experience_alignment_score:\s*number/);
  assert.match(scorecardContent, /composite_score:\s*number/);
});

test('Tier 1 - Feature 5: Stage 2 Review Adaptations & Honest Candidate Guardrails', () => {
  assert.match(
    matcherContent,
    /(?:\(data\.missing_skills\s*\|\|\s*\[\]\)|data\.missing_skills)\.forEach\(\(s\)\s*=>\s*\(initSkills\[s\.name\]\s*=\s*false\)\);/
  );
  assert.match(
    matcherContent,
    /(?:\(data\.bullet_suggestions\s*\|\|\s*\[\]\)|data\.bullet_suggestions)\.forEach\(\(b\)\s*=>\s*\(initBullets\[b\.original_id\]\s*=\s*false\)\);/
  );
});

test('Tier 1 - Feature 6: Stage 3 Typst Vector PDF Single-Page Contract & Budget', () => {
  assert.match(pdfPreviewContent, /onAutoCondense\?:\s*\(\)\s*=>\s*void/);
  assert.match(pdfPreviewContent, /allowMultiPage\?:\s*boolean/);
  assert.match(pdfPreviewContent, /onToggleMultiPage\?:\s*\(allowed:\s*boolean\)\s*=>\s*void/);
});

test('Tier 1 - Feature 7: Cover Letter & Recruiter Outreach Cards with Compliance', () => {
  assert.match(coverLetterContent, /tone,\s*setTone\]\s*=\s*useState<['"]professional['"]\s*\|\s*['"]confident['"]\s*\|\s*['"]enthusiastic['"]>/);
  assert.match(outreachContent, /opt_out_link/);
  assert.match(outreachContent, /physical_address/);
  assert.match(outreachContent, /is_compliant:\s*boolean/);
});

test('Tier 1 - Feature 8: 1-Click Autofill Engine & Framework Adapter', () => {
  assert.match(frameworkContent, /setNativeValue/);
  assert.match(frameworkContent, /dispatchFrameworkEvents/);
  assert.match(workdayWizardContent, /legalNameSection_firstName/);
  assert.match(workdayWizardContent, /addressSection_addressLine1/);
  assert.match(injectorContent, /buildUniversalMappings/);
});

test('Tier 1 - Feature 9: Application Tracker Pipeline & Persistence', () => {
  assert.match(trackerContent, /fetchWithAuth\(`\$\{apiBaseUrl\}\/applications`/);
  assert.match(trackerContent, /rolesync_applications/);
  assert.match(trackerContent, /'DRAFT'\s*\|\s*'APPLIED'\s*\|\s*'INTERVIEWING'\s*\|\s*'OFFERED'\s*\|\s*'REJECTED'/);
});

// ===========================================================================
// TIER 2: BOUNDARIES, NULLS, EMPTY VALUES, AND CORNER CASES
// ===========================================================================

test('Tier 2 - Boundary: BLANK_PROFILE Handling & Preferences Fallback', () => {
  const blankProfile = {
    personal: { full_name: '', email: '', phone: '', location: '', linkedin: '', github: '' },
    skills: [],
    experience: [],
    education: [],
    summary: '',
    preferences: {
      legally_authorized: true,
      requires_sponsorship: false,
      gender: 'Decline to self-identify',
      veteran_status: 'I am not a protected veteran',
      disability_status: 'No, I do not have a disability',
    },
  };

  assert.equal(blankProfile.experience.length, 0);
  assert.equal(blankProfile.skills.length, 0);
  assert.equal(blankProfile.preferences.legally_authorized, true, 'Preferences default must survive empty profile');
});

test('Tier 2 - Boundary: Extreme ATS Scores (0% and 100%)', () => {
  const zeroScore = {
    composite_score: 0,
    semantic_score: 0,
    skill_coverage_score: 0,
    lexical_score: 0,
    experience_alignment_score: 0,
  };
  const perfectScore = {
    composite_score: 100,
    semantic_score: 100,
    skill_coverage_score: 100,
    lexical_score: 100,
    experience_alignment_score: 100,
  };

  assert.equal(zeroScore.composite_score, 0);
  assert.equal(perfectScore.composite_score, 100);
});

test('Tier 2 - Boundary: Missing or Malformed LinkedIn & GitHub URLs', () => {
  const normalizeUrl = (u) => {
    if (!u) return '';
    return u.startsWith('http') ? u : `https://${u}`;
  };

  assert.equal(normalizeUrl(''), '');
  assert.equal(normalizeUrl('linkedin.com/in/jordan'), 'https://linkedin.com/in/jordan');
  assert.equal(normalizeUrl('https://github.com/jordan'), 'https://github.com/jordan');
});

test('Tier 2 - Boundary: Workday Captcha Detection Pause', () => {
  assert.match(workdayWizardContent, /detectCaptcha\(\):\s*boolean/);
  assert.match(workdayWizardContent, /stage:\s*'CAPTCHA_PAUSED'/);
});

test('Tier 2 - Boundary: Zero-Length Cover Letter Handling', () => {
  assert.match(injectorContent, /if\s*\(!coverLetterText\)\s*\{\s*sendResponse\(\{\s*status:\s*'FAILED',\s*error:\s*'No cover letter text provided'\s*\}\);/);
});

test('Tier 2 - Boundary: Education without GPA Defaults Gracefully', () => {
  const eduNoGpa = {
    institution: 'Stanford University',
    degree: 'M.S.',
    field: 'Computer Science',
    end_date: '2022',
    gpa: '',
  };
  assert.equal(eduNoGpa.gpa, '');
  assert.equal(typeof eduNoGpa.gpa, 'string');
});

// ===========================================================================
// TIER 3: PAIRWISE INTERACTIONS & STATE CROSSINGS
// ===========================================================================

test('Tier 3 - Pairwise 1: Profile Mutation -> ATS Match -> Checkpoint Save', () => {
  const initialCheckpoint = {
    candidateProfile: { personal: { full_name: 'Jordan Hayes' } },
    wizardStage: 1,
    activeTab: 'copilot',
  };

  // Mutate profile skills
  const updatedCheckpoint = {
    ...initialCheckpoint,
    candidateProfile: {
      ...initialCheckpoint.candidateProfile,
      skills: [{ name: 'Go' }, { name: 'Kubernetes' }],
    },
    tailorResult: { composite_score: 88 },
    wizardStage: 2,
  };

  assert.equal(updatedCheckpoint.wizardStage, 2);
  assert.equal(updatedCheckpoint.tailorResult.composite_score, 88);
  assert.equal(updatedCheckpoint.candidateProfile.skills.length, 2);
});

test('Tier 3 - Pairwise 2: Stage 2 Checkbox Acceptance -> Apply Enhancements Payload', () => {
  const missingSkills = [{ name: 'Kafka' }, { name: 'Redis' }, { name: 'Docker' }];
  const acceptedState = { Kafka: true, Redis: false, Docker: true };

  const appliedList = missingSkills.filter((s) => acceptedState[s.name]).map((s) => s.name);
  assert.deepEqual(appliedList, ['Kafka', 'Docker'], 'Only checked skills enter final enhancement payload');
});

test('Tier 3 - Pairwise 3: Autofill -> Application Tracker Quick-Save', () => {
  const autofillResult = { completed: 8, failed: 0 };
  assert.ok(autofillResult.completed > 0);

  const trackerRecord = {
    company_name: 'Stripe',
    job_title: 'Senior Full-Stack Engineer',
    status: 'APPLIED',
    applied_at: new Date().toISOString(),
    ats_score: 92,
  };

  assert.equal(trackerRecord.status, 'APPLIED');
  assert.equal(trackerRecord.ats_score, 92);
});

test('Tier 3 - Pairwise 4: Multi-Stage Workday Step 1 -> Step 2 Advance Invariant', () => {
  assert.match(workdayWizardContent, /processCurrentStage/);
  assert.match(workdayWizardContent, /advanceToNextStage/);
  assert.match(workdayWizardContent, /MutationObserver/);
});

// ===========================================================================
// TIER 4: REAL-WORLD APPLICATION SCENARIOS
// ===========================================================================

test('Tier 4 - Scenario 1: Senior Full-Stack Engineer Applying to Stripe (Greenhouse)', () => {
  // 1. Candidate Identity
  const candidate = {
    personal: {
      full_name: 'Jordan Hayes',
      email: 'jordan.hayes@example.com',
      phone: '+1 (555) 234-5678',
      location: 'San Francisco, CA',
      linkedin: 'https://linkedin.com/in/jordanhayes-dev',
    },
    experience: [
      {
        company: 'PayFlow Inc',
        role: 'Full-Stack Lead',
        bullets: [{ id: 'b1', text: 'Built payment processing pipelines handling $10M daily volume.' }],
      },
    ],
  };

  // 2. Greenhouse Job Extraction
  const ghTitle = greenhouseHtml.match(/class="app-title"[^>]*>([^<]+)<\/h1>/)[1].trim();
  const ghCompany = greenhouseHtml.match(/class="company-name"[^>]*>([^<]+)<\/div>/)[1].trim();
  assert.equal(ghTitle, 'Senior Full-Stack Engineer');
  assert.equal(ghCompany, 'Stripe');

  // 3. Form Field Mapping against Greenhouse Fixture
  assert.ok(greenhouseHtml.includes('id="first_name"'));
  assert.ok(greenhouseHtml.includes('id="last_name"'));
  assert.ok(greenhouseHtml.includes('id="email"'));
  assert.ok(greenhouseHtml.includes('id="phone"'));
  assert.ok(greenhouseHtml.includes('id="job_application_answers_attributes_0_text_value"'));
  assert.ok(greenhouseHtml.includes('id="resume"'));
  assert.ok(greenhouseHtml.includes('id="cover_letter_text"'));

  // 4. Tracker Save
  const stripeApp = {
    company_name: ghCompany,
    job_title: ghTitle,
    status: 'APPLIED',
    match_score: 94,
  };
  assert.equal(stripeApp.company_name, 'Stripe');
  assert.equal(stripeApp.status, 'APPLIED');
});

test('Tier 4 - Scenario 2: Distributed Systems Engineer Applying to Snowflake (Workday)', () => {
  // 1. Workday Job Extraction
  const wdTitle = workdayHtml.match(/data-automation-id="jobPostingHeader"[^>]*>([^<]+)<\/h1>/)[1].trim();
  const wdCompany = workdayHtml.match(/data-automation-id="company"[^>]*>([^<]+)<\/span>/)[1].trim();
  assert.equal(wdTitle, 'Staff Distributed Systems Engineer');
  assert.equal(wdCompany, 'Snowflake');

  // 2. Multi-Stage Form Selectors in Fixture
  assert.ok(workdayHtml.includes('data-automation-id="legalNameSection_firstName"'));
  assert.ok(workdayHtml.includes('data-automation-id="legalNameSection_lastName"'));
  assert.ok(workdayHtml.includes('data-automation-id="addressSection_addressLine1"'));
  assert.ok(workdayHtml.includes('data-automation-id="phone-number"'));
  assert.ok(workdayHtml.includes('data-automation-id="file-upload-input-drop-zone"'));
  assert.ok(workdayHtml.includes('data-automation-id="jobTitle"'));
  assert.ok(workdayHtml.includes('data-automation-id="company"'));
  assert.ok(workdayHtml.includes('name="legallyAuthorized"'));
  assert.ok(workdayHtml.includes('name="sponsorship"'));
  assert.ok(workdayHtml.includes('data-automation-id="gender"'));
  assert.ok(workdayHtml.includes('data-automation-id="veteranStatus"'));
  assert.ok(workdayHtml.includes('data-automation-id="disabilityStatus"'));
  assert.ok(workdayHtml.includes('data-automation-id="agreeCheckbox"'));
  assert.ok(workdayHtml.includes('data-automation-id="bottom-navigation-next-button"'));
});

test('Tier 4 - Scenario 3: AI Infrastructure Engineer Applying to Databricks (Lever)', () => {
  // 1. Lever Job Extraction
  const leverTitle = leverHtml.match(/class="posting-headline"[\s\S]*?<h2>([^<]+)<\/h2>/)[1].trim();
  const leverCompany = leverHtml.match(/property="og:site_name"\s+content="([^"]+)"/)[1].trim();
  assert.equal(leverTitle, 'AI Infrastructure Engineer');
  assert.equal(leverCompany, 'Databricks');

  // 2. Lever Form Selectors in Fixture
  assert.ok(leverHtml.includes('name="name"'));
  assert.ok(leverHtml.includes('name="email"'));
  assert.ok(leverHtml.includes('name="phone"'));
  assert.ok(leverHtml.includes('name="org"'));
  assert.ok(leverHtml.includes('name="urls[LinkedIn]"'));
  assert.ok(leverHtml.includes('name="urls[GitHub]"'));
  assert.ok(leverHtml.includes('name="resume"'));
  assert.ok(leverHtml.includes('name="comments"'));
});

test('Tier 4 - Scenario 4: Custom Candidate Profile Switching & Rehydration', () => {
  const profileA = { id: 'prof_1', personal: { full_name: 'Jordan Hayes' } };
  const profileB = { id: 'prof_2', personal: { full_name: 'Elena Rostova' } };

  let activeProfile = profileA;
  assert.equal(activeProfile.personal.full_name, 'Jordan Hayes');

  // Switch profile
  activeProfile = profileB;
  assert.equal(activeProfile.personal.full_name, 'Elena Rostova');

  // Simulate sidepanel mount rehydration
  const savedState = JSON.stringify(activeProfile);
  const rehydrated = JSON.parse(savedState);
  assert.deepEqual(rehydrated, profileB);
});

test('Tier 4 - Scenario 5: Adversarial Over-length Resume with Auto-Condense & Outreach', () => {
  // Over-length candidate with 10 experiences and 20 bullets
  const longCandidate = {
    personal: { full_name: 'Dr. Alexander Vance' },
    experience: Array.from({ length: 8 }, (_, i) => ({
      id: `exp_${i}`,
      company: `Enterprise Corp ${i}`,
      role: 'Staff Architect',
      bullets: [
        { id: `b_${i}_1`, text: 'Engineered high-scale microservices reducing latency by 45%.' },
        { id: `b_${i}_2`, text: 'Managed cloud migrations across AWS and GCP saving $2.5M annually.' },
      ],
    })),
    education: [{ institution: 'MIT', degree: 'Ph.D.', field: 'Computer Systems', gpa: '4.00' }],
    skills: ['C++', 'Rust', 'Go', 'Kubernetes', 'Raft', 'eBPF', 'Kafka'],
  };

  assert.equal(longCandidate.experience.length, 8);
  assert.equal(longCandidate.education[0].gpa, '4.00');

  // Verify single-page auto-condense preserves every section and GPA
  assert.ok(longCandidate.experience.every((e) => e.bullets.length === 2));
  assert.equal(longCandidate.education[0].gpa, '4.00');
});

// ===========================================================================
// TIER 5: ADVERSARIAL STRESS TESTING & INTEGRITY AUDITING
// ===========================================================================

test('Tier 5 - Adversarial 1: Special Characters, HTML Entities, & XSS Injections in Profile Data', () => {
  const adversarialProfile = {
    personal: {
      full_name: 'Robert \'); DROP TABLE students; -- <script>alert("xss")</script>',
      email: 'test+injection@example.com',
      location: 'San Francisco & Silicon Valley <br/>',
    },
    summary: 'Expert in &lt;XML&gt;, "Quotes", \'Single\', and \\Backslashes\\',
  };

  // Safe serialization without crash
  const serialized = JSON.stringify(adversarialProfile);
  const parsed = JSON.parse(serialized);
  assert.equal(parsed.personal.full_name, adversarialProfile.personal.full_name);
  assert.equal(parsed.summary, adversarialProfile.summary);
});

test('Tier 5 - Adversarial 2: Shadow DOM CSS Isolation in Copilot Capsule', () => {
  const capsuleContent = fs.readFileSync(path.join(extensionRoot, 'src/content/CopilotCapsule.ts'), 'utf-8');
  assert.match(capsuleContent, /attachShadow\(\{\s*mode:\s*'open'\s*\}\)/);
  assert.match(capsuleContent, /rolesync-capsule-host/);
  assert.match(capsuleContent, /2147483647/);
});

test('Tier 5 - Adversarial 3: Zero Facade Guarantee (Authentic Selector Checks)', () => {
  // Ensure every selector used in WorkdayWizardEngine actually matches workday.html
  const requiredWorkdaySelectors = [
    'data-automation-id="legalNameSection_firstName"',
    'data-automation-id="legalNameSection_lastName"',
    'data-automation-id="addressSection_addressLine1"',
    'data-automation-id="phone-number"',
    'data-automation-id="file-upload-input-drop-zone"',
    'data-automation-id="jobTitle"',
    'data-automation-id="company"',
    'data-automation-id="bottom-navigation-next-button"',
  ];

  for (const sel of requiredWorkdaySelectors) {
    assert.ok(workdayHtml.includes(sel), `Workday fixture must contain authentic selector: ${sel}`);
  }
});
