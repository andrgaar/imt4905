import sys
import os
import time
import socket
import select
import pickle
import random
from queue import Queue, Empty
from time import sleep
import threading
from threading import Event, Thread
from selectors import EVENT_READ, DefaultSelector

from torpy.consesus import TorConsensus
from torpy.crypto_state import CryptoState
from torpy.keyagreement import NtorKeyAgreement, FastKeyAgreement
from torpy.guard import TorGuard
from torpy.stream import TorStream
from torpy.circuit import CircuitNode, CircuitsList, CircuitReason
from torpy.cli.socks import SocksServer
from torpy.cells import CellRelayEstablishRendezvous, CellRelayRendezvousEstablished, CellCreate2, CellCreated2, CellRelaySendMe, \
    CellRelay, CellCreateFast, CellCreatedFast, CellRelayRendezvous1, CellRelayBegin, CellRelayData, CellRelayRendezvous2, CellRelayEnd, CellRelayConnected, CellNetInfo, CellDestroy
from torpy.cell_socket import TorCellSocket

import lsr

import logging
logger = logging.getLogger(__name__)

from messages import HelloMessage

MIN_CONNECTION_TTL = 60
MAX_CONNECTION_TTL = 120
GLOBAL_CIRCUIT_ID = 0x81000002

threads = {}

# Class to establish a Rendezvous Point
class RendezvousEstablish(Thread):
    def __init__(self, guard_nick, rendp_nick, rendezvous_cookie, receive_queue, condition=None, timeout=300):
        # execute the base constructor
        Thread.__init__(self)
        # store the values
        self.guard_nick = guard_nick
        self.rendp_nick = rendp_nick
        self.rendezvous_cookie = rendezvous_cookie
        self.receive_queue = receive_queue
        self.conn_queue = Queue()
        self.condition = condition
        self.id = None
        self.name = f"Establish-{self.rendp_nick}"
        self.start_time = None
        self.ALIVE = True
        self.timeout = timeout

    # 
    # Setup a rendezvous point and wait
    #
    def run(self):
        # Add self to thread info
        tid = threading.get_ident()
        self.id = tid
        thread = threading.current_thread()
        threads[tid] = thread

        logger.info(f"Establishing RP to {self.rendp_nick}")
        consensus = TorConsensus()
        guard_router = TorGuard(consensus.get_router_using_nick(self.guard_nick))
        rendp_router = consensus.get_router_using_nick(self.rendp_nick)
        peer_router_ip = "127.0.0.1"
        peer_router_port = 5000

        # Acquire a condition if this is a waiting RP
        if self.condition:
            self.condition.acquire()

        # Build circuit to rendezvous point
        circuit = self.build_circuit(guard_router, [ rendp_router ])
        logger.info(type(circuit))

        # Establish a rendezvous point
        self.establish_rendezvous(circuit, self.rendezvous_cookie)
    
        logger.info("Waiting for connections at relay {0} for cookie {1} ...".format(self.rendp_nick, self.rendezvous_cookie))
        with circuit.create_waiter(CellRelayRendezvous2) as w:
            rendezvous2_cell = w.get(timeout=self.timeout)
            logger.info(f"Got REND2 message from {self.rendp_nick}")
          
        # Here someone has connected - we notify a waiting thread
        if self.condition:
            self.condition.release()

        self.start_time = time.time()

        logger.debug("Derive shared secret with peer")
        extend_node = CircuitNode(rendp_router, key_agreement_cls=FastKeyAgreement)
        shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
        extend_node._crypto_state = CryptoState(shared_sec)
        circuit._circuit_nodes.append(extend_node)

        # Set up streams
        sock_r, sock_w = socket.socketpair()

        events = {TorStream: {'data': Event(), 'close': Event()},
                  socket.socket: {'data': Event(), 'close': Event()}}

        with guard_router as guard:

            def recv_callback(sock_or_stream, mask):
                logger.debug(f'recv_callback {sock_or_stream}')
                kind = type(sock_or_stream)
                data = sock_or_stream.recv(1024)
                logger.debug('%s', kind.__name__)

                if data:
                    events[kind]['data'].set()
                    #Put the received data into the ReceiverThread input queue with circuit data
                    self.receive_queue.put_nowait( [{'data' : data, 
                                            'circuit' : circuit, 
                                            'circuit_id' : circuit.id, 
                                            'stream' : stream, 
                                            'stream_id' : stream.id}]
                                        )
                else:
                    logger.debug('closing')
                    guard.unregister(sock_or_stream)
                    events[kind]['close'].set()

            with circuit as c:

                logger.info("Entered circuit context with id " + hex(c.id))

                with c.create_stream((peer_router_ip, peer_router_port)) as stream:
                    
                    #logger.info("Entered stream context with id " + hex(stream.id))

                    def recv_stream_callback(event):
                        logger.debug(f"Receive callback event: {event}")
                        data_str = stream._buffer.decode('utf-8')
                        logger.debug(f"Data: {data_str}")
        
                    logger.info(f"Sending HELLO to peer")
                    # Send a HELLO message to the other side
                    hello_msg = HelloMessage( lsr.global_router['RID'] ) 
                    hello_data = [{'Message' : 'HELLO', 'Peer' : lsr.global_router['RID']}]
                    hello_data = pickle.dumps(hello_data)
                    logger.info(f"Sending HELLO to peer: {hello_data}")
                    stream.send(hello_data)

                    while self.ALIVE:
                        cq = None
                        try:
                            cq = self.conn_queue.get_nowait()
                        except Empty:
                            pass
                        if cq:
                            # drop this connection
                            logger.info(f"Received CLOSE - closing connection thread ID {self.id}")
                            data = pickle.dumps([{'Message' : 'CLOSE', 'Thread ID' : self.id}])
                            self.ALIVE = False
                            return
                        else:
                            try:
                                data = stream.recv(1024)
                            except Exception as e:
                                logger.error(e)
                                logger.info(f"Closing connection {self.name}")  
                                # clean up
                                threads.pop(self.id, 'No thread key found')
                                return
                        
                        # put the received data into the ReceiverThread input queue with circuit data
                        self.receive_queue.put_nowait( [{'data' : data, 
                                                'circuit' : circuit, 
                                                'circuit_id' : circuit.id, 
                                                'stream' : stream, 
                                                'stream_id' : stream.id,
                                                'receive_node' : None,
                                                'extend_node' : None,
                                                'receive_socket' : None,
                                                'rendpoint' : self.rendp_nick,
                                                'thread_id' : self.id
                                                }]
                                            )
                    
                    logger.info(f"Closing connection {self.name}")  
                    return

    def build_circuit(self, guard_router, extend_routers): # returns Circuit
        # Build a circuit OP->Guard->RendPoint
        circuit =  guard_router.create_circuit(hops_count=-1, extend_routers=extend_routers)

        circuit_hex = hex(circuit.id)
        logger.debug(f"Built circuit to {extend_routers} with ID {circuit_hex}")

        return circuit
                
    def establish_rendezvous(self, circuit, rendezvous_cookie):
        # Establish a rendezvous point
        circuit._rendezvous_establish(rendezvous_cookie)

    def get_start_time(self):
        return self.start_time

    def close(self):
        self.ALIVE = False


# Client side class connecting to a rendezvous point
class RendezvousConnect(Thread):

    def __init__(self, rendp_nick, cookie, my_id, receive_queue):
        # execute the base constructor
        Thread.__init__(self)
        # store the values
        self.rendp_nick = rendp_nick
        self.rendezvous_cookie = cookie
        self.my_id = my_id
        self.receive_queue = receive_queue
        self.id = None
        self.start_time = None
        self.name = f"Connect-{self.rendp_nick}"
        self.ALIVE = True
        self.attempts = 12 # num of attempts to connect to RP

    def run(self):
        # Add self to thread info
        tid = threading.get_ident()
        self.id = tid
        thread = threading.current_thread()
        threads[tid] = thread

        # Try to connect to rendezvous point - restart on failure
        while True:
            try:
                logger.info("Calling connect_to_rendezvous_point")
                rcv_sock, rcv_cn, circuit_id = self.connect_to_rendezvous_point(self.rendp_nick, self.rendezvous_cookie)

                logger.debug("Derive shared secret")
                extend_node = CircuitNode("a")
                shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
                extend_node._crypto_state = CryptoState(shared_sec)

                logger.info("Waiting for peer to open stream")
                while True:
                    try:
                        b = rcv_sock.recv_cell()
                        if b:
                            logger.info("Received cell: " + str(type(b)))
                            if isinstance(b, CellDestroy):
                                logger.debug("Received CellDestroy reason: " + str(b.reason))
                                raise Exception("Receive CellDestroy from RP")
                            else:
                                break
                    except socket.timeout:
                        continue

            except KeyboardInterrupt:
                logger.info("Caught keyboard interrupt, exiting...")
                raise KeyboardInterrupt

            except Exception as e:
                if self.attempts == 0:
                    logger.warn(f"Could not connect to rendezvous point {self.rendp_nick}: {e}, exiting...")
                    # clean up
                    threads.pop(self.id, 'No thread key found')
                    return

                self.attempts -= 1
                logger.warn(f"Could not connect to rendezvous point {self.rendp_nick}: {e}, {self.attempts} attempts left...")
                time.sleep(5)
                continue
            break # break and continue

        logger.debug("Decrypting cells")
        rcv_cn.decrypt_backward(b)
        extend_node.decrypt_backward(b)
        cellbegin = b.get_decrypted()
        stream_id = b.stream_id
        logger.debug("CellRelay received, stream_id: " + str(stream_id))
        logger.debug(cellbegin.address)
        logger.debug(cellbegin.port)

        inner_cell = CellRelayConnected("127.0.0.1", 6000, circuit_id)
        relay_cell = CellRelay(inner_cell, stream_id=stream_id, circuit_id=circuit_id, padding=None)
        extend_node.encrypt_forward(relay_cell)
        rcv_cn.encrypt_forward(relay_cell)
        rcv_sock.send_cell(relay_cell)
        logger.info("Stream opened successfully")

        # Send a HELLO message to the other side
        hello_msg = HelloMessage( lsr.global_router['RID'] ) 
        #hello_data = pickle.dumps(hello_msg)
        hello_data = [{'Message' : 'HELLO', 'Peer' : lsr.global_router['RID']}]
        hello_data = pickle.dumps(hello_data)
        logger.info(f"Sending HELLO to peer: {hello_data}")
        snd_data(hello_data, circuit_id, extend_node, rcv_cn, rcv_sock, stream_id)

        self.start_time = time.time()

        while self.ALIVE:
            try:
                r, w, _ = select.select([rcv_sock.ssl_socket], [], [])
                if rcv_sock.ssl_socket in r:
                    buf = rcv_data(rcv_sock, rcv_cn, extend_node)

                    if buf == 404: # SENDME
                        continue
                    if buf == "RELAY_END" or buf == "DESTROY": # RELAY_END, DESTROY
                        logger.error(f"Got {buf}")
                        break

                    if buf == 503: # DESTROY
                        logger.error("Got DESTROY")
                        sys.exit()
                    if len(buf) == 0:
                        break
                    
                    #Put the received data into the ReceiverThread input queue with circuit data
                    self.receive_queue.put_nowait( [{'data' : buf, 
                                                'circuit' : None, 
                                                'circuit_id' : circuit_id, 
                                                'stream' : None, 
                                                'stream_id' : stream_id,
                                                'receive_node' : rcv_cn,
                                                'extend_node' : extend_node,
                                                'receive_socket' : rcv_sock,
                                                'rendpoint' : self.rendp_nick,
                                                'thread_id' : self.id
                                                }]
                                        )                

            except Exception as e:
                logger.error("Error in receive on socket: " + str(e))
                continue
        
        inner_cell = CellDestroy(CircuitReason.FINISHED, circuit_id)
        relay_cell = CellRelay(inner_cell, stream_id=0, circuit_id=circuit_id)
        rcv_cn.encrypt_forward(relay_cell)
        rcv_sock.send_cell(relay_cell)

        # clean up
        threads.pop(self.id, 'No thread key found')
        return

    #
    # Connect to a rendezvous point with one-hop to rendezvous
    #
    def connect_to_rendezvous_point(self, nick, cookie, circuit_id=0x80000002):
        logger.info("Connect to rendezvous point " + nick)
        global GLOBAL_CIRCUIT_ID
        
        consensus = TorConsensus()
        router = consensus.get_router_using_nick(nick)

        tor_cell_socket = TorCellSocket(router)
        tor_cell_socket.connect()

        circuit_id = GLOBAL_CIRCUIT_ID
        GLOBAL_CIRCUIT_ID += 1

        logger.debug("Key agreement")
        if False:
            key_agreement_cls = NtorKeyAgreement
            create_cls = partial(CellCreate2, key_agreement_cls.TYPE)
            created_cls = CellCreated2
        else:
            key_agreement_cls = FastKeyAgreement
            create_cls = CellCreateFast
            created_cls = CellCreatedFast

        circuit_node = CircuitNode(router, key_agreement_cls=key_agreement_cls)
        onion_skin = circuit_node.create_onion_skin()
        cell_create = create_cls(onion_skin, circuit_id)
        tor_cell_socket.send_cell(cell_create)
        cell_created = tor_cell_socket.recv_cell()
        logger.debug('Complete handshake..."')
        circuit_node.complete_handshake(cell_created.handshake_data)


        logger.debug("Cell created circuit ID: " + str(cell_created.circuit_id))
        circuit_node.complete_handshake(cell_created.handshake_data)
        inner_cell = CellRelayRendezvous1(os.urandom(128+20), cookie, cell_created.circuit_id)
        relay_cell = CellRelay(inner_cell, stream_id=0, circuit_id=circuit_id)
        circuit_node.encrypt_forward(relay_cell)
        tor_cell_socket.send_cell(relay_cell)
        logger.debug("Sent cookie")

        logger.info("Connected to rendezvous point " + nick)

        return tor_cell_socket, circuit_node, circuit_id

    def get_start_time(self):
        return self.start_time
    
    def close(self):
        self.ALIVE = False
#
# Receive data on socket created for rendezvous point
#    
def rcv_data(rcv_sock, rcv_cn, extend_node):
    b = rcv_sock.recv_cell()
    logger.debug("rcv cell: " + str(type(b)))
    if isinstance(b, CellDestroy):
        return "DESTROY"
    
    rcv_cn.decrypt_backward(b)
    extend_node.decrypt_backward(b)

    cellrelaydata = b.get_decrypted()
    if isinstance(cellrelaydata, CellRelayEnd):
        return "RELAY_END"
    elif isinstance(cellrelaydata, CellRelaySendMe):
        logger.warning("Got SENDME")
        return 404
    else:
        #print("Got " + str(type(cellrelaydata)))
        pass

    return cellrelaydata.data

#
# Send data on socket created for rendezvous point
#    
def snd_data(rsp, circuit_id, extend_node, rcv_cn, rcv_sock, stream_id=0):
    logger.debug(f"Sending cell: {rsp} to {circuit_id}")
    inner_cell = CellRelayData(rsp, circuit_id)
    relay_cell = CellRelay(inner_cell, stream_id=stream_id, circuit_id=circuit_id, padding=None)
    
    try:
        extend_node.encrypt_forward(relay_cell)
        rcv_cn.encrypt_forward(relay_cell)
        rcv_sock.send_cell(relay_cell)
    except Exception as e:
        logger.error(f"snd_data: {e}")



