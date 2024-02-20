# -*- coding: utf-8 -*-
import re

from globaleaks.utils.agent import get_page


#EXIT_ADDR_URL = b'https://deb.globaleaks.org/app/exit-addresses'
EXIT_ADDR_URL = b'https://check.torproject.org/torbulkexitlist'


class TorExitSet(set):
    """Set that keep the list of Tor exit nodes ip using check.torproject.org"""

    def processData(self, data):
        self.clear()

        # for ip in re.findall(r'ExitAddress ([^ ]*) ', data.decode()):
        #     self.add(ip)
        ip_list = data.decode().strip().split('\n')
        for ip in ip_list:
            self.add(ip)

    def update(self, agent):
        return get_page(agent, EXIT_ADDR_URL).addCallback(self.processData)
