
from twisted.internet.defer import inlineCallbacks

from globaleaks.handlers.admin import context
from globaleaks.handlers.base import BaseHandler
from globaleaks.models import Context
from globaleaks.rest import errors
from globaleaks.tests import helpers


class TestContextsCollection(helpers.TestCollectionHandler):
    _handler = context.ContextsCollection
    _test_desc = {
        'model': Context,
        'create': context.create_context,
        'data': {
            'tip_timetolive': 100
        }
    }


class TestContextInstance(helpers.TestInstanceHandler):
    _handler = context.ContextInstance
    _test_desc = {
        'model': Context,
        'create': context.create_context,
        'data': {
            'tip_timetolive': 100
        }
    }

    @inlineCallbacks
    def test_delete_requires_confirmation(self):
        self.patch(BaseHandler, 'check_confirmation', BaseHandler.real_check_confirmation)

        data = self.get_dummy_request()
        data = yield self._test_desc['create'](1, self.session, data, 'en')

        handler = self.request(data, role='admin')

        self.assertRaises(errors.InvalidAuthentication, handler.delete, data['id'])

    @inlineCallbacks
    def test_delete_with_confirmation(self):
        self.patch(BaseHandler, 'check_confirmation', BaseHandler.real_check_confirmation)

        confirmation = helpers.VALID_CONFIRMATION

        data = self.get_dummy_request()
        data = yield self._test_desc['create'](1, self.session, data, 'en')

        handler = self.request(data, role='admin', headers={'x-confirmation': confirmation})

        yield handler.delete(data['id'])


class TestChannelSlugs(helpers.TestGLWithPopulatedDB):
    @inlineCallbacks
    def test_slug_unique_and_clearable(self):
        request = dict(self.dummyContext)
        request['id'] = ''
        request['slug'] = 'test-company'
        first = yield context.create_context(1, None, request, 'en')
        self.assertEqual(first['slug'], 'test-company')
        second = dict(self.dummyContext)
        second['id'] = ''
        second['slug'] = 'test-company'
        yield self.assertFailure(context.create_context(1, None, second, 'en'), errors.InputValidationError)
        first['slug'] = ''
        cleared = yield context.update_context(1, first['id'], first, 'en')
        self.assertEqual(cleared['slug'], '')
        created = yield context.create_context(1, None, second, 'en')
        self.assertEqual(created['slug'], 'test-company')

    @inlineCallbacks
    def test_reject_invalid_slug(self):
        for slug in ['Azienda', 'two words', '../admin', '-company', 'company-', 'a' * 65]:
            request = dict(self.dummyContext)
            request['slug'] = slug
            yield self.assertFailure(context.create_context(1, None, request, 'en'), errors.InputValidationError)
