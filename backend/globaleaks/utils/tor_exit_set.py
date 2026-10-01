import ipaddress

from globaleaks.utils.agent import get_page


EXIT_ADDR_URL = b'https://check.torproject.org/torbulkexitlist'


class TorExitSet(set):
    """Set that keep the list of Tor exit nodes ip using check.torproject.org"""

    def processData(self, data):
        addresses = set()
        for line in data.decode().splitlines():
            try:
                addresses.add(str(ipaddress.ip_address(line.strip())))
            except ValueError:
                continue
        self.clear()
        super().update(addresses)

    def update(self, agent):
        return get_page(agent, EXIT_ADDR_URL).addCallback(self.processData)
