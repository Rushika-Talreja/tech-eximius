import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { mockContractCode, mockAuditJob, mockReportDashboard, mockPatchDiff, mockEvidence } from './mockData.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENS_DIR = path.resolve(__dirname, '../frontend/stitch_screens');
const PORT = 3000;

// Map URL path -> screen file
const SCREEN_MAP = {
  '/':               'workspace_intake.html',
  '/workspace':      'workspace_intake.html',
  '/live-run':       'live_progress_tracker.html',
  '/report-summary': 'report_summary.html',
  '/patch-diff':     'patch_diff.html',
  '/evidence-drawer':'evidence_drawer.html',
};

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css',
  '.js':   'text/javascript',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.svg':  'image/svg+xml',
  '.json': 'application/json',
};

// Nav injection: replace each data-path href="#" with the correct page href
// so the nav links actually navigate between pages.
function injectNav(html, currentPath) {
  const pathMap = {
    'workspace':       '/',
    'live-run':        '/live-run',
    'report-summary':  '/report-summary',
    'patch-diff':      '/patch-diff',
    'evidence-drawer': '/evidence-drawer',
  };

  // Wire Run Audit button to /live-run
  html = html.replace(
    /(<button[^>]*>\s*)(Run Audit)(\s*<\/button>)/gi,
    (m, pre, label, post) => `${pre}<a href="/live-run" style="color:inherit;text-decoration:none">${label}</a>${post}`
  );
  // Wire View Results / Report Summary button
  html = html.replace(
    /(<button[^>]*>\s*)(View Results|View Report|Go to Report)(\s*<\/button>)/gi,
    (m, pre, label, post) => `${pre}<a href="/report-summary" style="color:inherit;text-decoration:none">${label}</a>${post}`
  );

  // Wire each nav anchor by data-path to its page
  for (const [dp, href] of Object.entries(pathMap)) {
    const isActive = currentPath === href || (href === '/' && currentPath === '/workspace');
    // Replace href="#" on links with matching data-path
    html = html.replace(
      new RegExp(`(data-path="${dp}"[^>]*href=")#(")`, 'g'),
      `$1${href}$2`
    );
    html = html.replace(
      new RegExp(`(href=")#("[^>]*data-path="${dp}")`, 'g'),
      `$1${href}$2`
    );
  }

  return html;
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  const url = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = url.pathname;

  // ── API routes ──────────────────────────────────────────────────────────────
  if (pathname === '/api/contract') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ code: mockContractCode, filename: 'YieldVault.sol', version: '0.8.20' }));
  }
  if (pathname === '/api/audit-job') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(mockAuditJob));
  }
  if (pathname === '/api/report') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(mockReportDashboard));
  }
  if (pathname === '/api/patch-diff') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(mockPatchDiff));
  }
  if (pathname.startsWith('/api/evidence/')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(mockEvidence));
  }
  if (pathname === '/api/audit/start' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'STARTED', jobId: 'AUD-2024-8841-B' }));
    });
    return;
  }

  // ── Static screen files ──────────────────────────────────────────────────────
  const screenFile = SCREEN_MAP[pathname];
  if (screenFile) {
    const filePath = path.join(SCREENS_DIR, screenFile);
    fs.readFile(filePath, 'utf8', (err, data) => {
      if (err) { res.writeHead(404); return res.end('Screen not found'); }
      const patched = injectNav(data, pathname);
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(patched);
    });
    return;
  }

  // ── Serve any other static asset from stitch_screens ───────────────────────
  const assetPath = path.join(SCREENS_DIR, pathname.replace(/^\//, ''));
  if (!assetPath.startsWith(SCREENS_DIR)) {
    res.writeHead(403); return res.end('Forbidden');
  }
  fs.readFile(assetPath, (err, data) => {
    if (err) { res.writeHead(404); return res.end('Not found'); }
    const ext = path.extname(assetPath).toLowerCase();
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    res.end(data);
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`DeFi Contract Auditor running at http://localhost:${PORT}`);
  console.log('  /                -> Workspace - Intake & Configuration');
  console.log('  /live-run        -> Live Progress Tracker');
  console.log('  /report-summary  -> Security & Regulatory Dashboard');
  console.log('  /patch-diff      -> Patch Diff - Side-by-Side Remediation Viewer');
  console.log('  /evidence-drawer -> Evidence & Citation Drawer');
});
