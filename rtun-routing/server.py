import socket
import main
import select
import time

from torpy import TorClient
from torpy.cells import CellRelayEnd, CellDestroy, CellRelaySendMe
from torpy.cell_socket import TorCellSocket
from torpy.cells import CellRelayEstablishRendezvous, CellRelayRendezvousEstablished, CellCreate2, CellCreated2, \
    CellRelay, CellCreateFast, CellCreatedFast, CellRelayRendezvous1, CellRelayBegin, CellRelayData, CellRelayRendezvous2, CellRelayEnd, CellRelayConnected, \
    CellNetInfo
from torpy.circuit import CircuitNode
from torpy.cli.socks import SocksServer
from torpy.consesus import TorConsensus
from torpy.crypto_state import CryptoState
from torpy.keyagreement import NtorKeyAgreement, FastKeyAgreement

import socksserver

import logging
logging.basicConfig(level=logging.INFO)

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
        print("Got " + str(type(cellrelaydata)))


    return cellrelaydata.data

def snd_data(rsp, circuit_id, extend_node, rcv_cn, rcv_sock):
    inner_cell = main.CellRelayData(rsp, circuit_id)
    relay_cell = main.CellRelay(inner_cell, stream_id=3, circuit_id=circuit_id, padding=None)

    extend_node.encrypt_forward(relay_cell)
    rcv_cn.encrypt_forward(relay_cell)
    rcv_sock.send_cell(relay_cell)


def list_rend_server(cookie, router_nick):

    rcv_sock, rcv_cn, circuit_id = main.connect_to_rendezvous_point(router_nick, cookie)

    extend_node = main.CircuitNode("a")
    shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
    extend_node._crypto_state = main.CryptoState(shared_sec)
    while True:
        try:
            b = rcv_sock.recv_cell()
            if b:
                break
        except socket.timeout:
            continue

    print(type(b))
    if b.NUM == 4:
        print(b.reason)

    rcv_cn.decrypt_backward(b)
    extend_node.decrypt_backward(b)
    cellbegin = b.get_decrypted()

    s = create_sock(cellbegin.address, cellbegin.port)


    print("Connection OK")
    inner_cell = main.CellRelayConnected("1.1.1.1", 5000, circuit_id)
    relay_cell = main.CellRelay(inner_cell, stream_id=3, circuit_id=circuit_id, padding=None)
    extend_node.encrypt_forward(relay_cell)
    rcv_cn.encrypt_forward(relay_cell)
    rcv_sock.send_cell(relay_cell)

    print("Socket select")

    while True:
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

            snd_data(buf, circuit_id, extend_node, rcv_cn, rcv_sock)

def setup_rendserver(cookie, router_nick, guard_nick, port_num):

    with TorClient() as tor:

        with tor.get_guard(nick=guard_nick) as guard:
            circuit = guard._circuits.create_new()
            try:
                circuit.create()

                router = circuit._guard.consensus.get_router_using_nick(router_nick)
                circuit.extend(router)
                circuit._rendezvous_establish(cookie)
                print('Rendezvous established')

                print("Waiting for REND2")
                with circuit.create_waiter(CellRelayRendezvous2) as w:
                        rendezvous2_cell = w.get(timeout=200)
                        print('Got REND2 message')

                extend_node = CircuitNode(router, key_agreement_cls=FastKeyAgreement)
                shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')

                extend_node._crypto_state = CryptoState(shared_sec)

                circuit._circuit_nodes.append(extend_node)
                
                #socksserver.startserver("127.0.0.1", port_num)

                tor_cell_socket = TorCellSocket(router)
                tor_cell_socket.connect()

                while True:
                    rcv_cell = tor_cell_socket.recv_cell()
                    print(rcv_cell)
                    print("Sending CellNetInfo")
                    tor_cell_socket.send_cell(CellNetInfo(int(time.time()), "10.2.0.2", "10.1.0.1"))
                    time.sleep(5)
                

                #print("Creating socket on 127.0.0.1:" + str(port_num))
                #s = create_sock("127.0.0.1", port_num)

                #print("Entering socket loop")
                #while True:
                #    r, w, _ = select.select([tor_cell_socket.ssl_socket, s], [], [])
                #    if rcv_sock.ssl_socket in r:
                #        buf = server.cv_data(rcv_sock, rcv_cn, extend_node)
                #        if buf == 404:
                #            continue
                #        if len(buf) == 0:
                #            break
                #        s.send(buf)
                #    if s in r:
                #        buf = s.recv(498)
                #        if len(buf) == 0:
                #            break

                 #   server.snd_data(buf, circuit_id, extend_node, rcv_cn, rcv_sock)
                        

            except Exception:
                # We must close here because we didn't enter to circuit yet to guard by context manager
                circuit.close()
                raise
            
            circuit.close()



def create_sock(target_host, target_port):

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # connect the client
    client.connect((target_host, target_port))
    return client
