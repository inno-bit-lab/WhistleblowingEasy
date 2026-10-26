"""Portable recipient-list regression tests; isolated in-memory SQLite only."""
import datetime
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from globaleaks import models
from globaleaks.handlers.recipient import get_receivertips


class RecipientListQueryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        self.addCleanup(self.engine.dispose)
        models.Base.metadata.create_all(self.engine)
        self.session = Session(bind=self.engine)
        self.addCleanup(self.session.close)
        self.date = datetime.datetime(2026, 1, 1)
        self.session.execute(models.Context.__table__.insert().values(id='channel', tid=1))
        self.session.execute(models.ReceiverContext.__table__.insert().values(
            context_id='channel', receiver_id='recipient'))
        self.session.execute(models.InternalTip.__table__.insert().values(
            id='report', tid=1, context_id='channel', receipt_hash='synthetic', label='label',
            creation_date=self.date, update_date=self.date))
        # Another recipient deliberately inserted first; own access must win.
        for recipient in ['other', 'recipient']:
            self.session.execute(models.ReceiverTip.__table__.insert().values(
                id='rtip-' + recipient, internaltip_id='report', receiver_id=recipient))
        # Reverse insertion/hash ordering catches arbitrary GROUP BY selection.
        for name, offset in [('aaa-later', 1), ('zzz-initial', 0)]:
            self.session.execute(models.InternalTipAnswers.__table__.insert().values(
                internaltip_id='report', questionnaire_hash=name,
                creation_date=self.date + datetime.timedelta(days=offset),
                answers={'selected': name}))
        self.session.execute(models.InternalTipData.__table__.insert().values(
            internaltip_id='report', key='whistleblower_identity', creation_date=self.date,
            value={'synthetic': True}))
        self.session.flush()

    def test_first_questionnaire_single_report_access_and_subscription(self):
        compiled = []
        def capture(conn, clause, multiparams, params, execution_options):
            compiled.append(str(clause.compile(dialect=postgresql.dialect())))
        event.listen(self.engine, 'before_execute', capture)
        with patch('globaleaks.handlers.recipient.db_user_can_bypass_masking', return_value=True):
            rows = get_receivertips.method(self.session, 1, 'recipient', None, 'en')
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['accessible'])
        self.assertEqual(rows[0]['answers'], {'selected': 'zzz-initial'})
        self.assertEqual(rows[0]['receiver_count'], 2)
        self.assertEqual(rows[0]['subscription'], 1)
        main = next(sql for sql in compiled if 'SELECT receivertip.id ' in sql)
        self.assertNotIn('GROUP BY', main)
        self.assertIn('LIMIT', main)

    def test_channel_visibility_does_not_expose_unassigned_answers(self):
        self.session.execute(models.ReceiverTip.__table__.delete().where(
            models.ReceiverTip.receiver_id == 'recipient'))
        with patch('globaleaks.handlers.recipient.db_user_can_bypass_masking', return_value=True):
            rows = get_receivertips.method(self.session, 1, 'recipient', None, 'en')
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['accessible'])
        self.assertEqual(rows[0]['answers'], '')
        self.assertEqual(rows[0]['label'], '')


if __name__ == '__main__':
    unittest.main()
