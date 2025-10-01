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
from utils import get_config, Timer, calculate_sla_impact

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

        # Initialize graph
        self._initialize_graph()

    def _initialize_graph(self):
        """Initialize the supply chain graph."""
        with Timer("Initializing simulation graph"):
            self.original_graph = self.graph_builder.build_graph_from_neo4j()
            self.current_graph = self.original_graph.copy()
            logger.info("Simulation engine initialized with supply chain graph")

    def reset_simulation(self):
        """Reset simulation to original state."""
        self.current_graph = self.original_graph.copy()
        self.current_scenario = None
        logger.info("Simulation reset to original state")

    def simulate_supplier_delay(self,
                               supplier_id: str,
                               delay_days: int,
                               scenario_name: str = None) -> Dict[str, Any]:
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
                results = self._execute_supplier_delay_simulation(supplier_id, delay_days)
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

    def _execute_supplier_delay_simulation(self, supplier_id: str, delay_days: int) -> Dict[str, Any]:
        """Execute the core supplier delay simulation logic."""

        # 1. Find all affected paths from this supplier
        affected_paths = self._find_affected_supply_paths(supplier_id)

        # 2. Update lead times in the graph
        impact_details = []
        total_quantity_impact = 0

        for path in affected_paths:
            # Update supplier->product edge
            supplier_product_edge = self.current_graph[path['supplier']][path['product']]
            original_lead_time = supplier_product_edge.get('lead_time', 7)
            new_lead_time = original_lead_time + delay_days
            supplier_product_edge['lead_time'] = new_lead_time

            # Calculate impact for this path
            quantity = supplier_product_edge.get('volume', 0)
            sla_threshold = self.config['simulation']['sla_threshold_days']
            path_impact = calculate_sla_impact(new_lead_time, quantity, sla_threshold)

            impact_detail = {
                'supplier': path['supplier'],
                'supplier_name': self.current_graph.nodes[path['supplier']].get('name', ''),
                'product': path['product'],
                'product_name': self.current_graph.nodes[path['product']].get('name', ''),
                'warehouse': path['warehouse'],
                'warehouse_location': self.current_graph.nodes[path['warehouse']].get('location', ''),
                'warehouse_region': self.current_graph.nodes[path['warehouse']].get('region', ''),
                'original_lead_time': original_lead_time,
                'new_lead_time': new_lead_time,
                'delay_added': delay_days,
                'quantity_affected': quantity,
                'sla_impact_score': path_impact,
                'exceeds_sla': new_lead_time > sla_threshold
            }

            impact_details.append(impact_detail)
            total_quantity_impact += quantity if new_lead_time > sla_threshold else 0

        # 3. Calculate regional and overall SLA impacts
        regional_impacts = self._calculate_regional_sla_impacts()
        overall_sla_impact = self._calculate_overall_sla_impact()

        # 4. Identify cascading effects
        cascading_effects = self._analyze_cascading_effects(supplier_id, delay_days)

        # 5. Generate business impact summary
        business_impact = self._calculate_business_impact(impact_details, regional_impacts)

        return {
            'simulation_parameters': {
                'supplier_id': supplier_id,
                'supplier_name': self.current_graph.nodes[supplier_id].get('name', ''),
                'delay_days': delay_days,
                'sla_threshold_days': self.config['simulation']['sla_threshold_days']
            },
            'affected_paths': impact_details,
            'path_count': len(impact_details),
            'total_quantity_affected': sum(p['quantity_affected'] for p in impact_details),
            'quantity_exceeding_sla': total_quantity_impact,
            'regional_impacts': regional_impacts,
            'overall_sla_impact': overall_sla_impact,
            'cascading_effects': cascading_effects,
            'business_impact': business_impact,
            'summary': self._generate_simulation_summary(
                supplier_id, delay_days, impact_details, regional_impacts, overall_sla_impact
            )
        }

    def _find_affected_supply_paths(self, supplier_id: str) -> List[Dict[str, str]]:
        """Find all supply chain paths affected by supplier delay."""
        paths = []

        # Find supplier -> product -> warehouse paths
        for product in self.current_graph.successors(supplier_id):
            if self.current_graph.nodes[product].get('node_type') == 'product':
                for warehouse in self.current_graph.successors(product):
                    if self.current_graph.nodes[warehouse].get('node_type') == 'warehouse':
                        paths.append({
                            'supplier': supplier_id,
                            'product': product,
                            'warehouse': warehouse
                        })

        return paths

    def _calculate_regional_sla_impacts(self) -> Dict[str, Dict[str, Any]]:
        """Calculate SLA impacts by region."""
        regional_data = {}
        sla_threshold = self.config['simulation']['sla_threshold_days']

        # Group by warehouse region
        for node, data in self.current_graph.nodes(data=True):
            if data.get('node_type') == 'warehouse':
                region = data.get('region', 'Unknown')
                if region not in regional_data:
                    regional_data[region] = {
                        'total_volume': 0,
                        'delayed_volume': 0,
                        'warehouses': [],
                        'products_affected': set()
                    }

                regional_data[region]['warehouses'].append(node)

                # Check incoming products for SLA impacts
                for product in self.current_graph.predecessors(node):
                    if self.current_graph.nodes[product].get('node_type') == 'product':
                        # Check all suppliers for this product
                        for supplier in self.current_graph.predecessors(product):
                            if self.current_graph.nodes[supplier].get('node_type') == 'supplier':
                                edge_data = self.current_graph[supplier][product]
                                lead_time = edge_data.get('lead_time', 7)
                                volume = edge_data.get('volume', 0)

                                regional_data[region]['total_volume'] += volume
                                if lead_time > sla_threshold:
                                    regional_data[region]['delayed_volume'] += volume
                                    regional_data[region]['products_affected'].add(product)

        # Calculate SLA percentages
        for region, data in regional_data.items():
            total_vol = data['total_volume']
            delayed_vol = data['delayed_volume']
            data['sla_impact_percent'] = (delayed_vol / total_vol * 100) if total_vol > 0 else 0
            data['products_affected'] = len(data['products_affected'])

        return regional_data

    def _calculate_overall_sla_impact(self) -> float:
        """Calculate overall SLA impact percentage."""
        total_volume = 0
        delayed_volume = 0
        sla_threshold = self.config['simulation']['sla_threshold_days']

        for supplier, product, edge_data in self.current_graph.edges(data=True):
            if (self.current_graph.nodes[supplier].get('node_type') == 'supplier' and
                self.current_graph.nodes[product].get('node_type') == 'product'):

                lead_time = edge_data.get('lead_time', 7)
                volume = edge_data.get('volume', 0)

                total_volume += volume
                if lead_time > sla_threshold:
                    delayed_volume += volume

        return (delayed_volume / total_volume * 100) if total_volume > 0 else 0

    def _analyze_cascading_effects(self, supplier_id: str, delay_days: int) -> Dict[str, Any]:
        """Analyze cascading effects of the delay."""
        effects = {
            'immediate_products': [],
            'downstream_warehouses': [],
            'affected_customers': [],
            'supply_chain_depth': 0
        }

        # Find immediate products
        for product in self.current_graph.successors(supplier_id):
            if self.current_graph.nodes[product].get('node_type') == 'product':
                effects['immediate_products'].append({
                    'product_id': product,
                    'product_name': self.current_graph.nodes[product].get('name', ''),
                    'category': self.current_graph.nodes[product].get('category', '')
                })

        # Find downstream warehouses
        warehouses = set()
        for product in effects['immediate_products']:
            for warehouse in self.current_graph.successors(product['product_id']):
                if self.current_graph.nodes[warehouse].get('node_type') == 'warehouse':
                    warehouses.add(warehouse)

        effects['downstream_warehouses'] = [
            {
                'warehouse_id': wh,
                'location': self.current_graph.nodes[wh].get('location', ''),
                'region': self.current_graph.nodes[wh].get('region', ''),
                'capacity': self.current_graph.nodes[wh].get('capacity', 0)
            }
            for wh in warehouses
        ]

        # Find affected customers
        customers = set()
        for warehouse in warehouses:
            for customer in self.current_graph.successors(warehouse):
                if self.current_graph.nodes[customer].get('node_type') == 'customer':
                    customers.add(customer)

        effects['affected_customers'] = [
            {
                'customer_id': cust,
                'name': self.current_graph.nodes[cust].get('name', ''),
                'region': self.current_graph.nodes[cust].get('region', ''),
                'demand': self.current_graph.nodes[cust].get('demand', 0)
            }
            for cust in customers
        ]

        # Calculate supply chain depth
        effects['supply_chain_depth'] = len(effects['immediate_products']) + len(warehouses) + len(customers)

        return effects

    def _calculate_business_impact(self,
                                 impact_details: List[Dict[str, Any]],
                                 regional_impacts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate business impact metrics."""

        # Calculate cost impacts (simplified model)
        total_volume_at_risk = sum(p['quantity_affected'] for p in impact_details if p['exceeds_sla'])
        estimated_unit_cost = 25.0  # Mock unit cost
        potential_revenue_at_risk = total_volume_at_risk * estimated_unit_cost

        # SLA penalty calculation (mock)
        sla_penalty_rate = 0.05  # 5% penalty for SLA breaches
        estimated_sla_penalties = potential_revenue_at_risk * sla_penalty_rate

        # Customer impact
        total_orders_delayed = len([p for p in impact_details if p['exceeds_sla']])
        total_orders = len(impact_details)
        customer_satisfaction_impact = (total_orders_delayed / total_orders * 100) if total_orders > 0 else 0

        # Regional prioritization
        most_impacted_region = max(regional_impacts.items(),
                                 key=lambda x: x[1]['sla_impact_percent']) if regional_impacts else ('Unknown', {'sla_impact_percent': 0})

        return {
            'financial': {
                'potential_revenue_at_risk': potential_revenue_at_risk,
                'estimated_sla_penalties': estimated_sla_penalties,
                'total_financial_impact': potential_revenue_at_risk + estimated_sla_penalties
            },
            'operational': {
                'orders_delayed': total_orders_delayed,
                'orders_total': total_orders,
                'delay_rate_percent': (total_orders_delayed / total_orders * 100) if total_orders > 0 else 0,
                'volume_at_risk': total_volume_at_risk
            },
            'strategic': {
                'customer_satisfaction_impact': customer_satisfaction_impact,
                'most_impacted_region': most_impacted_region[0],
                'highest_regional_impact': most_impacted_region[1]['sla_impact_percent'],
                'supply_chain_resilience_score': max(0, 100 - customer_satisfaction_impact)
            }
        }

    def _generate_simulation_summary(self,
                                   supplier_id: str,
                                   delay_days: int,
                                   impact_details: List[Dict[str, Any]],
                                   regional_impacts: Dict[str, Dict[str, Any]],
                                   overall_sla_impact: float) -> str:
        """Generate human-readable simulation summary."""
        supplier_name = self.current_graph.nodes[supplier_id].get('name', supplier_id)

        # Find most impacted region
        most_impacted_region = 'Unknown'
        highest_impact = 0
        for region, data in regional_impacts.items():
            if data['sla_impact_percent'] > highest_impact:
                highest_impact = data['sla_impact_percent']
                most_impacted_region = region

        delayed_orders = len([p for p in impact_details if p['exceeds_sla']])
        total_orders = len(impact_details)

        summary = f"""
🚨 SUPPLY CHAIN DISRUPTION SIMULATION RESULTS

📊 Scenario: {supplier_name} delayed by {delay_days} days

🎯 Key Impact:
• Overall SLA Impact: {overall_sla_impact:.1f}%
• Most Affected Region: {most_impacted_region} ({highest_impact:.1f}% impact)
• Orders Delayed: {delayed_orders} out of {total_orders} total shipments
• Supply Chain Paths Affected: {len(impact_details)}

📈 This demonstrates the classic Foundry capability:
"Delay Supplier X by Y days → Z% SLA drop in region"
        """.strip()

        return summary

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

        # Compare key metrics
        metrics = ['overall_sla_impact', 'path_count', 'total_quantity_affected']
        for metric in metrics:
            values = []
            for scenario in scenarios:
                if 'results' in scenario:
                    values.append(scenario['results'].get(metric, 0))

            if values:
                comparison['comparison_metrics'][metric] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values)
                }

        # Generate recommendations
        if len(scenarios) >= 2:
            # Find least impactful scenario
            least_impact_scenario = min(scenarios,
                                      key=lambda s: s.get('results', {}).get('overall_sla_impact', 100))

            comparison['recommendations'].append(
                f"Least impactful scenario: {least_impact_scenario['name']} "
                f"with {least_impact_scenario.get('results', {}).get('overall_sla_impact', 0):.1f}% SLA impact"
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
            for path in results.get('affected_paths', []):
                export_data.append({
                    'scenario_id': scenario['id'],
                    'scenario_name': scenario['name'],
                    'supplier_id': path['supplier'],
                    'supplier_name': path['supplier_name'],
                    'product_id': path['product'],
                    'product_name': path['product_name'],
                    'warehouse_id': path['warehouse'],
                    'warehouse_location': path['warehouse_location'],
                    'warehouse_region': path['warehouse_region'],
                    'original_lead_time': path['original_lead_time'],
                    'new_lead_time': path['new_lead_time'],
                    'delay_added': path['delay_added'],
                    'quantity_affected': path['quantity_affected'],
                    'exceeds_sla': path['exceeds_sla'],
                    'sla_impact_score': path['sla_impact_score']
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