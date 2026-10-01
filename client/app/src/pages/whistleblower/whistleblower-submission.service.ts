import {Injectable} from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class WhistleblowerSubmissionService {
  constructor() { }

  private scrollToForm(scope: any): void {
    if (typeof scope.scrollToReportForm === 'function') {
      scope.scrollToReportForm();
    } else {
      // Additional questionnaires also use this service, outside the channel landing.
      scope.utilsService.scrollToTop();
    }
  }

  checkForInvalidFields(scope:any) {
    let enabled_counter = 0;
    for (let counter = 0; counter <= scope.navigation; counter++) {
      scope.validate[counter] = true;
      if (scope.questionnaire.steps[counter].enabled) {
        if (scope.stepForms.get(enabled_counter)?.invalid) {
          scope.navigation = counter;
          return false;
        }
	enabled_counter++;
      }
    }
    return true;
  }

  decrementStep(scope:any) {
    if (!scope.hasPreviousStep()) {
      return;
    }

    for (let i = scope.navigation - 1; i >= scope.firstStepIndex(); i--) {
      if (i === -1 || scope.fieldUtilitiesService.isFieldTriggered(null, scope.questionnaire.steps[i], scope.answers, scope.identity_provided, false)) {
        scope.navigation = i;
        this.scrollToForm(scope);
        return;
      }
    }
  }

  incrementStep(scope:any) {
    if (!scope.hasNextStep()) {
      return;
    }

    scope.fieldUtilitiesService.onAnswersUpdate(scope);

    if (!scope.runValidation()) {
      this.scrollToForm(scope);
      return;
    }

    for (let i = scope.navigation + 1; i <= scope.lastStepIndex(); i++) {
      if (scope.fieldUtilitiesService.isFieldTriggered(null, scope.questionnaire.steps[i], scope.answers, scope.submission.identity_provided, false)) {
        scope.navigation = i;
        this.scrollToForm(scope);
        return;
      }
    }
  }
}
