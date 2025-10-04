#!/usr/bin/env python3
"""
Direct Data Loading to Neo4j using Python
Bypasses LOAD CSV by directly creating nodes and relationships via Python.
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from data_loader import Neo4jConnection
from utils import setup_logging

logger = setup_logging()


def load_suppliers(neo4j: Neo4jConnection, data_path: Path):
    """Load suppliers from CSV."""
    df = pd.read_csv(data_path / 'suppliers.csv')
    logger.info(f"Loading {len(df)} suppliers...")

    for _, row in df.iterrows():
        query = """
        MERGE (s:Supplier {supplier_id: $supplier_id})
        SET s.name = $name,
            s.region = $region,
            s.reliability_score = $reliability_score,
            s.avg_lead_time_days = $avg_lead_time_days,
            s.updated_at = datetime()
        """
        params = {
            'supplier_id': row['supplier_id'],
            'name': row['name'],
            'region': row['region'],
            'reliability_score': float(row['reliability_score']),
            'avg_lead_time_days': int(row['avg_lead_time_days'])
        }
        neo4j.execute_cypher(query, params)
    logger.info(f"✅ Loaded {len(df)} suppliers")


def load_products(neo4j: Neo4jConnection, data_path: Path):
    """Load products from CSV."""
    df = pd.read_csv(data_path / 'products.csv')
    logger.info(f"Loading {len(df)} products...")

    for _, row in df.iterrows():
        query = """
        MERGE (p:Product {product_id: $product_id})
        SET p.product_name = $product_name,
            p.category = $category,
            p.safety_stock = $safety_stock,
            p.demand_forecast = $demand_forecast,
            p.updated_at = datetime()
        """
        params = {
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'category': row['category'],
            'safety_stock': int(row['safety_stock']),
            'demand_forecast': int(row['demand_forecast'])
        }
        neo4j.execute_cypher(query, params)
    logger.info(f"✅ Loaded {len(df)} products")


def load_warehouses(neo4j: Neo4jConnection, data_path: Path):
    """Load warehouses from CSV."""
    df = pd.read_csv(data_path / 'warehouses.csv')
    logger.info(f"Loading {len(df)} warehouses...")

    for _, row in df.iterrows():
        query = """
        MERGE (w:Warehouse {warehouse_id: $warehouse_id})
        SET w.location = $location,
            w.capacity_units = $capacity_units,
            w.region = $region,
            w.updated_at = datetime()
        """
        params = {
            'warehouse_id': row['warehouse_id'],
            'location': row['location'],
            'capacity_units': int(row['capacity_units']),
            'region': row['region']
        }
        neo4j.execute_cypher(query, params)
    logger.info(f"✅ Loaded {len(df)} warehouses")


def load_customers(neo4j: Neo4jConnection, data_path: Path):
    """Load customers from CSV."""
    df = pd.read_csv(data_path / 'customers.csv')
    logger.info(f"Loading {len(df)} customers...")

    for _, row in df.iterrows():
        query = """
        MERGE (c:Customer {customer_id: $customer_id})
        SET c.name = $name,
            c.region = $region,
            c.avg_demand_units = $avg_demand_units,
            c.updated_at = datetime()
        """
        params = {
            'customer_id': row['customer_id'],
            'name': row['name'],
            'region': row['region'],
            'avg_demand_units': int(row['avg_demand_units'])
        }
        neo4j.execute_cypher(query, params)
    logger.info(f"✅ Loaded {len(df)} customers")


def load_shipments_and_relationships(neo4j: Neo4jConnection, data_path: Path):
    """Load shipments and create all relationships."""
    df = pd.read_csv(data_path / 'shipments.csv')
    logger.info(f"Loading {len(df)} shipments and relationships...")

    for _, row in df.iterrows():
        query = """
        MATCH (s:Supplier {supplier_id: $supplier_id})
        MATCH (p:Product {product_id: $product_id})
        MATCH (w:Warehouse {warehouse_id: $warehouse_id})

        // Create shipment
        CREATE (sh:Shipment {
            shipment_id: $shipment_id,
            qty_units: $qty_units,
            planned_lead_time_days: $planned_lead_time_days,
            actual_lead_time_days: $actual_lead_time_days,
            status: $status,
            created_at: datetime()
        })

        // Create SUPPLIES relationship
        MERGE (s)-[:SUPPLIES {
            lead_time_days: $planned_lead_time_days,
            reliability: s.reliability_score,
            total_volume: $qty_units
        }]->(p)

        // Create STOCKED_AT relationship
        MERGE (p)-[:STOCKED_AT {
            current_inventory: $qty_units,
            reorder_point: p.safety_stock,
            max_capacity: $qty_units * 2
        }]->(w)

        // Create CREATES relationship
        CREATE (s)-[:CREATES {
            shipment_date: date(),
            volume: $qty_units
        }]->(sh)

        // Create CONTAINS relationship
        CREATE (sh)-[:CONTAINS {
            quantity: $qty_units,
            unit_cost: 15.0
        }]->(p)

        // Create DELIVERED_TO relationship
        CREATE (sh)-[:DELIVERED_TO {
            transport_mode: 'Ground',
            tracking_status: $status
        }]->(w)
        """
        params = {
            'shipment_id': row['shipment_id'],
            'supplier_id': row['supplier_id'],
            'product_id': row['product_id'],
            'warehouse_id': row['warehouse_id'],
            'qty_units': int(row['qty_units']),
            'planned_lead_time_days': int(row['planned_lead_time_days']),
            'actual_lead_time_days': int(row['planned_lead_time_days']),
            'status': row['status']
        }
        neo4j.execute_cypher(query, params)
    logger.info(f"✅ Loaded {len(df)} shipments and relationships")


def create_warehouse_customer_relationships(neo4j: Neo4jConnection):
    """Create relationships between warehouses and customers in the same region."""
    logger.info("Creating warehouse-customer relationships...")
    query = """
    MATCH (w:Warehouse), (c:Customer)
    WHERE w.region = c.region
    MERGE (w)-[:DELIVERS_TO {
        avg_delivery_days: 2,
        shipping_cost: 25.0,
        service_level: 0.95
    }]->(c)
    """
    neo4j.execute_cypher(query)
    logger.info("✅ Created warehouse-customer relationships")


def load_pilot_supporting_data(neo4j: Neo4jConnection, data_path: Path):
    """Load pilot supporting files (SLA rules, lots, events, etc.)."""
    pilot_path = data_path / 'pilot_missing_supporting_files'

    if not pilot_path.exists():
        logger.warning(f"Pilot data directory not found: {pilot_path}")
        return

    # Load SLA Rules
    sla_file = pilot_path / 'sla_rules.csv'
    if sla_file.exists():
        df = pd.read_csv(sla_file)
        logger.info(f"Loading {len(df)} SLA rules...")
        for _, row in df.iterrows():
            query = """
            MERGE (s:SLARule {rule_id: $rule_id})
            SET s.region = $region,
                s.product_id = $product_id,
                s.promised_days = $promised_days,
                s.priority = $priority,
                s.updated_at = datetime()
            """
            params = {
                'rule_id': f"{row['region']}_{row['product_id']}",
                'region': row['region'],
                'product_id': row['product_id'],
                'promised_days': int(row['promised_days']),
                'priority': row.get('priority', 'MEDIUM')
            }
            neo4j.execute_cypher(query, params)
        logger.info(f"✅ Loaded {len(df)} SLA rules")

    # Load Lots
    lots_file = pilot_path / 'lots.csv'
    if lots_file.exists():
        df = pd.read_csv(lots_file)
        logger.info(f"Loading {len(df)} lots...")
        for _, row in df.iterrows():
            query = """
            MERGE (l:Lot {lot_id: $lot_id})
            SET l.product_id = $product_id,
                l.status = $status,
                l.quality_status = $quality_status,
                l.hold_reason = $hold_reason,
                l.recall_status = $recall_status,
                l.updated_at = datetime()
            """
            params = {
                'lot_id': row['lot_id'],
                'product_id': row['product_id'],
                'status': row.get('status', 'ACTIVE'),
                'quality_status': row.get('quality_status', 'OK'),
                'hold_reason': row.get('hold_reason', ''),
                'recall_status': row.get('recall_status', '')
            }
            neo4j.execute_cypher(query, params)
        logger.info(f"✅ Loaded {len(df)} lots")

    # Load Events
    events_file = pilot_path / 'events.csv'
    if events_file.exists():
        df = pd.read_csv(events_file)
        logger.info(f"Loading {len(df)} events...")
        for _, row in df.iterrows():
            query = """
            MERGE (e:Event {event_id: $event_id})
            SET e.event_type = $event_type,
                e.scope_type = $scope_type,
                e.scope_id = $scope_id,
                e.start_date = $start_date,
                e.end_date = $end_date,
                e.severity = $severity,
                e.status = $status,
                e.description = $description,
                e.impact_value = $impact_value,
                e.updated_at = datetime()
            """
            params = {
                'event_id': row['event_id'],
                'event_type': row['event_type'],
                'scope_type': row.get('scope_type', ''),
                'scope_id': row.get('scope_id', ''),
                'start_date': str(row.get('start_date', '')),
                'end_date': str(row.get('end_date', '')),
                'severity': row.get('severity', 'MEDIUM'),
                'status': row.get('status', 'ACTIVE'),
                'description': row.get('description', ''),
                'impact_value': int(row.get('impact_value', 0)) if pd.notna(row.get('impact_value')) else 0
            }
            neo4j.execute_cypher(query, params)
        logger.info(f"✅ Loaded {len(df)} events")

    # Load Costs
    costs_file = pilot_path / 'costs.csv'
    if costs_file.exists():
        df = pd.read_csv(costs_file)
        logger.info(f"Loading {len(df)} cost records...")
        for _, row in df.iterrows():
            query = """
            MERGE (c:Cost {cost_id: $cost_id})
            SET c.cost_type = $cost_type,
                c.region = $region,
                c.value = $value,
                c.currency = $currency,
                c.updated_at = datetime()
            """
            params = {
                'cost_id': f"{row['cost_type']}_{row['region']}",
                'cost_type': row['cost_type'],
                'region': row['region'],
                'value': float(row['value']),
                'currency': row.get('currency', 'USD')
            }
            neo4j.execute_cypher(query, params)
        logger.info(f"✅ Loaded {len(df)} cost records")

    # Load Cold Chain Readings
    cold_chain_file = pilot_path / 'cold_chain_readings.csv'
    if cold_chain_file.exists():
        df = pd.read_csv(cold_chain_file)
        logger.info(f"Loading {len(df)} cold chain readings...")
        for _, row in df.iterrows():
            # Convert timestamp to ISO format (replace space with 'T')
            timestamp_str = str(row.get('timestamp', '')).strip()
            if timestamp_str and ' ' in timestamp_str:
                timestamp_str = timestamp_str.replace(' ', 'T')

            query = """
            MERGE (r:ColdChainReading {reading_id: $reading_id})
            SET r.shipment_id = $shipment_id,
                r.lot_id = $lot_id,
                r.timestamp = $timestamp,
                r.temperature_c = $temperature_c,
                r.threshold_min_c = $threshold_min_c,
                r.threshold_max_c = $threshold_max_c,
                r.excursion_flag = $excursion_flag,
                r.excursion_duration_minutes = $excursion_duration_minutes,
                r.notes = $notes,
                r.updated_at = datetime()
            """
            params = {
                'reading_id': row['reading_id'],
                'shipment_id': row.get('shipment_id', ''),
                'lot_id': row.get('lot_id', ''),
                'timestamp': timestamp_str,
                'temperature_c': float(row['temperature_c']),
                'threshold_min_c': float(row.get('threshold_min_c', 2.0)),
                'threshold_max_c': float(row.get('threshold_max_c', 8.0)),
                'excursion_flag': row.get('excursion_flag', 'NO'),
                'excursion_duration_minutes': int(row.get('excursion_duration_minutes', 0)) if pd.notna(row.get('excursion_duration_minutes')) else 0,
                'notes': row.get('notes', '')
            }
            neo4j.execute_cypher(query, params)
        logger.info(f"✅ Loaded {len(df)} cold chain readings")

    # Load Shipment-Lot mappings
    shipment_lots_file = pilot_path / 'shipments_lots.csv'
    if shipment_lots_file.exists():
        df = pd.read_csv(shipment_lots_file)
        logger.info(f"Loading {len(df)} shipment-lot relationships...")
        for _, row in df.iterrows():
            query = """
            MATCH (sh:Shipment {shipment_id: $shipment_id})
            MATCH (l:Lot {lot_id: $lot_id})
            MERGE (sh)-[r:CONTAINS_LOT]->(l)
            SET r.quantity_units = $quantity_units,
                r.packing_date = $packing_date,
                r.shipping_date = $shipping_date,
                r.temperature_monitored = $temperature_monitored,
                r.notes = $notes
            """
            params = {
                'shipment_id': row['shipment_id'],
                'lot_id': row['lot_id'],
                'quantity_units': int(row.get('quantity_units', 0)) if pd.notna(row.get('quantity_units')) else 0,
                'packing_date': str(row.get('packing_date', '')),
                'shipping_date': str(row.get('shipping_date', '')),
                'temperature_monitored': row.get('temperature_monitored', 'NO'),
                'notes': row.get('notes', '')
            }
            neo4j.execute_cypher(query, params)
        logger.info(f"✅ Loaded {len(df)} shipment-lot relationships")


def get_stats(neo4j: Neo4jConnection):
    """Get and display database statistics."""
    stats_queries = {
        'Suppliers': 'MATCH (s:Supplier) RETURN count(s) as count',
        'Products': 'MATCH (p:Product) RETURN count(p) as count',
        'Warehouses': 'MATCH (w:Warehouse) RETURN count(w) as count',
        'Customers': 'MATCH (c:Customer) RETURN count(c) as count',
        'Shipments': 'MATCH (sh:Shipment) RETURN count(sh) as count',
        'SLA Rules': 'MATCH (s:SLARule) RETURN count(s) as count',
        'Lots': 'MATCH (l:Lot) RETURN count(l) as count',
        'Events': 'MATCH (e:Event) RETURN count(e) as count',
        'Costs': 'MATCH (c:Cost) RETURN count(c) as count',
        'Cold Chain Readings': 'MATCH (r:ColdChainReading) RETURN count(r) as count',
        'SUPPLIES': 'MATCH ()-[r:SUPPLIES]-() RETURN count(r) as count',
        'STOCKED_AT': 'MATCH ()-[r:STOCKED_AT]-() RETURN count(r) as count',
        'CREATES': 'MATCH ()-[r:CREATES]-() RETURN count(r) as count',
        'CONTAINS': 'MATCH ()-[r:CONTAINS]-() RETURN count(r) as count',
        'DELIVERED_TO': 'MATCH ()-[r:DELIVERED_TO]-() RETURN count(r) as count',
        'DELIVERS_TO': 'MATCH ()-[r:DELIVERS_TO]-() RETURN count(r) as count',
    }

    logger.info("\n📊 Database Statistics:")
    for name, query in stats_queries.items():
        try:
            result = neo4j.execute_cypher(query)
            count = result[0]['count'] if result else 0
            logger.info(f"  {name}: {count}")
        except Exception as e:
            logger.error(f"  {name}: Error - {str(e)}")


def main():
    """Main loading function."""
    logger.info("🚀 Starting Direct Data Load to Neo4j")

    try:
        # Initialize connection
        neo4j = Neo4jConnection()
        logger.info("✅ Connected to Neo4j")

        # Determine data path
        repo_root = Path(__file__).parent.parent
        data_path = repo_root / 'data'

        if not data_path.exists():
            logger.error(f"❌ Data directory not found: {data_path}")
            return False

        # Optional: Clear existing data
        clear = input("\n⚠️  Clear existing data? (y/N): ").lower().strip()
        if clear == 'y':
            logger.info("Clearing existing data...")
            neo4j.execute_cypher("MATCH (n) DETACH DELETE n")
            logger.info("✅ Database cleared")

        # Load core data
        load_suppliers(neo4j, data_path)
        load_products(neo4j, data_path)
        load_warehouses(neo4j, data_path)
        load_customers(neo4j, data_path)
        load_shipments_and_relationships(neo4j, data_path)
        create_warehouse_customer_relationships(neo4j)

        # Load pilot supporting data
        load_pilot_supporting_data(neo4j, data_path)

        # Display stats
        get_stats(neo4j)

        logger.info("\n🎉 Data loading completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run the dashboard: streamlit run dashboard/app.py")
        logger.info("2. Or: python main.py")

        neo4j.close()
        return True

    except Exception as e:
        logger.error(f"❌ Data loading failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
