import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { createFrontend } from '../../deploy/dev/frontend-server/server.mjs';

const listen = (server, target = 0) => new Promise((resolve, reject) => {
  server.once('error', reject);
  if (typeof target === 'string') server.listen(target, resolve);
  else server.listen(target, '127.0.0.1', () => resolve(`http://127.0.0.1:${server.address().port}`));
});
const close = server => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); });
const request = (base, target, headers = {}, method = 'GET', body) => new Promise((resolve, reject) => {
  const req = http.request(base + target, { method, headers }, res => {
    const chunks = [];
    res.on('data', chunk => chunks.push(chunk));
    res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString() }));
  });
  req.on('error', reject);
  req.end(body);
});
const forwarded = { 'x-forwarded-proto': 'https', 'x-forwarded-for': '198.51.100.17' };

test('production mode rejects incomplete trust configuration', () => {
  for (const trustedProxyIps of ['', 'localhost', '127.0.0.0/8', '127.0.0.1,invalid']) {
    assert.throws(() => createFrontend({ socketDir: '/tmp/wbe-proxy', trustedProxyIps }), /exact IP/);
  }
  assert.throws(() => createFrontend({ socketDir: 'relative', trustedProxyIps: '127.0.0.1' }), /absolute/);
  assert.throws(() => createFrontend({ socketDir: '', onion: true }), /requires Unix/);
});

test('real Unix upstreams separate trusted HTTPS identity from onion identity', async t => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'wbe-prod-fe-'));
  const build = path.join(root, 'build');
  await mkdir(build);
  await writeFile(path.join(build, 'index.html'), '<html lang="en" dir="ltr"><style nonce="randomCspNonce"></style></html>');
  const seen = { web: [], onion: [] };
  const backends = {};
  for (const channel of ['web', 'onion']) {
    backends[channel] = http.createServer(async (req, res) => {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const record = { headers: req.headers, path: req.url, method: req.method, body: Buffer.concat(chunks).toString() };
      seen[channel].push(record);
      if (req.url === '/api/health') return res.end('OK');
      if (req.url.startsWith('/api/') || req.url.startsWith('/t/tenant/api/')) {
        res.writeHead(202, { 'content-type': 'application/json', 'x-backend-channel': channel });
        return res.end(JSON.stringify({ channel }));
      }
      res.writeHead(200, { 'x-wbe-frontend': '1', 'content-security-policy': `style-src 'nonce-${channel}123'`, 'x-backend-channel': channel });
      res.end(JSON.stringify({ wbe_frontend: 1, filename: 'index.html', language: 'it', direction: 'ltr', nonce: `${channel}123` }));
    });
    await listen(backends[channel], path.join(root, `${channel}.sock`));
  }
  const web = createFrontend({ socketDir: root, clientRoot: build, trustedProxyIps: '127.0.0.1' });
  const untrusted = createFrontend({ socketDir: root, clientRoot: build, trustedProxyIps: '127.0.0.2' });
  const onion = createFrontend({ socketDir: root, clientRoot: build, onion: true, trustedProxyIps: '' });
  const [webBase, unknownBase, onionBase] = await Promise.all([listen(web), listen(untrusted), listen(onion)]);
  t.after(async () => {
    await Promise.all([close(web), close(untrusted), close(onion), close(backends.web), close(backends.onion)]);
    await rm(root, { recursive: true, force: true });
  });

  for (const headers of [
    {}, { 'x-forwarded-for': '198.51.100.17' }, { 'x-forwarded-proto': 'https' },
    { ...forwarded, 'x-forwarded-proto': 'http' }, { ...forwarded, 'x-forwarded-proto': 'https, https' },
    { ...forwarded, 'x-forwarded-proto': 'HTTPS' },
    ...['', 'garbage', '198.51.100.17, ', '198.51.100.17:123', '198.51.100.17, bad', '[2001:db8::1]', 'fe80::1%eth0'].map(value => ({ ...forwarded, 'x-forwarded-for': value })),
  ]) assert.equal((await request(webBase, '/api/session', headers)).status, 403);
  assert.equal((await request(unknownBase, '/api/session', { ...forwarded, 'x-real-ip': '127.0.0.2', 'x-wbe-client-ip': '127.0.0.2' })).status, 403);
  assert.equal(seen.web.length, 0, 'Rejected requests must not reach either Unix backend');
  assert.equal(seen.onion.length, 0);

  const body = 'synthetic-upload-'.repeat(20000);
  const accepted = await request(webBase, '/t/tenant/api/upload?encoded=%2f', {
    ...forwarded, 'x-forwarded-for': 'spoofed-client-value, 2001:db8::17',
    host: 'tenant.example', dpop: 'synthetic-proof', 'x-wbe-client-ip': '203.0.113.99',
    'x-wbe-extra': 'untrusted', 'x-wbe-frontend': '1', forwarded: 'for=evil;proto=http',
    'x-real-ip': '203.0.113.98', 'x-forwarded-host': 'evil.example',
    connection: 'x-hop', 'x-hop': 'untrusted',
  }, 'POST', body);
  assert.equal(accepted.status, 202);
  assert.equal(accepted.headers['x-backend-channel'], 'web');
  const captured = seen.web.at(-1);
  assert.equal(captured.path, '/t/tenant/api/upload?encoded=%2f');
  assert.equal(captured.method, 'POST');
  assert.equal(captured.body, body);
  assert.equal(captured.headers.host, 'tenant.example');
  assert.equal(captured.headers.dpop, 'synthetic-proof');
  assert.equal(captured.headers['x-wbe-client-ip'], '2001:db8::17');
  for (const key of ['x-forwarded-proto', 'x-forwarded-for', 'x-forwarded-host', 'forwarded', 'x-real-ip', 'x-wbe-extra', 'x-wbe-frontend', 'x-hop']) assert.equal(captured.headers[key], undefined);

  for (const [base, channel, headers] of [[webBase, 'web', forwarded], [onionBase, 'onion', { 'x-forwarded-proto': 'http', 'x-forwarded-for': 'bad', 'x-wbe-client-ip': '203.0.113.1', 'x-wbe-extra': 'bad' }]]) {
    const shell = await request(base, '/channel/report?lang=it', { ...headers, host: 'tenant.example' });
    assert.equal(shell.status, 200);
    assert.equal(shell.headers['content-security-policy'], `style-src 'nonce-${channel}123'`);
    assert.match(shell.body, /lang="it"/);
    assert.match(shell.body, new RegExp(`nonce="${channel}123"`));
    assert.equal(shell.headers['x-wbe-frontend'], undefined);
    assert.equal(seen[channel].at(-1).path, '/?lang=it');
    if (channel === 'onion') {
      assert.equal(seen.onion.at(-1).headers['x-wbe-client-ip'], undefined);
      assert.equal(seen.onion.at(-1).headers['x-wbe-extra'], undefined);
      assert.equal(seen.onion.at(-1).headers['x-forwarded-for'], undefined);
      assert.equal(seen.onion.at(-1).headers.host, 'tenant.example');
      const api = await request(base, '/api/receipt?x=%2F', { ...headers, dpop: 'onion-proof' }, 'HEAD');
      assert.equal(api.status, 202);
      assert.equal(seen.onion.at(-1).method, 'HEAD');
      assert.equal(seen.onion.at(-1).path, '/api/receipt?x=%2F');
      assert.equal(seen.onion.at(-1).headers.dpop, 'onion-proof');
    }
    const health = await request(base, '/healthz', { ...headers, 'x-wbe-client-ip': 'evil', cookie: 'secret' });
    assert.equal(health.status, 200);
    assert.equal(health.body, 'OK\n');
    assert.equal(seen[channel].at(-1).path, '/api/health');
    assert.equal(seen[channel].at(-1).headers['x-wbe-client-ip'], undefined);
    assert.equal(seen[channel].at(-1).headers.cookie, undefined);
  }
  assert.equal((await request(unknownBase, '/healthz')).status, 200, 'Readiness exposes no visitor identity');
  await close(backends.web);
  assert.equal((await request(webBase, '/api/session', forwarded)).status, 502);
  assert.equal((await request(webBase, '/healthz')).status, 503);
  assert.equal((await request(onionBase, '/api/session')).status, 202, 'Onion retains its own upstream');
});
