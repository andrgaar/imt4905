import socket
import time
import main
import select
import threading

from torpy.cells import CellRelayEnd, CellDestroy, CellRelaySendMe, StreamReason
from torpy.circuit import TorCircuit, TorCircuitState
from torpy.guard import TorGuard

import lsr
from lsr import ReceiveThread, SendThread, HeartBeatThread

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


def list_rend_server(cookie, router_nick, my_id, peer_id):

    # Start router
    lsr.start_router(my_id, 5000)

    receiver_thread = ReceiveThread("RECEIVER", lsr.threadLock)
    sender_thread = SendThread("SENDER", lsr.threadLock)


    HB_message = [{'RID' : lsr.global_router['RID']}]
    heartbeat_thread = HeartBeatThread("HEART BEAT", HB_message, lsr.threadLock)
                
    receiver_thread.start()
    sender_thread.start()
    heartbeat_thread.start()
                
    lsr.threads.append(receiver_thread)
    lsr.threads.append(sender_thread)
    lsr.threads.append(heartbeat_thread)
    
    while True:
        try:
            logger.info("Calling connect_to_rendezvous_point")
            rcv_sock, rcv_cn, circuit_id = main.connect_to_rendezvous_point(router_nick, cookie)

        except KeyboardInterrupt:
            logger.warn("Caught keyboard interrupt, exiting...")
            raise KeyboardInterrupt

        except Exception as e:
            logger.warn("Could not connect to rendezvous point {router_nick}, retrying in 5 seconds...")
            time.sleep(5)
            continue
        break

    logger.debug("Derive shared secret")
    extend_node = main.CircuitNode("a")
    shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
    extend_node._crypto_state = main.CryptoState(shared_sec)

    logger.debug("Waiting for cell")
    while True:
        try:
            b = rcv_sock.recv_cell()
            if b:
                logger.debug("Received cell")
                break
        except socket.timeout:
            continue

    logger.debug(type(b))
    if b.NUM == 4:
        logger.debug(b.reason)

    logger.debug("Decrypting cells")
    rcv_cn.decrypt_backward(b)
    extend_node.decrypt_backward(b)
    cellbegin = b.get_decrypted()
    stream_id = b.stream_id
    logger.debug("CellRelay received, stream_id: " + str(stream_id))
    logger.debug(cellbegin.address)
    logger.debug(cellbegin.port)



    logger.debug("Creating socket")
    try:
        s = create_sock(cellbegin.address, cellbegin.port)
    except Exception as e:
        logger.error("Error creating socket: " + str(e))
        inner_cell = main.CellRelayEnd(StreamReason(7), circuit_id)
        relay_cell = main.CellRelay(inner_cell, stream_id=stream_id, circuit_id=circuit_id, padding=None)
        extend_node.encrypt_forward(relay_cell)
        rcv_cn.encrypt_forward(relay_cell)
        rcv_sock.send_cell(relay_cell)
    
        raise Exception

    logger.info("Stream opened successfully")
    inner_cell = main.CellRelayConnected("127.0.0.1", 5000, circuit_id)
    relay_cell = main.CellRelay(inner_cell, stream_id=stream_id, circuit_id=circuit_id, padding=None)
    extend_node.encrypt_forward(relay_cell)
    rcv_cn.encrypt_forward(relay_cell)
    rcv_sock.send_cell(relay_cell)

    # Add neighbour
    lsr.add_neighbour(peer_id, 100, '127.0.0.1', 5000, None, circuit_id, None, stream_id, 
                        receive_node=rcv_cn, extend_node=extend_node, receive_socket=rcv_sock)

    while True:
        try:
            r, w, _ = select.select([rcv_sock.ssl_socket, s], [], [])
            if rcv_sock.ssl_socket in r:
                buf = rcv_data(rcv_sock, rcv_cn, extend_node)

                if buf == 404:
                    continue
                if len(buf) == 0:
                    break
                
                s.send(buf)

            if s in r:
                buf = s.recv(498)
                if len(buf) == 0:
                    break

                snd_data(buf, circuit_id, extend_node, rcv_cn, rcv_sock, stream_id)

        except Exception as e:
            logger.error("Error in receive on socket: " + str(e))
            continue

def create_sock(target_host, target_port):

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # connect the client
    client.connect((target_host, target_port))
    return client
