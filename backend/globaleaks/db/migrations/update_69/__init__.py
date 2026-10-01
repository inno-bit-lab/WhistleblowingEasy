import re
import unicodedata
from sqlalchemy.orm import declared_attr
from sqlalchemy.schema import ForeignKeyConstraint
from globaleaks.models import Model
from globaleaks.models.properties import Column, UnicodeText, Integer, Boolean, JSON
from globaleaks.utils.utility import uuid4
from globaleaks.db.migrations.update import MigrationBase

class Context_v_68(Model):
    """
    This model keeps track of contexts settings.
    """
    __tablename__ = 'context'

    id = Column(UnicodeText(36), primary_key=True, default=uuid4)
    tid = Column(Integer, default=1, nullable=False)
    show_steps_navigation_interface = Column(Boolean, default=True, nullable=False)
    allow_recipients_selection = Column(Boolean, default=False, nullable=False)
    maximum_selectable_receivers = Column(Integer, default=0, nullable=False)
    select_all_receivers = Column(Boolean, default=True, nullable=False)
    tip_timetolive = Column(Integer, default=90, nullable=False)
    tip_reminder = Column(Integer, default=0, nullable=False)
    name = Column(JSON, default=dict, nullable=False)
    description = Column(JSON, default=dict, nullable=False)
    show_receivers_in_alphabetical_order = Column(Boolean, default=True, nullable=False)
    score_threshold_high = Column(Integer, default=0, nullable=False)
    score_threshold_medium = Column(Integer, default=0, nullable=False)
    questionnaire_id = Column(UnicodeText(36), default='default', nullable=False, index=True)
    additional_questionnaire_id = Column(UnicodeText(36), index=True)
    hidden = Column(Boolean, default=False, nullable=False)
    order = Column(Integer, default=0, nullable=False)

    unicode_keys = [
        'questionnaire_id',
        'additional_questionnaire_id'
    ]

    localized_keys = [
        'name',
        'description'
    ]

    int_keys = [
        'tip_timetolive',
        'tip_reminder',
        'maximum_selectable_receivers',
        'order',
        'score_threshold_high',
        'score_threshold_medium'
    ]

    bool_keys = [
        'hidden',
        'select_all_receivers',
        'show_context',
        'show_receivers_in_alphabetical_order',
        'show_steps_navigation_interface',
        'allow_recipients_selection'
    ]

    list_keys = ['receivers']

    @declared_attr
    def __table_args__(self):
        return (ForeignKeyConstraint(['tid'], ['tenant.id'], ondelete='CASCADE', deferrable=True, initially='DEFERRED'),
                ForeignKeyConstraint(['questionnaire_id'], ['questionnaire.id'], deferrable=True, initially='DEFERRED'))



class MigrationScript(MigrationBase):
    def migrate_Context(self):
        presets = {'8511cdb9-fcce-4889-8bf6-e0492ea0cc16': 'kronos-finance', 'a985e6ea-147c-47d9-baca-7bc955bf8232': 'zeverino', 'ec928d88-f9e4-490e-8d51-97222826c1a6': 'longo-euroservice', 'b7e82a06-11df-404d-8bb3-b388a977a960': 'lama-distribuzione', '448ef625-393f-4da1-a602-a2542eb21e86': 'donato-trasporti', '7c392242-9ccc-4cdf-a132-f90b67f1e8d6': 'test', '1e908330-c085-4494-ad5f-fe6c0e26daa4': 'lagolosadipuglia', '32f2c037-c6cb-4aae-b2de-036d397efe30': 'impresa-resta'}
        used = set()
        for old in self.session_old.query(self.model_from['Context']).order_by(self.model_from['Context'].tid, self.model_from['Context'].id):
            new = self.model_to['Context']()
            for key in old.__mapper__.column_attrs.keys():
                setattr(new, key, getattr(old, key))
            name = old.name.get('it') or old.name.get('en') or next(iter(old.name.values()), '')
            slug = presets.get(old.id) or re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()).strip('-')[:64] or 'channel'
            candidate = slug
            index = 2
            while (old.tid, candidate) in used:
                candidate = slug[:55] + '-' + str(index)
                index += 1
            new.slug = candidate
            used.add((old.tid, candidate))
            self.session_new.add(new)
