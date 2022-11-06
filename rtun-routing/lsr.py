import os
import sys
import pickle
import time
import heapq
import socket

from datetime import datetime, timedelta
from threading import Thread, Lock, Timer
from socket import socket, create_server, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR


from torpy.circuit import TorCircuit
from torpy.stream import TorStream

import server

import logging
logger = logging.getLogger(__name__)

UPDATE_INTERVAL = 15
ROUTE_UPDATE_INTERVAL = 30
PERIODIC_HEART_BEAT = 10
NODE_FAILURE_INTERVAL = 4
TIMEOUT = 15

# Global graph object to represent network topology
graph = {}
global_router = {}
circuit_info = {}
neighbour_stats = {}
display_paths = None
threadLock = None
threads = None

class ReceiveThread(Thread):

    def __init__(self, name, thread_lock):
        Thread.__init__(self)
        self.name = name
        self.thread_lock = thread_lock
        self.server_socket = socket(AF_INET, SOCK_STREAM)
        self.packets = set()
        self.LSA_SN = {}
        self.HB_set = {}
        self.LSA_DB = {}
        self.inactive_list = set()
        self.forward_set = set()

    def __exit__(self, exc_type, exc_value, traceback):

        logger.debug("ReceiveThread __exit__")
        logger.info("Closing socket") 
        self.server_socket.close()

    def run(self):
        try:
            self.serverSide()
        except Exception as e:
            logger.error("Error in ReceiveThread: " + str(e))


    def __str__(self):
        return "I am Router {0} with PORT {1} - READY TO RECEIVE".format(
            global_router['RID'],
            global_router['Port']
        )

    def __del__(self):
        self.server_socket.close()

    def serverSide(self):

        server_name = 'localhost'
        server_port = int(global_router['Port'])
        logger.debug("Binding to localhost port " + str(server_port))
        self.server_socket.bind((server_name, server_port))
        self.server_socket.listen()
        inactive_list_size = len(self.inactive_list)

        conn, addr = self.server_socket.accept()
        self.server_socket = conn
        logger.debug(f"Connected by {addr}")
        while True:

            data, client_address = self.server_socket.recvfrom(1024)
            local_copy_LSA = pickle.loads(data)

            logger.debug("Received local_copy_LSA: " +str(local_copy_LSA))

            # Handle case if message received is a heartbeat message
            if isinstance(local_copy_LSA , list):

                # Get current date and time at which heart beat for
                # respective router was received
                now = datetime.now()
                RID = local_copy_LSA[0]['RID']

                neighbour_stats[RID]['HB received'] += 1 
                logger.info(f"Received HB from {RID}") 

                # Update local routers database of heart beat timestamps
                # for each neighbouring router (provided it is still alive)
                if RID not in self.inactive_list:
                    self.HB_set.update({RID : now})

                # Periodically check for any dead neighbours and update
                # inactive list of routers
                Timer(NODE_FAILURE_INTERVAL, self.checkForNodeFailure).start()

                # If the list of inactive routers is ever updated, we must transmit
                # a new LSA to notify other routers of the update to the topology
                if len(self.inactive_list) > inactive_list_size:

                    logger.debug("UPDATING NEIGHBOURS")

                    # Update this router's list of neighbours using inactive list
                    self.updateNeighboursList()

                    # If new routers have been declared dead, we need to transmit
                    # a fresh LSA with updated neighbour information
                    self.transmitNewLSA()

                    # Clear the set so that the fresh set
                    # will only track active neighbours
                    self.HB_set.clear()

                    # Update size of inactive list
                    inactive_list_size = len(self.inactive_list)

            # Handle case if the message received is an LSA
            else:

                logger.debug("Received LSA: " + str(local_copy_LSA))

                RID = local_copy_LSA['RID']

                logger.info("Received LSA from {0}".format(RID))

                # Might get a LSA from non-neighbour
                try:
                    neighbour_stats[RID]['LSA received'] += 1 
                except KeyError:
                    stats_dict = {}
                    stats_dict['HB sent'] = 0
                    stats_dict['HB received'] = 0
                    stats_dict['LSA sent'] = 0
                    stats_dict['LSA received'] = 1

                    neighbour_stats[RID] = stats_dict 

                # Grab list of neighbouring routers of router that sent this LSA
                neighbour_routers = global_router['Neighbours Data']

                # Grab 'FLAG' field from LSA received
                flag = local_copy_LSA['FLAG']

                # Append this router's ID to LSA_SN database
                self.LSA_SN.update({global_router['RID'] : 0})

                # Any new LSA received that have not been seen before are stored within this
                # routers local link-state database
                if local_copy_LSA['RID'] not in self.packets:
                    logger.info("LSA received from {0} is new".format(local_copy_LSA['RID']))
                    self.packets.add(local_copy_LSA['RID'])
                    self.LSA_SN.update({local_copy_LSA['RID']: local_copy_LSA['SN']})
                    self.LSA_DB.update({local_copy_LSA['RID'] : local_copy_LSA})
                    
                    for router in neighbour_routers:
                        if router['NID'] != local_copy_LSA['RID']:
                            # If the LSA received does not exist within router database , forward it to neighbours
                            # If LSA exists within database, do not forward it (silently drop it)
                            logger.info("Sending update to " + str(router['NID']))
                            send_to_stream(router['NID'], pickle.dumps(self.LSA_DB[local_copy_LSA['RID']]))
                            neighbour_stats[router['NID']]['LSA sent'] += 1
                            time.sleep(1)
                    # Update global graph using constructed link-state database
                    self.updateGraph(graph, self.LSA_DB, 0)

                # If a router is removed from the topology, we receive an updated LSA
                # which we use to update the graph network.
                
                # (ALL UPDATED LSA HAVE A UNIQUE 'FLAG' WITH VALUE 1 TO IDENTIFY THEM)
                
                if flag is 1:
                    # If the LSA received has a SN number that is greater than the existing record of
                    # SN for that router, we can confirm that the LSA received is a fresh LSA
                    logger.debug("Flag is set")
                    if local_copy_LSA['SN'] > self.LSA_SN[local_copy_LSA['RID']]:
                        logger.debug("LSA SN is {0} greater than {1}".format(local_copy_LSA['SN'], self.LSA_SN[local_copy_LSA['RID']]))
                        self.LSA_SN.update({local_copy_LSA['RID'] : local_copy_LSA['SN']})
                        self.LSA_DB.update({local_copy_LSA['RID'] : local_copy_LSA})
                        # If the new LSA has any router listed as inactive (i.e dead) we remove these explicitly from
                        # the topology so that they are excluded from future shortest path calculations
                        if len(local_copy_LSA['DEAD']) > 0:
                            self.updateLSADB(local_copy_LSA['DEAD'])
                            self.updateGraphOnly(graph, local_copy_LSA['DEAD'])
                        # Send the new LSA received back to the sending router (so as to ensure that it is a two-way
                        # update for the sender and recipient's local database)
                        logger.info("Sending update to " + str(local_copy_LSA['RID']))
                        send_to_stream(local_copy_LSA['RID'], pickle.dumps(self.LSA_DB[local_copy_LSA['RID']]))
                        neighbour_stats[local_copy_LSA['RID']]['LSA sent'] += 1
                        time.sleep(1)
                    else:
                        # If old data is being received, that is, there is no new LSA, we simply forward the message
                        # onto our neighbours (now with the list of updated neighbours and higher SN)
                        logger.debug("LSA is old - forwarding to my neighbours")
                        for new_router in global_router['Neighbours Data']:
                            if new_router['NID'] != global_router['RID']:
                                try:
                                    logger.debug("Nothing to do, forwarding LSA to " + str(local_copy_LSA['RID']))
                                    send_to_stream(new_router['NID'], pickle.dumps(self.LSA_DB[local_copy_LSA['RID']]))
                                    neighbour_stats[new_router['NID']]['LSA sent'] += 1
                                except KeyError:
                                    pass
                            time.sleep(1)
                    # After getting a fresh LSA, we wait for sometime (so that the global graph can update) and then
                    # recompute shortest paths using Dijkstra algorithm
                    Timer(10, self.updateGraphAfterFailure, [
                        graph,
                        self.inactive_list,
                        self.LSA_DB,
                        1,
                        self.thread_lock]
                    ).start()

    # Helper function to update the global graph when a router
    # in the topology fails
    def updateGraphOnly(self, graph_arg, dead_list):

        for node in graph_arg:
            if node[0] in dead_list:
                graph_arg.remove(node)
            if node[1] in dead_list:
                graph_arg.remove(node)

    # Update this router's local link-state database
    # after a router fails
    def updateLSADB(self, lsa_db):

        for node in lsa_db:
            if node in self.LSA_DB:
                del self.LSA_DB[node]

    # Period function that runs in the HeartBeat Thread
    # Used to check for any failed nodes in the topology
    def checkForNodeFailure(self):

        current_time = datetime.now()
        td = timedelta(seconds=TIMEOUT)

        for node in self.HB_set:
            difference = current_time - self.HB_set[node]
            if difference > td:
                if node not in self.inactive_list:
                    self.inactive_list.add(node)

    # Helper function to update this router's list
    # of active neighbours after a router fails
    def updateNeighboursList(self):

        for node in global_router['Neighbours Data']:
            if node['NID'] in self.inactive_list:
                global_router['Neighbours Data'].remove(node)

    # Triggered by all active neighbouring routers
    # when a neighbour to them fails
    def transmitNewLSA(self):

        server_name = 'localhost'
        updated_global_router = {}

        updated_global_router['RID'] = global_router['RID']
        updated_global_router['Port'] = global_router['Port']

        global_router['Neighbours'] = global_router['Neighbours'] - 1

        updated_global_router['Neighbours'] = global_router['Neighbours']
        updated_global_router['Neighbours Data'] = global_router['Neighbours Data']

        global_router['SN'] = global_router['SN'] + 1
        updated_global_router['SN'] = global_router['SN']

        updated_global_router['FLAG'] = 1
        updated_global_router['DEAD'] = self.inactive_list

        new_data = pickle.dumps(updated_global_router)

        for router in global_router['Neighbours Data']:
            logger.debug("SENT THIS NEW LSA TO {0}".format(router['NID']))
            #self.server_socket.sendto(new_data , (server_name , int(router['Port'])))
            send_to_stream(router['NID'], new_data)
            neighbour_stats[router['NID']]['LSA sent'] += 1

        time.sleep(1)

    def updateGraphAfterFailure(self, *args):

        if args[3] is 1:
            try:
                for node in args[2]:
                    if args[2][node]['RID'] in args[1]:
                        del args[2][node]
            except RuntimeError:
                pass

        for node in args[0]:
            if node[0] in args[1]:
                args[0].remove(node)
            if node[1] in args[1]:
                args[0].remove(node)

        for node in args[2]:
            for router in args[2][node]['Neighbours Data']:
                if router['NID'] in args[1]:
                    args[2][node]['Neighbours Data'].remove(router)

        self.updateGraph(args[0], args[2], 1)

    # Helper function that builds a useful data structure
    # that will in turn be used by another helper function
    # to construct an adjacency list from the global graph.
    # The adjacency list is then in turn used by the
    # Dijkstra function to compute shortest path
    def updateGraph(self, graph_arg, lsa_data, flag):

        logger.debug("Updating graph:")
        logger.debug(graph_arg)
        logger.debug("With LSA data:")
        logger.debug(lsa_data)

        if flag is 1:

            graph.clear()

        for node in lsa_data:

            source_node = lsa_data[node]['RID']
            neighbours_dict = lsa_data[node]['Neighbours Data']
            neighbours_list = []

            for neighbour in neighbours_dict:
                if (source_node < neighbour['NID']):
                    graph_data = [source_node, neighbour['NID'], neighbour['Cost'], neighbour['Port']]
                else:
                    graph_data = [neighbour['NID'], source_node, neighbour['Cost'], neighbour['Port']]
                neighbours_list.append(graph_data)

            for node in neighbours_list:
                exists = False
                for graph_node in graph_arg:
                    if node[0] == graph_node[0] and node[1] == graph_node[1]:
                        exists = True
                        break
                if exists is False:
                    graph_arg.append(node)

        # Get adjacency list and list of graph nodes
        adjacency_list , graph_nodes = self.organizeGraph(graph_arg)

        # Run Dijkstra's algorithm periodically
        Timer(ROUTE_UPDATE_INTERVAL, self.runDijkstra, [adjacency_list, graph_nodes]).start()

    # Uses the global graph to construct a adjacency list
    # (represented using python 'dict') which in turn is
    # used by the Dijkstra function to compute shortest paths
    def organizeGraph(self, graph_arg):

        # Set to contain nodes within graph
        nodes = set()

        # Determine nodes in entire topology
        # and update set of nodes
        for node in graph_arg:
            if node[0] not in nodes:
                nodes.add(node[0])
            if node[1] not in nodes:
                nodes.add(node[1])

        # Sort nodes alphabetically
        sorted_nodes = sorted(nodes)

        # Create dict to store all edges between
        # vertices as an adjacency list
        new_LL = dict()
        for node in sorted_nodes:
            new_LL[node] = dict()

        # Using all link-state advertisement received
        # from all nodes, create the initial adjacency list
        # based solely on data received from neighbours
        for node in sorted_nodes:
            for link in graph_arg:
                if node == link[0]:
                    new_LL[node].update({link[1] : link[2]})

        # Update adjacency list so as to reflect all outgoing/incoming
        # links (Graph should now fully represent the network topology
        for node in sorted_nodes:
            for source_node , cost in new_LL[node].items():
                new_LL[source_node].update({node : cost})

        # Return adjacency list and least_cost_path dict
        # to use for Dijkstra Computation
        return (new_LL , sorted_nodes)

    # Runs Dijkstra's algorithm on the given adjacency list
    # and prints out the shortest paths. Makes use of
    # python's heapq
    def runDijkstra(self, *args):

        # Use each router ID as start vertex for algorithm
        start_vertex = global_router['RID']
        # Initially, distances to all vertices (except source) is infinity
        distances = {vertex: float('infinity') for vertex in args[0]}
        # Distance to source node is 0
        distances[start_vertex] = 0

        # Create a least cost path dict to be updated using
        # Dijkstra calculation
        least_cost_path = {}
        for node in args[0]:
            least_cost_path[node] = []

        # Add start vertex to priority queue
        pq = [(0 , start_vertex)]
        while len(pq) > 0:
            # Pop item from queue and grab distance and vertex ID
            current_distance , current_vertex = heapq.heappop(pq)
            if current_distance > distances[current_vertex]:
                continue
            for n , w in args[0][current_vertex].items():
                # Round path cost to 1 d.p
                distance = round((current_distance + w) , 1)
                # If aggregated cost is less than current known cost,
                # update cost to that vertex
                if distance < distances[n]:
                    distances[n] = distance
                    least_cost_path[n].append(current_vertex)
                    # Push next neighbour onto queue
                    heapq.heappush(pq , (distance , n))

        # Finalise path array
        final_paths = []
        for node in args[0]:
            path_string = ""
            if node != global_router['RID']:
                end_node = node
                while(not (path_string.endswith(global_router['RID']))):
                    temp_path = least_cost_path[node][-1]
                    path_string = path_string + temp_path
                    node = temp_path
                path_string = (path_string)[::-1] + end_node
                final_paths.append(path_string)

        # Display final output after Dijkstra computation
        self.showPaths(final_paths , distances , global_router['RID'])

    def showPaths(path, graph_nodes, distances, source_node):

        global display_paths

        # Delete source node from list of paths
        del distances[source_node]

        # Print router ID
        display_paths = "I am Router {0} and know these paths:\n".format(source_node)

        index = 0
        # Display output for dijkstra
        for vertex in distances:
            display_paths = display_paths + "Least cost path to router {0}:{1} and the cost is {2}\n".format(
                vertex,
                graph_nodes[index],
                distances[vertex])
            
            index = index + 1

class SendThread(Thread):

    def __init__(self, name, thread_lock):
        Thread.__init__(self)
        self.name = name
        self.thread_lock = thread_lock
        self.client_socket = socket(AF_INET, SOCK_STREAM)

    def run(self):
        self.clientSide()

    def __str__(self):
        return "I am Router {0}".format(global_router['RID'])

    def __del__(self):
        self.client_socket.close()

    def clientSide(self):

        while True:
            
            message = pickle.dumps(global_router)
            
            for dict in global_router['Neighbours Data']:
                logger.debug("Sending neighbour data for " + str(dict['NID']))
                logger.debug(global_router)
                send_to_stream(dict['NID'], message)
                neighbour_stats[dict['NID']]['LSA sent'] += 1

            time.sleep(UPDATE_INTERVAL)

class HeartBeatThread(Thread):

    def __init__(self, name, HB_message, thread_lock):
        Thread.__init__(self)
        self.name = name
        self.HB_message = HB_message
        self.thread_lock = thread_lock

    def run(self):
        self.broadcastHB()

    def broadcastHB(self):

        while True:
            for neighbour in global_router['Neighbours Data']:
                logger.debug("Sending HB to " + str(neighbour['NID']))
                message = pickle.dumps(self.HB_message)
                send_to_stream( neighbour['NID'], message)
                neighbour_stats[neighbour['NID']]['HB sent'] += 1 
            
            time.sleep(PERIODIC_HEART_BEAT)

    def __del__(self):
        self.HB_socket.close()




def print_stats():

    while True:
        os.system('clear')
        print("Router ID: " + str(global_router['RID']))
        print("SN: " + str(global_router['SN']))
        print("Flag: " + str(global_router['FLAG']))
        print()
        print("Number of neighbours: " + str(global_router['Neighbours']))
        print()
        print("Neighbours:")
        print()
        print(" %-15s %5s %8s %8s %8s %8s" % ('Peer', 'Cost', 'HB sent', 'HB rcvd', 'LSA sent', 'LSA rcvd'))
    
        for neighbour in global_router['Neighbours Data']:
            print( " %-15s %5s %8s %8s %8s %8s" % 
                (neighbour['NID'], neighbour['Cost'], 
                 neighbour_stats[neighbour['NID']]['HB sent'],
                 neighbour_stats[neighbour['NID']]['HB received'],
                 neighbour_stats[neighbour['NID']]['LSA sent'],
                 neighbour_stats[neighbour['NID']]['LSA received'])
                )
    
        print()
        print("Computed shortest paths (Dijsktra)")
        print()
        if display_paths:
            print(display_paths)

        time.sleep(3)



def start_router(router_id, router_port):

    global global_router
    global circuit_info
    global neighbour_stats
    global threads
    global threadLock

    # Dictionary to hold data of current router
    global_router = {}
    circuit_info = {}
    neighbour_stats = {}
    display_paths = 'No current paths'

    # Parse data related to the current router
    global_router['RID'] = router_id
    global_router['Port'] = router_port
    global_router['Neighbours'] = 0
    global_router['Neighbours Data'] = []
    global_router['SN'] = 0
    global_router['FLAG'] = 0

    # Create a list to hold each thread
    threads = []

    # Create a lock to be used by all threads
    threadLock = Lock()

    logger.info("Started router " + str(router_id))

def add_neighbour(r_id, r_cost, r_hostname, r_port, circuit, circuit_id, stream, stream_id, receive_node=None, extend_node=None, receive_socket=None):

    # Dict to hold data regarding each of this router's neighbours
    global graph
    router_dict = {}
    circuit_dict = {}
    stats_dict = {}

    # For LSA
    router_dict['NID']  = r_id
    router_dict['Cost'] = float(r_cost)
    router_dict['Hostname'] = r_hostname
    router_dict['Port'] = r_port
    router_dict['FLAG'] = 0

    # Internal to router
    circuit_dict['NID']  = r_id
    circuit_dict['Circuit'] = circuit
    circuit_dict['Circuit ID'] = circuit_id
    circuit_dict['Stream'] = stream
    circuit_dict['Stream ID'] = stream_id
    circuit_dict['Receive Node'] = receive_node
    circuit_dict['Extend Node'] = extend_node
    circuit_dict['Receive Socket'] = receive_socket

    # Append the dict to current routers dict of neighbours data
    global_router['Neighbours Data'].append(router_dict)
    global_router['Neighbours'] += 1

    # Add circuit info for this neighbour
    circuit_info[r_id] = circuit_dict

    # Add stats for this neighbour
    stats_dict['HB sent'] = 0
    stats_dict['HB received'] = 0
    stats_dict['LSA sent'] = 0
    stats_dict['LSA received'] = 0

    neighbour_stats[r_id] = stats_dict    

    # Temporary graph list to hold state of current network topology
    temp_graph = []

    # Grab data about all the neighbours of this router
    for neighbour in global_router['Neighbours Data']:

        # Dict to hold data regarding each of this router's neighbours
        router_dict = {}

        router_dict['NID']  = neighbour['NID']
        router_dict['Cost'] = float(neighbour['Cost'])
        router_dict['Port'] = neighbour['Port']

        # Package this routers data in a useful format and append to temporary graph list
        if(str(global_router['RID']) < str(router_dict['NID'])):
             graph_data = [global_router['RID'], router_dict['NID'], router_dict['Cost'], router_dict['Port']]
        else:
             graph_data = [router_dict['NID'], global_router['RID'], router_dict['Cost'], router_dict['Port']]
        temp_graph.append(graph_data)

    # Copy over the data in temporary graph to global graph object (used elsewhere)
    graph = temp_graph[:]

    logger.info("Added neighbour " + str(r_id))

def send_to_stream(router_id, message):

    stream_data = circuit_info[router_id]

    # If we have a stream object send to it 
    if stream_data['Stream']:
        stream_data['Stream'].send(message)
    else:
        # else create the cells
        server.snd_data(message, 
                        stream_data['Circuit ID'], 
                        stream_data['Extend Node'], 
                        stream_data['Receive Node'], 
                        stream_data['Receive Socket'],
                        stream_data['Stream ID'])

if __name__ == "__main__":

    # Dictionary to hold data of current router
    global_router = {}

    # Open file for reading
    with open(sys.argv[1]) as f:
        data = f.read().split('\n')

    # Split the data on " "
    ID = data[0].split(" ")

    # Parse data related to the current router
    global_router['RID'] = ID[0]
    global_router['Port'] = ID[1]
    global_router['Neighbours'] = int(data[1])
    global_router['Neighbours Data'] = []
    global_router['SN'] = 0
    global_router['FLAG'] = 0

    # Temporary graph list to hold state of current network topology
    temp_graph = []

    # Grab data about all the neighbours of this router
    for line in range(2 , len(data) - 1):

        # Dict to hold data regarding each of this router's neighbours
        router_dict = {}

        neighbour = data[line].split(" ")

        router_dict['NID']  = neighbour[0]
        router_dict['Cost'] = float(neighbour[1])
        router_dict['Port'] = neighbour[2]

        # Append the dict to current routers dict of neighbours data
        global_router['Neighbours Data'].append(router_dict)

        # Package this routers data in a useful format and append to temporary graph list
        if(global_router['RID'] < router_dict['NID']):
             graph_data = [global_router['RID'], router_dict['NID'], router_dict['Cost'], router_dict['Port']]
        else:
             graph_data = [router_dict['NID'], global_router['RID'], router_dict['Cost'], router_dict['Port']]
        temp_graph.append(graph_data)

    # Copy over the data in temporary graph to global graph object (used elsewhere)
    graph = temp_graph[:]

    # Create a list to hold each thread
    threads = []

    # Create a lock to be used by all threads
    threadLock = Lock()

    # Create heart beat message to transmit
    HB_message = [{'RID' : global_router['RID']}]

    sender_thread = SendThread("SENDER", global_router, threadLock)
    receiver_thread = ReceiveThread("RECEIVER", global_router, threadLock)
    heartbeat_thread = HeartBeatThread("HEART BEAT", HB_message, global_router['Neighbours Data'], threadLock)

    # Start each thread
    sender_thread.start()
    receiver_thread.start()
    heartbeat_thread.start()

    # Append each thread to list of threads
    threads.append(sender_thread)
    threads.append(receiver_thread)
    threads.append(heartbeat_thread)

    # Call join on each tread (so that they wait)
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print(graph)

    logger.debug("Exiting Main Thread")
    
