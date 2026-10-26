import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtemp, writeFile, mkdir, symlink, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createFrontend, route } from '../../deploy/dev/frontend-server/server.mjs';
const listen = server => new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${server.address().port}`)));
const close = server => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); });
function request(origin, target, { method = 'GET', headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request(origin + target, { method, headers }, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString() }));
    });
    req.on('error', reject);
    req.end(body);
  });
}
test('routing preserves technical and tenant paths and query bytes', () => {
  for (const target of ['/api/admin/login?x=%2f', '/s/file', '/viewer/index.html', '/images', '/assets', '/l10n/it', '/t/abc/api/session']) assert.equal(route(target, 'GET').target, target);
  assert.deepEqual(route('/my-channel/?lang=it', 'GET'), { target: '/?lang=it', redirect: '/my-channel/report?lang=it', isApi: false });
  assert.equal(route('/t/abc/my-channel/admin/users?a=1', 'GET').target, '/t/abc/?a=1');
  assert.equal(route('/my-channel/report', 'POST').target, '/my-channel/report');
  assert.throws(() => route('/%2e%2e/secret.js', 'GET'));
});
test('proxy renders only marked static responses, streams APIs and enforces containment', async t => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'wbe-fe-test-'));
  const build = path.join(root, 'build');
  await mkdir(build);
  await writeFile(path.join(build, 'index.html'), '<html lang="en" dir="ltr"><style nonce="randomCspNonce"></style></html>');
  await writeFile(path.join(build, 'main.js'), 'console.log("ok")');
  await writeFile(path.join(build, 'secret.env'), 'secret');
  await writeFile(path.join(root, 'outside.js'), 'secret');
  await symlink(path.join(root, 'outside.js'), path.join(build, 'escape.js'));
  let seen;
  const backend = http.createServer(async (req, res) => {
    seen = { url: req.url, method: req.method, headers: req.headers };
    if (req.url === '/api/health') return res.end('"OK"');
    if (req.url.startsWith('/api/')) {
      res.writeHead(201, { 'content-type': 'application/json', 'x-session': 'session', 'set-cookie': ['a=1; HttpOnly', 'b=2; HttpOnly'] });
      for await (const chunk of req) res.write(chunk);
      return res.end();
    }
    const filename = req.url.split('?')[0].slice(1) || 'index.html';
    res.writeHead(200, { 'x-wbe-frontend': '1', 'content-type': 'application/json', 'content-security-policy': "style-src 'nonce-fresh123'", 'x-frame-options': 'DENY' });
    res.end(JSON.stringify({ wbe_frontend: 1, filename, language: 'it', direction: 'ltr', nonce: 'fresh123' }));
  });
  const backendUrl = await listen(backend);
  const fe = createFrontend({ backendUrl, clientRoot: build });
  const base = await listen(fe);
  t.after(async () => { await close(fe); await close(backend); await rm(root, { recursive: true, force: true }); });
  const index = await request(base, '/channel/report?lang=it');
  assert.equal(seen.url, '/?lang=it');
  assert.equal(index.status, 200);
  assert.match(index.headers['content-type'], /^text\/html/);
  assert.equal(index.headers['content-security-policy'], "style-src 'nonce-fresh123'");
  assert.match(index.body, /lang="it"/);
  assert.match(index.body, /nonce="fresh123"/);
  assert.equal(index.headers['x-wbe-frontend'], undefined);
  assert.equal(index.headers['cache-control'], 'no-store');
  const redirect = await request(base, '/channel?lang=it');
  assert.equal(redirect.status, 302);
  assert.equal(redirect.headers.location, '/channel/report?lang=it');
  const head = await request(base, '/', { method: 'HEAD' });
  assert.equal(head.body, '');
  assert.ok(Number(head.headers['content-length']) > 0);
  assert.equal((await request(base, '/main.js')).body, 'console.log("ok")');
  for (const file of ['/escape.js', '/missing.js', '/secret.env']) assert.equal((await request(base, file)).status, 404);
  const body = 'x'.repeat(300000);
  const api = await request(base, '/api/upload?x=%2f', { method: 'POST', body, headers: { 'x-forwarded-for': 'evil', forwarded: 'evil', 'x-real-ip': 'evil', dpop: 'proof', host: 'tenant.example', connection: 'x-malicious', 'x-malicious': 'value' } });
  assert.equal(api.status, 201);
  assert.equal(api.body, body);
  assert.equal(api.headers['x-session'], 'session');
  assert.equal(api.headers['set-cookie'].length, 2);
  assert.equal(seen.url, '/api/upload?x=%2f');
  assert.equal(seen.headers.dpop, 'proof');
  assert.equal(seen.headers.host, 'tenant.example');
  for (const name of ['x-forwarded-for', 'forwarded', 'x-real-ip', 'x-malicious']) assert.equal(seen.headers[name], undefined);
  await request(base, '/api/head', { method: 'HEAD' });
  assert.equal(seen.method, 'HEAD');
  assert.equal((await request(base, '/healthz')).status, 200);
  await close(backend);
  assert.equal((await request(base, '/healthz')).status, 503);
  assert.equal((await request(base, '/')).status, 502);
});
