// Lightweight HTTP Fixture Server for RoleSync E2E Form Testing
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.pdf': 'application/pdf',
};

export function createFixtureApp() {
  return (req, res) => {
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    let pathname = parsedUrl.pathname;

    // Normalization
    if (pathname === '/' || pathname === '') {
      pathname = '/index.html';
    }

    // Direct aliases for fixtures
    if (pathname === '/workday' || pathname === '/workday.html') pathname = '/workday.html';
    else if (pathname === '/greenhouse' || pathname === '/greenhouse.html') pathname = '/greenhouse.html';
    else if (pathname === '/lever' || pathname === '/lever.html') pathname = '/lever.html';
    else if (pathname.startsWith('/fixtures/')) pathname = pathname.replace(/^\/fixtures/, '');

    // Map to local file
    const filePath = path.join(__dirname, pathname.replace(/^\//, ''));

    // Handle form submit simulation
    if (req.method === 'POST' && (pathname === '/submit' || pathname.endsWith('/submit'))) {
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', () => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'SUCCESS', receivedBytes: body.length }));
      });
      return;
    }

    fs.stat(filePath, (err, stats) => {
      if (err || !stats.isFile()) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end(`404 Fixture Not Found: ${pathname}`);
        return;
      }

      const ext = path.extname(filePath).toLowerCase();
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';

      res.writeHead(200, { 'Content-Type': contentType });
      const readStream = fs.createReadStream(filePath);
      readStream.pipe(res);
    });
  };
}

export function startFixtureServer(port = 3000) {
  return new Promise((resolve, reject) => {
    const handler = createFixtureApp();
    const server = http.createServer(handler);

    server.listen(port, '0.0.0.0', () => {
      const address = server.address();
      const actualPort = typeof address === 'object' && address ? address.port : port;
      resolve({
        server,
        port: actualPort,
        url: `http://localhost:${actualPort}`,
        close: () => new Promise((done) => server.close(done)),
      });
    });

    server.on('error', reject);
  });
}

// Direct execution CLI
if (process.argv[1] === __filename) {
  const port = parseInt(process.env.PORT || '3000', 10);
  startFixtureServer(port).then(({ url }) => {
    console.log(`[RoleSync Fixture Server] Running at ${url}`);
    console.log(`  - Workday fixture:    ${url}/workday.html`);
    console.log(`  - Greenhouse fixture: ${url}/greenhouse.html`);
    console.log(`  - Lever fixture:      ${url}/lever.html`);
  }).catch((err) => {
    console.error('[RoleSync Fixture Server] Error:', err);
    process.exit(1);
  });
}
