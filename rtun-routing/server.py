import socket
import main
import select
import threading

from torpy.cells import CellRelayEnd, CellDestroy, CellRelaySendMe, StreamReason

from router import TorRouter

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

    print("Calling connect_to_rendezvous_point")
    rcv_sock, rcv_cn, circuit_id = main.connect_to_rendezvous_point(router_nick, cookie)

    print("Derive shared secret")
    extend_node = main.CircuitNode("a")
    shared_sec = "000000000000000000010000000000000000000100000000000000010000000000000001".encode('utf-8')
    extend_node._crypto_state = main.CryptoState(shared_sec)

    print("Waiting for cell")
    while True:
        try:
            b = rcv_sock.recv_cell()
            if b:
                print("Received cell")
                break
        except socket.timeout:
            continue

    print(type(b))
    if b.NUM == 4:
        print(b.reason)

    print("Decrypting cells")
    rcv_cn.decrypt_backward(b)
    extend_node.decrypt_backward(b)
    cellbegin = b.get_decrypted()
    print(cellbegin)

    #print("Starting a TorRouter thread")
    #router = TorRouter("127.0.0.1", 5000)

    print("Creating socket")
    try:
        s = create_sock(cellbegin.address, cellbegin.port)
    except Exception:
        inner_cell = main.CellRelayEnd(StreamReason(7), circuit_id)
        relay_cell = main.CellRelay(inner_cell, stream_id=1, circuit_id=circuit_id, padding=None)
        extend_node.encrypt_forward(relay_cell)
        rcv_cn.encrypt_forward(relay_cell)
        rcv_sock.send_cell(relay_cell)
    
        raise Exception

    print("Connection OK")
    inner_cell = main.CellRelayConnected("127.0.0.1", 5000, circuit_id)
    relay_cell = main.CellRelay(inner_cell, stream_id=1, circuit_id=circuit_id, padding=None)
    extend_node.encrypt_forward(relay_cell)
    rcv_cn.encrypt_forward(relay_cell)
    rcv_sock.send_cell(relay_cell)

    print("Sending CellNetInfo")
    #rcv_sock.send_cell(CellNetInfo(int(time.time()), "10.1.0.1", "10.2.0.2"))
    rcv_sock.send_cell(relay_cell)
    time.sleep(10)

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


def create_sock(target_host, target_port):

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # connect the client
    client.connect((target_host, target_port))
    return client
