import socket
import time
import main
import select
import threading

from torpy.cells import CellRelayEnd, CellDestroy, CellRelaySendMe, StreamReason
from torpy.circuit import TorCircuit, TorCircuitState
from torpy.guard import TorGuard

from messages import HelloMessage
import lsr
from lsr import ReceiveThread, SendThread, HeartBeatThread

import pickle
import logging

logger = logging.getLogger(__name__)

def rcv_data(rcv_sock, rcv_cn, extend_node):
    b = rcv_sock.recv_cell()
    rcv_cn.decrypt_backward(b)
    extend_node.decrypt_backward(b)

    cellrelaydata = b.get_decrypted()
    if isinstance(cellrelaydata, CellRelayEnd):
        print("Got relayend, exiting")
        exit()
    elif isinstance(cellrelaydata, CellDestroy):
        print("Got destroy, exiting")
        exit()
    elif isinstance(cellrelaydata, CellRelaySendMe):
        print("Got SENDME")
        return 404
    else:
        #print("Got " + str(type(cellrelaydata)))
        pass

    return cellrelaydata.data

def snd_data(rsp, circuit_id, extend_node, rcv_cn, rcv_sock, stream_id=0):
    inner_cell = main.CellRelayData(rsp, circuit_id)
    relay_cell = main.CellRelay(inner_cell, stream_id=stream_id, circuit_id=circuit_id, padding=None)

    extend_node.encrypt_forward(relay_cell)
    rcv_cn.encrypt_forward(relay_cell)
    rcv_sock.send_cell(relay_cell)
    logger.debug("Sent cell:" + str(inner_cell))


def list_rend_server(cookie, router_nick, my_id, peer_id, peer_router_addr):

    # Try to connect to rendezvous point - restart on failure
    while True:
        try:
            logger.info("Calling connect_to_rendezvous_point")
            rcv_sock, rcv_cn, circuit_id = main.connect_to_rendezvous_point(router_nick, cookie)

            logger.debug("Derive shared secret")
            extend_node = main.CircuitNode("a")
            shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
            extend_node._crypto_state = main.CryptoState(shared_sec)

            logger.debug("Waiting for peer to open stream")
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
            logger.warn(f"Could not connect to rendezvous point {router_nick}: {e}, retrying in 5 seconds...")
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

    inner_cell = main.CellRelayConnected("127.0.0.1", 6000, circuit_id)
    relay_cell = main.CellRelay(inner_cell, stream_id=stream_id, circuit_id=circuit_id, padding=None)
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

    # Add neighbour
    #peer_router_ip, peer_router_port = peer_router_addr.split(':')
    #lsr.add_neighbour(peer_id, 100, '127.0.0.1', peer_router_port, None, circuit_id, None, stream_id, 
    #                    receive_node=rcv_cn, extend_node=extend_node, receive_socket=rcv_sock)

    while True:
        try:
            r, w, _ = select.select([rcv_sock.ssl_socket], [], [])
            if rcv_sock.ssl_socket in r:
                buf = rcv_data(rcv_sock, rcv_cn, extend_node)

                if buf == 404:
                    continue
                if len(buf) == 0:
                    break
                
                #Put the received data into the ReceiverThread input queue with circuit data
                main.rcv_queue.put_nowait( [{'data' : buf, 
                                            'circuit' : None, 
                                            'circuit_id' : circuit_id, 
                                            'stream' : None, 
                                            'stream_id' : stream_id,
                                            'receive_node' : rcv_cn,
                                            'extend_node' : extend_node,
                                            'receive_socket' : rcv_sock,
                                            'rendpoint' : router_nick
                                            }]
                                    )                

            #if main.global_router_sock in r:
            #    buf = main.global_router_sock.recv(498)
            #    if len(buf) == 0:
            #        break

            #    snd_data(buf, circuit_id, extend_node, rcv_cn, rcv_sock, stream_id)

        except Exception as e:
            logger.error("Error in receive on socket: " + str(e))
            continue

def create_sock(target_host, target_port):

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # connect the client
    client.connect((target_host, target_port))
    return client
