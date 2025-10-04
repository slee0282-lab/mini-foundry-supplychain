"""
Supply Chain Simulation Engine

Core simulation engine for disruption propagation analysis and scenario modeling.
Demonstrates the key capability of the Mini Foundry approach.
"""

import logging
import pandas as pd
import networkx as nx
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
from copy import deepcopy
import numpy as np

from data_loader import Neo4jConnection
from graph_builder import SupplyChainGraphBuilder
from utils import get_config, Timer

logger = logging.getLogger(__name__)


class SupplyChainSimulator:
    """
    Main simulation engine for supply chain disruption analysis.

    Demonstrates Palantir Foundry-style scenario modeling:
    - Select supplier, add delay
    - Propagate through network
    - Calculate business impact
    """

    def __init__(self, neo4j_connection: Neo4jConnection = None):
        self.neo4j = neo4j_connection or Neo4jConnection()
        self.graph_builder = SupplyChainGraphBuilder(self.neo4j)
        self.config = get_config()

        # Core simulation data
        self.original_graph = None
        self.current_graph = None
        self.simulation_history = []
        self.current_scenario = None
        self.shipments_df = pd.DataFrame()
        self.sla_lookup = {}
        self.expedite_costs = {}
        self.baseline_metrics = {}
        self._impacted_nodes_cache = set()
        self._impacted_edges_cache = set()

        # Initialize graph
        self._initialize_graph()

    def _initialize_graph(self):
        """Initialize the supply chain graph."""
        with Timer("Initializing simulation graph"):
            self.original_graph = self.graph_builder.build_graph_from_neo4j()
            self.current_graph = self.original_graph.copy()
            logger.info("Simulation engine initialized with supply chain graph")

        # Load baseline data for scenario analytics
        self._load_base_data()

    def reset_simulation(self):
        """Reset simulation to original state."""
        self.current_graph = self.original_graph.copy()
        self.current_scenario = None
        logger.info("Simulation reset to original state")

    def _load_base_data(self):
        """Load shipments, SLA rules, and cost data from Neo4j."""
        try:
            self.shipments_df = self._load_shipments_data()
            self.sla_lookup = self._load_sla_rules()
            self.expedite_costs = self._load_expedite_costs()
            self.baseline_metrics = self._calculate_baseline_metrics()
            logger.info("Baseline data loaded for simulation analytics")
        except Exception as e:
            logger.error(f"Failed to load baseline data: {str(e)}")
            self.shipments_df = pd.DataFrame()
            self.sla_lookup = {}
            self.expedite_costs = {}
            self.baseline_metrics = {}

    def _load_shipments_data(self) -> pd.DataFrame:
        """Load shipment information with supplier, product, and warehouse context."""
        query = """
        MATCH (s:Supplier)-[:CREATES]->(sh:Shipment)
        OPTIONAL MATCH (sh)-[:CONTAINS]->(p:Product)
        OPTIONAL MATCH (sh)-[:DELIVERED_TO]->(w:Warehouse)
        RETURN sh.shipment_id as shipment_id,
               s.supplier_id as supplier_id,
               s.name as supplier_name,
               s.region as supplier_region,
               coalesce(p.product_id, sh.product_id) as product_id,
               coalesce(p.product_name, '') as product_name,
               w.warehouse_id as warehouse_id,
               w.location as warehouse_location,
               w.region as warehouse_region,
               sh.qty_units as quantity,
               sh.planned_lead_time_days as planned_lead_time,
               sh.actual_lead_time_days as actual_lead_time,
               sh.status as status
        """

        result = self.neo4j.execute_cypher(query)
        shipments_df = pd.DataFrame(result)

        if shipments_df.empty:
            logger.warning("No shipment data available for simulations")
            return shipments_df

        shipments_df['planned_lead_time'] = shipments_df['planned_lead_time'].fillna(0).astype(float)
        shipments_df['actual_lead_time'] = shipments_df['actual_lead_time'].fillna(shipments_df['planned_lead_time']).astype(float)
        shipments_df['current_lead_time'] = shipments_df['actual_lead_time'].replace(0, shipments_df['planned_lead_time'])
        shipments_df['quantity'] = shipments_df['quantity'].fillna(0).astype(float)
        shipments_df['warehouse_region'] = shipments_df['warehouse_region'].fillna('Unknown')
        shipments_df['product_id'] = shipments_df['product_id'].fillna('').astype(str)

        return shipments_df

    def _load_sla_rules(self) -> Dict[Tuple[str, str], int]:
        """Load SLA promised days by region and product."""
        query = """
        MATCH (s:SLARule)
        RETURN s.region as region,
               s.product_id as product_id,
               s.promised_days as promised_days,
               s.priority as priority
        """

        result = self.neo4j.execute_cypher(query)
        sla_df = pd.DataFrame(result)

        if sla_df.empty:
            logger.warning("No SLA rules found; using default threshold")
            return {}

        sla_df = sla_df.dropna(subset=['region', 'product_id', 'promised_days'])
        sla_df['promised_days'] = sla_df['promised_days'].astype(int)

        # Priority ordering: HIGH -> MEDIUM -> LOW -> others
        priority_rank = {'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        sla_df['priority_rank'] = sla_df['priority'].map(priority_rank).fillna(4).astype(int)

        # Select the most stringent SLA (lowest promised days, highest priority)
        sla_df = sla_df.sort_values(['region', 'product_id', 'promised_days', 'priority_rank'])
        sla_lookup = {}
        for _, row in sla_df.iterrows():
            key = (row['region'], row['product_id'])
            if key not in sla_lookup:
                sla_lookup[key] = int(row['promised_days'])

        return sla_lookup

    def _load_expedite_costs(self) -> Dict[str, float]:
        """Load expedite shipping costs by region."""
        query = """
        MATCH (c:Cost)
        WHERE c.cost_type = 'EXPEDITE_SHIPPING'
        RETURN c.region as region,
               c.value as value
        """

        result = self.neo4j.execute_cypher(query)
        costs_df = pd.DataFrame(result)

        if costs_df.empty:
            logger.warning("No expedite cost data found")
            return {}

        costs_df = costs_df.dropna(subset=['region', 'value'])
        costs_df['value'] = costs_df['value'].astype(float)

        # In case of multiple cost entries per region, pick the lowest cost option
        costs_lookup = costs_df.groupby('region')['value'].min().to_dict()
        return costs_lookup

    def _get_promised_days(self, region: str, product_id: str) -> int:
        """Get promised SLA days for a given region and product."""
        if not region:
            region = 'Unknown'
        key = (region, product_id)
        if key in self.sla_lookup:
            return self.sla_lookup[key]
        key_all_product = (region, 'ALL')
        if key_all_product in self.sla_lookup:
            return self.sla_lookup[key_all_product]
        return self.config['simulation']['sla_threshold_days']

    def _calculate_baseline_metrics(self) -> Dict[str, Any]:
        """Calculate baseline SLA metrics prior to simulations."""
        if self.shipments_df.empty:
            return {}

        df = self.shipments_df.copy()
        df['promised_days'] = df.apply(
            lambda row: self._get_promised_days(row.get('warehouse_region'), row.get('product_id')),
            axis=1
        )
        df['meets_sla'] = df['current_lead_time'] <= df['promised_days']

        total_shipments = len(df)
        baseline_sla = df['meets_sla'].mean() * 100 if total_shipments else 0.0

        regional_stats = {}
        for region, group in df.groupby('warehouse_region'):
            regional_stats[region] = {
                'baseline_sla': group['meets_sla'].mean() * 100 if len(group) else 0.0,
                'shipments': len(group)
            }

        return {
            'shipments': df,
            'overall_sla': baseline_sla,
            'regional': regional_stats,
            'total_shipments': total_shipments,
            'late_orders': int((~df['meets_sla']).sum())
        }

    def _clear_impact_tags(self):
        """Remove previous impact annotations from the graph."""
        self._impacted_nodes_cache = set()
        self._impacted_edges_cache = set()

        for node in self.current_graph.nodes:
            node_data = self.current_graph.nodes[node]
            for attr in ['impacted', 'impact_reason', 'impact_severity', 'impact_sla_delta']:
                if attr in node_data:
                    del node_data[attr]

        for u, v in self.current_graph.edges:
            edge_data = self.current_graph[u][v]
            for attr in ['impacted', 'impact_reason', 'impact_severity']:
                if attr in edge_data:
                    del edge_data[attr]

    def _mark_node_impacted(self, node_id: str, reason: str, severity: str = 'medium', sla_delta: float = 0.0):
        if node_id not in self.current_graph:
            return
        node_data = self.current_graph.nodes[node_id]
        node_data['impacted'] = True
        node_data['impact_reason'] = reason
        node_data['impact_severity'] = severity
        node_data['impact_sla_delta'] = sla_delta
        self._impacted_nodes_cache.add(node_id)

    def _mark_edge_impacted(self, source: str, target: str, reason: str, severity: str = 'medium'):
        if not self.current_graph.has_edge(source, target):
            return
        edge_data = self.current_graph[source][target]
        edge_data['impacted'] = True
        edge_data['impact_reason'] = reason
        edge_data['impact_severity'] = severity
        self._impacted_edges_cache.add((source, target))

    def _apply_supplier_delay_impacts(self, supplier_id: str, impacted_shipments: List[str]):
        """Annotate graph entities impacted by a supplier delay scenario."""
        self._clear_impact_tags()

        if not impacted_shipments:
            self._mark_node_impacted(supplier_id, 'SUPPLIER_DELAY', severity='low', sla_delta=0.0)
            return

        severity = 'high' if len(impacted_shipments) > 5 else 'medium'
        self._mark_node_impacted(supplier_id, 'SUPPLIER_DELAY', severity=severity)

        for shipment_id in impacted_shipments:
            self._mark_node_impacted(shipment_id, 'SUPPLIER_DELAY', severity=severity)
            self._mark_edge_impacted(supplier_id, shipment_id, 'SUPPLIER_DELAY', severity)

            # Highlight downstream product and warehouse nodes
            if shipment_id not in self.current_graph:
                continue

            for successor in self.current_graph.successors(shipment_id):
                node_type = self.current_graph.nodes[successor].get('node_type')
                if node_type in ['product', 'lot', 'warehouse']:
                    self._mark_node_impacted(successor, 'SUPPLIER_DELAY', severity=severity)
                    self._mark_edge_impacted(shipment_id, successor, 'SUPPLIER_DELAY', severity)

                    # Expand to customers downstream of warehouses
                    if node_type == 'warehouse':
                        for customer in self.current_graph.successors(successor):
                            if self.current_graph.nodes[customer].get('node_type') == 'customer':
                                self._mark_node_impacted(customer, 'SUPPLIER_DELAY', severity='medium')
                                self._mark_edge_impacted(successor, customer, 'SUPPLIER_DELAY', 'medium')

    def simulate_supplier_delay(self,
                               supplier_id: str,
                               delay_days: int,
                               scenario_name: str = None,
                               expedite: bool = False) -> Dict[str, Any]:
        """
        Core simulation: propagate supplier delay through supply chain.

        This is the key demo functionality:
        "Delay Supplier X by Y days → Z% SLA impact"
        """
        scenario_name = scenario_name or f"Delay_{supplier_id}_{delay_days}d"

        with Timer(f"Simulating delay: {supplier_id} +{delay_days} days"):
            # Validate inputs
            if supplier_id not in self.current_graph:
                raise ValueError(f"Supplier {supplier_id} not found in graph")

            if self.current_graph.nodes[supplier_id].get('node_type') != 'supplier':
                raise ValueError(f"Node {supplier_id} is not a supplier")

            # Create simulation scenario
            scenario = {
                'id': len(self.simulation_history) + 1,
                'name': scenario_name,
                'type': 'supplier_delay',
                'parameters': {
                    'supplier_id': supplier_id,
                    'delay_days': delay_days
                },
                'timestamp': datetime.now(),
                'status': 'running'
            }

            # Execute simulation
            try:
                results = self._execute_supplier_delay_simulation(supplier_id, delay_days, expedite)
                scenario['status'] = 'completed'
                scenario['results'] = results

                # Store scenario
                self.current_scenario = scenario
                self.simulation_history.append(scenario)

                logger.info(f"Simulation completed: {scenario_name}")
                return scenario

            except Exception as e:
                scenario['status'] = 'failed'
                scenario['error'] = str(e)
                logger.error(f"Simulation failed: {str(e)}")
                raise

    def _execute_supplier_delay_simulation(self, supplier_id: str, delay_days: int, expedite: bool) -> Dict[str, Any]:
        """Execute supplier delay simulation with SLA analytics and optional expedite recovery."""

        if self.shipments_df.empty:
            raise ValueError("Shipment data is not available. Load data before running simulations.")

        if supplier_id not in self.shipments_df['supplier_id'].unique():
            raise ValueError(f"Supplier {supplier_id} not found in shipment data")

        scenario_df = self.shipments_df.copy()
        scenario_df['promised_days'] = scenario_df.apply(
            lambda row: self._get_promised_days(row.get('warehouse_region'), row.get('product_id')),
            axis=1
        )
        scenario_df['baseline_meets_sla'] = scenario_df['current_lead_time'] <= scenario_df['promised_days']

        impacted_mask = scenario_df['supplier_id'] == supplier_id
        scenario_df['delay_days'] = 0
        scenario_df.loc[impacted_mask, 'delay_days'] = delay_days
        scenario_df['delayed_lead_time'] = scenario_df['current_lead_time'] + scenario_df['delay_days']
        scenario_df['late_after_delay'] = scenario_df['delayed_lead_time'] > scenario_df['promised_days']

        scenario_df['adjusted_lead_time'] = scenario_df['delayed_lead_time']
        scenario_df['expedited'] = False
        scenario_df['expedite_cost_candidate'] = scenario_df.apply(
            lambda row: self.expedite_costs.get(row['warehouse_region'], 0.0)
            if row['late_after_delay'] else 0.0,
            axis=1
        )

        if expedite:
            scenario_df.loc[scenario_df['late_after_delay'], 'adjusted_lead_time'] = scenario_df.loc[
                scenario_df['late_after_delay'], 'promised_days'
            ]
            scenario_df.loc[scenario_df['late_after_delay'], 'expedited'] = True
            scenario_df['expedite_cost_applied'] = scenario_df['expedite_cost_candidate']
        else:
            scenario_df['expedite_cost_applied'] = 0.0

        scenario_df['meets_sla_after_delay'] = scenario_df['adjusted_lead_time'] <= scenario_df['promised_days']

        total_shipments = len(scenario_df)
        baseline_sla = self.baseline_metrics.get('overall_sla', 0.0)
        new_sla = scenario_df['meets_sla_after_delay'].mean() * 100 if total_shipments else 0.0
        delta_sla = new_sla - baseline_sla

        late_orders_after_delay = int((~scenario_df['meets_sla_after_delay']).sum())
        late_orders_without_recovery = int(scenario_df['late_after_delay'].sum())
        expedite_cost_total = float(scenario_df['expedite_cost_applied'].sum())

        # Regional breakdown
        regional_impacts = []
        for region, group in scenario_df.groupby('warehouse_region'):
            baseline_region = self.baseline_metrics.get('regional', {}).get(region, {}).get('baseline_sla', baseline_sla)
            new_region_sla = group['meets_sla_after_delay'].mean() * 100 if len(group) else 0.0
            delta_region = new_region_sla - baseline_region
            late_region = int((~group['meets_sla_after_delay']).sum())
            late_region_without_recovery = int(group['late_after_delay'].sum())
            expedite_region_cost = float(group['expedite_cost_applied'].sum())

            regional_impacts.append({
                'region': region,
                'baseline_sla': baseline_region,
                'new_sla': new_region_sla,
                'delta_sla': delta_region,
                'late_orders': late_region,
                'late_orders_without_recovery': late_region_without_recovery,
                'expedite_cost': expedite_region_cost,
                'shipments': len(group)
            })

        # Impacted shipments details (before expedite recovery)
        impacted_shipments_df = scenario_df[scenario_df['late_after_delay']].copy()
        impacted_shipments_df['expedite_cost'] = impacted_shipments_df['expedite_cost_candidate'] if expedite else 0.0

        impacted_shipments = impacted_shipments_df[
            ['shipment_id', 'supplier_id', 'product_id', 'product_name', 'warehouse_id',
             'warehouse_region', 'quantity', 'current_lead_time', 'delayed_lead_time',
             'promised_days', 'expedited', 'expedite_cost']
        ].to_dict('records')

        # Update graph with impact tags for visualization
        impacted_shipment_ids = [record['shipment_id'] for record in impacted_shipments]
        self._apply_supplier_delay_impacts(supplier_id, impacted_shipment_ids)

        summary = (
            f"Supplier {supplier_id} delayed by {delay_days} days results in {late_orders_without_recovery} late shipments. "
            f"Post-mitigation SLA: {new_sla:.1f}% (Δ {delta_sla:.1f} pp)."
        )

        return {
            'simulation_parameters': {
                'supplier_id': supplier_id,
                'supplier_name': self.current_graph.nodes[supplier_id].get('name', ''),
                'delay_days': delay_days,
                'expedite_enabled': expedite,
                'sla_threshold_days': self.config['simulation']['sla_threshold_days']
            },
            'kpis': {
                'baseline_sla': baseline_sla,
                'new_sla': new_sla,
                'delta_sla': delta_sla,
                'late_orders_after_delay': late_orders_after_delay,
                'late_orders_without_recovery': late_orders_without_recovery,
                'expedite_cost_total': expedite_cost_total,
                'total_shipments': total_shipments
            },
            'regional_impacts': regional_impacts,
            'impacted_shipments': impacted_shipments,
            'dataframes': {
                'scenario_shipments': scenario_df
            },
            'graph_impacts': {
                'nodes': list(self._impacted_nodes_cache),
                'edges': list(self._impacted_edges_cache)
            },
            'summary': summary
        }


    def compare_scenarios(self, scenario_ids: List[int]) -> Dict[str, Any]:
        """Compare multiple simulation scenarios."""
        if not scenario_ids:
            return {}

        scenarios = [s for s in self.simulation_history if s['id'] in scenario_ids]
        if not scenarios:
            return {}

        comparison = {
            'scenarios': scenarios,
            'comparison_metrics': {},
            'recommendations': []
        }

        metric_extractors = {
            'new_sla': lambda r: r.get('kpis', {}).get('new_sla'),
            'delta_sla': lambda r: r.get('kpis', {}).get('delta_sla'),
            'late_orders_after_delay': lambda r: r.get('kpis', {}).get('late_orders_after_delay'),
            'late_orders_without_recovery': lambda r: r.get('kpis', {}).get('late_orders_without_recovery'),
            'expedite_cost_total': lambda r: r.get('kpis', {}).get('expedite_cost_total')
        }

        for metric, extractor in metric_extractors.items():
            values = []
            for scenario in scenarios:
                result = scenario.get('results', {})
                value = extractor(result)
                if value is not None:
                    values.append(value)

            if values:
                comparison['comparison_metrics'][metric] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values)
                }

        # Generate recommendations based on SLA and late orders
        if len(scenarios) >= 2:
            best_sla_scenario = max(
                scenarios,
                key=lambda s: s.get('results', {}).get('kpis', {}).get('new_sla', 0)
            )
            lowest_late_orders = min(
                scenarios,
                key=lambda s: s.get('results', {}).get('kpis', {}).get('late_orders_after_delay', float('inf'))
            )

            comparison['recommendations'].append(
                f"Highest SLA scenario: {best_sla_scenario['name']} "
                f"({best_sla_scenario.get('results', {}).get('kpis', {}).get('new_sla', 0):.1f}% SLA)"
            )
            comparison['recommendations'].append(
                f"Fewest late orders: {lowest_late_orders['name']} "
                f"({lowest_late_orders.get('results', {}).get('kpis', {}).get('late_orders_after_delay', 0)} late orders)"
            )

        return comparison

    def export_simulation_results(self, scenario_id: int = None) -> pd.DataFrame:
        """Export simulation results to pandas DataFrame."""
        if scenario_id:
            scenarios = [s for s in self.simulation_history if s['id'] == scenario_id]
        else:
            scenarios = self.simulation_history

        if not scenarios:
            return pd.DataFrame()

        export_data = []
        for scenario in scenarios:
            if 'results' not in scenario:
                continue

            results = scenario['results']
            kpis = results.get('kpis', {})
            for shipment in results.get('impacted_shipments', []):
                export_data.append({
                    'scenario_id': scenario['id'],
                    'scenario_name': scenario['name'],
                    'supplier_id': shipment.get('supplier_id'),
                    'shipment_id': shipment.get('shipment_id'),
                    'product_id': shipment.get('product_id'),
                    'product_name': shipment.get('product_name'),
                    'warehouse_id': shipment.get('warehouse_id'),
                    'warehouse_region': shipment.get('warehouse_region'),
                    'quantity': shipment.get('quantity'),
                    'baseline_lead_time': shipment.get('current_lead_time'),
                    'delayed_lead_time': shipment.get('delayed_lead_time'),
                    'promised_days': shipment.get('promised_days'),
                    'expedited': shipment.get('expedited'),
                    'expedite_cost': shipment.get('expedite_cost'),
                    'scenario_sla_post': kpis.get('new_sla'),
                    'scenario_delta_sla': kpis.get('delta_sla')
                })

        return pd.DataFrame(export_data)

    def get_simulation_status(self) -> Dict[str, Any]:
        """Get current simulation status and statistics."""
        return {
            'graph_loaded': self.original_graph is not None,
            'total_simulations': len(self.simulation_history),
            'current_scenario': self.current_scenario['name'] if self.current_scenario else None,
            'graph_stats': {
                'nodes': self.current_graph.number_of_nodes() if self.current_graph else 0,
                'edges': self.current_graph.number_of_edges() if self.current_graph else 0
            },
            'recent_simulations': [
                {
                    'id': s['id'],
                    'name': s['name'],
                    'timestamp': s['timestamp'].isoformat(),
                    'status': s['status']
                }
                for s in self.simulation_history[-5:]  # Last 5 simulations
            ]
        }


def main():
    """Test the simulation engine."""
    logging.basicConfig(level=logging.INFO)

    try:
        # Initialize simulator
        simulator = SupplyChainSimulator()

        # Get status
        status = simulator.get_simulation_status()
        logger.info(f"Simulator status: {status}")

        # Run a test simulation
        if status['graph_loaded']:
            logger.info("Running test simulation...")

            # Get first supplier from graph
            suppliers = [n for n, d in simulator.current_graph.nodes(data=True)
                        if d.get('node_type') == 'supplier']

            if suppliers:
                test_supplier = suppliers[0]
                scenario = simulator.simulate_supplier_delay(test_supplier, 5, "Test Simulation")

                logger.info("=== SIMULATION RESULTS ===")
                logger.info(scenario['results']['summary'])

                # Export results
                df = simulator.export_simulation_results(scenario['id'])
                logger.info(f"Exported {len(df)} simulation records")

                logger.info("✓ Simulation engine test completed successfully")
            else:
                logger.warning("No suppliers found in graph")
        else:
            logger.error("Graph not loaded - cannot run simulation")

    except Exception as e:
        logger.error(f"Error in simulation test: {str(e)}")
        raise
    finally:
        if 'simulator' in locals():
            simulator.neo4j.close()


if __name__ == "__main__":
    main()
