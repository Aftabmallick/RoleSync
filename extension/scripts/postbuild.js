import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionRoot = path.resolve(__dirname, '..');
const distDir = path.resolve(extensionRoot, 'dist');

// 1. Ensure dist/sidepanel/index.html exists and has proper relative paths (../assets/)
const srcSidepanelDir = path.resolve(distDir, 'src', 'sidepanel');
const targetSidepanelDir = path.resolve(distDir, 'sidepanel');

if (fs.existsSync(srcSidepanelDir)) {
  if (!fs.existsSync(targetSidepanelDir)) {
    fs.mkdirSync(targetSidepanelDir, { recursive: true });
  }

  const rawHtml = fs.readFileSync(path.resolve(srcSidepanelDir, 'index.html'), 'utf-8');
  // In dist/sidepanel/index.html, assets are 1 directory up (../assets/), not 2 (../../assets/)
  const adjustedHtml = rawHtml.replace(/\.\.\/\.\.\/assets\//g, '../assets/');

  fs.writeFileSync(path.resolve(targetSidepanelDir, 'index.html'), adjustedHtml, 'utf-8');
  console.log('[RoleSync Build] Generated dist/sidepanel/index.html with relative asset paths (../assets/)');
}

// 2. Mirror dist/assets to extensionRoot/assets so absolute /assets/ requests resolve under extension root
const distAssetsDir = path.resolve(distDir, 'assets');
const rootAssetsDir = path.resolve(extensionRoot, 'assets');

if (fs.existsSync(distAssetsDir)) {
  if (!fs.existsSync(rootAssetsDir)) {
    fs.mkdirSync(rootAssetsDir, { recursive: true });
  }
  for (const file of fs.readdirSync(distAssetsDir)) {
    fs.copyFileSync(path.resolve(distAssetsDir, file), path.resolve(rootAssetsDir, file));
  }
  console.log('[RoleSync Build] Mirrored assets to extension/assets/');
}

// 3. Create placeholder logo.png and isolated.css to satisfy web_accessible_resources
const base64Png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
const logoBuffer = Buffer.from(base64Png, 'base64');
fs.writeFileSync(path.resolve(rootAssetsDir, 'logo.png'), logoBuffer);
if (fs.existsSync(distAssetsDir)) {
  fs.writeFileSync(path.resolve(distAssetsDir, 'logo.png'), logoBuffer);
}

const distContentDir = path.resolve(distDir, 'content');
if (!fs.existsSync(distContentDir)) {
  fs.mkdirSync(distContentDir, { recursive: true });
}
fs.writeFileSync(path.resolve(distContentDir, 'isolated.css'), '/* RoleSync isolated styles */\n', 'utf-8');

// 4. Generate dist/manifest.json so loading either extension/ or extension/dist/ works
const rootManifestPath = path.resolve(extensionRoot, 'manifest.json');
if (fs.existsSync(rootManifestPath)) {
  const rootManifest = JSON.parse(fs.readFileSync(rootManifestPath, 'utf-8'));
  const distManifest = JSON.parse(JSON.stringify(rootManifest));

  // Strip 'dist/' prefixes for standalone dist/ loading
  if (distManifest.background?.service_worker?.startsWith('dist/')) {
    distManifest.background.service_worker = distManifest.background.service_worker.replace(/^dist\//, '');
  }
  if (distManifest.content_scripts) {
    distManifest.content_scripts.forEach((cs) => {
      cs.js = cs.js.map((f) => f.replace(/^dist\//, ''));
    });
  }
  if (distManifest.side_panel?.default_path?.startsWith('dist/')) {
    distManifest.side_panel.default_path = distManifest.side_panel.default_path.replace(/^dist\//, '');
  }

  fs.writeFileSync(
    path.resolve(distDir, 'manifest.json'),
    JSON.stringify(distManifest, null, 2)
  );
  console.log('[RoleSync Build] Created dist/manifest.json for standalone dist/ loading');
}
