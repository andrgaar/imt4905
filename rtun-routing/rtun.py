import argparse
import sys
import time
import main
import server
import lsr
import subprocess
from time import sleep
from threading import Thread
import pandas as pd
import hashlib
import traceback
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='rtun.log', encoding='utf-8')

logger = logging.getLogger(__name__)

def choose_relay(tun_name, namespace='default', time_frame="1 min"):
    all_relays = []
    a_r = []
    blacklist = []
    actual_relays = []
    with open("/root/.local/share/torpy/network_status", 'r') as f:
        line = True
        while line:
            line = f.readline()
            spl = line.split(' ')
            if spl[0] == "r":
                if spl[1] in a_r:
                    blacklist.append(spl[1])
                a_r.append(spl[1])
                all_relays.append([spl[1], spl[6], spl[7]])
    for rel in all_relays:
        if not rel[0] in blacklist:
            actual_relays.append(rel)
    all_relays = actual_relays
    num_of_relays = len(all_relays)
    print(num_of_relays)
    # How long to use 1 relay as RP. Rotates every :30 seconds with the round-function in Pandas.
    ts = pd.Timestamp.now().round(time_frame).value


    h = str(ts)+namespace+tun_name  # Concat all values as input to hash function
    h = hashlib.sha256(h.encode())
    n = int(h.hexdigest(), base=16)  # Convert to integer to be able to use modulo

    #print(n)
    selected = n%num_of_relays
    cookie = h.hexdigest().encode()[0:20]
    logging.info(f"I want to connect to {all_relays[selected][0]}({selected}) at {all_relays[selected][1]}:{all_relays[selected][2]} with cookie {cookie}")
    return all_relays[selected][0], cookie


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

parser.add_argument('-x', '--dummy', action="store_true",  help="do not connect, only test")

args = parser.parse_args()

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

file_rendps = []
if args.file:
    with open(args.file) as f:
        [file_rendps.append(line.strip()) for line in f.readlines()]

if args.dummy:
    exit()

# Open an OpenVPN log file
vpn_log = open('/tmp/openvpn.out', 'w')

if args.listen:
    port_num = int("105"+str(args.did))

    #openvpn_client = subprocess.Popen(["/usr/sbin/openvpn", "--remote", "127.0.0.1", "--proto", "tcp-client", "--cipher", "AES-256-CBC",
    #                                   "--secret", "static.key", "--socks-proxy", "127.0.0.1", f"105{args.did}",
    #                                   "--ifconfig", f"10.{args.id}.0.1", f"10.{args.did}.0.1",
    #                                   "--dev", f"tun{args.did}", "--port", f"119{args.did}"], stdout=vpn_log)

    my_id = "PEER" + str(args.id)

    main.setup_router(my_id, 5000)
    
    rendp_threads = []

    if len(file_rendps) > 0:
        for rp in file_rendps:
            a, b, c = rp.split()
            relay_nick = a
            cookie = b.encode("UTF-8")
            port_num = int("105"+str(c))
            peer_id = "PEER" + str(c)

            rendp_threads.append(Thread(name='Thread-' + relay_nick, target=main.setup_rendezvous2, args=(guard_nick, relay_nick, cookie, port_num, peer_id)))
    else:
            rendp_threads.append(Thread(name='Thread-' + relay_nick, target=main.setup_rendezvous2, args=(guard_nick, relay_nick, cookie, port_num. peer_id)))
            
    for rendp_thread in rendp_threads:
        print("Starting thread " + str(rendp_thread.name))
        rendp_thread.start()
        lsr.threads.append(rendp_thread)

    # Display program statistics
    while True:
        lsr.print_stats()
        time.sleep(3)

    # Call join on each tread (so that they wait)
    try:
        for thread in lsr.threads:
            thread.join()
    
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting...")
        print("Graph:")
        print(lsr.graph)
        sys.exit()
            
    except Exception as e:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        print(message)
    
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

    while True:
        try:
            server.list_rend_server(cookie, relay_nick, my_id, peer_id)
        except Exception as e:
            print("Error, trying again in 5 seconds..." + str(e))
            #tb = traceback.format_exc()
            #print(tb)
            sleep(5)
            continue
        break
        
    print("Terminating")

    openvpn_server.terminate()

