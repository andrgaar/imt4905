import sys
import json
import random
import time
import networkx as nx
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
        
        with open('sent.log', 'w') as f:
            f.write("Timestamp;Peer;ID;Destination;Route\n")
        
        while True:
            peers = set()
            edges = lsr.graph
            for e in edges:
                peers.add(e[0])
                peers.add(e[1])

            if not lsr.G:
                continue
            try:
                paths = list(nx.shortest_simple_paths(lsr.G, 'P1', 'P5'))
            except Exception:
                paths = []

            for path in paths:
                peer = 'P5'
            #for peer in peers:
                #if peer != 'P1':
                #    continue
                #if peer == my_id:
                #    continue
                ms = my_id + "_" + str(lsr.current_milli_time())
                route = path
                #route.pop(0) # remove ref to self
                #try:
                #    route = lsr.shortest_paths[peer].copy()
                #    route.pop(0)
                #except Exception:
                #    pass
                message = [{'Message' : 'LOOKUP', 'Destination' : peer, 'Source' : my_id, 'TTL': 5, 'ID': ms, 'Route': route, 'Path' : [my_id]}]
                try:
                    relay_hop = lsr.route_message(message)
                    with open('sent.log', 'a') as f:
                        f.write(';'.join([str(lsr.current_milli_time()), my_id, ms, peer, str(route)]))
                        f.write("\n")
                    lsr.log_queue.put_nowait( message )
                except Exception as e:
                    logger.error(e)
            
            time.sleep(random.randint(5,5))

