# Implementation of health status resource
from globaleaks.handlers.base import BaseHandler


class HealthStatusHandler(BaseHandler):
    """
    Handler that implements health status checks
    """
    check_roles = 'any'

    def get(self):
        """
        Get the health status
        """
        from globaleaks.orm import is_postgresql
        if is_postgresql():
            from globaleaks.orm import tw
            def check(session):
                from sqlalchemy import text
                session.execute(text('SELECT 1'))
                return "OK"
            return tw(check)
        return "OK"
