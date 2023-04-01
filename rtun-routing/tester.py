import sys
import json
import random
import time
from threading import Thread

import lsr

import logging
logger = logging.getLogger(__name__)

# Class to establish a Rendezvous Point
class RtunTest(Thread):
    def __init__(self):
        # execute the base constructor
        Thread.__init__(self)

        self.setName(f"TESTER")

    # 
    # Run test
    #
    def run(self):
        # Pick random vertex from graph to send a LOOKUP
        # e.g. [['P2', 'P3', 364, 'TERRAHOSTrocks'], ['P1', 'P2', 126, 'SidRelay']]
        logger.info("Started tester")
        my_id = lsr.global_router['RID']
        
        while True:
            peers = set()
            edges = lsr.graph
            for e in edges:
                peers.add(e[0])
                peers.add(e[1])

            for peer in peers:
                if peer == my_id:
                    continue
                ms = lsr.current_milli_time()
                route = None
                try:
                    route = lsr.shortest_paths[peer].copy()
                    route.pop(0)
                except Exception:
                    pass
                message = [{'Message' : 'LOOKUP', 'Destination' : peer, 'Source' : my_id, "ID": ms, 'Route': route, 'Path' : [my_id]}]
                try:
                    relay_hop = lsr.route_message(message)
                    #lsr.log_metrics("LOOKUP SENT", json.dumps( {'Peer':peer, 'ID': ms, 'Relay':relay_hop} )) 
                    lsr.log_queue.put_nowait( message )
                except Exception as e:
                    logger.error(e)
            
            time.sleep(random.randint(5,10))

