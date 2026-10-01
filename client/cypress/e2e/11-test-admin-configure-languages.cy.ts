describe("admin configure languages", () => {
  it("should configure languages", () => {
    cy.login_admin();
    cy.visit("/#/admin/settings");
    cy.get('[data-cy="languages"]').click();
    cy.get(".add-language-btn").click();

    if (Cypress.env('language')!=="en") {
      cy.get("body").click("top");
      cy.get('ng-select').last().click();
      cy.get('div.ng-option').contains('English [en]').click();
      cy.get('ul.selection-list li').should('contain', 'English [en]');
    }

    if (Cypress.env('language')!=="it") {
      cy.get("body").click("top");
      cy.get('ng-select').last().click();
      cy.get('div.ng-option').contains('Italian [it]').click();
      cy.get('ul.selection-list li').should('contain', 'Italian [it]');
    }

    if (Cypress.env('language')!=="de") {
      cy.get("body").click("top");
      cy.get('ng-select').last().click();
      cy.get('div.ng-option').contains('German [de]').click();
      cy.get('ul.selection-list li').should('contain', 'German [de]');
    }

    cy.intercept("PUT", "**/api/admin/node").as("saveLanguages");
    cy.get("#save_language").click();
    cy.wait("@saveLanguages").its("response.statusCode").should("eq", 202);

    // Saving languages reloads the settings route through /blank. Wait for
    // the default tab to return before starting the language switch reload.
    cy.get('[name="node.dataModel.header_title_homepage"]').should("be.visible");
    cy.waitForUrl("/#/admin/settings");
    cy.get('#LanguagePickerBox [data-cy="it"]').should('be.visible').click().should('have.attr', 'aria-pressed', 'true');
    cy.get('html').should('have.attr', 'lang', 'it');
    cy.waitForUrl("/#/admin/settings");
    cy.get('[name="node.dataModel.header_title_homepage"]').should('be.visible').and('have.value', '').clear().type("TEXT1_IT").should('have.value', 'TEXT1_IT');
    cy.get('[name="node.dataModel.presentation"]').should('be.visible').and('have.value', '').clear().type("TEXT2_IT").should('have.value', 'TEXT2_IT');
    cy.get('button.btn.btn-primary').eq(0).get("#save_settings").click();

    cy.logout();
  });
});

describe("Whistleblower Navigate Home Page in EN", () => {
  it("should see page properly internationalized", () => {

    cy.visit("/#/?lang=en");
    cy.get('html').should('have.attr', 'lang', 'en');
    cy.get('div').should('not.contain', 'TEXT1_IT');
    cy.get('div').should('not.contain', 'TEXT2_IT');
  });
});

describe("Whistleblower Navigate Home Page in IT", () => {
  it("should see page properly internationalized", () => {
    cy.visit("/#/?lang=it");
    cy.get('html').should('have.attr', 'lang', 'it');
    cy.get("#PageTitle").should("contain", "TEXT1_IT");
    cy.get(".kronos-presentation").should("contain", "TEXT2_IT");
  });
});

describe("admin configure languages", () => {
  it("should reset internationalization texts", () => {
    cy.login_admin();

    cy.waitForUrl("/#/admin/home");
    cy.visit("/#/admin/settings");
    cy.get('#ngb-nav-6').should('be.visible')
    cy.get('#LanguagePickerBox [data-cy="it"]').should('be.visible').click().should('have.attr', 'aria-pressed', 'true');
    cy.get('html').should('have.attr', 'lang', 'it');
    cy.get('[name="node.dataModel.header_title_homepage"]').should('be.visible').and('have.value', 'TEXT1_IT').clear().should('have.value', '');
    cy.get('[name="node.dataModel.presentation"]').should('be.visible').and('have.value', 'TEXT2_IT').clear().should('have.value', '');
    cy.get('button.btn.btn-primary').eq(0).get("#save_settings").click();

    cy.logout();
  });
});
