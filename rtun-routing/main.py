import os
import sys
import socket
from functools import partial
from torpy import TorClient
import logging
from torpy.cell_socket import TorCellSocket
from torpy.cells import CellRelayEstablishRendezvous, CellRelayRendezvousEstablished, CellCreate2, CellCreated2, \
    CellRelay, CellCreateFast, CellCreatedFast, CellRelayRendezvous1, CellRelayBegin, CellRelayData, CellRelayRendezvous2, CellRelayEnd, CellRelayConnected, CellNetInfo
from torpy.circuit import CircuitNode, CircuitsList
from torpy.cli.socks import SocksServer
from torpy.consesus import TorConsensus
from torpy.crypto_state import CryptoState
from torpy.keyagreement import NtorKeyAgreement, FastKeyAgreement
from torpy.guard import TorGuard
from torpy.stream import TorStream

import server
from messages import HelloMessage
import lsr
from lsr import HeartBeatThread, ReceiveThread, SendThread
import pickle

import threading
from threading import Event
from selectors import EVENT_READ, DefaultSelector
import time

from queue import Queue

logger = logging.getLogger(__name__)

# Queue to communicate with ReceiveThread
rcv_queue = Queue()

def setup_router(router_id, router_port):
    
    # 
    # Initialize the router
    # 
    lsr.init_router(router_id, router_port)

    receiver_thread = ReceiveThread("RECEIVER", rcv_queue, lsr.threadLock)
    sender_thread = SendThread("SENDER", lsr.threadLock)

    HB_message = [{'RID' : lsr.global_router['RID']}]
    heartbeat_thread = HeartBeatThread("HEART BEAT", HB_message, lsr.threadLock)
                
    receiver_thread.start()
    sender_thread.start()
    heartbeat_thread.start()
                
    lsr.threads.append(receiver_thread)
    lsr.threads.append(sender_thread)
    lsr.threads.append(heartbeat_thread)


def build_circuit(guard_router, extend_routers): # returns Circuit
    # Build a circuit OP->Guard->RendPoint
    circuit =  guard_router.create_circuit(hops_count=-1, extend_routers=extend_routers)

    circuit_hex = hex(circuit.id)
    logger.debug(f"Built circuit to {extend_routers} with ID {circuit_hex}")

    return circuit
            
def establish_rendezvous(circuit, rendezvous_cookie):
    # Establish a rendezvous point
    circuit._rendezvous_establish(rendezvous_cookie)


def setup_rendezvous2(guard_nick, rendp_nick, rendezvous_cookie, port_num, peer_id, peer_router_addr):
    # Setup a rendezvous point and wait
    consensus = TorConsensus()
    guard_router = TorGuard(consensus.get_router_using_nick(guard_nick))
    rendp_router = consensus.get_router_using_nick(rendp_nick)
    peer_port = str(peer_id)
    peer_router_ip, peer_router_port = peer_router_addr.split(':')

    # Build circuit to rendezvous point
    circuit = build_circuit(guard_router, [ rendp_router ])

    # Establish a rendezvous point
    establish_rendezvous(circuit, rendezvous_cookie)
    
    logger.info("Waiting for connections at relay {0} for cookie {1} ...".format(rendp_nick, rendezvous_cookie))
    with circuit.create_waiter(CellRelayRendezvous2) as w:
        rendezvous2_cell = w.get(timeout=600)
        logger.info(f"Got REND2 message from {rendp_nick}")
          
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
                rcv_queue.put_nowait( [{'data' : data, 
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

            logger.debug("Entered circuit context with id " + hex(c.id))

            with c.create_stream((peer_router_ip, peer_router_port)) as stream:
                
                def recv_stream_callback(event):
                    logger.debug(f"Receive callback event: {event}")
                    data_str = stream._buffer.decode('utf-8')
                    logger.debug(f"Data: {data_str}")

    
                # Wait for HELLO message
                #logger.info("Waiting for HELLO")
                #hello_msg = stream.recv(1024)
                #logger.info("Received HELLO: " + str(hello_msg))

                #guard.register(sock_r, EVENT_READ, recv_callback)
                #guard.register(stream, EVENT_READ, recv_callback)
                #stream.register(recv_stream_callback)

                #lsr.add_neighbour(peer_id, 100, peer_router_ip, peer_router_port, circuit, circuit.id, stream, stream.id)

                # Send a HELLO message to the other side
                hello_msg = HelloMessage( lsr.global_router['RID'] ) 
                hello_data = [{'Message' : 'HELLO', 'Peer' : lsr.global_router['RID']}]
                hello_data = pickle.dumps(hello_data)
                logger.info(f"Sending HELLO to peer: {hello_data}")
                stream.send(hello_data)

                while True:
                    data = stream.recv(1024)
                    logger.debug("Received data on stream: " + str(data))
                    # Put the received data into the ReceiverThread input queue with circuit data
                    rcv_queue.put_nowait( [{'data' : data, 
                                            'circuit' : circuit, 
                                            'circuit_id' : circuit.id, 
                                            'stream' : stream, 
                                            'stream_id' : stream.id,
                                            'receive_node' : None,
                                            'extend_node' : None,
                                            'receive_socket' : None,

                                            }]
                                        )
                    #time.sleep(5)



def connect_to_rendezvous_point(nick, cookie, circuit_id=0x80000002):
    logger.info("Connect to rendezvous point " + nick)

    consensus = TorConsensus()
    router = consensus.get_router_using_nick(nick)

    tor_cell_socket = TorCellSocket(router)
    tor_cell_socket.connect()

    #circuit_id = 0x80000002

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

# Connect to a Rendezvous Point through a Guard node
def connect_to_rendezvous_point2(guard_nick, rendp_nick, cookie):
    logger.info(f"Connecting to Rendezvous Point {rendp_nick} with cookie '{cookie}'")

    # Set circuit ID
    with CircuitsList.LOCK:
        CircuitsList.GLOBAL_CIRCUIT_ID += 10

    consensus = TorConsensus()
    guard_router = TorGuard(consensus.get_router_using_nick(guard_nick))
    rendp_router = consensus.get_router_using_nick(rendp_nick)

    # Build circuit to rendezvous point
    circuit = build_circuit(guard_router, [ rendp_router ])

    # Join a rendezvous point
    #rcv_sock, rcv_cn, circuit_id = connect_to_rendezvous_point(rendp_nick, cookie, circuit.id)
    
    #logger.debug("Derive shared secret with peer")
    #extend_node = CircuitNode(rendp_router, key_agreement_cls=FastKeyAgreement)
    #shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
    #extend_node._crypto_state = CryptoState(shared_sec)
    #circuit._circuit_nodes.append(extend_node)
 #   cn_last = len(circuit._circuit_nodes) - 1
 #   logger.debug(f"Setting shared secret on CN index {cn_last}")
 #   circuit._circuit_nodes[cn_last]._crypto_state = CryptoState(shared_sec)


    # Set up streams
    sock_r, sock_w = socket.socketpair()

    events = {TorStream: {'data': Event(), 'close': Event()},
              socket.socket: {'data': Event(), 'close': Event()}}
        
    with guard_router as guard:

        logger.debug("Entered guard context")

        def _on_relay_begin(cell: CellRelayBegin, circuit):
            logger.debug(f"Received RELAY_BEGIN")

        def recv_callback(sock_or_stream, mask):
            logger.debug(f'recv_callback {sock_or_stream}')
            kind = type(sock_or_stream)
            data = sock_or_stream.recv(1024)
            logger.debug('%s', kind.__name__)

            if data:
                events[kind]['data'].set()
                #Put the received data into the ReceiverThread input queue with circuit data
                #rcv_queue.put_nowait( [{'data' : data, 
                #                        'circuit' : circuit, 
                #                        'circuit_id' : circuit.id, 
                #                        'stream' : stream, 
                #                        'stream_id' : stream.id}]
                #                    )
            else:
                logger.debug('closing')
                guard.unregister(sock_or_stream)
                events[kind]['close'].set()

        #guard._handler_mgr.subscribe_for(CellRelayBegin, _on_relay_begin)

        with circuit as c:
            logger.debug("Entered circuit context with id " + hex(c.id))
            
            guard.register(sock_r, EVENT_READ, recv_callback)
            #guard.register(stream, EVENT_READ, recv_callback)

           # shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
           # c._circuit_nodes[-1]._crypto_state = CryptoState(shared_sec)

            try:
                inner_cell = CellRelayRendezvous1(os.urandom(128+20), cookie, c.id)
                c.send_relay(inner_cell)
                logger.debug("Sent CellRelayRendezvous1, waiting for RELAY_BEGIN")
            except Exception as e:
                logger.debug("Exception in send_relay:")
                logger.debug(e)

            while True:
                time.sleep(5)



