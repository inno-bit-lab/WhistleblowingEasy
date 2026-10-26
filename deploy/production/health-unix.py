import socket
import http.client
connection = http.client.HTTPConnection('localhost', timeout=4)
connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
connection.sock.settimeout(4)
connection.sock.connect('/run/wbe-proxy/web.sock')
connection.request('GET', '/api/health')
response = connection.getresponse()
if response.status != 200:
    raise SystemExit(1)
response.read()
connection.close()
