const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.resolve(__dirname, '../app/src/pages/whistleblower/whistleblower-submission.service.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, experimentalDecorators: true}}).outputText;
const exportsObject = {};
vm.runInNewContext(compiled, {exports: exportsObject, require: () => ({Injectable: () => target => target})});
const service = new exportsObject.WhistleblowerSubmissionService();
for (const channelLanding of [true, false]) {
  const calls = [];
  const scope = {
    navigation: 0,
    questionnaire: {steps: [{enabled: true}, {enabled: true}]},
    answers: {}, submission: {},
    firstStepIndex: () => 0, lastStepIndex: () => 1,
    hasPreviousStep() {return this.navigation > 0;},
    hasNextStep() {return this.navigation < 1;},
    runValidation: () => true,
    fieldUtilitiesService: {onAnswersUpdate() {}, isFieldTriggered: () => true},
    utilsService: {scrollToTop() {calls.push('legacy');}}
  };
  if (channelLanding) scope.scrollToReportForm = () => calls.push('channel');
  service.incrementStep(scope);
  assert.equal(scope.navigation, 1);
  service.decrementStep(scope);
  assert.equal(scope.navigation, 0);
  scope.runValidation = () => false;
  service.incrementStep(scope);
  assert.equal(scope.navigation, 0);
  assert.deepEqual(calls, Array(3).fill(channelLanding ? 'channel' : 'legacy'));
}
console.log('Submission navigation: channel and additional questionnaire passed');
