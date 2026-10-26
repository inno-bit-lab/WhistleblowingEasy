// Opt-in browser tests against the isolated development stack.
// WBE_E2E_SETUP=1 initializes synthetic accounts; WBE_E2E_REPORT=1 writes synthetic reports.
// WBE_E2E_URL=http://127.0.0.1:18090 PUPPETEER_MODULE=/path/to/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js
// CHROMIUM_PATH=/path/to/chrome-headless-shell node --test tests/phase1/frontend-browser.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL, fileURLToPath } from 'node:url';
const enabled = Boolean(process.env.WBE_E2E_URL);
test('synthetic development wizard and fresh-session admin login', { skip: !(enabled && process.env.WBE_E2E_SETUP === '1'), timeout: 180000 }, async () => {
  const base = process.env.WBE_E2E_URL;
  assert.equal(base, 'http://127.0.0.1:18090');
  const { readFile, writeFile, mkdir } = await import('node:fs/promises');
  const { randomBytes } = await import('node:crypto');
  const { default: puppeteer } = await import(pathToFileURL(process.env.PUPPETEER_MODULE).href);
  const secretUrl = new URL('../../.local/secrets/browser-fixture.json', import.meta.url);
  await mkdir(new URL('.', secretUrl), { recursive: true, mode: 0o700 });
  let credentials;
  try { credentials = JSON.parse(await readFile(secretUrl, 'utf8')); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error;
    credentials = { admin: 'phase1-admin', recipient: 'phase1-recipient', password: `DevOnly!${randomBytes(24).toString('base64url')}` };
    await writeFile(secretUrl, JSON.stringify(credentials), { mode: 0o600, flag: 'wx' });
  }
  const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true, defaultViewport: { width: 1280, height: 900 }, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    const page = await browser.newPage();
    await page.goto(`${base}/?lang=en`, { waitUntil: 'networkidle0' });
    await page.waitForFunction(() => document.querySelector('app-root')?.textContent.trim().length > 30);
    if (await page.$('src-wizard')) {
      await page.click('.ButtonNext');
      await page.waitForSelector('[name="node_name"]', { visible: true });
      await page.type('[name="node_name"]', 'WBE Phase 1 Synthetic Lab');
      await page.click('.ButtonNext');
      await page.waitForSelector('[name="admin_username"]', { visible: true });
      for (const [name, value] of Object.entries({ admin_username: credentials.admin, admin_name: 'Synthetic Administrator', admin_mail_address: 'admin@invalid.example', admin_password: credentials.password, admin_password_check: credentials.password })) await page.type(`[name="${name}"]`, value);
      await page.click('.ButtonNext');
      await page.waitForSelector('[name="receiver_username"]', { visible: true });
      for (const [name, value] of Object.entries({ receiver_username: credentials.recipient, receiver_name: 'Synthetic Recipient', receiver_mail_address: 'recipient@invalid.example', receiver_password: credentials.password, receiver_password_check: credentials.password })) await page.type(`[name="${name}"]`, value);
      await page.click('.ButtonNext');
      await page.waitForSelector('.tos-agreement-input', { visible: true });
      await page.click('.tos-agreement-input');
      const notifications = await page.$('#enable_developers_exception_notification_checkbox');
      if (notifications && await notifications.evaluate(el => el.checked)) await notifications.click();
      await page.click('.ButtonNext');
      await page.waitForSelector('button[name="proceed"]', { visible: true, timeout: 90000 });
      await page.click('button[name="proceed"]');
      await page.waitForFunction(() => location.hash.includes('/admin/'), { timeout: 60000 });
    }
    // New browser context proves credentials and configuration persist in PostgreSQL.
    const context = await browser.createBrowserContext();
    const login = await context.newPage();
    await login.goto(`${base}/#/login`, { waitUntil: 'networkidle0' });
    await login.waitForSelector('[name="username"]', { visible: true });
    await login.type('[name="username"]', credentials.admin);
    await login.type('[name="password"]', credentials.password);
    await login.click('#login-button');
    await login.waitForFunction(() => location.hash.includes('/admin/'), { timeout: 60000 });
    await login.waitForSelector('#LogoutLink', { visible: true });
    const currentPublic = await (await fetch(`${base}/api/public`)).json();
    if (!currentPublic.node.languages_enabled.includes('it')) {
      await login.goto(`${base}/#/admin/settings`, { waitUntil: 'networkidle0' });
      await login.waitForSelector('[name="node.dataModel.header_title_homepage"]', { visible: true });
      await login.$eval('[data-cy="languages"]', el => el.click());
      await login.waitForFunction(() => document.querySelector('[data-cy="languages"]')?.getAttribute('aria-selected') === 'true');
      await login.waitForSelector('.add-language-btn', { visible: true });
      if (!(await login.$eval('body', el => el.textContent.includes('Italian [it]')))) {
        await login.click('.add-language-btn');
        await login.waitForSelector('#language-adder-select', { visible: true });
        await login.click('#language-adder-select');
        await login.waitForSelector('div.ng-option');
        const options = await login.$$('div.ng-option');
        for (const option of options) {
          if (/Italian\s*\[it\]/.test(await option.evaluate(el => el.textContent))) { await option.click(); break; }
        }
        const saved = login.waitForResponse(response => response.url().endsWith('/api/admin/node') && response.request().method() === 'PUT');
        await login.click('#save_language');
        assert.equal((await saved).status(), 202);
        await login.waitForSelector('[name="node.dataModel.header_title_homepage"]', { visible: true });
      }
    }
    await login.click('#LogoutLink');
    await context.close();
  } finally { await browser.close(); }
});

test('development FE boots Angular with CSP, JS, worker, viewer and IT/EN', { skip: !enabled, timeout: 90000 }, async () => {
  const base = process.env.WBE_E2E_URL;
  assert.equal(base, 'http://127.0.0.1:18090', 'This test is restricted to the isolated dev listener');
  assert.ok(process.env.PUPPETEER_MODULE && process.env.CHROMIUM_PATH, 'Set browser tooling paths explicitly');
  const { default: puppeteer } = await import(pathToFileURL(process.env.PUPPETEER_MODULE).href);
  const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true, defaultViewport: { width: 1280, height: 900 }, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    for (const language of ['en', 'it']) {
      const context = await browser.createBrowserContext();
      const page = await context.newPage();
      const pageErrors = [];
      const violations = [];
      const brokenAssets = [];
      page.on('pageerror', error => pageErrors.push(error.message));
      page.on('response', response => {
        if (response.status() >= 400 && /\.(?:js|css|woff2)(?:\?|$)/.test(response.url())) brokenAssets.push(new URL(response.url()).pathname);
      });
      await page.exposeFunction('recordCspViolation', directive => violations.push(directive));
      await page.evaluateOnNewDocument(() => document.addEventListener('securitypolicyviolation', event => window.recordCspViolation(event.violatedDirective)));
      await page.setExtraHTTPHeaders({ 'Accept-Language': language });
      const response = await page.goto(`${base}/?lang=${language}#/?lang=${language}`, { waitUntil: 'networkidle0' });
      assert.equal(response.status(), 200);
      assert.match(response.headers()['content-type'], /^text\/html/);
      assert.match(response.headers()['content-security-policy'], /nonce-/);
      await page.waitForFunction(() => document.querySelector('app-root')?.textContent.trim().length > 30, { timeout: 30000 });
      assert.equal(await page.$eval('html', html => html.lang), language);
      const assets = await page.evaluate(async () => {
        const output = {};
        for (const pathname of ['/workers/crypto.worker.js', '/viewer/index.html', '/healthz']) {
          const result = await fetch(pathname);
          output[pathname] = { status: result.status, type: result.headers.get('content-type'), csp: result.headers.get('content-security-policy') };
        }
        return output;
      });
      assert.equal(assets['/workers/crypto.worker.js'].status, 200);
      assert.match(assets['/workers/crypto.worker.js'].type, /javascript/);
      assert.match(assets['/workers/crypto.worker.js'].csp, /wasm-unsafe-eval/);
      assert.equal(assets['/viewer/index.html'].status, 200);
      assert.match(assets['/viewer/index.html'].csp, /frame-ancestors 'self'/);
      assert.equal(assets['/healthz'].status, 200);
      assert.deepEqual(brokenAssets, []);
      assert.deepEqual(pageErrors, []);
      assert.deepEqual(violations, []);
      await context.close();
    }
  } finally { await browser.close(); }
});


test('synthetic report submission and receipt access in a fresh browser session', { skip: !(enabled && process.env.WBE_E2E_REPORT === '1'), timeout: 180000 }, async () => {
  const base = process.env.WBE_E2E_URL;
  assert.equal(base, 'http://127.0.0.1:18090');
  const { default: puppeteer } = await import(pathToFileURL(process.env.PUPPETEER_MODULE).href);
  const { writeFile } = await import('node:fs/promises');
  const publicData = await (await fetch(`${base}/api/public`)).json();
  assert.equal(publicData.node.wizard_done, true);
  assert.ok(publicData.contexts.length > 0);
  const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true, defaultViewport: { width: 1280, height: 900 }, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    const page = await browser.newPage();
    const channel = process.env.WBE_E2E_CHANNEL;
    if (channel) assert.match(channel, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    const entry = channel ? `${base}/${channel}/report?lang=en`
      : `${base}/#/submission?context=${encodeURIComponent(publicData.contexts[0].id)}&lang=en`;
    const failedChannelAssets = [];
    page.on('response', response => {
      if (response.status() >= 400 && /\/(?:css|s|viewer|workers)\//.test(new URL(response.url()).pathname)) {
        failedChannelAssets.push(new URL(response.url()).pathname);
      }
    });
    await page.goto(entry, { waitUntil: 'networkidle0' });
    if (channel) {
      await page.waitForFunction(() => ['/css/fonts.css', '/s/css'].every(path =>
        [...document.querySelectorAll('link[rel="stylesheet"]')].some(link =>
          new URL(link.href).pathname === path && link.sheet)));
      assert.deepEqual(failedChannelAssets, []);
    }
    await page.waitForSelector('[aria-controls="kronos-report-form"]', { visible: true });
    await page.click('[aria-controls="kronos-report-form"]');
    await page.waitForSelector('#step-0', { visible: true });
    const questionnaire = channel
      ? await (await fetch(`${base}/api/public/contexts/${publicData.contexts[0].id}`)).json()
      : null;
    const uploadTriggers = [];
    function collectUploadTriggers(node) {
      if (!node || typeof node !== 'object') return;
      if (node.type === 'fileupload') {
        uploadTriggers.push(...node.triggered_by_options.map(trigger => trigger.option));
      }
      for (const value of Object.values(node)) collectUploadTriggers(value);
    }
    collectUploadTriggers(questionnaire);
    if (channel) assert.ok(uploadTriggers.length > 0);
    const selections = await page.$$('#step-0 select');
    for (const select of selections) {
      if (!(await select.isVisible())) continue;
      const value = await select.evaluate((el, triggers) => {
        const options = [...el.options].filter(option => option.value && !option.disabled);
        return (options.find(option => triggers.includes(option.value)) || options.at(-1))?.value;
      }, uploadTriggers);
      if (value) await select.select(value);
    }
    for (const field of await page.$$('#step-0 input[type="text"], #step-0 textarea')) {
      if (await field.isVisible()) await field.type('Synthetic phase 1 PostgreSQL browser validation; no real report data.');
    }
    let initialUpload;
    if (channel) {
      const attachment = new URL('../../.local/imports/browser-synthetic.txt', import.meta.url);
      await writeFile(attachment, 'Synthetic attachment for WBE phase 1 PostgreSQL validation.\n', { mode: 0o600 });
      const upload = await page.waitForSelector('#step-0 input[type="file"]');
      await upload.uploadFile(fileURLToPath(attachment));
      // Adding evidence reveals its required description asynchronously.
      await page.waitForFunction(() => [...document.querySelectorAll('#step-0 textarea')]
        .some(el => el.getBoundingClientRect().height > 0 && !el.value));
      for (const field of await page.$$('#step-0 input[type="text"], #step-0 textarea')) {
        if (await field.isVisible() && !(await field.evaluate(el => el.value))) {
          await field.type('Synthetic evidence description for browser validation.');
        }
      }
      initialUpload = page.waitForResponse(r => r.request().method() === 'POST' && r.url().includes('/submission/attachment'));
    }
    await page.waitForSelector('#SubmitButton', { visible: true });
    await page.locator('#SubmitButton').click();
    if (initialUpload) {
      const response = await initialUpload;
      assert.equal(new URL(response.url()).pathname, '/api/whistleblower/submission/attachment');
      assert.ok(response.status() >= 200 && response.status() < 300, `Upload status ${response.status()}`);
    }
    await page.waitForSelector('#ReceiptCode', { visible: true, timeout: 90000 });
    const receipt = await page.$eval('#ReceiptCode', el => el.value.replace(/\s/g, ''));
    assert.match(receipt, /^\d{16}$/);
    await writeFile(new URL('../../.local/secrets/browser-receipt.txt', import.meta.url), receipt, { mode: 0o600 });
    const context = await browser.createBrowserContext();
    const reader = await context.newPage();
    await reader.goto(`${base}/`, { waitUntil: 'networkidle0' });
    await reader.waitForSelector('[name="receipt"]', { visible: true });
    await reader.type('[name="receipt"]', receipt);
    await reader.locator('#ReceiptButton').click();
    await reader.waitForSelector('#TipInfoBox', { visible: true, timeout: 60000 });
    if (!channel) {
      const attachment = new URL('../../.local/imports/browser-synthetic.txt', import.meta.url);
      await writeFile(attachment, 'Synthetic attachment for WBE phase 1 PostgreSQL validation.\n', { mode: 0o600 });
      const upload = await reader.waitForSelector('#TipPageFilesInfoBox input[type="file"]');
      await upload.uploadFile(fileURLToPath(attachment));
      await reader.waitForSelector('#files-action-confirm', { visible: true });
      await reader.locator('#files-action-confirm').click();
      await reader.waitForSelector('[data-cy="progress-bar-complete"]', { visible: true, timeout: 90000 });
    }
    await context.close();
  } finally { await browser.close(); }
});

test('synthetic recipient decrypts and downloads the browser attachment', { skip: !(enabled && (process.env.WBE_E2E_REPORT === '1' || process.env.WBE_E2E_DOWNLOAD === '1')), timeout: 120000 }, async () => {
  const base = process.env.WBE_E2E_URL;
  assert.equal(base, 'http://127.0.0.1:18090');
  const { default: puppeteer } = await import(pathToFileURL(process.env.PUPPETEER_MODULE).href);
  const { readFile, mkdtemp } = await import('node:fs/promises');
  const credentials = JSON.parse(await readFile(new URL('../../.local/secrets/browser-fixture.json', import.meta.url), 'utf8'));
  const downloadDirectory = await mkdtemp(fileURLToPath(new URL('../../.local/imports/browser-download-', import.meta.url)));
  const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true, defaultViewport: { width: 1280, height: 900 }, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    const page = await browser.newPage();
    await page.goto(`${base}/#/login`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('[name="username"]', { visible: true });
    await page.type('[name="username"]', credentials.recipient);
    await page.type('[name="password"]', credentials.password);
    await page.locator('#login-button').click();
    await page.waitForFunction(() => location.hash.includes('/recipient/'), { timeout: 60000 });
    await page.goto(`${base}/#/recipient/reports`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('#tip-0', { visible: true });
    await page.locator('#tip-0').click();
    await page.waitForSelector('#TipInfoBox', { visible: true });
    await page.waitForFunction(() => document.querySelector('#fileListBody')?.textContent.includes('browser-synthetic.txt'), { timeout: 60000 });
    const cdp = await page.createCDPSession();
    await cdp.send('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: downloadDirectory });
    await page.locator('.tip-action-download-file').click();
    let content;
    for (let attempt = 0; attempt < 100; attempt++) {
      try { content = await readFile(`${downloadDirectory}/browser-synthetic.txt`, 'utf8'); break; }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.equal(content, 'Synthetic attachment for WBE phase 1 PostgreSQL validation.\n');
  } finally { await browser.close(); }
});
