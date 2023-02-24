# 
# rtun-messages.py
#
# Defines application protocol messages exchanged in the routing and data channels
#
class HelloMessage:

    NUM = 1

    def __init__(self, peer_id):

        self.peer_id = peer_id

    def __str__(self):

        return f"HELLO: {self.peer_id}"
