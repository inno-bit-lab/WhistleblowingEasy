describe("admin configure mail", function() {
  it("should configure mail", async function() {
    await browser.gl.utils.login_admin();
    await browser.setLocation("admin/mail");

    expect(await element(by.model("resources.notification.tip_expiration_threshold")).getAttribute("value")).toEqual("72");

    await element(by.model("resources.notification.tip_expiration_threshold")).clear();
    await element(by.model("resources.notification.tip_expiration_threshold")).sendKeys("24");

    // save settings
    await element(by.css("[data-ng-click=\"Utils.update(resources.notification)\"]")).click();
    expect(await element(by.model("resources.notification.tip_expiration_threshold")).getAttribute("value")).toEqual("24");
  });
});