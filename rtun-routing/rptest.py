import lsr
from lsr import HeartBeatThread, ReceiveThread, SendThread
from rendezvous import RendezvousEstablish, RendezvousConnect
from queue import Queue

rp_rcv_queue = Queue()
rc_rcv_queue = Queue()

lsr.init_router("PEERCONNECT", 5000)

receiver_thread = ReceiveThread("RECEIVER", rp_rcv_queue, lsr.threadLock)
sender_thread = SendThread("SENDER", lsr.threadLock)

HB_message = [{'RID' : lsr.global_router['RID']}]
heartbeat_thread = HeartBeatThread("HEART BEAT", HB_message, lsr.threadLock)
            
receiver_thread.start()
sender_thread.start()
heartbeat_thread.start()
            
lsr.threads.append(receiver_thread)
lsr.threads.append(sender_thread)
lsr.threads.append(heartbeat_thread)

# Test
guard_nick = "umbriel"
rendp_nick = "lint"
rendezvous_cookie = "eb688e4f52df90278060"

print("Starting RP thread, waiting to join...")
rp = RendezvousEstablish(guard_nick, rendp_nick, rendezvous_cookie, condition=None)
rp.start()
print("Started RP thread, waiting to join...")

print("Starting RC thread")
rc = RendezvousConnect(rendp_nick, rendezvous_cookie, "P2", rcv_queue)
rc.start()
print("Started RC thread")

rc.join()
rp.join()
print("RP thread finished")

