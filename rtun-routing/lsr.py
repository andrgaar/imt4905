import os
import sys
import pickle
import time
import heapq
import socket
import traceback
import json
import jsonpickle
import pandas as pd
import hashlib
import random
import string
import networkx as nx
import copy

from datetime import datetime, timedelta
from threading import Thread, Lock, Timer
from socket import socket, create_server, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from queue import Queue # Queues messages to a thread

from torpy.circuit import TorCircuit
from torpy.stream import TorStream
from torpy.consesus import TorConsensus
from torpy.documents.network_status import RouterFlags

#import server
import messages
import rendezvous as rnd

import logging
logger = logging.getLogger(__name__)

UPDATE_INTERVAL = 15
ROUTE_UPDATE_INTERVAL = 15
PERIODIC_HEART_BEAT = 5
NODE_FAILURE_INTERVAL = 10
TIMEOUT = 15
LATENCY_SAMPLES = 10
PERIODIC_CONN_CHECK = 60
MIN_NEIGHBOUR_CONNECTIONS = 4
MAX_CONNECTION_TIME = 300

# Log metrics to file
graph_metrics_file = "router.log"

# Global graph object to represent network topology
G = None
graph = {}
global_least_cost_path = {}
shortest_paths = None
path_cost = {}
global_router = {}
circuit_info = {}
neighbour_stats = {}
rendp_conn = set()
display_paths = None
threadLock = None
threads = None
HB_time = 0 #  the last HB to be sent
join_queue = [] # relays to join
log_queue = None # log data
receiver_thread = None
'''
LSA structure:

RID = str : Own ID
Port = int: Own router port
SN = int : Sequence no of LSA
FLAG = 0|1 : Update flag
RP = set { relay|cookie } : RPs to connect to this node
Neighbours = int : Number of neighbours
Neighbours Data = []
    {
     NID  = str : ID of neighbour
     Cost = int : Cost of route
     Hostname = str : Hostname of neighbour
     RP = str : Rendezvous Point
     FLAG = 0
    }

JOIN message:
{
    Message: JOIN
    Destination: <Peer ID>
    Source: <Peer ID>
    Relay: <RP relay>
    Cookie: <Cookie>
}

LOOKUP message:
{
    Destination: <Peer ID>
    Source: <Peer ID>
    Path: [<path>]
}
'''
# This class handles data that comes on the routing stream
class ReceiveThread(Thread):

    def __init__(self, name, rcv_queue, conn_queue, thread_lock):
        Thread.__init__(self)
        self.name = name
        self.queue = rcv_queue
        self.conn_queue = conn_queue
        self.thread_lock = thread_lock
        self.packets = set()
        self.LSA_SN = {}
        self.LSA_SN_forwarded = {}
        self.HB_set = {}
        self.LSA_DB = {}
        self.inactive_list = set()
        self.inactive_list_size = 0
        self.forward_set = set()


    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def run(self):
        try:
            Timer(NODE_FAILURE_INTERVAL, self.checkForNodeFailure).start()

            while True:
                queue_data = self.queue.get()
                self.serverSide(queue_data)

        except Exception as e:
            logger.error("Error in ReceiveThread: " + str(e))
            traceback.print_exc()


    def __str__(self):
        return "I am Router {0} with - READY TO RECEIVE".format(
            global_router['RID']
        )

    def __del__(self):
        pass

    def serverSide(self, queue_data):

        # Load received data to format
        try:
            local_copy_LSA = pickle.loads(queue_data[0]['data'])
        except Exception as e:
            logger.error(e)
            return

        circuit = queue_data[0]['circuit']
        circuit_id = queue_data[0]['circuit_id']
        stream = queue_data[0]['stream']
        stream_id = queue_data[0]['stream_id']
        receive_node = queue_data[0]['receive_node']
        extend_node = queue_data[0]['extend_node']
        receive_socket = queue_data[0]['receive_socket']
        rendpoint = queue_data[0]['rendpoint']
        thread_id = queue_data[0]['thread_id']

        if log_queue:
            log_queue.put_nowait( local_copy_LSA )

        # Handle case if message received is a heartbeat message or other
        if isinstance(local_copy_LSA , list):

            message = local_copy_LSA[0]['Message']
            
            if message == 'HB':
                self.handle_HB(local_copy_LSA)
            elif message == 'HELLO':
                self.handle_HELLO(local_copy_LSA, rendpoint, circuit, circuit_id, stream, stream_id, receive_node, extend_node, receive_socket, thread_id)
            elif message == 'JOIN':
                self.handle_JOIN(local_copy_LSA)
            elif message == 'LOOKUP':
                self.handle_LOOKUP(local_copy_LSA)
            elif message == 'REMOVE':
                self.remove_neighbour([local_copy_LSA[0]['Destination']])
            elif message == 'CLOSE':
                thread_id = local_copy_LSA[0]['Thread ID']
                ci = circuit_info
                for c in ci.values():
                    if c['Thread ID'] == thread_id:
                        self.inactive_list.add(c['NID'])
                        self.remove_inactive()
                        break

            else:
                logger.info(f"Unknown message: {message}")
            
        # Handle case if the message received is an LSA
        else:

            RID = local_copy_LSA['RID']

            logger.debug("Received LSA from {0} with SN: {1} and FLAG: {2}".format(RID, local_copy_LSA['SN'], local_copy_LSA['FLAG']))

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
            #self.LSA_SN.update({global_router['RID'] : 0})

            # Any new LSA received that have not been seen before are stored within this
            # routers local link-state database
            if local_copy_LSA['RID'] not in self.packets:
                logger.debug("LSA received from {0} is new".format(local_copy_LSA['RID']))
                self.packets.add(local_copy_LSA['RID'])
                self.LSA_SN.update({local_copy_LSA['RID']: local_copy_LSA['SN']})
                self.LSA_SN_forwarded.update({local_copy_LSA['RID']: -1})
                self.LSA_DB.update({local_copy_LSA['RID'] : local_copy_LSA})
                
                # Update global graph using constructed link-state database
                self.updateGraph(graph, self.LSA_DB, 0)

            # If a router is removed from the topology, we receive an updated LSA
            # which we use to update the graph network.
            
            # (ALL UPDATED LSA HAVE A UNIQUE 'FLAG' WITH VALUE 1 TO IDENTIFY THEM)
            
            elif flag == 1:
                # If the LSA received has a SN number that is greater than the existing record of
                # SN for that router, we can confirm that the LSA received is a fresh LSA
                logger.debug("Flag is set")
                if local_copy_LSA['SN'] > self.LSA_SN[local_copy_LSA['RID']]:
                    logger.debug("LSA SN is {0} greater than {1}".format(local_copy_LSA['SN'], self.LSA_SN[local_copy_LSA['RID']]))
                    self.LSA_SN.update({local_copy_LSA['RID'] : local_copy_LSA['SN']})
                    self.LSA_DB.update({local_copy_LSA['RID'] : local_copy_LSA})
                    # If the new LSA has any router listed as inactive (i.e dead) we remove these explicitly from
                    # the topology so that they are excluded from future shortest path calculations
                    if 'DEAD' in local_copy_LSA and len(local_copy_LSA['DEAD']) > 0:
                        #log_metrics("DEAD ROUTES RECEIVED", local_copy_LSA['DEAD'])
                        self.updateLSADB(local_copy_LSA['DEAD'])
                        self.updateGraphOnly(graph, local_copy_LSA['DEAD'])
                
                    # After getting a fresh LSA, we wait for sometime (so that the global graph can update) and then
                    # recompute shortest paths using Dijkstra algorithm
                    Timer(2, self.updateGraphAfterFailure, [
                            graph,
                            self.inactive_list,
                            self.LSA_DB,
                            1,
                            self.thread_lock]
                        ).start()
                else:
                    logger.debug("Update LSA is old, forwarding only")

            # Forward the LSA to our neighbours if it hasn't already
            if RID != global_router['RID'] and self.LSA_SN_forwarded[RID] < local_copy_LSA['SN']:
                for router in neighbour_routers:
                    if router['NID'] != local_copy_LSA['RID']:
                        send_to_stream(router['NID'], pickle.dumps(self.LSA_DB[local_copy_LSA['RID']]))
                        neighbour_stats[router['NID']]['LSA sent'] += 1
                        time.sleep(1)
                # Update the forwarded SN for this peer
                self.LSA_SN_forwarded.update({local_copy_LSA['RID']: local_copy_LSA['SN']})




    # Handle receive of HELLO
    def handle_HELLO(self, msg_data, rendpoint, circuit, circuit_id, stream, stream_id, receive_node=None, extend_node=None, receive_socket=None, thread_id=None):
        logger.debug(f"handle_HELLO: {msg_data}")        
        peer_id = msg_data[0]['Peer']
        # remove from inactive_list if
        if peer_id in self.inactive_list:
            self.inactive_list.remove(peer_id)
            self.inactive_list_size = len(self.inactive_list)

        add_neighbour(peer_id, '127.0.0.1', rendpoint, 100, circuit, circuit_id, stream, stream_id, receive_node, extend_node, receive_socket, thread_id)
        global_router['FLAG'] = 1 # update LSA
        global_router['SN'] = global_router['SN'] + 1 # increment to trigger update LSA


    # Handle receive of HeartBeat
    def handle_HB(self, msg_data):
        logger.debug(f"handle_HB: {msg_data}")
        # Get current date and time at which heart beat for
        # respective router was received
        now = current_milli_time()
        RID = msg_data[0]['RID']
        HBref = msg_data[0]['HBref']
        HBresp = msg_data[0]['HBresp']

        # Return if RID unknown
        if RID not in neighbour_stats:
            logger.debug(f"Key {RID} not in neighbour_stats")
            return

        neighbour_stats[RID]['HB received'] += 1 
        #logger.info(f"Received HB from {RID} ref: {HBref} resp: {HBresp}") 

        # Update local routers database of heart beat timestamps
        # for each neighbouring router (provided it is still alive)
        if RID not in self.inactive_list:
            self.HB_set.update({RID : datetime.now()})

            # Craft a response HB message if it is a ping
            if HBresp == 0:
                HB_message = [{'Message' : 'HB', 'RID' : global_router['RID'], 'HBref' : HBref, 'HBresp' : now}]
                #logger.info("Sending HB response to " + str(RID))
                message = pickle.dumps(HB_message)
                send_to_stream( RID, message)

            # Last sent HB timestamp matches received HB
            elif HBref == HB_time:
                # Set the latency for the neighbour
                latency_list = neighbour_stats[RID]['Latencies MS']
                latency = now - HBref
                latency_list.append(latency) 
                #log_metrics("MEASURED LATENCY", {RID : latency})
                # If we have enough measurements update the cost
                if len(latency_list) == LATENCY_SAMPLES:
                    avg_latency = round( sum(latency_list) / len(latency_list) )
                    latency_list = list()

                    for i in range(len(global_router['Neighbours Data'])):
                        if global_router['Neighbours Data'][i]['NID'] == RID:
                            global_router['Neighbours Data'][i]['Cost'] = int(avg_latency)
                            global_router['FLAG'] = 1 # update LSA
                            global_router['SN'] = global_router['SN'] + 1 # increment to trigger update LSA
                            #log_metrics("APPLIED LATENCY", json.dumps({RID : latency}))
                            break

                    neighbour_stats[RID]['Latencies MS'] = latency_list 
            else:
                logger.debug("HBref does not match last sent, skipping")

        # Periodically check for any dead neighbours and update
        # inactive list of routers
        #Timer(NODE_FAILURE_INTERVAL, self.checkForNodeFailure).start()


    # Removes a dead route
    def remove_inactive(self):
        logger.info("DEAD ROUTES DETECTED: {0}", format( ','.join(self.inactive_list)))

        # Update this router's list of neighbours using inactive list
        self.updateNeighboursList()

        # Remove circuit connection
        remove_circuit(self.inactive_list)

        # Update the LSA_DB and graph
        self.updateLSADB(self.inactive_list)
        self.updateGraphOnly(graph, self.inactive_list)
            
        # If new routers have been declared dead, we need to transmit
        # a fresh LSA with updated neighbour information
        self.transmitNewLSA()

        # Clear the set so that the fresh set
        # will only track active neighbours
        self.HB_set.clear()

        # Update size of inactive list
        self.inactive_list_size = len(self.inactive_list)

        Timer(1, self.updateGraphAfterFailure, [
                graph,
                self.inactive_list,
                self.LSA_DB,
                1,
                self.thread_lock]
            ).start()

    # Handles a JOIN message 
    def handle_JOIN(self, msg_data):
        logger.debug(f"handle_JOIN: {msg_data}")

        destination = msg_data[0]['Destination']
        source = msg_data[0]['Source']
        relay = msg_data[0]['Relay']
        cookie = msg_data[0]['Cookie']

        # If we are the source - drop it
        if source == global_router['RID']:
            logger.debug(f"We are source of JOIN - dropping")
            return

        # If it's for us - add it to join queue
        if destination == global_router['RID']:
            logger.debug(f"We are destination of JOIN message")
            #neighbours = set()
            #for n in global_router['Neighbours Data']:
            #    neighbours.add(n['NID'])
            
            #if source in neighbours:
                # remove neighbour connection
            #    self.remove_neighbour([source])

            self.conn_queue.put_nowait(["JOIN", relay, cookie])
            logger.info(f"Added relay {relay} from {source} to JOIN queue")
            #else:
            #    logger.info(f"{source} already a neighbour")

            return 

        # If for someone else - route it along
        logger.debug(f"Routing JOIN message")
        route_message(msg_data)

    # Handles a LOOKUP message
    def handle_LOOKUP(self, msg_data):
        logger.debug(f"handle_LOOKUP: {msg_data}")
        
        source = msg_data[0]['Source']
        destination = msg_data[0]['Destination']
        ident = msg_data[0]['ID']

        if global_router['RID'] in msg_data[0]['Path']:
            msg_data[0]['Path'].append(global_router['RID'])
            path = '-'.join(msg_data[0]['Path'])
            # it's a routing loop
            logger.warn(f"Routing loop: {path}")
            return
        else:
            msg_data[0]['Path'].append(global_router['RID'])

        # This is for us
        if destination == global_router['RID']:
            #log_metrics("LOOKUP RECEIVED", json.dumps(msg_data))
            pass
        else:
            route_message(msg_data)

    # Handles a CLOSE message
    def handle_CLOSE(self, msg_data):
        logger.debug(f"handle_CLOSE: {msg_data}")
        
        tid = msg_data[0]['Thread ID']




    # Helper function to update the global graph when a router
    # in the topology fails
    def updateGraphOnly(self, graph_arg, dead_list):
        try:
            for node in graph_arg:
                if node[0] in dead_list:
                    graph_arg.remove(node)
                if node[1] in dead_list:
                    graph_arg.remove(node)
        except Exception as e:
            logger.warn(f"updateGraphOnly: {e}") 

    # Update this router's local link-state database
    # after a router fails
    def updateLSADB(self, lsa_db):

        for node in lsa_db:
            if node in self.LSA_DB:
                del self.LSA_DB[node]

    # Period function that runs in the HeartBeat Thread
    # Used to check for any failed nodes in the topology
    def checkForNodeFailure(self):

        while True:
            current_time = datetime.now()
            td = timedelta(seconds=TIMEOUT)

            for node in self.HB_set:
                difference = current_time - self.HB_set[node]
                if difference > td:
                    if node not in self.inactive_list:
                        self.inactive_list.add(node)
                        logger.info("Adding " + node + " to list of inactive")
            
            # If the list of inactive routers is ever updated, we must transmit
            # a new LSA to notify other routers of the update to the topology
            if len(self.inactive_list) > self.inactive_list_size:
                self.remove_inactive()

            time.sleep(NODE_FAILURE_INTERVAL)

    # Helper function to update this router's list
    # of active neighbours after a router fails
    def updateNeighboursList(self):

        for node in global_router['Neighbours Data']:
            if node['NID'] in self.inactive_list:
                global_router['Neighbours Data'].remove(node)
                logger.info("Removing " + node['NID'] + " from neighbours")




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

        if flag == 1:

            graph.clear()

        for node in lsa_data:

            source_node = lsa_data[node]['RID']
            neighbours_dict = lsa_data[node]['Neighbours Data']
            neighbours_list = []

            for neighbour in neighbours_dict:
                if (source_node < neighbour['NID']):
                    graph_data = [source_node, neighbour['NID'], neighbour['Cost'], neighbour['RP']]
                else:
                    graph_data = [neighbour['NID'], source_node, neighbour['Cost'], neighbour['RP']]
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
        adjacency_list , graph_nodes, rp_nodes = self.organizeGraph(graph_arg)

        # Log the updated graph to a metrics file
        #log_metrics("TOPOLOGY UPDATE", json.dumps(adjacency_list))
        
        # Run Dijkstra's algorithm 
        Timer(1, self.shortest_paths, [adjacency_list, graph_nodes, rp_nodes]).start()
        #Timer(ROUTE_UPDATE_INTERVAL, self.runDijkstra, [adjacency_list, graph_nodes, rp_nodes]).start()


    # Use adjancency list to compute shortest path to all non-neighbors
    def shortest_paths(self, adjacency_list, graph_nodes, rp_nodes):
        
        global G
        global shortest_paths
        global path_cost

        for k, d in adjacency_list.items():
                for ik in d:
                    d[ik] = {'weight': d[ik]}
            
        G = nx.Graph(adjacency_list)
        #for k in nx.neighbors(G, global_router['RID']):
        #    logger.info(f"Neighbor: {k}")
        #for k in nx.non_neighbors(G, global_router['RID']):
        #    logger.info(f"Not neighbor: {k}")
        try:
            shortest_paths = nx.shortest_path(G, global_router['RID'], weight='weight')
        except networkx.exception.NodeNotFound as e:
            logger.error(f"networkx.exception.NodeNotFound: {e}")
            sys.exit() # 

        for k, v in shortest_paths.items():
            cost = nx.path_weight(G, v, 'weight')
            path_cost[k] = cost

        #log_metrics("SHORTEST PATH", json.dumps(shortest_paths))

        
        

    # Uses the global graph to construct a adjacency list
    # (represented using python 'dict') which in turn is
    # used by the Dijkstra function to compute shortest paths
    def organizeGraph(self, graph_arg):

        logger.debug(f"organizeGraph(graph_arg): {graph_arg}")
        # Set to contain nodes within graph
        nodes = set()

        # Determine nodes in entire topology
        # and update set of nodes
        for node in graph_arg:
            if node[0] not in nodes:
                nodes.add(node[0])
                #nodes.add(node[0] + node[3])
            if node[1] not in nodes:
                nodes.add(node[1])
                #nodes.add(node[1]+node[3])

        # Sort nodes alphabetically
        sorted_nodes = sorted(nodes)

        # Create dict to store all edges between
        # vertices as an adjacency list
        new_LL = dict()
        new_RP = dict() # holds RP of peer
        for node in sorted_nodes:
            new_LL[node] = dict()
            new_RP[node] = dict()

        # Using all link-state advertisement received
        # from all nodes, create the initial adjacency list
        # based solely on data received from neighbours
        for node in sorted_nodes:
            for link in graph_arg:
                if node == link[0]:
                    new_LL[node].update({link[1] : link[2]})
                    new_RP[node].update({link[1] : link[3]})
                    logger.debug(f"adjancency list update: {link}")

        # Update adjacency list so as to reflect all outgoing/incoming
        # links (Graph should now fully represent the network topology
        for node in sorted_nodes:
            for source_node , cost in new_LL[node].items():
                new_LL[source_node].update({node : cost})
            for source_node , rp_node in new_RP[node].items():
                new_RP[source_node].update({node : rp_node})


        # Return adjacency list and least_cost_path dict
        # to use for Dijkstra Computation
        return (new_LL , sorted_nodes, new_RP)

    # Runs Dijkstra's algorithm on the given adjacency list
    # and prints out the shortest paths. Makes use of
    # python's heapq
    def runDijkstra(self, *args):
        global global_least_cost_path

        logger.debug(f"Running Dijkstra: {args}")
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
    
        global_least_cost_path = least_cost_path

        #log_metrics("LEAST COST PATH", json.dumps(least_cost_path))

        # Finalise path array
        final_paths = []
        temp_paths = []
        rp_paths = args[2]
        for node in args[1]:
            path_string = ""
            if node != global_router['RID']:
                end_node = node
                temp_node = node
                #temp_paths.append(temp_node)
                logger.debug(f"Build path for: {node}")
                #while(not (path_string.endswith(global_router['RID']))):
                #while( temp_node != global_router['RID'] ):
                #    logger.info(f"least cost path: {temp_node} : {least_cost_path[temp_node]}")
                #    temp_node = least_cost_path[node][-1]
                #    temp_paths.append(temp_node)
                

                for temp_node in least_cost_path[node]:
                    logger.debug(f"temp_node: {temp_node}")
                    if temp_node == global_router['RID']:
                        temp_paths.append(node)
                    else:
                        temp_paths.append(temp_node)

                prev_node = global_router['RID']

                while len(temp_paths) > 0:
                    next_node = temp_paths.pop()
                    logger.debug(f"prev_node: {prev_node} next_node: {next_node}")
                    rp_node = rp_paths[prev_node][next_node]
                    path_string = prev_node + '<<' + rp_node + '>>' + next_node


                #    if path_string == "":
                #        path_string = temp_path
                #    else:
                #        rp_node = rp_paths[temp_path][node]
                #        path_string = path_string + '<<' + rp_node + '>>' + temp_path
                #    node = temp_path
                #    logger.info(f"path_string: {path_string}")
                #path_string = (path_string)[::-1] + end_node
                #rp_node = rp_paths[node][end_node]
                #path_string = path_string + '<<' + rp_node + '>>' + end_node
                final_paths.append(path_string)

        # Display final output after Dijkstra computation
        self.showPaths(final_paths , distances , global_router['RID'])
    

    # Function to remove a neighbour from router
    def remove_neighbour(self, remove_list):
        for node in global_router['Neighbours Data']:
            if node['NID'] in remove_list:
                global_router['Neighbours Data'].remove(node)
                global_router['Neighbours'] -= 1
        
        remove_circuit(remove_list)      
        self.updateLSADB(remove_list)
        self.updateGraphOnly(graph, remove_list)
        self.HB_set.clear()


    def showPaths(path, graph_nodes, distances, source_node):

        global display_paths

        # Delete source node from list of paths
        del distances[source_node]

        # Print router ID
        display_paths = "I am {0} and know these paths:\n".format(source_node)

        index = 0
        # Display output for dijkstra
        for vertex in distances:
            display_paths = display_paths + "{0}: {1} and the cost is {2}\n".format(
                vertex,
                graph_nodes[index],
                distances[vertex])
            
            index = index + 1

        for vertex in distances:
            display_paths = display_paths + "{0} next hop {1}\n".format(vertex, next_hop(vertex))




class SendThread(Thread):

    def __init__(self, name, thread_lock):
        Thread.__init__(self)
        self.name = name
        self.thread_lock = thread_lock

    def run(self):
        self.clientSide()

    def __str__(self):
        return "I am Router {0}".format(global_router['RID'])

    def __del__(self):
        pass

    def clientSide(self):

        while True:
            lsa_tmp = global_router
            #lsa_tmp['FLAG'] = 1
            
            message = pickle.dumps(lsa_tmp)
            
            for dict in global_router['Neighbours Data']:
                send_to_stream(dict['NID'], message)
                neighbour_stats[dict['NID']]['LSA sent'] += 1

            global_router['FLAG'] = 0 # reset update LSA
            time.sleep(UPDATE_INTERVAL)

class HeartBeatThread(Thread):

    def __init__(self, name, HB_message, thread_lock, rcv_queue):
        Thread.__init__(self)
        self.name = name
        self.HB_message = HB_message
        self.thread_lock = thread_lock
        self.rcv_queue = rcv_queue

    def run(self):
        self.broadcastHB()

    def broadcastHB(self):
        global HB_time

        while True:
            HB_time = current_milli_time()
            HB_message = [{'Message' : 'HB', 'RID' : global_router['RID'], 'HBref' : HB_time, 'HBresp' : 0}]

            for neighbour in global_router['Neighbours Data']:
                message = pickle.dumps(HB_message)
                try:
                    send_to_stream( neighbour['NID'], message)
                    neighbour_stats[neighbour['NID']]['HB sent'] += 1 
                except KeyError as e:
                    message = [{'Message' : 'REMOVE', 'NID' : neighbour['NID']}]
                    self.rcv_queue.put_nowait(message)

            
            time.sleep(PERIODIC_HEART_BEAT)

    def __del__(self):
        pass

class LogThread(Thread):
    
    def __init__(self, name, logfile, queue):
        Thread.__init__(self)
        self.name = name
        self.logfile = logfile
        self.queue = queue

    def run(self):

        with open(self.logfile, "ab") as f:
            while True:
                d = self.queue.get()
                pd = [current_milli_time(), global_router['RID'], d]
                try:
                    pickle.dump(pd, f)
                except Exception as e:
                    logger.error(e)


# ConnectionThread periodically checks if neighbouring connections 
# satisfy criteria
class ConnectionThread(Thread):
    def __init__(self, name, conn_queue, rcv_queue):
        Thread.__init__(self)
        self.name = name
        self.conn_queue = conn_queue
        self.rcv_queue = rcv_queue

    def run(self):
        self.connections()

    def connections(self):

        RID = global_router['RID']

        while True:
            time.sleep(PERIODIC_CONN_CHECK)

            # check if we have enough connections
            #len_n = len(global_router['Neighbours Data'])
            if global_router['Neighbours'] >= MIN_NEIGHBOUR_CONNECTIONS:
            #    # find oldest connection to kill
                oldest = 0
                kill_tid = None
                threads_tmp = rnd.threads
                for tid, thd in threads_tmp.items():
                    # select only establisher thread
                    if type(thd).__name__ != 'RendezvousEstablish':
                        continue
                    if not thd.start_time:
                        continue
                    if thd.start_time > oldest:
                        kill_tid = tid
                        oldest = thd.start_time
                if not kill_tid: # no threads found
                    continue

                oldest_age = round(time.time() - oldest)
                logger.debug(f"Age of oldest thread is {oldest_age} seconds (MAX {MAX_CONNECTION_TIME})")
                if oldest_age > MAX_CONNECTION_TIME:
                    # find the peer id
                    join_peer = None
                    for c in circuit_info.values():
                        if c['Thread ID'] == kill_tid:
                            join_peer = c['NID']
                    if not join_peer:
                        continue
                    # find a new RP to join
                    rp_relay, rp_cookie = get_rendezvous_relay()
                    self.conn_queue.put_nowait(["ESTABLISH", rp_relay.nickname, rp_cookie])
                    time.sleep(10)
                    logger.info(f"Sending JOIN to {join_peer} for relay {rp_relay.nickname} with cookie {rp_cookie}")
                    message = [{'Message' : 'JOIN', 'Destination' : join_peer, 'Source' : RID, 'Relay' : rp_relay.nickname, 'Cookie' : rp_cookie}]
                    route_message(message)
                    #rejoin = [{'Message' : 'REJOIN', 'Destination' : join_peer}]
                    #receiver_thread.remove_neighbour([join_peer])
                    # kill the connection
                    #logger.info(f"Reached MAX_CONNECTION_TIME - killing thread {kill_tid}")
                    #threads_tmp[kill_tid].conn_queue.put(object())

                continue

            neighbours = set()
            for n in global_router['Neighbours Data']:
                neighbours.add(n['NID'])
           
            if len(neighbours) == 0:
                logger.info("Neighbour connections are 0, exiting...")
                sys.exit()

            logger.info("Neighbour connections ({0}) less than MIN_NEIGHBOUR_CONNECTIONS ({1})".format(len(neighbours), MIN_NEIGHBOUR_CONNECTIONS))
    
            # find all peers in network 
            peers = set()
            for e in graph:
                peers.add(e[0])
                peers.add(e[1])
            # remove myself from peers
            if RID in peers:
                peers.remove(RID)
            # remove neighbours from peers
            candidates = list(peers - neighbours)
            logger.info(f"Candidate peers: {candidates}")

            # find a candidate peer to join with highest latency
            join_peer = None
            peers_sorted = sorted(path_cost.items(), key=lambda x:x[1], reverse=True)
            logger.info(f"Highest cost peers: {peers_sorted}")
            for p in peers_sorted:
                if p[0] in candidates:
                    join_peer = p[0]
                    break
                       
            if not join_peer:
                logger.info("No join peers found")
                continue

            # Tell main thread to establish RP
            rp_relay, cookie = get_rendezvous_relay()
            self.conn_queue.put_nowait(["ESTABLISH", rp_relay.nickname, cookie])
            time.sleep(10)

            # Send JOIN to peer                
            logger.info(f"Sending JOIN to {join_peer} at relay {rp_relay.nickname}")
            message = [{'Message' : 'JOIN', 'Destination' : join_peer, 'Source' : RID, 'Relay' : rp_relay.nickname, 'Cookie' : cookie}]
            route_message(message)


    def __del__(self):
        pass



# Function to update the connections after failure
def remove_circuit(inactive_list):

    # remove circuits from inactive peers
    for p in inactive_list:
        if p not in circuit_info:
            continue
        ci = circuit_info[p]
        tid = ci['Thread ID']
        del circuit_info[p]
        # find the connection thread to close
        if tid in rnd.threads:
            th = rnd.threads[tid]
            th.close()
            del rnd.threads[tid]

# Routes it along the least cost path
def route_message(msg_data):
    logger.debug(f"route_message: {msg_data}")

    destination = msg_data[0]['Destination']
    source = msg_data[0]['Source']

    # If it's for us
    if destination == global_router['RID']:
        return destination

    # Find the neighbour with the least cost path to destination
    dst_relay = next_hop(destination)
    if dst_relay:
        # Send the message
        send_to_stream(dst_relay, pickle.dumps(msg_data))
        
    else:
        return 0

    return dst_relay
# Return the next hop in least cost path
def next_hop(dst_peer):
    logger.debug(f"next_hop: {global_least_cost_path}")
    
    this_peer = global_router['RID']
    
    # Work our way back the least path route to find
    # the next hop
    if not shortest_paths or not dst_peer in shortest_paths:
        return None

    next_peer = shortest_paths[dst_peer][1]
    
    logger.debug(f"Found next_hop: {next_peer}")
    return next_peer


# Get current time in ms
def current_milli_time():
    return round(time.time() * 1000)

# Lookup a value in the Neighbours list
def lookup_neighbour(NID, item):

    logger.info(f"Lookup {NID} : {item}")
    for n in global_router['Neighbours Data']:
        if n['NID'] == NID:
            logger.info(f"Lookup return: {n[item]}")
            return n[item]
    return "<none>"

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
        print("-------------------------------------------------------------------------")
        print("Shortest paths:")
        print()
        #if display_paths:
        #    print(display_paths)
        if shortest_paths:
            for k, v in shortest_paths.items():
                print(k, ": ", v, " total cost ", path_cost[k])
        print("-------------------------------------------------------------------------")
        print(" %-25s %-15s" % ('Circuit neighbour', 'Circuit ID'))
        print()
        for k in circuit_info:
            c = circuit_info[k]
            print(" %-25s #%x" % (c['NID'], c['Circuit ID']))

        print("-------------------------------------------------------------------------")
        print("Running threads:")
        print()
        for tid, thread in rnd.threads.items():
            print(tid, thread.name, thread.rendezvous_cookie)
        
        # output the topology to file
        time_stamp = time.time()
        with open('topology.log', "a") as f:
            f.write("{0};{1};{2}\n".format(time_stamp, 
                                            global_router['RID'], 
                                            json.dumps(graph)))


        time.sleep(3)

# Log metrics to file
def log_metrics(event, msg):
    time_stamp = time.time()
    with open(graph_metrics_file, "a") as f:
        f.write("{0};{1};{2};{3}\n".format(time_stamp, 
                                            global_router['RID'], 
                                            event,
                                            msg))

def setup_router(router_id, router_port):
    global receiver_thread
    # 
    # Initialize the router
    # 
    init_router(router_id, router_port)

    # Setup a queue for communicating with ReceiveThread
    rcv_queue = Queue()
    conn_queue = Queue()

    receiver_thread = ReceiveThread("RECEIVER", rcv_queue, conn_queue, threadLock)
    sender_thread = SendThread("SENDER", threadLock)

    HB_message = [{'RID' : global_router['RID']}]
    heartbeat_thread = HeartBeatThread("HEART BEAT", HB_message, threadLock, rcv_queue)
                
    receiver_thread.start()
    sender_thread.start()
    heartbeat_thread.start()
                
    return rcv_queue, conn_queue

def init_router(router_id, router_port):

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
    global_router['RP'] = set()

    # Create a dict to hold each thread info
    threads = {}

    # Create a lock to be used by all threads
    threadLock = Lock()

    pid = os.getpid()
    logger.info(f"Initialized router {router_id} at port {router_port} PID {pid}")

def add_neighbour(r_id, r_hostname, rendpoint, r_cost, circuit, circuit_id, stream, stream_id, receive_node=None, extend_node=None, receive_socket=None, thread_id=None):
    logger.debug(f"add_neighbour: {r_id}")
    # Dict to hold data regarding each of this router's neighbours
    global graph
    router_dict = {}
    circuit_dict = {}
    stats_dict = {}

    # For LSA
    router_dict['NID']  = r_id
    router_dict['Cost'] = round(r_cost)
    router_dict['Hostname'] = r_hostname
    router_dict['RP'] = rendpoint
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
    circuit_dict['Thread ID'] = thread_id

    # Append the dict to current routers dict of neighbours data
    # Replace any old neighbour info
    i = 0
    while i < len(global_router['Neighbours Data']):
        if global_router['Neighbours Data'][i]['NID'] == r_id: # and global_router['Neighbours Data'][i]['RP'] == rendpoint:
            logger.debug(f"Replace neighbour data")
            global_router['Neighbours Data'][i] = router_dict
            break
        i = i + 1
    # else append it if we didn't find it
    if i == len(global_router['Neighbours Data']):
        logger.debug(f"Append neighbour data")
        global_router['Neighbours Data'].append(router_dict)
        global_router['Neighbours'] += 1

    # Kill the old thread if we are replacing it
    if r_id in circuit_info:
        logger.debug(f"Kill old thread")
        tid = circuit_info[r_id]['Thread ID']
        old_thread = rnd.threads[tid]
        #old_thread.close()

    # Add circuit info for this neighbour, replace old info
    circuit_info[r_id] = circuit_dict

    # Add stats for this neighbour
    stats_dict['HB sent'] = 0
    stats_dict['HB received'] = 0
    stats_dict['LSA sent'] = 0
    stats_dict['LSA received'] = 0
    stats_dict['Latencies MS'] = list()
    neighbour_stats[r_id] = stats_dict    

    # Temporary graph list to hold state of current network topology
    logger.debug("Update graph data")
    temp_graph = []

    # Grab data about all the neighbours of this router
    for neighbour in global_router['Neighbours Data']:

        # Dict to hold data regarding each of this router's neighbours
        router_dict = {}

        router_dict['NID']  = neighbour['NID']
        router_dict['Cost'] = int(neighbour['Cost'])
        router_dict['RP'] = neighbour['RP']

        # Package this routers data in a useful format and append to temporary graph list
        if(str(global_router['RID']) < str(router_dict['NID'])):
             graph_data = [global_router['RID'], router_dict['NID'], router_dict['Cost'], router_dict['RP']]
        else:
             graph_data = [router_dict['NID'], global_router['RID'], router_dict['Cost'], router_dict['RP']]
        temp_graph.append(graph_data)

    # Copy over the data in temporary graph to global graph object (used elsewhere)
    graph = temp_graph[:]

    logger.info("Added neighbour " + str(r_id))
    #log_metrics("NEIGHBOUR CONNECTION", r_id)

def get_rendezvous_relay(flags=None):
    # get relay
    consensus = TorConsensus()
    if not flags:
        flags = [RouterFlags.Stable, RouterFlags.Valid, RouterFlags.Running]
    relay = consensus.get_random_router(flags=flags, has_dir_port=None, with_renew=True)
    # get cookie
    namespace = "default"
    tun_name = "default"
    ts = pd.Timestamp.now().round("1 min").value
    h = str(ts)+namespace+tun_name  # Concat all values as input to hash function
    h = hashlib.sha256(h.encode())
    n = int(h.hexdigest(), base=16)  # Convert to integer to be able to use modulo
    cookie = h.hexdigest().encode()[0:20]

    return relay, cookie

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
    #print(num_of_relays)
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


def get_random_string(length):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str

def send_to_stream(router_id, message):
    logger.debug(f"send_to_stream: {router_id} , {message}")

    try:
        stream_data = circuit_info[router_id]

        # If we have a stream object send to it 
        if stream_data['Stream']:
            stream_data['Stream'].send(message)
        else:
            # else create the cells
            rnd.snd_data(message, 
                        stream_data['Circuit ID'], 
                        stream_data['Extend Node'], 
                        stream_data['Receive Node'], 
                        stream_data['Receive Socket'],
                        stream_data['Stream ID'])
    except KeyError as e:
        logger.error(f"send_to_stream: Key not found: {e}")
    except Exception as e:
        logger.error("send_to_stream: {0} {1}".format(type(e).__name__, e))

    #log_metrics("DATA SENT", "Payload: {0} bytes".format(sys.getsizeof(message)))


    
