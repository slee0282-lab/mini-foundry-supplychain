"""
Supply Chain Simulation Engine

Core simulation engine for disruption propagation analysis and scenario modeling.
Demonstrates the key capability of the Mini Foundry approach.
"""

import logging
import pandas as pd
import networkx as nx
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
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
        self.products_df = pd.DataFrame()
        self.shipment_schedule_df = pd.DataFrame()
        self.events_df = pd.DataFrame()
        self.cold_chain_df = pd.DataFrame()
        self.lots_df = pd.DataFrame()
        self.shipment_lot_map_df = pd.DataFrame()
        self._impacted_nodes_cache = set()
        self._impacted_edges_cache = set()

        # Local data paths (used when Neo4j data is unavailable)
        data_root = self.config['data'].get('path', './data') if self.config.get('data') else './data'
        self.data_path = Path(data_root)
        self.pilot_data_path = self.data_path / 'pilot_missing_supporting_files'

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
            self.products_df = self._load_products_data()
            self.lots_df = self._load_lots_data()
            self.shipment_schedule_df = self._load_shipment_schedule()
            self.events_df = self._load_events_data()
            self.cold_chain_df = self._load_cold_chain_data()

            if not self.shipment_schedule_df.empty and not self.shipments_df.empty:
                self.shipments_df = self.shipments_df.merge(
                    self.shipment_schedule_df,
                    on='shipment_id',
                    how='left'
                )

            self.baseline_metrics = self._calculate_baseline_metrics()
            logger.info("Baseline data loaded for simulation analytics")
        except Exception as e:
            logger.error(f"Failed to load baseline data: {str(e)}")
            self.shipments_df = pd.DataFrame()
            self.sla_lookup = {}
            self.expedite_costs = {}
            self.baseline_metrics = {}
            self.products_df = pd.DataFrame()
            self.shipment_schedule_df = pd.DataFrame()
            self.events_df = pd.DataFrame()
            self.cold_chain_df = pd.DataFrame()
            self.lots_df = pd.DataFrame()
            self.shipment_lot_map_df = pd.DataFrame()

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

        result = []
        try:
            result = self.neo4j.execute_cypher(query)
        except Exception as e:
            logger.warning(f"Neo4j shipment query failed: {str(e)}")

        shipments_df = pd.DataFrame(result)

        if shipments_df.empty:
            logger.warning("No shipment data returned from Neo4j; attempting CSV fallback.")
            shipments_df = self._load_shipments_from_csv()

        if shipments_df.empty:
            logger.error("Shipment data unavailable from both Neo4j and CSV sources.")
            return shipments_df

        shipments_df['planned_lead_time'] = shipments_df['planned_lead_time'].fillna(0).astype(float)
        shipments_df['actual_lead_time'] = shipments_df['actual_lead_time'].fillna(shipments_df['planned_lead_time']).astype(float)
        shipments_df['current_lead_time'] = shipments_df['actual_lead_time'].replace(0, shipments_df['planned_lead_time'])
        shipments_df['quantity'] = shipments_df['quantity'].fillna(0).astype(float)
        shipments_df['warehouse_region'] = shipments_df['warehouse_region'].fillna('Unknown')
        shipments_df['product_id'] = shipments_df['product_id'].fillna('').astype(str)

        return shipments_df

    def _load_shipments_from_csv(self) -> pd.DataFrame:
        """Fallback: load shipment data by joining local CSV files."""
        shipments_file = self.data_path / 'shipments.csv'
        suppliers_file = self.data_path / 'suppliers.csv'
        products_file = self.data_path / 'products.csv'
        warehouses_file = self.data_path / 'warehouses.csv'

        if not shipments_file.exists():
            logger.error(f"Shipments CSV not found at {shipments_file}")
            return pd.DataFrame()

        try:
            shipments_df = pd.read_csv(shipments_file)
        except Exception as e:
            logger.error(f"Failed to read shipments CSV: {str(e)}")
            return pd.DataFrame()

        # Optional enrichment tables
        suppliers_df = pd.read_csv(suppliers_file) if suppliers_file.exists() else pd.DataFrame()
        products_df = pd.read_csv(products_file) if products_file.exists() else pd.DataFrame()
        warehouses_df = pd.read_csv(warehouses_file) if warehouses_file.exists() else pd.DataFrame()

        if not suppliers_df.empty:
            suppliers_subset = suppliers_df[['supplier_id', 'name', 'region']].rename(
                columns={'name': 'supplier_name', 'region': 'supplier_region'}
            )
            shipments_df = shipments_df.merge(suppliers_subset, on='supplier_id', how='left')
        else:
            shipments_df['supplier_name'] = shipments_df['supplier_id']
            shipments_df['supplier_region'] = 'Unknown'

        if not products_df.empty:
            products_subset = products_df[['product_id', 'product_name']]
            shipments_df = shipments_df.merge(products_subset, on='product_id', how='left')
        else:
            shipments_df['product_name'] = ''

        if not warehouses_df.empty:
            warehouses_subset = warehouses_df[['warehouse_id', 'location', 'region']].rename(
                columns={'location': 'warehouse_location', 'region': 'warehouse_region'}
            )
            shipments_df = shipments_df.merge(warehouses_subset, on='warehouse_id', how='left')
        else:
            shipments_df['warehouse_location'] = shipments_df['warehouse_id']
            shipments_df['warehouse_region'] = 'Unknown'

        shipments_df['planned_lead_time_days'] = shipments_df.get('planned_lead_time_days', pd.Series(dtype=float)).fillna(0)
        shipments_df['actual_lead_time_days'] = shipments_df.get('actual_lead_time_days', pd.Series(dtype=float)).fillna(shipments_df['planned_lead_time_days'])
        shipments_df['status'] = shipments_df.get('status', pd.Series(dtype=str)).fillna('Unknown')

        shipments_df.rename(columns={
            'planned_lead_time_days': 'planned_lead_time',
            'actual_lead_time_days': 'actual_lead_time',
            'qty_units': 'quantity'
        }, inplace=True)

        shipments_df['quantity'] = shipments_df['quantity'].fillna(0)
        shipments_df['product_name'] = shipments_df['product_name'].fillna('')
        shipments_df['supplier_name'] = shipments_df['supplier_name'].fillna(shipments_df['supplier_id'])
        shipments_df['supplier_region'] = shipments_df['supplier_region'].fillna('Unknown')
        shipments_df['warehouse_region'] = shipments_df['warehouse_region'].fillna('Unknown')

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

        result = []
        try:
            result = self.neo4j.execute_cypher(query)
        except Exception as e:
            logger.warning(f"Neo4j SLA query failed: {str(e)}")

        sla_df = pd.DataFrame(result)

        if sla_df.empty:
            logger.warning("No SLA rules returned from Neo4j; attempting CSV fallback.")
            sla_df = self._load_sla_rules_from_csv()

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

    def _load_sla_rules_from_csv(self) -> pd.DataFrame:
        """Fallback: load SLA rules from local CSV."""
        sla_file = self.pilot_data_path / 'sla_rules.csv'
        if not sla_file.exists():
            logger.error(f"SLA rules CSV not found at {sla_file}")
            return pd.DataFrame()

        try:
            sla_df = pd.read_csv(sla_file)
            return sla_df
        except Exception as e:
            logger.error(f"Failed to read SLA rules CSV: {str(e)}")
            return pd.DataFrame()

    def _load_expedite_costs(self) -> Dict[str, float]:
        """Load expedite shipping costs by region."""
        query = """
        MATCH (c:Cost)
        WHERE c.cost_type = 'EXPEDITE_SHIPPING'
        RETURN c.region as region,
               c.value as value
        """

        result = []
        try:
            result = self.neo4j.execute_cypher(query)
        except Exception as e:
            logger.warning(f"Neo4j cost query failed: {str(e)}")

        costs_df = pd.DataFrame(result)

        if costs_df.empty:
            logger.warning("No expedite cost data returned from Neo4j; attempting CSV fallback.")
            costs_df = self._load_expedite_costs_from_csv()

        if costs_df.empty:
            logger.warning("No expedite cost data found")
            return {}

        costs_df = costs_df.dropna(subset=['region', 'value'])
        costs_df['value'] = costs_df['value'].astype(float)

        # In case of multiple cost entries per region, pick the lowest cost option
        costs_lookup = costs_df.groupby('region')['value'].min().to_dict()
        return costs_lookup

    def _load_expedite_costs_from_csv(self) -> pd.DataFrame:
        """Fallback: load expedite cost data from local CSV."""
        costs_file = self.pilot_data_path / 'costs.csv'
        if not costs_file.exists():
            logger.error(f"Cost CSV not found at {costs_file}")
            return pd.DataFrame()

        try:
            costs_df = pd.read_csv(costs_file)
            costs_df = costs_df[costs_df['cost_type'] == 'EXPEDITE_SHIPPING']
            return costs_df[['region', 'value']]
        except Exception as e:
            logger.error(f"Failed to read costs CSV: {str(e)}")
            return pd.DataFrame()

    def _load_products_data(self) -> pd.DataFrame:
        """Load product master data from Neo4j or CSV."""
        query = """
        MATCH (p:Product)
        RETURN p.product_id as product_id,
               p.product_name as product_name,
               p.category as category,
               p.safety_stock as safety_stock,
               p.demand_forecast as demand_forecast
        """

        result = []
        try:
            result = self.neo4j.execute_cypher(query)
        except Exception as e:
            logger.warning(f"Neo4j product query failed: {str(e)}")

        products_df = pd.DataFrame(result)

        if products_df.empty:
            products_file = self.data_path / 'products.csv'
            if products_file.exists():
                try:
                    products_df = pd.read_csv(products_file)
                except Exception as e:
                    logger.error(f"Failed to read products CSV: {str(e)}")
                    products_df = pd.DataFrame()
            else:
                logger.warning(f"Products CSV not found at {products_file}")

        return products_df

    def _load_lots_data(self) -> pd.DataFrame:
        """Load lot/batch information from Neo4j or CSV."""
        query = """
        MATCH (l:Lot)
        RETURN l.lot_id as lot_id,
               l.product_id as product_id,
               l.status as status,
               l.quality_status as quality_status,
               l.hold_reason as hold_reason,
               l.recall_status as recall_status
        """

        result = []
        try:
            result = self.neo4j.execute_cypher(query)
        except Exception as e:
            logger.warning(f"Neo4j lot query failed: {str(e)}")

        lots_df = pd.DataFrame(result)

        if lots_df.empty:
            lots_file = self.pilot_data_path / 'lots.csv'
            if lots_file.exists():
                try:
                    lots_df = pd.read_csv(lots_file)
                except Exception as e:
                    logger.error(f"Failed to read lots CSV: {str(e)}")
                    lots_df = pd.DataFrame()
            else:
                logger.warning(f"Lots CSV not found at {lots_file}")

        return lots_df

    def _load_shipment_schedule(self) -> pd.DataFrame:
        """Load shipment packing/shipping schedule information."""
        query = """
        MATCH (sh:Shipment)-[r:CONTAINS]->(:Lot)
        RETURN sh.shipment_id as shipment_id,
               r.packing_date as packing_date,
               r.shipping_date as shipping_date
        """

        result = []
        try:
            result = self.neo4j.execute_cypher(query)
        except Exception as e:
            logger.warning(f"Neo4j shipment schedule query failed: {str(e)}")

        schedule_df = pd.DataFrame(result)

        if schedule_df.empty:
            mapping_file = self.pilot_data_path / 'shipments_lots.csv'
            if mapping_file.exists():
                try:
                    schedule_df = pd.read_csv(mapping_file)
                except Exception as e:
                    logger.error(f"Failed to read shipment-lot CSV: {str(e)}")
                    schedule_df = pd.DataFrame()
            else:
                logger.warning(f"Shipment-lot mapping CSV not found at {mapping_file}")

        if schedule_df.empty:
            self.shipment_lot_map_df = pd.DataFrame()
            return schedule_df

        # Preserve detailed mapping for downstream traceability
        detailed_df = schedule_df.copy()

        if 'packing_date' not in detailed_df.columns and 'packing_date_x' in detailed_df.columns:
            detailed_df.rename(columns={'packing_date_x': 'packing_date'}, inplace=True)
        if 'shipping_date' not in detailed_df.columns and 'shipping_date_x' in detailed_df.columns:
            detailed_df.rename(columns={'shipping_date_x': 'shipping_date'}, inplace=True)

        for col in ['packing_date', 'shipping_date']:
            if col in detailed_df.columns:
                detailed_df[col] = pd.to_datetime(detailed_df[col], errors='coerce')

        self.shipment_lot_map_df = detailed_df

        if 'shipment_id' not in detailed_df.columns:
            logger.warning("Shipment schedule data missing shipment_id column")
            return pd.DataFrame()

        aggregated = detailed_df.groupby('shipment_id').agg({
            'packing_date': 'min',
            'shipping_date': 'min'
        }).reset_index().rename(columns={
            'packing_date': 'first_packing_date',
            'shipping_date': 'first_shipping_date'
        })

        return aggregated

    def _load_events_data(self) -> pd.DataFrame:
        """Load scenario events from Neo4j or CSV."""
        query = """
        MATCH (e:Event)
        RETURN e.event_id as event_id,
               e.event_type as event_type,
               e.scope_type as scope_type,
               e.scope_id as scope_id,
               e.start_date as start_date,
               e.end_date as end_date,
               e.severity as severity,
               e.status as status,
               e.description as description,
               e.impact_value as impact_value
        """

        result = []
        try:
            result = self.neo4j.execute_cypher(query)
        except Exception as e:
            logger.warning(f"Neo4j events query failed: {str(e)}")

        events_df = pd.DataFrame(result)

        if events_df.empty:
            events_file = self.pilot_data_path / 'events.csv'
            if events_file.exists():
                try:
                    events_df = pd.read_csv(events_file)
                except Exception as e:
                    logger.error(f"Failed to read events CSV: {str(e)}")
                    events_df = pd.DataFrame()
            else:
                logger.warning(f"Events CSV not found at {events_file}")

        if not events_df.empty:
            for col in ['start_date', 'end_date']:
                if col in events_df.columns:
                    events_df[col] = pd.to_datetime(events_df[col], errors='coerce')

        return events_df

    def _load_cold_chain_data(self) -> pd.DataFrame:
        """Load cold chain readings from Neo4j or CSV."""
        query = """
        MATCH (r:ColdChainReading)
        RETURN r.reading_id as reading_id,
               r.shipment_id as shipment_id,
               r.lot_id as lot_id,
               r.timestamp as timestamp,
               r.temperature_c as temperature_c,
               r.threshold_min_c as threshold_min_c,
               r.threshold_max_c as threshold_max_c,
               r.excursion_flag as excursion_flag,
               r.excursion_duration_minutes as excursion_duration_minutes,
               r.notes as notes
        """

        result = []
        try:
            result = self.neo4j.execute_cypher(query)
        except Exception as e:
            logger.warning(f"Neo4j cold chain query failed: {str(e)}")

        cold_chain_df = pd.DataFrame(result)

        if cold_chain_df.empty:
            readings_file = self.pilot_data_path / 'cold_chain_readings.csv'
            if readings_file.exists():
                try:
                    cold_chain_df = pd.read_csv(readings_file)
                except Exception as e:
                    logger.error(f"Failed to read cold chain CSV: {str(e)}")
                    cold_chain_df = pd.DataFrame()
            else:
                logger.warning(f"Cold chain readings CSV not found at {readings_file}")

        if not cold_chain_df.empty and 'timestamp' in cold_chain_df.columns:
            cold_chain_df['timestamp'] = pd.to_datetime(cold_chain_df['timestamp'], errors='coerce')

        return cold_chain_df

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

    def _apply_supplier_delay_impacts(self,
                                     supplier_id: str,
                                     impacted_shipments: List[str],
                                     reason: str = 'SUPPLIER_DELAY'):
        """Annotate graph entities impacted by a supplier-centric scenario."""
        self._clear_impact_tags()

        if not impacted_shipments:
            if supplier_id and supplier_id in self.current_graph:
                self._mark_node_impacted(supplier_id, reason, severity='low', sla_delta=0.0)
            return

        severity = 'high' if len(impacted_shipments) > 5 else 'medium'
        if supplier_id and supplier_id in self.current_graph:
            self._mark_node_impacted(supplier_id, reason, severity=severity)

        for shipment_id in impacted_shipments:
            self._mark_node_impacted(shipment_id, reason, severity=severity)
            if supplier_id and self.current_graph.has_edge(supplier_id, shipment_id):
                self._mark_edge_impacted(supplier_id, shipment_id, reason, severity)

            # Highlight downstream product and warehouse nodes
            if shipment_id not in self.current_graph:
                continue

            # Link to actual suppliers from the graph (covers multi-supplier scenarios)
            for predecessor in self.current_graph.predecessors(shipment_id):
                if self.current_graph.nodes[predecessor].get('node_type') == 'supplier':
                    self._mark_node_impacted(predecessor, reason, severity=severity)
                    self._mark_edge_impacted(predecessor, shipment_id, reason, severity)

            for successor in self.current_graph.successors(shipment_id):
                node_type = self.current_graph.nodes[successor].get('node_type')
                if node_type in ['product', 'lot', 'warehouse']:
                    self._mark_node_impacted(successor, reason, severity=severity)
                    self._mark_edge_impacted(shipment_id, successor, reason, severity)

                    # Expand to customers downstream of warehouses
                    if node_type == 'warehouse':
                        for customer in self.current_graph.successors(successor):
                            if self.current_graph.nodes[customer].get('node_type') == 'customer':
                                self._mark_node_impacted(customer, reason, severity='medium')
                                self._mark_edge_impacted(successor, customer, reason, 'medium')

    def _apply_lot_recall_impacts(self, lot_id: str, impacted_shipments: List[str]):
        """Highlight graph entities impacted by a lot recall."""
        self._clear_impact_tags()

        reason = 'LOT_RECALL'
        if lot_id in self.current_graph:
            self._mark_node_impacted(lot_id, reason, severity='high')

        for shipment_id in impacted_shipments:
            self._mark_node_impacted(shipment_id, reason, severity='high')
            if self.current_graph.has_edge(shipment_id, lot_id):
                self._mark_edge_impacted(shipment_id, lot_id, reason, 'high')
            if self.current_graph.has_edge(lot_id, shipment_id):
                self._mark_edge_impacted(lot_id, shipment_id, reason, 'high')

            # Highlight suppliers and downstream nodes
            for supplier in self.current_graph.predecessors(shipment_id):
                if self.current_graph.nodes[supplier].get('node_type') == 'supplier':
                    self._mark_node_impacted(supplier, reason, severity='high')
                    self._mark_edge_impacted(supplier, shipment_id, reason, 'high')

            for successor in self.current_graph.successors(shipment_id):
                succ_type = self.current_graph.nodes[successor].get('node_type')
                if succ_type in ['warehouse', 'product', 'customer']:
                    self._mark_node_impacted(successor, reason, severity='high' if succ_type != 'customer' else 'medium')
                    self._mark_edge_impacted(shipment_id, successor, reason, 'medium')
                    if succ_type == 'warehouse':
                        for customer in self.current_graph.successors(successor):
                            if self.current_graph.nodes[customer].get('node_type') == 'customer':
                                self._mark_node_impacted(customer, reason, severity='medium')
                                self._mark_edge_impacted(successor, customer, reason, 'medium')

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
                results = self._execute_supplier_delay_simulation(
                    supplier_id,
                    delay_days,
                    expedite,
                    impacted_shipment_ids=None,
                    scenario_label=f"Supplier {supplier_id} delayed by {delay_days} days"
                )
                results['scenario_type'] = 'supplier_delay'
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

    def simulate_supplier_outage(self,
                                 supplier_id: str,
                                 outage_days: int,
                                 start_date: Optional[datetime] = None,
                                 scenario_name: str = None,
                                 expedite: bool = False) -> Dict[str, Any]:
        """Simulate a supplier outage over a defined window."""

        scenario_name = scenario_name or f"Outage_{supplier_id}_{outage_days}d"

        scenario = {
            'id': len(self.simulation_history) + 1,
            'name': scenario_name,
            'type': 'supplier_outage',
            'parameters': {
                'supplier_id': supplier_id,
                'outage_days': outage_days
            },
            'timestamp': datetime.now(),
            'status': 'running'
        }

        try:
            with Timer(f"Simulating outage: {supplier_id} {outage_days} days"):
                if self.shipments_df.empty:
                    raise ValueError("Shipment data is not available. Load data before running simulations.")

                if supplier_id not in self.shipments_df['supplier_id'].unique():
                    raise ValueError(f"Supplier {supplier_id} not found in shipment data")

                # Determine outage window
                outage_start = start_date
                if outage_start is None and not self.events_df.empty:
                    event_match = self.events_df[
                        (self.events_df.get('event_type') == 'SUPPLIER_OUTAGE') &
                        (self.events_df.get('scope_id') == supplier_id)
                    ]
                    if not event_match.empty and pd.notna(event_match.iloc[0].get('start_date')):
                        outage_start = event_match.iloc[0]['start_date']

                if outage_start is None:
                    supplier_shipments = self.shipments_df[self.shipments_df['supplier_id'] == supplier_id]
                    outage_start = supplier_shipments.get('first_shipping_date').min()
                    if pd.isna(outage_start):
                        outage_start = datetime.now()

                outage_end = outage_start + timedelta(days=outage_days)

                # Shipments impacted within outage window
                supplier_shipments = self.shipments_df[self.shipments_df['supplier_id'] == supplier_id].copy()
                shipment_dates = supplier_shipments.get('first_shipping_date')
                if shipment_dates is not None:
                    impacted_mask = shipment_dates.isna() | (
                        (shipment_dates >= outage_start) & (shipment_dates <= outage_end)
                    )
                else:
                    impacted_mask = pd.Series(True, index=supplier_shipments.index)

                impacted_ids = supplier_shipments.loc[impacted_mask, 'shipment_id'].tolist()

                results = self._execute_supplier_delay_simulation(
                    supplier_id,
                    delay_days=outage_days,
                    expedite=expedite,
                    impacted_shipment_ids=impacted_ids,
                    scenario_label=f"Supplier {supplier_id} {outage_days} day outage",
                    impact_reason='SUPPLIER_OUTAGE'
                )
                results['scenario_type'] = 'supplier_outage'

                scenario_shipments_df = results['dataframes']['scenario_shipments']
                impacted_df = scenario_shipments_df[scenario_shipments_df['shipment_id'].isin(impacted_ids)]

                breaches = []
                if not impacted_df.empty and not self.products_df.empty and 'quantity' in impacted_df.columns:
                    product_delays = impacted_df.groupby('product_id')['quantity'].sum()
                    product_lookup = self.products_df.set_index('product_id') if 'product_id' in self.products_df.columns else pd.DataFrame()
                    for product_id, delayed_qty in product_delays.items():
                        safety_stock = None
                        if product_id in product_lookup.index and 'safety_stock' in product_lookup.columns:
                            safety_stock = product_lookup.loc[product_id].get('safety_stock')
                        if safety_stock is not None and pd.notna(safety_stock) and delayed_qty > safety_stock:
                            product_name = product_lookup.loc[product_id].get('product_name', product_id) if product_id in product_lookup.index else product_id
                            breaches.append({
                                'product_id': product_id,
                                'product_name': product_name,
                                'delayed_quantity': delayed_qty,
                                'safety_stock': safety_stock,
                                'breach_units': delayed_qty - safety_stock
                            })

                results['simulation_parameters']['outage_start'] = outage_start
                results['simulation_parameters']['outage_end'] = outage_end
                results['simulation_parameters']['expedite_enabled'] = expedite

                results['resilience_metrics'] = {
                    'shipments_impacted': len(impacted_ids),
                    'window_start': outage_start,
                    'window_end': outage_end,
                    'safety_stock_breaches': breaches,
                    'potential_backorders_units': impacted_df['quantity'].sum() if not impacted_df.empty else 0
                }

                if breaches:
                    results['summary'] += f" Potential safety stock breach on {len(breaches)} product(s)."

                results['scenario_name'] = scenario_name
                scenario['status'] = 'completed'
                scenario['results'] = results
                self.current_scenario = scenario
                self.simulation_history.append(scenario)
                return scenario
        except Exception as e:
            scenario['status'] = 'failed'
            scenario['error'] = str(e)
            self.simulation_history.append(scenario)
            logger.error(f"Supplier outage simulation failed: {str(e)}")
            raise


    def simulate_regional_hold(self,
                               region: str,
                               hold_days: int,
                               start_date: Optional[datetime] = None,
                               scenario_name: str = None,
                               expedite: bool = False) -> Dict[str, Any]:
        """Simulate a regulatory/customs hold on a destination region."""

        scenario_name = scenario_name or f"RegHold_{region}_{hold_days}d"

        scenario = {
            'id': len(self.simulation_history) + 1,
            'name': scenario_name,
            'type': 'regulatory_hold',
            'parameters': {
                'region': region,
                'hold_days': hold_days
            },
            'timestamp': datetime.now(),
            'status': 'running'
        }

        try:
            if self.shipments_df.empty:
                raise ValueError("Shipment data is not available. Load data before running simulations.")

            shipments_in_region = self.shipments_df[self.shipments_df['warehouse_region'] == region]
            if shipments_in_region.empty:
                raise ValueError(f"No shipments found for region {region}")

            hold_start = start_date
            if hold_start is None and not self.events_df.empty:
                event_match = self.events_df[
                    (self.events_df.get('event_type').isin(['REG_HOLD', 'REGULATORY_HOLD'])) &
                    (self.events_df.get('scope_id') == region)
                ]
                if not event_match.empty and pd.notna(event_match.iloc[0].get('start_date')):
                    hold_start = event_match.iloc[0]['start_date']

            if hold_start is None:
                hold_start = shipments_in_region.get('first_shipping_date').min()
                if pd.isna(hold_start):
                    hold_start = datetime.now()

            hold_end = hold_start + timedelta(days=hold_days)

            shipment_dates = shipments_in_region.get('first_shipping_date')
            if shipment_dates is not None:
                impacted_mask = shipment_dates.isna() | (
                    (shipment_dates >= hold_start) & (shipment_dates <= hold_end)
                )
            else:
                impacted_mask = pd.Series(True, index=shipments_in_region.index)

            impacted_ids = shipments_in_region.loc[impacted_mask, 'shipment_id'].tolist()

            results = self._execute_supplier_delay_simulation(
                supplier_id=None,
                delay_days=hold_days,
                expedite=expedite,
                impacted_shipment_ids=impacted_ids,
                scenario_label=f"Regulatory hold in {region} ({hold_days} days)",
                impact_reason='REGULATORY_HOLD'
            )
            results['scenario_type'] = 'regulatory_hold'

            results['simulation_parameters']['region'] = region
            results['simulation_parameters']['hold_start'] = hold_start
            results['simulation_parameters']['hold_end'] = hold_end
            results['scenario_name'] = scenario_name

            scenario_shipments_df = results['dataframes']['scenario_shipments']
            impacted_df = scenario_shipments_df[scenario_shipments_df['shipment_id'].isin(impacted_ids)]

            lane_metrics = []
            if not impacted_df.empty:
                lane_metrics = (
                    impacted_df.groupby(['supplier_id', 'warehouse_id'])
                    .agg({
                        'quantity': 'sum',
                        'late_after_delay': 'sum',
                        'meets_sla_after_delay': lambda x: (~x).sum()
                    })
                    .reset_index()
                    .rename(columns={'quantity': 'total_quantity',
                                     'late_after_delay': 'late_orders_without_recovery',
                                     'meets_sla_after_delay': 'late_orders_after_mitigation'})
                    .to_dict('records')
                )

            results['regional_hold'] = {
                'region': region,
                'shipments_impacted': len(impacted_ids),
                'lanes': lane_metrics,
                'expedite_enabled': expedite
            }

            results['summary'] += f" Regulatory hold impacted {len(impacted_ids)} shipments bound for {region}."

            scenario['status'] = 'completed'
            scenario['results'] = results
            self.current_scenario = scenario
            self.simulation_history.append(scenario)
            return scenario
        except Exception as e:
            scenario['status'] = 'failed'
            scenario['error'] = str(e)
            self.simulation_history.append(scenario)
            logger.error(f"Regional hold simulation failed: {str(e)}")
            raise

    def simulate_cold_chain_excursion(self,
                                      hold_extension_days: int = 5,
                                      focus_shipment: Optional[str] = None,
                                      scenario_name: Optional[str] = None) -> Dict[str, Any]:
        """Evaluate cold chain excursions and simulate quality hold impact."""

        scenario_name = scenario_name or f"ColdChainHold_{hold_extension_days}d"
        scenario = {
            'id': len(self.simulation_history) + 1,
            'name': scenario_name,
            'type': 'cold_chain_hold',
            'parameters': {
                'hold_extension_days': hold_extension_days,
                'focus_shipment': focus_shipment
            },
            'timestamp': datetime.now(),
            'status': 'running'
        }

        try:
            if self.cold_chain_df.empty:
                raise ValueError("Cold chain data is not available.")

            readings_df = self.cold_chain_df.copy()

            if focus_shipment:
                readings_df = readings_df[readings_df['shipment_id'] == focus_shipment]

            if readings_df.empty:
                raise ValueError("No cold chain readings match the provided criteria.")

            def is_excursion(row):
                flag = str(row.get('excursion_flag', '')).upper()
                if flag == 'YES':
                    return True
                temp = row.get('temperature_c')
                min_t = row.get('threshold_min_c')
                max_t = row.get('threshold_max_c')
                if pd.notna(temp) and (pd.notna(min_t) and temp < min_t or pd.notna(max_t) and temp > max_t):
                    return True
                return False

            readings_df['is_excursion'] = readings_df.apply(is_excursion, axis=1)
            excursion_df = readings_df[readings_df['is_excursion'] == True]

            if excursion_df.empty:
                raise ValueError("No excursions detected for the selected shipment(s).")

            impacted_shipments = excursion_df['shipment_id'].dropna().unique().tolist()

            results = self._execute_supplier_delay_simulation(
                supplier_id=None,
                delay_days=hold_extension_days,
                expedite=False,
                impacted_shipment_ids=impacted_shipments,
                scenario_label=f"Cold chain hold (+{hold_extension_days} days)",
                impact_reason='COLD_CHAIN_HOLD'
            )
            results['scenario_type'] = 'cold_chain_hold'

            results['scenario_name'] = scenario_name

            metrics = (
                excursion_df.groupby('shipment_id')
                .agg({
                    'temperature_c': ['max', 'min', 'count'],
                    'excursion_duration_minutes': 'max'
                })
            )
            metrics.columns = ['max_temp', 'min_temp', 'reading_count', 'max_excursion_minutes']
            metrics = metrics.reset_index()

            results['cold_chain'] = {
                'shipments_impacted': impacted_shipments,
                'metrics': metrics.to_dict('records'),
                'hold_extension_days': hold_extension_days
            }

            results['summary'] += f" Cold chain excursion detected on {len(impacted_shipments)} shipment(s); quality hold applied."

            scenario['status'] = 'completed'
            scenario['results'] = results
            self.current_scenario = scenario
            self.simulation_history.append(scenario)
            return scenario
        except Exception as e:
            scenario['status'] = 'failed'
            scenario['error'] = str(e)
            self.simulation_history.append(scenario)
            logger.error(f"Cold chain excursion simulation failed: {str(e)}")
            raise

    def trace_lot_recall(self,
                         lot_id: str,
                         scenario_name: Optional[str] = None) -> Dict[str, Any]:
        """Perform one-click trace for a recalled lot."""

        if self.lots_df.empty:
            raise ValueError("Lot data is not available.")

        lot_row = self.lots_df[self.lots_df['lot_id'] == lot_id]
        if lot_row.empty:
            raise ValueError(f"Lot {lot_id} not found in data")

        if self.shipment_lot_map_df.empty:
            raise ValueError("Shipment-lot mapping data is not available.")

        lot_shipments = self.shipment_lot_map_df[self.shipment_lot_map_df['lot_id'] == lot_id]
        if lot_shipments.empty:
            raise ValueError(f"No shipments associated with lot {lot_id}")

        impacted_shipments = lot_shipments['shipment_id'].dropna().unique().tolist()

        scenario = {
            'id': len(self.simulation_history) + 1,
            'name': scenario_name or f"LotRecall_{lot_id}",
            'type': 'lot_recall_trace',
            'parameters': {
                'lot_id': lot_id
            },
            'timestamp': datetime.now(),
            'status': 'running'
        }

        self._apply_lot_recall_impacts(lot_id, impacted_shipments)

        shipments_info = self.shipments_df[self.shipments_df['shipment_id'].isin(impacted_shipments)].copy()
        warehouses_impacted = shipments_info['warehouse_id'].dropna().unique().tolist() if not shipments_info.empty else []
        customers_impacted = []

        results = {
            'scenario_name': scenario_name or f"LotRecall_{lot_id}",
            'lot': lot_row.to_dict('records')[0],
            'shipments_impacted': shipments_info.to_dict('records') if not shipments_info.empty else [],
            'warehouses_impacted': warehouses_impacted,
            'customers_impacted': customers_impacted,
            'summary': f"Lot {lot_id} recall traces to {len(impacted_shipments)} shipment(s) and {len(warehouses_impacted)} warehouse(s).",
            'scenario_type': 'lot_recall_trace'
        }

        scenario['status'] = 'completed'
        scenario['results'] = results
        self.current_scenario = scenario
        self.simulation_history.append(scenario)

        return scenario

    def _execute_supplier_delay_simulation(self,
                                           supplier_id: str,
                                           delay_days: int,
                                           expedite: bool,
                                           impacted_shipment_ids: Optional[List[str]] = None,
                                           scenario_label: Optional[str] = None,
                                           impact_reason: str = 'SUPPLIER_DELAY') -> Dict[str, Any]:
        """Execute supplier delay simulation with SLA analytics and optional expedite recovery."""

        if self.shipments_df.empty:
            raise ValueError("Shipment data is not available. Load data before running simulations.")

        if supplier_id is not None and supplier_id not in self.shipments_df['supplier_id'].unique():
            raise ValueError(f"Supplier {supplier_id} not found in shipment data")

        scenario_df = self.shipments_df.copy()
        scenario_df['promised_days'] = scenario_df.apply(
            lambda row: self._get_promised_days(row.get('warehouse_region'), row.get('product_id')),
            axis=1
        )
        scenario_df['baseline_meets_sla'] = scenario_df['current_lead_time'] <= scenario_df['promised_days']

        if impacted_shipment_ids is not None:
            impacted_mask = scenario_df['shipment_id'].isin(impacted_shipment_ids)
        else:
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
        impacted_ids_resolved = impacted_shipment_ids or scenario_df.loc[impacted_mask, 'shipment_id'].tolist()
        self._apply_supplier_delay_impacts(supplier_id, impacted_ids_resolved, impact_reason)

        supplier_node = self.current_graph.nodes[supplier_id] if supplier_id and supplier_id in self.current_graph else {}
        supplier_name = supplier_node.get('name', supplier_id if supplier_id else 'Multiple Suppliers')

        label = scenario_label or f"Supplier {supplier_name} +{delay_days} day delay"
        summary = (
            f"{label} results in {late_orders_without_recovery} late shipments before mitigation. "
            f"Post-mitigation SLA: {new_sla:.1f}% (Δ {delta_sla:.1f} pp)."
        )

        return {
            'simulation_parameters': {
                'supplier_id': supplier_id,
                'supplier_name': supplier_name,
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
