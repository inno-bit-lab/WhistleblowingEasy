# -*- coding: utf-8 -*-
from twisted.internet.defer import inlineCallbacks, succeed

from globaleaks import models
from globaleaks.jobs.delivery import Delivery
from globaleaks.jobs.notification import Notification
from globaleaks.tests import helpers


class TestNotification(helpers.TestGLWithPopulatedDB):
    @inlineCallbacks
    def setUp(self):
        yield helpers.TestGLWithPopulatedDB.setUp(self)
        yield self.perform_full_submission_actions()

    @inlineCallbacks
    def test_notification_success(self):
        yield self.test_model_count(models.Mail, 2)

        yield Delivery().run()

        notification = Notification()
        notification.skip_sleep = True
        yield notification.run()

        yield self.test_model_count(models.Mail, 0)

    @inlineCallbacks
    def test_notification_failure(self):
        yield self.test_model_count(models.Mail, 2)

        yield Delivery().run()

        notification = Notification()
        notification.skip_sleep = True

        def sendmail_failure(_):
            # simulate the failure just returning with no action
            return succeed(None)

        notification.sendmail = sendmail_failure

        for _ in range(10):
            yield notification.run()
            yield self.test_model_count(models.Mail, 2 + 24)

        yield notification.run()

        yield self.test_model_count(models.Mail, 0)
