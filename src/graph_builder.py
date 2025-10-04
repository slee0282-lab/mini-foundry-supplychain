"""
Graph Builder Module for Supply Chain Network Analysis

Builds NetworkX graphs from Neo4j data and provides graph analysis capabilities.
"""

import logging
import networkx as nx
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
from data_loader import Neo4jConnection
from utils import get_config, Timer
import numpy as np

logger = logging.getLogger(__name__)


class SupplyChainGraphBuilder:
    """Builds and manages NetworkX graphs for supply chain analysis."""

    def __init__(self, neo4j_connection: Neo4jConnection = None):
        self.neo4j = neo4j_connection or Neo4jConnection()
        self.config = get_config()
        self.graph = None
        self.node_positions = None

    def build_graph_from_neo4j(self) -> nx.DiGraph:
        """Build NetworkX graph from Neo4j data."""
        with Timer("Building NetworkX graph from Neo4j"):
            graph = nx.DiGraph()

            # Add nodes for each entity type
            self._add_supplier_nodes(graph)
            self._add_product_nodes(graph)
            self._add_warehouse_nodes(graph)
            self._add_customer_nodes(graph)
            self._add_shipment_nodes(graph)

            # Add Phase 1 pilot data nodes
            self._add_lot_nodes(graph)
            self._add_event_nodes(graph)
            self._add_sla_rule_nodes(graph)
            self._add_lane_nodes(graph)
            self._add_cost_nodes(graph)
            self._add_cold_chain_reading_nodes(graph)

            # Add edges for relationships
            self._add_supply_relationships(graph)
            self._add_stocking_relationships(graph)
            self._add_delivery_relationships(graph)
            self._add_shipment_relationships(graph)

            # Add Phase 1 relationships
            self._add_lot_relationships(graph)
            self._add_event_relationships(graph)

            self.graph = graph
            logger.info(f"Graph built: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

            return graph

    def _add_supplier_nodes(self, graph: nx.DiGraph):
        """Add supplier nodes to the graph."""
        query = """
        MATCH (s:Supplier)
        RETURN s.supplier_id as id, s.name as name, s.region as region,
               s.reliability_score as reliability, s.avg_lead_time_days as lead_time
        """

        result = self.neo4j.execute_cypher(query)
        for record in result:
            graph.add_node(
                record['id'],
                node_type='supplier',
                name=record['name'],
                region=record['region'],
                reliability=record['reliability'],
                lead_time=record['lead_time'],
                size=800,  # For visualization
                color='lightblue'
            )

        logger.info(f"Added {len(result)} supplier nodes")

    def _add_product_nodes(self, graph: nx.DiGraph):
        """Add product nodes to the graph."""
        query = """
        MATCH (p:Product)
        RETURN p.product_id as id, p.product_name as name, p.category as category,
               p.safety_stock as safety_stock, p.demand_forecast as demand
        """

        result = self.neo4j.execute_cypher(query)
        for record in result:
            graph.add_node(
                record['id'],
                node_type='product',
                name=record['name'],
                category=record['category'],
                safety_stock=record['safety_stock'],
                demand=record['demand'],
                size=600,
                color='lightgreen'
            )

        logger.info(f"Added {len(result)} product nodes")

    def _add_warehouse_nodes(self, graph: nx.DiGraph):
        """Add warehouse nodes to the graph."""
        query = """
        MATCH (w:Warehouse)
        RETURN w.warehouse_id as id, w.location as location, w.region as region,
               w.capacity_units as capacity
        """

        result = self.neo4j.execute_cypher(query)
        for record in result:
            graph.add_node(
                record['id'],
                node_type='warehouse',
                location=record['location'],
                region=record['region'],
                capacity=record['capacity'],
                size=700,
                color='orange'
            )

        logger.info(f"Added {len(result)} warehouse nodes")

    def _add_customer_nodes(self, graph: nx.DiGraph):
        """Add customer nodes to the graph."""
        query = """
        MATCH (c:Customer)
        RETURN c.customer_id as id, c.name as name, c.region as region,
               c.avg_demand_units as demand
        """

        result = self.neo4j.execute_cypher(query)
        for record in result:
            graph.add_node(
                record['id'],
                node_type='customer',
                name=record['name'],
                region=record['region'],
                demand=record['demand'],
                size=500,
                color='lightcoral'
            )

        logger.info(f"Added {len(result)} customer nodes")

    def _add_shipment_nodes(self, graph: nx.DiGraph):
        """Add shipment nodes to the graph."""
        query = """
        MATCH (sh:Shipment)
        RETURN sh.shipment_id as id, sh.qty_units as quantity,
               sh.planned_lead_time_days as planned_lead_time,
               sh.actual_lead_time_days as actual_lead_time,
               sh.status as status
        """

        result = self.neo4j.execute_cypher(query)
        for record in result:
            # Color based on status
            color = {
                'On-Time': 'green',
                'In-Transit': 'yellow',
                'Delayed': 'red'
            }.get(record['status'], 'gray')

            graph.add_node(
                record['id'],
                node_type='shipment',
                quantity=record['quantity'],
                planned_lead_time=record['planned_lead_time'],
                actual_lead_time=record['actual_lead_time'],
                status=record['status'],
                size=300,
                color=color
            )

        logger.info(f"Added {len(result)} shipment nodes")

    def _add_supply_relationships(self, graph: nx.DiGraph):
        """Add supplier-product relationships."""
        query = """
        MATCH (s:Supplier)-[r:SUPPLIES]->(p:Product)
        RETURN s.supplier_id as supplier, p.product_id as product,
               r.lead_time_days as lead_time, r.reliability as reliability,
               r.total_volume as volume
        """

        result = self.neo4j.execute_cypher(query)
        for record in result:
            graph.add_edge(
                record['supplier'],
                record['product'],
                relationship='supplies',
                lead_time=record['lead_time'],
                reliability=record['reliability'],
                volume=record['volume'] or 0,
                weight=1.0
            )

        logger.info(f"Added {len(result)} supply relationships")

    def _add_stocking_relationships(self, graph: nx.DiGraph):
        """Add product-warehouse stocking relationships."""
        query = """
        MATCH (p:Product)-[r:STOCKED_AT]->(w:Warehouse)
        RETURN p.product_id as product, w.warehouse_id as warehouse,
               r.current_inventory as inventory, r.reorder_point as reorder_point,
               r.max_capacity as max_capacity
        """

        result = self.neo4j.execute_cypher(query)
        for record in result:
            graph.add_edge(
                record['product'],
                record['warehouse'],
                relationship='stocked_at',
                inventory=record['inventory'],
                reorder_point=record['reorder_point'],
                max_capacity=record['max_capacity'],
                weight=1.0
            )

        logger.info(f"Added {len(result)} stocking relationships")

    def _add_delivery_relationships(self, graph: nx.DiGraph):
        """Add warehouse-customer delivery relationships."""
        query = """
        MATCH (w:Warehouse)-[r:DELIVERS_TO]->(c:Customer)
        RETURN w.warehouse_id as warehouse, c.customer_id as customer,
               r.avg_delivery_days as delivery_days, r.shipping_cost as cost,
               r.service_level as service_level
        """

        result = self.neo4j.execute_cypher(query)
        for record in result:
            graph.add_edge(
                record['warehouse'],
                record['customer'],
                relationship='delivers_to',
                delivery_days=record['delivery_days'],
                cost=record['cost'],
                service_level=record['service_level'],
                weight=1.0
            )

        logger.info(f"Added {len(result)} delivery relationships")

    def _add_shipment_relationships(self, graph: nx.DiGraph):
        """Add shipment-related relationships."""
        # Supplier creates shipment
        query1 = """
        MATCH (s:Supplier)-[r:CREATES]->(sh:Shipment)
        RETURN s.supplier_id as supplier, sh.shipment_id as shipment,
               r.shipment_date as date, r.volume as volume
        """

        result1 = self.neo4j.execute_cypher(query1)
        for record in result1:
            graph.add_edge(
                record['supplier'],
                record['shipment'],
                relationship='creates',
                date=str(record['date']) if record['date'] else None,
                volume=record['volume'],
                weight=0.5
            )

        # Shipment contains product
        query2 = """
        MATCH (sh:Shipment)-[r:CONTAINS]->(p:Product)
        RETURN sh.shipment_id as shipment, p.product_id as product,
               r.quantity as quantity, r.unit_cost as cost
        """

        result2 = self.neo4j.execute_cypher(query2)
        for record in result2:
            graph.add_edge(
                record['shipment'],
                record['product'],
                relationship='contains',
                quantity=record['quantity'],
                cost=record['cost'],
                weight=0.5
            )

        # Shipment delivered to warehouse
        query3 = """
        MATCH (sh:Shipment)-[r:DELIVERED_TO]->(w:Warehouse)
        RETURN sh.shipment_id as shipment, w.warehouse_id as warehouse,
               r.delivery_date as date, r.transport_mode as mode,
               r.tracking_status as status
        """

        result3 = self.neo4j.execute_cypher(query3)
        for record in result3:
            graph.add_edge(
                record['shipment'],
                record['warehouse'],
                relationship='delivered_to',
                date=str(record['date']) if record['date'] else None,
                mode=record['mode'],
                status=record['status'],
                weight=0.5
            )

        total_shipment_edges = len(result1) + len(result2) + len(result3)
        logger.info(f"Added {total_shipment_edges} shipment relationships")

    def calculate_node_positions(self, layout: str = 'spring') -> Dict[str, Tuple[float, float]]:
        """Calculate node positions for visualization."""
        if self.graph is None:
            raise ValueError("Graph not built yet. Call build_graph_from_neo4j() first.")

        if layout == 'spring':
            pos = nx.spring_layout(self.graph, k=3, iterations=50, seed=42)
        elif layout == 'circular':
            pos = nx.circular_layout(self.graph)
        elif layout == 'hierarchical':
            pos = self._hierarchical_layout()
        else:
            pos = nx.random_layout(self.graph, seed=42)

        self.node_positions = pos
        return pos

    def _hierarchical_layout(self) -> Dict[str, Tuple[float, float]]:
        """Create hierarchical layout based on supply chain flow."""
        pos = {}

        # Define layers
        suppliers = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'supplier']
        products = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'product']
        warehouses = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'warehouse']
        customers = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'customer']
        shipments = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'shipment']

        # Position nodes in layers
        layers = [suppliers, products, shipments, warehouses, customers]
        y_positions = [4, 3, 2, 1, 0]

        for layer, y in zip(layers, y_positions):
            for i, node in enumerate(layer):
                x = i - len(layer) / 2
                pos[node] = (x, y)

        return pos

    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get comprehensive graph statistics."""
        if self.graph is None:
            return {}

        stats = {
            'basic': {
                'nodes': self.graph.number_of_nodes(),
                'edges': self.graph.number_of_edges(),
                'density': nx.density(self.graph),
                'is_connected': nx.is_weakly_connected(self.graph)
            },
            'node_types': {},
            'centrality': {},
            'paths': {}
        }

        # Count nodes by type
        for node, data in self.graph.nodes(data=True):
            node_type = data.get('node_type', 'unknown')
            stats['node_types'][node_type] = stats['node_types'].get(node_type, 0) + 1

        # Calculate centrality measures
        try:
            stats['centrality']['degree'] = nx.degree_centrality(self.graph)
            stats['centrality']['betweenness'] = nx.betweenness_centrality(self.graph)
            stats['centrality']['closeness'] = nx.closeness_centrality(self.graph)

            # Page rank for directed graphs
            stats['centrality']['pagerank'] = nx.pagerank(self.graph)
        except Exception as e:
            logger.warning(f"Error calculating centrality: {str(e)}")

        # Path analysis
        try:
            if nx.is_weakly_connected(self.graph):
                stats['paths']['diameter'] = nx.diameter(self.graph.to_undirected())
                stats['paths']['average_path_length'] = nx.average_shortest_path_length(self.graph.to_undirected())
            else:
                stats['paths']['diameter'] = "Graph not connected"
                stats['paths']['average_path_length'] = "Graph not connected"
        except Exception as e:
            logger.warning(f"Error calculating path metrics: {str(e)}")

        return stats

    def find_supply_chain_paths(self, source_type: str = 'supplier',
                               target_type: str = 'customer',
                               max_paths: int = 10) -> List[List[str]]:
        """Find paths through the supply chain from source to target type."""
        if self.graph is None:
            return []

        source_nodes = [n for n, d in self.graph.nodes(data=True)
                       if d.get('node_type') == source_type]
        target_nodes = [n for n, d in self.graph.nodes(data=True)
                       if d.get('node_type') == target_type]

        paths = []
        for source in source_nodes:
            for target in target_nodes:
                try:
                    # Find all simple paths (up to a reasonable length)
                    simple_paths = list(nx.all_simple_paths(
                        self.graph, source, target, cutoff=6
                    ))
                    paths.extend(simple_paths[:max_paths])
                except nx.NetworkXNoPath:
                    continue

        return paths[:max_paths]

    def analyze_supplier_criticality(self) -> pd.DataFrame:
        """Analyze supplier criticality based on network position."""
        if self.graph is None:
            return pd.DataFrame()

        suppliers = [n for n, d in self.graph.nodes(data=True)
                    if d.get('node_type') == 'supplier']

        criticality_data = []
        for supplier in suppliers:
            supplier_data = self.graph.nodes[supplier]

            # Calculate network metrics
            out_degree = self.graph.out_degree(supplier)

            # Find all downstream nodes
            downstream_nodes = set()
            try:
                for path in nx.single_source_shortest_path(self.graph, supplier, cutoff=4).values():
                    downstream_nodes.update(path)
            except:
                pass

            # Calculate criticality score
            reliability = supplier_data.get('reliability', 0.5)
            lead_time = supplier_data.get('lead_time', 10)

            criticality_score = (
                (1 - reliability) * 40 +  # Reliability impact
                (lead_time / 30.0) * 30 +  # Lead time impact
                (out_degree / 10.0) * 30   # Network connectivity impact
            )

            criticality_data.append({
                'supplier_id': supplier,
                'name': supplier_data.get('name', ''),
                'region': supplier_data.get('region', ''),
                'reliability': reliability,
                'lead_time': lead_time,
                'out_degree': out_degree,
                'downstream_nodes': len(downstream_nodes),
                'criticality_score': min(criticality_score, 100)
            })

        df = pd.DataFrame(criticality_data)
        return df.sort_values('criticality_score', ascending=False)

    def simulate_node_removal(self, node_id: str) -> Dict[str, Any]:
        """Simulate the impact of removing a node from the network."""
        if self.graph is None or node_id not in self.graph:
            return {}

        original_stats = self.get_graph_statistics()

        # Create a copy and remove the node
        temp_graph = self.graph.copy()
        temp_graph.remove_node(node_id)

        # Calculate new statistics
        new_stats = {
            'nodes': temp_graph.number_of_nodes(),
            'edges': temp_graph.number_of_edges(),
            'density': nx.density(temp_graph),
            'is_connected': nx.is_weakly_connected(temp_graph)
        }

        # Calculate impact
        impact = {
            'removed_node': node_id,
            'node_type': self.graph.nodes[node_id].get('node_type', 'unknown'),
            'original_stats': original_stats['basic'],
            'new_stats': new_stats,
            'impact': {
                'nodes_lost': original_stats['basic']['nodes'] - new_stats['nodes'],
                'edges_lost': original_stats['basic']['edges'] - new_stats['edges'],
                'connectivity_lost': original_stats['basic']['is_connected'] and not new_stats['is_connected']
            }
        }

        return impact

    def export_graph_data(self) -> Dict[str, Any]:
        """Export graph data for external analysis."""
        if self.graph is None:
            return {}

        # Nodes data
        nodes_data = []
        for node, data in self.graph.nodes(data=True):
            node_info = {'id': node}
            node_info.update(data)
            nodes_data.append(node_info)

        # Edges data
        edges_data = []
        for source, target, data in self.graph.edges(data=True):
            edge_info = {
                'source': source,
                'target': target
            }
            edge_info.update(data)
            edges_data.append(edge_info)

        return {
            'nodes': nodes_data,
            'edges': edges_data,
            'statistics': self.get_graph_statistics()
        }


def main():
    """Test the graph builder."""
    logging.basicConfig(level=logging.INFO)

    try:
        builder = SupplyChainGraphBuilder()

        # Build graph
        graph = builder.build_graph_from_neo4j()

        # Get statistics
        stats = builder.get_graph_statistics()
        logger.info(f"Graph Statistics: {stats['basic']}")

        # Calculate positions
        positions = builder.calculate_node_positions()
        logger.info(f"Calculated positions for {len(positions)} nodes")

        # Analyze supplier criticality
        criticality = builder.analyze_supplier_criticality()
        logger.info(f"Supplier criticality analysis: {len(criticality)} suppliers")

        # Find supply chain paths
        paths = builder.find_supply_chain_paths()
        logger.info(f"Found {len(paths)} supply chain paths")

        logger.info("✓ Graph builder test completed successfully")

    except Exception as e:
        logger.error(f"Error in graph builder test: {str(e)}")
        raise
    finally:
        if 'builder' in locals():
            builder.neo4j.close()


if __name__ == "__main__":
    main()