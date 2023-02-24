import matplotlib.pyplot as plt
import networkx as nx

def display_graph(graph):

    # Create a graph
    G = nx.Graph(graph)

    # Add nodes
    #G.add_node(1)
    #G.add_node(2)

    # Add edges
    #G.add_edge(1, 2)
    #G.add_edge(2, 3)

    # Visualize the graph
    nx.draw(G, with_labels=True)

    # Show the plot
    plt.show()
