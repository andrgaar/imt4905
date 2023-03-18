import argparse
import sys
import time
#import main
import subprocess
from time import sleep
from threading import Thread
import traceback
import logging

import server
import lsr
from lsr import ConnectionThread
from rendezvous import RendezvousEstablish, RendezvousConnect
from tester import RtunTest

condition = None # acquired by executing thread to notify main thread to unblock

parser = argparse.ArgumentParser()
parser.add_argument('-r', '--relay', help="relay to be used as rendezvous point", type=str)
parser.add_argument('-g', '--guard', help="optional router to be used as guard node", type=str)
parser.add_argument('-l', '--listen', action="store_true", help="create the rendezvous point an wait")
parser.add_argument('-c', '--connect', action="store_true",  help="connect to an already established rendezvous point")
parser.add_argument('-k', '--cookie', help="a 20 byte rendezvous cookie", type=str)
parser.add_argument('-p', '--pairwise', action="store_true",  help="select relay automatically using the "
                                                                   "pairwise algorithm")
#parser.add_argument('-d', '--destination', action="store_true",  help="select relay automatically using the "
#                                                                      "recipient algorithm")

parser.add_argument('-t', '--tunnel_name', help="name of the tunnel, default is the two peers"
                                                " name concatenated", type=str)
parser.add_argument('-n', '--namespace', help="secret key used to differentiate between different nets", type=str)
parser.add_argument('-i', '--id', help="id of our own client(used for addressing and port allocation)", type=int)
parser.add_argument('-d', '--did', help="destination id", type=int)

parser.add_argument('-f', '--file', help="filename of connection info", type=str)
parser.add_argument('-v', '--loglevel', help="override log level (DEBUG,INFO,WARNING,ERROR,CRITICAL)", type=str)

parser.add_argument('-x', '--dummy', action="store_true",  help="do not connect, only test")

args = parser.parse_args()

# Define a log handler for application
if args.loglevel:
    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.loglevel)
else:
    numeric_level = logging.INFO

logging.basicConfig(level=numeric_level, format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s', filename='rtun.log', encoding='utf-8')
logger = logging.getLogger(__name__)

if args.connect and args.listen:
    print(f"Illegal combination of arguments")
    exit()
if args.namespace:
    namespace = args.namespace
else:
    namespace = "default"
if args.relay:
    relay_nick = args.relay

if args.pairwise:
    relay_nick, cookie = choose_relay(args.tunnel_name, namespace=namespace)
if args.guard:
    guard_nick = args.guard
else:
    guard_nick = "XXX"



if not args.cookie:
    cookie = "00000000000000000001".encode("UTF-8")
else:
    if len(args.cookie) != 20:
        print("Cookie is of unacceptable length")
        exit()
    cookie = args.cookie.encode("UTF-8")


if args.dummy:
    exit()

# Open an OpenVPN log file
vpn_log = open('openvpn.out', 'w')

file_rendps = []
if args.file:
    with open(args.file) as f:
        [file_rendps.append(line.strip()) for line in f.readlines()]


    #openvpn_client = subprocess.Popen(["/usr/sbin/openvpn", "--remote", "127.0.0.1", "--proto", "tcp-client", "--cipher", "AES-256-CBC",
    #                                   "--secret", "static.key", "--socks-proxy", "127.0.0.1", f"105{args.did}",
    #                                   "--ifconfig", f"10.{args.id}.0.1", f"10.{args.did}.0.1",
    #                                   "--dev", f"tun{args.did}", "--port", f"119{args.did}"], stdout=vpn_log)

    my_id = "P" + str(args.id)
    port_num = int("105"+str(args.did))
    my_router_port = int("5" + f'{args.id:03}')

    rcv_queue, conn_queue = lsr.setup_router(my_id, my_router_port)
    
    #lsr.threads = []

    for rp in file_rendps:
        a, b, c, d, e = rp.split()
        connection = a
        relay_nick = b
        cookie = c.encode("UTF-8")
        port_num = int("105"+str(d))
        peer_id = "PEER" + str(d)
        peer_router_addr = e

        if connection == "LISTEN": 
            # Start a listening thread
            logger.info(f"Adding listener for {relay_nick}")
            #lsr.threads.append(Thread(name='Thread-' + relay_nick, 
            #                            target=main.setup_rendezvous2, 
            #                            args=(guard_nick, relay_nick, cookie, port_num, peer_id, peer_router_addr)))
            RendezvousEstablish(guard_nick, relay_nick, cookie, rcv_queue).start() 


        elif connection == "CONNECT": 
            # Start a connecting thread
            logger.info(f"Adding a connection to {relay_nick}")
            #lsr.threads.append(Thread(name='Thread-' + relay_nick, 
            #                            target=server.list_rend_server, 
            #                            args=(cookie, relay_nick, my_id, peer_id, peer_router_addr)))
            RendezvousConnect(relay_nick, cookie, my_id, rcv_queue).start()
        else:
            logger.info(f"Unknown connection option: {connection}")

    # Display program statistics
    Thread(name='Thread-Stats', target=lsr.print_stats).start()

    if my_id:
        # Start a tester thread
        logger.info("Starting testing thread")
        tester_thread = RtunTest()
        tester_thread.start()

    # Start ConnectionThread
    logger.info("Starting connection thread")
    conn_thread = ConnectionThread("CONNECTION", conn_queue, rcv_queue)
    conn_thread.start()

    try:
        # Create RP loop - creates new rendezvous points for peers to connect
        while True:
            conn = conn_queue.get()

            logger.info(conn)
            conn_cmd = conn[0]
            conn_nick = conn[1]
            conn_cookie = conn[2]

            # Process the JOIN
            if conn_cmd == "JOIN":
                logger.info(f"Got JOIN to relay {conn_nick}, waiting 10 sec to connect")
                RendezvousConnect(conn_nick, conn_cookie, my_id, rcv_queue).start()

            elif conn_cmd == "ESTABLISH":
                logger.info(f"Got ESTABLISH to relay {conn_nick}:{conn_cookie} via {guard_nick}")
                RendezvousEstablish(guard_nick, conn_nick, conn_cookie, rcv_queue).start() 
             
    
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting...")
        print("Graph:")
        print(lsr.graph)
        lsr.log_metrics("PEER EXITED", "")
        sys.exit()
            
    except Exception as e:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        logger.error(message)
        logger.error(traceback.print_exc())
    
    #openvpn_client.terminate()


if args.connect:
    print(relay_nick)
    print("Starting openvpn server")
    openvpn_server = subprocess.Popen(["/usr/sbin/openvpn", "--proto", "tcp-server", "--secret", "static.key", "--cipher", "AES-256-CBC",
                                       "--ifconfig", f"10.{args.id}.0.1", f"10.{args.did}.0.1",
                                       "--dev", f"tun{args.did}", "--port", f"119{args.id}"], stdout=vpn_log)
    sleep(1)

    my_id = "PEER" + str(args.id)
    peer_id = "PEER" + str(args.did)

    ## TODO: thread this
    while True:
        try:
            server.list_rend_server(cookie, relay_nick, my_id, peer_id)

            # Display program statistics
            while True:
                lsr.print_stats()
                time.sleep(3)

        except Exception as e:
            print("Error, trying again in 5 seconds..." + str(e))
            #tb = traceback.format_exc()
            #print(tb)
            sleep(5)
            continue
        break
        
    print("Terminating")

    openvpn_server.terminate()

