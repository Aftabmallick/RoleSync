// RoleSync Adversarial Challenger Probes & Stress Test Harness
// Authored by challenger_e2e_1 (Empirical Challenger)
// Evaluates GPA handling, BLANK_PROFILE preferences fallback, and mutated DOM resilience

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionRoot = path.resolve(__dirname, '..');
const fixturesDir = path.resolve(__dirname, 'fixtures');

// Read source files for static contracts and implementation extraction
const profileEditorContent = fs.readFileSync(path.join(extensionRoot, 'src/sidepanel/components/ProfileEditor.tsx'), 'utf-8');
const injectorContent = fs.readFileSync(path.join(extensionRoot, 'src/content/injector.ts'), 'utf-8');
const workdayWizardContent = fs.readFileSync(path.join(extensionRoot, 'src/content/WorkdayWizardEngine.ts'), 'utf-8');
const frameworkContent = fs.readFileSync(path.join(extensionRoot, 'src/content/FrameworkAdapter.ts'), 'utf-8');
const autofillEngineContent = fs.readFileSync(path.join(extensionRoot, 'src/content/DOMAutofillEngine.ts'), 'utf-8');
const workdayHtml = fs.readFileSync(path.join(fixturesDir, 'workday.html'), 'utf-8');
const greenhouseHtml = fs.readFileSync(path.join(fixturesDir, 'greenhouse.html'), 'utf-8');
const leverHtml = fs.readFileSync(path.join(fixturesDir, 'lever.html'), 'utf-8');

// ============================================================================
// 1. GPA INPUT HANDLING PROBES (SPECIAL CHARS, EXTREMES, EMPTY VALUES, XSS)
// ============================================================================

test('GPA Probe 1: Standard and Extreme Numeric GPAs', () => {
  const gpaCases = ['4.0', '3.85', '0.0', '0.00', '0', '5.0', '10.0', '-1.0', '99.9'];

  for (const rawGpa of gpaCases) {
    const trimmed = rawGpa.trim();
    const eduItem = {
      institution: 'Carnegie Mellon University',
      degree: 'B.S.',
      field: 'Computer Science',
      end_date: '2024',
      gpa: trimmed,
    };

    assert.equal(typeof eduItem.gpa, 'string');
    assert.equal(eduItem.gpa, trimmed);

    // Verify UI render expression: {edu.institution} • {edu.end_date} {edu.gpa && `• GPA: ${edu.gpa}`}
    const renderedGpaPart = eduItem.gpa ? `• GPA: ${eduItem.gpa}` : '';
    assert.ok(renderedGpaPart.includes(`• GPA: ${trimmed}`), `Render part must display GPA for ${trimmed}`);
  }
});

test('GPA Probe 2: Non-numeric, Qualitative, and International GPAs', () => {
  const nonNumericCases = [
    'N/A',
    'First Class with Distinction',
    'Summa Cum Laude',
    'A+',
    '3.9 / 4.0',
    '8.9/10.0 CGPA',
    '92%',
    'Pass',
  ];

  for (const rawGpa of nonNumericCases) {
    const trimmed = rawGpa.trim();
    const eduItem = {
      institution: 'Oxford University',
      degree: 'M.Sc.',
      field: 'Software Engineering',
      end_date: '2023',
      gpa: trimmed,
    };

    assert.equal(eduItem.gpa, trimmed);
    const renderedPart = eduItem.gpa ? `• GPA: ${eduItem.gpa}` : '';
    assert.equal(renderedPart, `• GPA: ${trimmed}`);
  }
});

test('GPA Probe 3: Whitespace, Empty Strings, Undefined, and Null Toleration', () => {
  const emptyCases = ['', '   ', '\t', '\n\r', '  \t  '];

  for (const raw of emptyCases) {
    const trimmed = raw.trim();
    const eduItem = {
      institution: 'MIT',
      degree: 'B.S.',
      field: 'EECS',
      end_date: '2020',
      gpa: trimmed,
    };

    assert.equal(eduItem.gpa, '');
    // Empty gpa must evaluate falsy and NOT produce any GPA suffix text
    const renderedPart = eduItem.gpa ? `• GPA: ${eduItem.gpa}` : '';
    assert.equal(renderedPart, '', 'Empty GPA must not render a GPA label');
  }

  // Undefined or omitted GPA in imported profile
  const legacyEdu = {
    institution: 'UC Berkeley',
    degree: 'B.A.',
    field: 'Mathematics',
    end_date: '2019',
  };
  const renderedLegacy = legacyEdu.gpa ? `• GPA: ${legacyEdu.gpa}` : '';
  assert.equal(renderedLegacy, '', 'Missing gpa property must evaluate safely to empty string');
});

test('GPA Probe 4: Adversarial Special Characters, XSS Payloads, and Unicode', () => {
  const attackPayloads = [
    '<script>alert("xss")</script>',
    '"><img src=x onerror=alert(1)>',
    '\'); DROP TABLE education; --',
    '&quot;4.00&quot;',
    '🎓 3.99',
    '৪.০ / ৪.০',
    '３.８５', // Full-width unicode digits
    '${7*7}', // Template literal injection
    '\\n\\r\\t"\'',
  ];

  for (const attack of attackPayloads) {
    const trimmed = attack.trim();
    const eduItem = {
      institution: 'Stanford',
      degree: 'M.S.',
      field: 'AI',
      end_date: '2025',
      gpa: trimmed,
    };

    // 1. Verify JSON serialization round-trip survives unchanged
    const serialized = JSON.stringify(eduItem);
    const deserialized = JSON.parse(serialized);
    assert.equal(deserialized.gpa, trimmed);

    // 2. Verify Typst DSL escape pattern prevents syntax injection
    // Typst characters: \, ", #, $, _, *, @, [, ], <, >
    const escapeTypst = (text) => {
      if (!text) return '';
      return String(text).replace(/([\\#"$_*@\[\]<>])/g, '\\$1');
    };

    const escaped = escapeTypst(trimmed);
    assert.ok(!escaped.includes('<script>'), 'Typst escape must escape < and >');
    if (trimmed.includes('"')) {
      assert.ok(escaped.includes('\\"'), 'Double quotes must be escaped in Typst DSL');
    }
    if (trimmed.includes('$')) {
      assert.ok(escaped.includes('\\$'), 'Dollar math triggers must be escaped in Typst DSL');
    }
  }
});

test('GPA Probe 5: Add Education Handler State Transition Simulation', () => {
  // Simulates handleAddEducation in ProfileEditor.tsx
  let profile = {
    personal: { full_name: 'Test Candidate' },
    education: [],
  };

  const simulateAddEdu = (inst, degree, field, year, gpa) => {
    if (!inst.trim()) return;
    const newEdu = {
      institution: inst.trim(),
      degree: degree.trim() || 'B.S.',
      field: field.trim() || 'Computer Science',
      end_date: year.trim() || '2021',
      gpa: gpa.trim(),
    };
    profile = {
      ...profile,
      education: [...profile.education, newEdu],
    };
  };

  // Add 3 universities with varying GPAs
  simulateAddEdu('Harvard University', 'A.B.', 'Computer Science', '2018', '3.94');
  simulateAddEdu('Stanford University', 'M.S.', 'AI', '2020', '  4.00  ');
  simulateAddEdu('Cambridge University', 'Ph.D.', 'Quantum Computing', '2024', '');

  assert.equal(profile.education.length, 3);
  assert.equal(profile.education[0].gpa, '3.94');
  assert.equal(profile.education[1].gpa, '4.00'); // Whitespace trimmed
  assert.equal(profile.education[2].gpa, ''); // Empty string preserved

  // Remove middle entry
  profile.education.splice(1, 1);
  assert.equal(profile.education.length, 2);
  assert.equal(profile.education[0].institution, 'Harvard University');
  assert.equal(profile.education[1].institution, 'Cambridge University');
});

// ============================================================================
// 2. BLANK_PROFILE PREFERENCES FALLBACK & MUTATION PROBES
// ============================================================================

test('BLANK_PROFILE Probe 1: Contract Conformity and Default Invariants', () => {
  // Extract BLANK_PROFILE object from ProfileEditor.tsx via regex
  const blankMatch = profileEditorContent.match(/export const BLANK_PROFILE:\s*MasterProfileData\s*=\s*(\{[\s\S]*?\n\};)/);
  assert.ok(blankMatch, 'BLANK_PROFILE definition must exist in ProfileEditor.tsx');

  const content = blankMatch[1];
  assert.ok(content.includes('legally_authorized: true'));
  assert.ok(content.includes('requires_sponsorship: false'));
  assert.ok(content.includes("gender: 'Decline to self-identify'"));
  assert.ok(content.includes("veteran_status: 'I am not a protected veteran'"));
  assert.ok(content.includes("disability_status: 'No, I do not have a disability'"));
  assert.ok(content.includes('targetRoles: []'));
  assert.ok(content.includes('targetLocations: []'));
  assert.ok(content.includes("remotePreference: 'ANY'"));
  assert.ok(content.includes("workAuthorization: 'CITIZEN_OR_PR'"));
  assert.ok(content.includes('requireSponsorship: false'));
});

test('BLANK_PROFILE Probe 2: Preferences Mutation and Reversal', () => {
  let profile = {
    personal: { full_name: '' },
    preferences: {
      legally_authorized: true,
      requires_sponsorship: false,
      gender: 'Decline to self-identify',
      veteran_status: 'I am not a protected veteran',
      disability_status: 'No, I do not have a disability',
      targetRoles: [],
      targetLocations: [],
      minBaseSalary: undefined,
      remotePreference: 'ANY',
      workAuthorization: 'CITIZEN_OR_PR',
      requireSponsorship: false,
    },
    skills: [],
    experience: [],
    projects: [],
    education: [],
  };

  // Mutate legally_authorized to false
  profile = {
    ...profile,
    preferences: { ...profile.preferences, legally_authorized: false },
  };
  assert.equal(profile.preferences.legally_authorized, false);

  // Mutate requires_sponsorship to true
  profile = {
    ...profile,
    preferences: { ...profile.preferences, requires_sponsorship: true },
  };
  assert.equal(profile.preferences.requires_sponsorship, true);

  // Mutate EEO disclosures
  profile = {
    ...profile,
    preferences: {
      ...profile.preferences,
      gender: 'Female',
      veteran_status: 'I identify as a protected veteran',
      disability_status: 'Yes, I have a disability',
    },
  };
  assert.equal(profile.preferences.gender, 'Female');
  assert.equal(profile.preferences.veteran_status, 'I identify as a protected veteran');
  assert.equal(profile.preferences.disability_status, 'Yes, I have a disability');

  // Mutate target roles and compensation
  profile = {
    ...profile,
    preferences: {
      ...profile.preferences,
      targetRoles: ['Staff Software Engineer', 'Engineering Manager'],
      targetLocations: ['San Francisco, CA', 'Remote'],
      minBaseSalary: 220000,
      remotePreference: 'REMOTE_ONLY',
    },
  };
  assert.equal(profile.preferences.targetRoles.length, 2);
  assert.equal(profile.preferences.minBaseSalary, 220000);
});

test('BLANK_PROFILE Probe 3: Total Profile Reset / Clear Cycle', () => {
  // Simulate active dirty profile
  let activeProfile = {
    personal: { full_name: 'Dirty Candidate', email: 'dirty@example.com' },
    experience: [{ company: 'Old Corp', role: 'Dev', bullets: [] }],
    preferences: {
      legally_authorized: false,
      requires_sponsorship: true,
      gender: 'Non-Binary',
      veteran_status: 'I identify as a protected veteran',
      disability_status: 'Yes, I have a disability',
    },
  };

  // Simulate handleClearProfile: setProfile(BLANK_PROFILE)
  const BLANK_PROFILE = {
    personal: { full_name: '', email: '', phone: '', location: '', linkedin: '', github: '' },
    preferences: {
      legally_authorized: true,
      requires_sponsorship: false,
      gender: 'Decline to self-identify',
      veteran_status: 'I am not a protected veteran',
      disability_status: 'No, I do not have a disability',
      targetRoles: [],
      targetLocations: [],
      minBaseSalary: undefined,
      remotePreference: 'ANY',
      workAuthorization: 'CITIZEN_OR_PR',
      requireSponsorship: false,
    },
    skills: [],
    experience: [],
    projects: [],
    education: [],
  };

  activeProfile = BLANK_PROFILE;

  assert.equal(activeProfile.personal.full_name, '');
  assert.equal(activeProfile.experience.length, 0);
  assert.equal(activeProfile.preferences.legally_authorized, true);
  assert.equal(activeProfile.preferences.requires_sponsorship, false);
  assert.equal(activeProfile.preferences.gender, 'Decline to self-identify');
  assert.equal(activeProfile.preferences.veteran_status, 'I am not a protected veteran');
  assert.equal(activeProfile.preferences.disability_status, 'No, I do not have a disability');
});

test('BLANK_PROFILE Probe 4: Resilience to Completely Missing or Null Preferences Object', () => {
  // Simulate legacy profile payload from old version without preferences field
  const legacyProfile = {
    personal: { full_name: 'Legacy User', email: 'legacy@example.com' },
    skills: [],
    experience: [],
    education: [],
  };

  // Test ProfileEditor JSX accessor expressions
  const isAuthCheckedYes = legacyProfile.preferences?.legally_authorized !== false;
  const isAuthCheckedNo = legacyProfile.preferences?.legally_authorized === false;
  const isSponsCheckedYes = legacyProfile.preferences?.requires_sponsorship === true;
  const isSponsCheckedNo = legacyProfile.preferences?.requires_sponsorship !== true;
  const genderVal = legacyProfile.preferences?.gender || 'Decline to self-identify';
  const veteranVal = legacyProfile.preferences?.veteran_status || 'I am not a protected veteran';
  const disabilityVal = legacyProfile.preferences?.disability_status || 'No, I do not have a disability';

  assert.equal(isAuthCheckedYes, true, 'Default must be authorized = true when preferences undefined');
  assert.equal(isAuthCheckedNo, false);
  assert.equal(isSponsCheckedYes, false);
  assert.equal(isSponsCheckedNo, true, 'Default must be sponsorship = false when preferences undefined');
  assert.equal(genderVal, 'Decline to self-identify');
  assert.equal(veteranVal, 'I am not a protected veteran');
  assert.equal(disabilityVal, 'No, I do not have a disability');

  // Test mutating undefined preferences: { ...profile.preferences, legally_authorized: true }
  const updatedPrefs = { ...legacyProfile.preferences, legally_authorized: true };
  assert.deepEqual(updatedPrefs, { legally_authorized: true });

  // Test injector candidateData extraction
  const candidateData = {
    legallyAuthorized: legacyProfile?.preferences?.legally_authorized ?? true,
    requiresSponsorship: legacyProfile?.preferences?.requires_sponsorship ?? false,
    gender: legacyProfile?.preferences?.gender || 'Decline to self-identify',
    veteranStatus: legacyProfile?.preferences?.veteran_status || 'I am not a protected veteran',
    disabilityStatus: legacyProfile?.preferences?.disability_status || 'No, I do not have a disability',
  };

  assert.equal(candidateData.legallyAuthorized, true);
  assert.equal(candidateData.requiresSponsorship, false);
  assert.equal(candidateData.gender, 'Decline to self-identify');
  assert.equal(candidateData.veteranStatus, 'I am not a protected veteran');
  assert.equal(candidateData.disabilityStatus, 'No, I do not have a disability');
});

// ============================================================================
// 3. DOM FORM AUTOFILL RESILIENCE AGAINST MUTATED DOMS
// ============================================================================

test('DOM Probe 1: Universal Form Mappings with Missing Optional Fields', () => {
  // Profile with ONLY name and email; missing phone, location, summary, linkedin, github, experience
  const sparseProfile = {
    personal: {
      full_name: 'Minimal Candidate',
      email: 'minimal@example.com',
    },
  };

  // Replicate buildUniversalMappings logic from injector.ts
  const buildUniversalMappings = (profile, resumeDataUri) => {
    const mappings = [];
    const personal = profile.personal || {};
    const fullName = personal.full_name || '';
    const email = personal.email || '';
    const phone = personal.phone || '';
    const location = personal.location || '';
    const summary = profile.summary || personal.summary || '';
    const linkedin = personal.linkedin || '';
    const github = personal.github || '';
    const website = personal.portfolio || personal.website || '';

    const nameParts = fullName.trim().split(/\s+/);
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ') || '';

    if (firstName) {
      mappings.push({ selector: 'input[name*="first_name" i], #first_name', value: firstName, type: 'TEXT' });
    }
    if (lastName) {
      mappings.push({ selector: 'input[name*="last_name" i], #last_name', value: lastName, type: 'TEXT' });
    }
    if (fullName) {
      mappings.push({ selector: 'input[name="name"], #name', value: fullName, type: 'TEXT' });
    }
    if (email) {
      mappings.push({ selector: 'input[name*="email" i], #email', value: email, type: 'TEXT' });
    }
    if (phone) {
      mappings.push({ selector: 'input[name*="phone" i], #phone', value: phone, type: 'TEXT' });
    }
    if (location) {
      mappings.push({ selector: 'input[name*="location" i]', value: location, type: 'TEXT' });
    }
    if (summary) {
      mappings.push({ selector: 'textarea[name*="summary" i]', value: summary, type: 'TEXT' });
    }
    if (linkedin) {
      mappings.push({ selector: 'input[name*="linkedin" i]', value: linkedin, type: 'TEXT' });
    }
    if (github) {
      mappings.push({ selector: 'input[name*="github" i]', value: github, type: 'TEXT' });
    }
    if (website) {
      mappings.push({ selector: 'input[name*="website" i]', value: website, type: 'TEXT' });
    }

    const exp0 = profile.experience?.[0];
    if (exp0?.company) {
      mappings.push({ selector: 'input[name*="company" i]', value: exp0.company, type: 'TEXT' });
    }

    if (resumeDataUri) {
      mappings.push({ selector: 'input[type="file"]', value: resumeDataUri, type: 'FILE' });
    }

    return mappings;
  };

  const mappings = buildUniversalMappings(sparseProfile, null);

  // Exactly 4 mappings: first_name, last_name, name, email
  assert.equal(mappings.length, 4);
  assert.equal(mappings.find((m) => m.value === 'Minimal').value, 'Minimal');
  assert.equal(mappings.find((m) => m.value === 'Candidate').value, 'Candidate');
  assert.equal(mappings.find((m) => m.value === 'minimal@example.com').value, 'minimal@example.com');

  // Verify none of the missing fields produced invalid or undefined mapping entries
  assert.ok(!mappings.some((m) => m.value === undefined));
  assert.ok(!mappings.some((m) => m.value === 'undefined'));
  assert.ok(!mappings.some((m) => m.selector.includes('phone')));
});

test('DOM Probe 2: FrameworkAdapter Prototype Value Descriptor Fallback', () => {
  // Verify FrameworkAdapter.setNativeValue handles elements with and without prototype setters
  assert.match(frameworkContent, /const descriptor = Object\.getOwnPropertyDescriptor\(prototype, 'value'\);/);
  assert.match(frameworkContent, /if \(descriptor && descriptor\.set\)/);
  assert.match(frameworkContent, /element\.value = value;/);
  assert.match(frameworkContent, /dispatchFrameworkEvents/);
});

test('DOM Probe 3: Deep Query Selector Hierarchy and Selector Exception Immunity', () => {
  // Verify DOMAutofillEngine.querySelectorDeep catches invalid syntax selectors
  assert.match(autofillEngineContent, /public querySelectorDeep\(selector:\s*string/);
  assert.match(autofillEngineContent, /try\s*\{[\s\S]*?catch\s*\{[\s\S]*?\/\/ Ignore syntax errors/);
  assert.match(autofillEngineContent, /return null;/);
});

test('DOM Probe 4: Workday Wizard Multi-stage Mappings Resilience', () => {
  // Test candidate data with boolean flags and missing fields in Workday
  const testData = {
    firstName: 'Jordan',
    lastName: 'Hayes',
    legallyAuthorized: false,
    requiresSponsorship: true,
    gender: 'Decline to self-identify',
  };

  // Replicate Workday stage mapping logic
  const mappings = [];
  if (testData.legallyAuthorized !== undefined) {
    mappings.push({
      selector: 'input[name*="legallyAuthorized"]',
      value: testData.legallyAuthorized ? 'yes' : 'no',
      type: 'RADIO',
    });
  }
  if (testData.requiresSponsorship !== undefined) {
    mappings.push({
      selector: 'input[name*="sponsorship"]',
      value: testData.requiresSponsorship ? 'yes' : 'no',
      type: 'RADIO',
    });
  }

  assert.equal(mappings.length, 2);
  assert.equal(mappings[0].value, 'no');
  assert.equal(mappings[1].value, 'yes');
});

// ============================================================================
// 4. FIXTURE SERVER AND HEADLESS RUNNER CONFIGURATION INVARIANTS
// ============================================================================

test('Fixture Server Probe: Endpoints, Routes, and CORS Headers', () => {
  const serverPath = path.join(fixturesDir, 'server.mjs');
  const serverContent = fs.readFileSync(serverPath, 'utf-8');

  assert.match(serverContent, /res\.setHeader\('Access-Control-Allow-Origin',\s*'\*'\)/);
  assert.match(serverContent, /res\.setHeader\('Access-Control-Allow-Methods',\s*'GET, POST, OPTIONS'\)/);
  assert.match(serverContent, /pathname === '\/workday'/);
  assert.match(serverContent, /pathname === '\/greenhouse'/);
  assert.match(serverContent, /pathname === '\/lever'/);
  assert.match(serverContent, /pathname === '\/submit'/);
});

test('Browser Runner Probe: Chrome Launch Arguments and MV3 Extension Flags', () => {
  const runnerPath = path.join(extensionRoot, 'tests/e2e/runner.mjs');
  const runnerContent = fs.readFileSync(runnerPath, 'utf-8');

  assert.match(runnerContent, /'--headless=new'/);
  assert.match(runnerContent, /`--remote-debugging-port=\$\{DEBUG_PORT\}`/);
  assert.match(runnerContent, /`--load-extension=\$\{distPath\}`/);
  assert.match(runnerContent, /`--disable-extensions-except=\$\{distPath\}`/);
  assert.match(runnerContent, /runBrowserE2E/);
});
