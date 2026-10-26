# Handler exposing application files
import os

from globaleaks import get_language_direction, to_bcp47
from globaleaks.handlers.base import BaseHandler
from globaleaks.utils.fs import directory_traversal_check


class StaticFileHandler(BaseHandler):
    check_roles = 'any'
    allowed_mimetypes = [
        'text/css',
        'text/html',
        'text/javascript'
    ]

    def __init__(self, state, request):
        BaseHandler.__init__(self, state, request)

        self.root = "%s%s" % (os.path.abspath(state.settings.client_path), "/")

    def get(self, filename):
        if self.state.settings.separate_frontend:
            self.request.setHeader(b'X-WBE-Frontend', b'1')
            # Internal representation contract: the FE renders/streams files from
            # its own bind mount. Tenant, language and security policy remain here.
            return {'wbe_frontend': 1, 'filename': filename or 'index.html',
                    'language': to_bcp47(self.request.language),
                    'direction': get_language_direction(self.request.language),
                    'nonce': self.request.nonce.decode('ascii')}
        abspath = os.path.abspath(os.path.join(self.root, filename))
        directory_traversal_check(self.root, abspath)

        if filename == '':
            with open(os.path.join(abspath, 'index.html'), 'rb') as f:
                data = f.read()
                data = data.replace(b'lang="en"', b'lang="' + to_bcp47(self.request.language).encode() + b'"')
                data = data.replace(b'dir="ltr"', b'dir="' + get_language_direction(self.request.language).encode() + b'"')
                data = data.replace(b'randomCspNonce', self.request.nonce)
                self.request.write(data)
                return

        return self.write_file(filename, abspath)
