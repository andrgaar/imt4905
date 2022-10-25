import os
import socket
from functools import partial
from torpy import TorClient
import logging
from torpy.cell_socket import TorCellSocket
from torpy.cells import CellRelayEstablishRendezvous, CellRelayRendezvousEstablished, CellCreate2, CellCreated2, \
    CellRelay, CellCreateFast, CellCreatedFast, CellRelayRendezvous1, CellRelayBegin, CellRelayData, CellRelayRendezvous2, CellRelayEnd, CellRelayConnected, CellNetInfo
from torpy.circuit import CircuitNode
from torpy.cli.socks import SocksServer
from torpy.consesus import TorConsensus
from torpy.crypto_state import CryptoState
from torpy.keyagreement import NtorKeyAgreement, FastKeyAgreement
from torpy.guard import TorGuard

import server
import lsr
from lsr import HeartBeatThread, ReceiveThread, SendThread
import pickle

import logging
logging.basicConfig(level=logging.INFO)

# Threading 
import threading
import time

exitFlag = 0

class myThread (threading.Thread):
   def __init__(self, threadID, name, counter):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.name = name
      self.counter = counter
   def run(self):
      print ("Starting " + self.name)
      print_time(self.name, self.counter, 5)
      print ("Exiting " + self.name)

def print_time(threadName, delay, counter):
   while counter:
      if exitFlag:
         threadName.exit()
      time.sleep(delay)
      print ("%s: %s" % (threadName, time.ctime(time.time())))
      counter -= 1



logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

def send_routing_update(circuit):
    pass

def build_circuit(guard_router, extend_routers): # returns Circuit
    # Build a circuit OP->Guard->RendPoint
    circuit =  guard_router.create_circuit(hops_count=-1, extend_routers=extend_routers)

    return circuit
            
def establish_rendezvous(circuit, rendezvous_cookie):
    # Establish a rendezvous point
    circuit._rendezvous_establish(rendezvous_cookie)

def setup_rendezvous(guard_nick, rendp_nick, rendezvous_cookie, port_num):
    # Setup a rendezvous point and wait
    consensus = TorConsensus()
    guard_router = TorGuard(consensus.get_router_using_nick(guard_nick))
    rendp_router = consensus.get_router_using_nick(rendp_nick)

    # Build circuit to rendezvous point
    circuit = build_circuit(guard_router, [ rendp_router ])

    # Establish a rendezvous point
    establish_rendezvous(circuit, rendezvous_cookie)
    
    logger.info("Waiting for connections")
    with circuit.create_waiter(CellRelayRendezvous2) as w:
        rendezvous2_cell = w.get(timeout=200)
        logger.info('Got REND2 message')
          
    logger.info("Derive shared secret with peer")
    extend_node = CircuitNode(rendp_router, key_agreement_cls=FastKeyAgreement)
    shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
    extend_node._crypto_state = CryptoState(shared_sec)
    circuit._circuit_nodes.append(extend_node)

    ## TODO: Exchange nodeIDs to determine which peers are connecting
    ##        create a class Peer  
    peer_id = 'PEER2'

    logger.info("Built circuit with " + str(circuit.nodes_count) + " nodes")
    logger.info("Last node IP: " + '.'.join(circuit.last_node.router.ip.split('.')[:-1]) + '.')

    # Open a stream with the peer router
    stream = circuit.create_stream(('127.0.0.1', 5000))
    
    print("Starting router")
    lsr.start_router(1, 5000)
    lsr.add_neighbour(peer_id, 100, '127.0.0.1', 5000, circuit, stream)

    print("Creating router thread")
    HB_message = [{'RID' : lsr.router_information['RID']}]
    heartbeat_thread = HeartBeatThread("HEART BEAT", HB_message, lsr.router_information['Neighbours Data'], lsr.threadLock)
    sender_thread = SendThread("SENDER", lsr.router_information, lsr.threadLock)
    receiver_thread = ReceiveThread("RECEIVER", lsr.router_information, lsr.threadLock)

    # Start each thread
    sender_thread.start()
    receiver_thread.start()
    heartbeat_thread.start()

    # Append each thread to list of threads
    lsr.threads.append(sender_thread)
    lsr.threads.append(receiver_thread)
    lsr.threads.append(heartbeat_thread)

    # Here we enter a read/write loop for the router
    #
    tor_socket = TorCellSocket(rendp_router)
    tor_socket.connect()

    router_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    while True:
        try:
            rcv_cell = tor_socket.recv_cell()
            if isinstance(rcv_cell, CellRelayData):
                print("Received CellRelayData:")
                s = router_socket.connect(("127.0.0.1", 5000))
                print(rcv_cell.data)
                s.send(rcv_cell.data)
            else:
                print(type(rcv_cell))
                s.send(1)

        except Exception as e:
            print("Error in receive on socket: " + str(e))
            continue


    #for thread in threading.enumerate(): 
    #    print(thread.name)

    # Here we implement the SOCKS5 connection
    print("Starting SOCKS5")
    with SocksServer(circuit, "127.0.0.1", 5000) as socks_serv:
        socks_serv.start()

    print("Closing circuit")
    circuit.close()

def set_up_rendezvous_point(nick, cookie):

    consensus = TorConsensus()
    router = consensus.get_router_using_nick(nick)
    tor_cell_socket = TorCellSocket(router)
    tor_cell_socket.connect()

    circuit_id = 0x80000001

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

    logger.debug('Verifying response...')
    circuit_node.complete_handshake(cell_created.handshake_data)

    logger.debug(cell_created.circuit_id)

    circuit_node.complete_handshake(cell_created.handshake_data)

    rendezvous_cookie = cookie

    inner_cell = CellRelayEstablishRendezvous(rendezvous_cookie, cell_created.circuit_id)

    relay_cell = CellRelay(inner_cell, stream_id=0, circuit_id=circuit_id)

    circuit_node.encrypt_forward(relay_cell)

    tor_cell_socket.send_cell(relay_cell)
    rcv_cell = tor_cell_socket.recv_cell()
    circuit_node.decrypt_backward(rcv_cell)

    logger.debug(rcv_cell)

    return tor_cell_socket, circuit_node, cell_created.circuit_id


def connect_to_rendezvous_point(nick, cookie):
    print("Connect to rendezvous point " + nick)

    consensus = TorConsensus()
    router = consensus.get_router_using_nick(nick)

    tor_cell_socket = TorCellSocket(router)
    tor_cell_socket.connect()

    circuit_id = 0x80000002

    print("Key agreement")
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


    print("Cell created circuit ID: " + str(cell_created.circuit_id))

    circuit_node.complete_handshake(cell_created.handshake_data)

    inner_cell = CellRelayRendezvous1(os.urandom(128+20), cookie, cell_created.circuit_id)

    relay_cell = CellRelay(inner_cell, stream_id=0, circuit_id=circuit_id)

    circuit_node.encrypt_forward(relay_cell)

    tor_cell_socket.send_cell(relay_cell)

    print("Sent cookie")

    return tor_cell_socket, circuit_node, circuit_id


def two_hop(cookie, router_nick, guard_nick, port_num):
    with TorClient() as tor:

        with tor.get_guard(nick=guard_nick) as guard:
            circuit = guard._circuits.create_new()
            try:
                circuit.create()

                router = circuit._guard.consensus.get_router_using_nick(router_nick)
                circuit.extend(router)
                circuit._rendezvous_establish(cookie)
                #logger.info('Rendezvous established')

                logger.info("Waiting for REND2")
                with circuit.create_waiter(CellRelayRendezvous2) as w:
                        rendezvous2_cell = w.get(timeout=200)
                        logger.info('Got REND2 message')

                extend_node = CircuitNode(router, key_agreement_cls=FastKeyAgreement)
                shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')

                extend_node._crypto_state = CryptoState(shared_sec)

                circuit._circuit_nodes.append(extend_node)
                
                print("Starting SOCKS5")
                with SocksServer(circuit, "127.0.0.1", port_num) as socks_serv:
                    socks_serv.start()

            except Exception:
                # We must close here because we didn't enter to circuit yet to guard by context manager
                circuit.close()
                raise
            circuit.close()
