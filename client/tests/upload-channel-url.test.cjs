const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const ts = require('typescript');
const source = fs.readFileSync(path.resolve(__dirname, '../app/src/shared/services/utils.service.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, experimentalDecorators: true}}).outputText;
const exportsObject = {};
vm.runInNewContext(compiled, {exports: exportsObject, require: () => ({Injectable: () => target => target})});

for (const target of ['api/whistleblower/submission/attachment', 'api/whistleblower/wbtip/wbfiles', 'api/recipient/rtips/report-id/rfiles', '/t/2/api/whistleblower/submission/attachment']) {
 test(`upload URL and DPoP remain aligned from a channel document: ${target}`, async () => {
  const proofs = [];
  const service = {authenticationService: {session: {id: 'synthetic-session'}}, cryptoService: {generateDpopProof: async (...args) => {proofs.push(args); return 'synthetic-proof';}}};
  const options = exportsObject.UtilsService.prototype.getFlowOptions.call(service, {target});
  const expected = target.startsWith('/') ? target : '/' + target;
  for (const base of ['http://localhost:18090/', 'http://localhost:61626/channel/report', 'http://localhost:61626/channel/report/']) {
   assert.equal(new URL(options.target, base).pathname, expected);
  }
  const chunk = {fileObj: {flowObj: {opts: options}}};
  await new Promise(resolve => {chunk.preprocessFinished = resolve; options.preprocess(chunk);});
  assert.equal(proofs.length, 1);
  assert.equal(proofs[0][0], 'POST');
  assert.equal(proofs[0][1], expected.replace(/^\/t\/[^/]+/, ''));
  assert.equal(options.headers(null, chunk).DPoP, 'synthetic-proof');
  assert.equal(options.headers(null, chunk)['X-Session'], 'synthetic-session');
  assert.equal(options.maxChunkRetries, 0);
 });
}
