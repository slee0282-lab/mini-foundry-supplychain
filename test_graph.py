#!/usr/bin/env python3
"""Test graph building"""
import sys
sys.path.append('src')

from data_loader import Neo4jConnection
from graph_builder import SupplyChainGraphBuilder

# Connect to Neo4j
neo4j = Neo4jConnection()

# Build graph
builder = SupplyChainGraphBuilder(neo4j)
G = builder.build_graph_from_neo4j()

print(f"Graph nodes: {G.number_of_nodes()}")
print(f"Graph edges: {G.number_of_edges()}")

# Print sample nodes
print("\nSample nodes:")
for i, (node, data) in enumerate(G.nodes(data=True)):
    if i < 5:
        print(f"  {node}: {data}")

# Close connection
neo4j.close()
