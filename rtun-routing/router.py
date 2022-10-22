import socket
import sys
from socketserver import ThreadingMixIn, TCPServer, StreamRequestHandler
import logging

logging.basicConfig(level=logging.INFO)

ADDRESS = "127.0.0.1"
PORT = 5000

class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    pass


class RoutingService(StreamRequestHandler):

    def handle(self):
        print("Received by TorRouter")

class TorRouter:
    def __init__(self, address, port):
        
        with ThreadingTCPServer((address, port), RoutingService) as server:
            server.serve_forever()

if __name__ == '__main__':
    with ThreadingTCPServer((ADDRESS, PORT), RoutingService) as server:
        server.serve_forever()

