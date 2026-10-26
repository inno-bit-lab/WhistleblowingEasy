import http from 'node:http';
import { isIP } from 'node:net';
import https from 'node:https';
import { createReadStream } from 'node:fs';
import { realpath, stat, readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { pipeline } from 'node:stream';

const HOP = new Set(['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade']);
const RESERVED = new Set('api s js css fonts workers l10n images assets data login admin recipient custodian analyst action wizard signup submission password activation reports blank viewer t healthz'.split(' '));
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.wasm': 'application/wasm', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.txt': 'text/plain; charset=utf-8', '.pdf': 'application/pdf' };
function cleanHeaders(headers, request = false) {
  const blocked = new Set([...HOP, ...(headers.connection || '').toLowerCase().split(',').map(x => x.trim())]);
  return Object.fromEntries(Object.entries(headers).filter(([key]) => !blocked.has(key) && key !== 'x-wbe-frontend' && (!request || (!key.startsWith('x-wbe-') && !key.startsWith('x-forwarded-') && !['forwarded', 'x-real-ip', 'x-original-url', 'x-rewrite-url'].includes(key)))));
}
export function route(raw, method) {
  if (!raw.startsWith('/') || raw.startsWith('//')) throw new Error('invalid request target');
  const q = raw.indexOf('?');
  const pathname = q < 0 ? raw : raw.slice(0, q);
  const query = q < 0 ? '' : raw.slice(q);
  const tenant = pathname.match(/^(\/t\/[a-z0-9-]+)(\/.*)$/);
  const prefix = tenant?.[1] || '';
  const local = tenant?.[2] || pathname;
  const isApi = /^\/api(?:\/|$)/.test(local);
  if (isApi || !['GET', 'HEAD'].includes(method)) return { target: raw, isApi };
  const decoded = decodeURIComponent(local);
  if (decoded.includes('\\') || decoded.includes('\0') || decoded.split('/').some(p => p === '..' || p === '.')) throw new Error('invalid path');
  const slug = local.match(/^\/([a-z0-9]+(?:-[a-z0-9]+)*)(\/.*)?$/);
  if (slug && !RESERVED.has(slug[1])) {
    if (!slug[2] || slug[2] === '/') return { target: `${prefix}/${query}`, redirect: `${prefix}/${slug[1]}/report${query}`, isApi };
    if (/^\/(report\/?|admin(?:\/.*)?|login(?:\/.*)?)$/.test(slug[2])) return { target: `${prefix}/${query}`, isApi };
  }
  return { target: raw, isApi };
}
async function asset(root, filename) {
  if (typeof filename !== 'string' || filename.includes('\\') || filename.includes('\0') || path.isAbsolute(filename) || filename.split('/').some(p => p === '..' || p.startsWith('.'))) throw new Error('invalid asset');
  if (!Object.hasOwn(MIME, path.extname(filename).toLowerCase())) throw new Error('unsupported asset');
  const base = await realpath(root);
  const resolved = await realpath(path.join(base, filename));
  if (!resolved.startsWith(base + path.sep)) throw new Error('invalid asset');
  const info = await stat(resolved);
  if (!info.isFile()) throw new Error('invalid asset');
  return { resolved, size: info.size };
}
function fail(res, status) {
  if (res.destroyed) return;
  if (res.headersSent) return res.destroy();
  res.writeHead(status, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
  res.end(status === 404 ? 'Not found\n' : status === 400 ? 'Bad request\n' : status === 403 ? 'Forbidden\n' : 'Service unavailable\n');
}
export function createFrontend({
  backendUrl = process.env.BACKEND_URL || 'http://backend:8080',
  clientRoot = process.env.CLIENT_ROOT || '/client/build',
  socketDir = process.env.WBE_FRONTEND_SOCKET_DIR || '',
  trustedProxyIps = process.env.WBE_TRUSTED_PROXY_IPS || '',
  onion = false,
} = {}) {
  if (onion && !socketDir) throw new Error('Onion frontend requires Unix backend sockets');
  if (socketDir && !path.isAbsolute(socketDir)) throw new Error('WBE_FRONTEND_SOCKET_DIR must be absolute');
  const trustedPeers = new Set(trustedProxyIps.split(',').map(value => value.trim()).filter(Boolean));
  if (socketDir && !onion && (!trustedPeers.size || [...trustedPeers].some(value => !isIP(value)))) {
    throw new Error('WBE_TRUSTED_PROXY_IPS must contain exact IP addresses');
  }
  const backend = socketDir ? null : new URL(backendUrl);
  if (backend && (!['http:', 'https:'].includes(backend.protocol) || backend.username || backend.password || backend.pathname !== '/')) throw new Error('Invalid BACKEND_URL');
  const transport = backend?.protocol === 'https:' ? https : http;
  const destination = socketDir
    ? { socketPath: path.join(socketDir, onion ? 'onion.sock' : 'web.sock') }
    : { protocol: backend.protocol, hostname: backend.hostname, port: backend.port };
  return http.createServer(async (req, res) => {
    if (req.url === '/healthz' && ['GET', 'HEAD'].includes(req.method)) {
      try {
        await asset(clientRoot, 'index.html');
        const ready = await new Promise((resolve) => {
          const check = transport.get({ ...destination, path: '/api/health', headers: { host: 'localhost' }, timeout: 5000 }, response => { response.resume(); resolve(response.statusCode === 200); });
          check.on('timeout', () => check.destroy());
          check.on('error', () => resolve(false));
        });
        if (!ready) return fail(res, 503);
        res.writeHead(200, { 'content-type': 'text/plain', 'cache-control': 'no-store' });
        return res.end(req.method === 'HEAD' ? undefined : 'OK\n');
      } catch { return fail(res, 503); }
    }
    let clientIp;
    if (socketDir && !onion) {
      const forwardedFor = req.headers['x-forwarded-for'];
      clientIp = typeof forwardedFor === 'string' ? forwardedFor.split(',').at(-1).trim() : '';
      // Only a configured immediate proxy may assert HTTPS and append the visitor IP.
      // Earlier XFF values can be browser-controlled and are never used as identity.
      if (!trustedPeers.has(req.socket.remoteAddress) || req.headers['x-forwarded-proto'] !== 'https' || !isIP(clientIp) || clientIp.includes('%')) {
        req.resume();
        return fail(res, 403);
      }
    }
    let routing;
    try { routing = route(req.url, req.method); } catch { return fail(res, 400); }
    const headers = cleanHeaders(req.headers, true);
    if (clientIp) headers['x-wbe-client-ip'] = clientIp;
    // Metadata must be identity encoded; API request targets and bodies remain byte-for-byte unchanged.
    if (!routing.isApi) headers['accept-encoding'] = 'identity';
    const upstream = transport.request({ ...destination, method: req.method === 'HEAD' && !routing.isApi ? 'GET' : req.method, path: routing.target, headers }, async response => {
      const outgoing = cleanHeaders(response.headers);
      if (response.headers['x-wbe-frontend'] !== '1') {
        res.writeHead(response.statusCode, outgoing);
        return pipeline(response, res, () => {});
      }
      try {
        if (response.statusCode !== 200 || !['GET', 'HEAD'].includes(req.method)) throw new Error('invalid metadata');
        let size = 0;
        const chunks = [];
        for await (const chunk of response) {
          size += chunk.length;
          if (size > 16384) throw new Error('metadata too large');
          chunks.push(chunk);
        }
        const meta = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        if (meta.wbe_frontend !== 1 || typeof meta.language !== 'string' || typeof meta.nonce !== 'string' || !/^[a-zA-Z0-9-]+$/.test(meta.language) || !['ltr', 'rtl'].includes(meta.direction) || !/^[a-zA-Z0-9+/_=-]+$/.test(meta.nonce)) throw new Error('invalid metadata');
        for (const key of ['content-length', 'content-encoding', 'etag', 'last-modified']) delete outgoing[key];
        outgoing['cache-control'] = 'no-store';
        if (routing.redirect) {
          res.writeHead(302, { ...outgoing, location: routing.redirect, 'content-length': '0' });
          return res.end();
        }
        let file;
        try { file = await asset(clientRoot, meta.filename); } catch { res.writeHead(404, { ...outgoing, 'content-type': 'text/plain' }); return res.end(req.method === 'HEAD' ? undefined : 'Not found\n'); }
        outgoing['content-type'] = MIME[path.extname(file.resolved).toLowerCase()] || 'application/octet-stream';
        if (meta.filename === 'index.html') {
          const html = (await readFile(file.resolved, 'utf8')).replaceAll('lang="en"', `lang="${meta.language}"`).replaceAll('dir="ltr"', `dir="${meta.direction}"`).replaceAll('randomCspNonce', meta.nonce);
          outgoing['content-length'] = Buffer.byteLength(html);
          res.writeHead(200, outgoing);
          return res.end(req.method === 'HEAD' ? undefined : html);
        }
        outgoing['content-length'] = file.size;
        res.writeHead(200, outgoing);
        if (req.method === 'HEAD') return res.end();
        pipeline(createReadStream(file.resolved), res, () => {});
      } catch { fail(res, 502); }
    });
    upstream.setTimeout(120000, () => upstream.destroy());
    upstream.on('error', () => fail(res, 502));
    req.on('aborted', () => upstream.destroy());
    res.on('close', () => { if (!res.writableEnded) upstream.destroy(); });
    req.pipe(upstream);
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const servers = [createFrontend()];
  const mainPort = Number(process.env.PORT || (process.env.WBE_FRONTEND_SOCKET_DIR ? 8084 : 8080));
  const onionPort = process.env.WBE_ONION_FRONTEND_PORT;
  // Construct and validate both endpoints before opening any listener.
  if (onionPort) servers.push(createFrontend({ onion: true }));
  servers[0].listen(mainPort, '0.0.0.0');
  if (servers[1]) servers[1].listen(Number(onionPort), '127.0.0.1');
  for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => servers.forEach(server => server.close()));
}
