"""
Load Pilot Missing Supporting Files to Neo4j

This script loads the additional data files needed for the 5 pharmaceutical scenarios:
1. Supplier delay
2. Supplier outage
3. Regulatory/customs hold
4. Cold-chain temperature excursion
5. Batch/lot recall traceability
"""

import os
import sys
import pandas as pd
import logging
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_loader import Neo4jConnection
from utils import setup_logging, get_config

logger = setup_logging()


class PilotDataLoader:
    """Load pilot supporting data files into Neo4j."""

    def __init__(self, neo4j_conn=None):
        self.neo4j = neo4j_conn or Neo4jConnection()
        self.config = get_config()
        self.data_dir = Path(__file__).parent.parent / 'data' / 'pilot_missing_supporting_files'

    def load_all(self):
        """Load all pilot data files."""
        logger.info("Starting pilot data load...")

        try:
            # Load in dependency order
            self.load_sla_rules()
            self.load_lanes()
            self.load_costs()
            self.load_lots()
            self.load_shipments_lots()
            self.load_cold_chain_readings()
            self.load_events()

            logger.info("✓ All pilot data loaded successfully")

        except Exception as e:
            logger.error(f"Error loading pilot data: {str(e)}")
            raise

    def load_sla_rules(self):
        """Load SLA rules."""
        logger.info("Loading SLA rules...")

        df = pd.read_csv(self.data_dir / 'sla_rules.csv')

        # Create SLA rule nodes
        query = """
        UNWIND $rules AS rule
        MERGE (s:SLARule {rule_id: rule.rule_id})
        SET s.region = rule.region,
            s.product_category = rule.product_category,
            s.product_id = rule.product_id,
            s.promised_days = toInteger(rule.promised_days),
            s.priority = rule.priority,
            s.customer_tier = rule.customer_tier

        // Link to product
        WITH s, rule
        MATCH (p:Product {product_id: rule.product_id})
        MERGE (s)-[:APPLIES_TO]->(p)
        """

        rules = df.to_dict('records')
        self.neo4j.execute_cypher(query, {'rules': rules})
        logger.info(f"✓ Loaded {len(rules)} SLA rules")

    def load_lanes(self):
        """Load logistics lanes."""
        logger.info("Loading lanes...")

        df = pd.read_csv(self.data_dir / 'lanes.csv')

        query = """
        UNWIND $lanes AS lane
        MERGE (l:Lane {lane_id: lane.lane_id})
        SET l.origin_region = lane.origin_region,
            l.dest_region = lane.dest_region,
            l.base_lead_time_days = toInteger(lane.base_lead_time_days),
            l.transport_mode = lane.transport_mode,
            l.distance_km = toInteger(lane.distance_km),
            l.reliability_score = toFloat(lane.reliability_score),
            l.capacity_units_per_week = toInteger(lane.capacity_units_per_week)
        """

        lanes = df.to_dict('records')
        self.neo4j.execute_cypher(query, {'lanes': lanes})
        logger.info(f"✓ Loaded {len(lanes)} lanes")

    def load_costs(self):
        """Load cost information."""
        logger.info("Loading costs...")

        df = pd.read_csv(self.data_dir / 'costs.csv')

        query = """
        UNWIND $costs AS cost
        MERGE (c:Cost {cost_id: cost.cost_id})
        SET c.cost_type = cost.cost_type,
            c.category = cost.category,
            c.product_id = cost.product_id,
            c.region = cost.region,
            c.customer_tier = cost.customer_tier,
            c.value = toFloat(cost.value),
            c.currency = cost.currency,
            c.unit = cost.unit,
            c.notes = cost.notes

        // Link to products if applicable
        WITH c, cost
        WHERE cost.product_id <> 'ALL'
        MATCH (p:Product {product_id: cost.product_id})
        MERGE (c)-[:APPLIES_TO]->(p)
        """

        costs = df.to_dict('records')
        self.neo4j.execute_cypher(query, {'costs': costs})
        logger.info(f"✓ Loaded {len(costs)} cost records")

    def load_lots(self):
        """Load lot/batch information."""
        logger.info("Loading lots...")

        df = pd.read_csv(self.data_dir / 'lots.csv')

        query = """
        UNWIND $lots AS lot
        MERGE (l:Lot {lot_id: lot.lot_id})
        SET l.product_id = lot.product_id,
            l.manufacturing_date = lot.manufacturing_date,
            l.expiry_date = lot.expiry_date,
            l.quantity_units = toInteger(lot.quantity_units),
            l.status = lot.status,
            l.storage_condition = lot.storage_condition,
            l.site_id = lot.site_id,
            l.batch_record_id = lot.batch_record_id,
            l.quality_status = lot.quality_status,
            l.hold_reason = lot.hold_reason,
            l.recall_status = lot.recall_status

        // Link to product
        WITH l, lot
        MATCH (p:Product {product_id: lot.product_id})
        MERGE (l)-[:BELONGS_TO]->(p)
        """

        lots = df.to_dict('records')
        self.neo4j.execute_cypher(query, {'lots': lots})
        logger.info(f"✓ Loaded {len(lots)} lots")

    def load_shipments_lots(self):
        """Load shipment-lot mapping."""
        logger.info("Loading shipment-lot mappings...")

        df = pd.read_csv(self.data_dir / 'shipments_lots.csv')

        query = """
        UNWIND $mappings AS mapping
        MATCH (s:Shipment {shipment_id: mapping.shipment_id})
        MATCH (l:Lot {lot_id: mapping.lot_id})
        MERGE (s)-[c:CONTAINS {shipment_lot_id: mapping.shipment_lot_id}]->(l)
        SET c.quantity_units = toInteger(mapping.quantity_units),
            c.packing_date = mapping.packing_date,
            c.shipping_date = mapping.shipping_date,
            c.temperature_monitored = mapping.temperature_monitored,
            c.notes = mapping.notes
        """

        mappings = df.to_dict('records')
        self.neo4j.execute_cypher(query, {'mappings': mappings})
        logger.info(f"✓ Loaded {len(mappings)} shipment-lot mappings")

    def load_cold_chain_readings(self):
        """Load cold chain temperature readings."""
        logger.info("Loading cold chain readings...")

        df = pd.read_csv(self.data_dir / 'cold_chain_readings.csv')

        query = """
        UNWIND $readings AS reading
        MERGE (r:ColdChainReading {reading_id: reading.reading_id})
        SET r.shipment_id = reading.shipment_id,
            r.lot_id = reading.lot_id,
            r.timestamp = reading.timestamp,
            r.temperature_c = toFloat(reading.temperature_c),
            r.humidity_percent = toFloat(reading.humidity_percent),
            r.location = reading.location,
            r.device_id = reading.device_id,
            r.threshold_min_c = toFloat(reading.threshold_min_c),
            r.threshold_max_c = toFloat(reading.threshold_max_c),
            r.excursion_flag = reading.excursion_flag,
            r.excursion_duration_minutes = toInteger(reading.excursion_duration_minutes),
            r.notes = reading.notes

        // Link to shipment
        WITH r, reading
        MATCH (s:Shipment {shipment_id: reading.shipment_id})
        MERGE (r)-[:MONITORS]->(s)

        // Link to lot
        WITH r, reading
        MATCH (l:Lot {lot_id: reading.lot_id})
        MERGE (r)-[:TRACKS]->(l)
        """

        readings = df.to_dict('records')
        self.neo4j.execute_cypher(query, {'readings': readings})
        logger.info(f"✓ Loaded {len(readings)} cold chain readings")

    def load_events(self):
        """Load scenario events."""
        logger.info("Loading events...")

        df = pd.read_csv(self.data_dir / 'events.csv')

        query = """
        UNWIND $events AS event
        MERGE (e:Event {event_id: event.event_id})
        SET e.event_type = event.event_type,
            e.scope_type = event.scope_type,
            e.scope_id = event.scope_id,
            e.impact_value = toFloat(event.impact_value),
            e.impact_unit = event.impact_unit,
            e.start_date = event.start_date,
            e.end_date = event.end_date,
            e.severity = event.severity,
            e.status = event.status,
            e.description = event.description
        """

        events = df.to_dict('records')
        self.neo4j.execute_cypher(query, {'events': events})

        # Create relationships based on scope_type
        self._link_events_to_entities(df)

        logger.info(f"✓ Loaded {len(events)} events")

    def _link_events_to_entities(self, events_df):
        """Link events to their target entities."""

        # Link to suppliers
        supplier_events = events_df[events_df['scope_type'] == 'SUPPLIER']
        if not supplier_events.empty:
            query = """
            UNWIND $events AS event
            MATCH (e:Event {event_id: event.event_id})
            MATCH (s:Supplier {supplier_id: event.scope_id})
            MERGE (e)-[:IMPACTS]->(s)
            """
            self.neo4j.execute_cypher(query, {'events': supplier_events.to_dict('records')})

        # Link to regions (warehouses in region)
        region_events = events_df[events_df['scope_type'] == 'REGION']
        if not region_events.empty:
            query = """
            UNWIND $events AS event
            MATCH (e:Event {event_id: event.event_id})
            MATCH (w:Warehouse {region: event.scope_id})
            MERGE (e)-[:IMPACTS]->(w)
            """
            self.neo4j.execute_cypher(query, {'events': region_events.to_dict('records')})

        # Link to shipments
        shipment_events = events_df[events_df['scope_type'] == 'SHIPMENT']
        if not shipment_events.empty:
            query = """
            UNWIND $events AS event
            MATCH (e:Event {event_id: event.event_id})
            MATCH (s:Shipment {shipment_id: event.scope_id})
            MERGE (e)-[:IMPACTS]->(s)
            """
            self.neo4j.execute_cypher(query, {'events': shipment_events.to_dict('records')})

        # Link to lots
        lot_events = events_df[events_df['scope_type'] == 'LOT']
        if not lot_events.empty:
            query = """
            UNWIND $events AS event
            MATCH (e:Event {event_id: event.event_id})
            MATCH (l:Lot {lot_id: event.scope_id})
            MERGE (e)-[:IMPACTS]->(l)
            """
            self.neo4j.execute_cypher(query, {'events': lot_events.to_dict('records')})

    def verify_load(self):
        """Verify all data was loaded correctly."""
        logger.info("\nVerifying data load...")

        checks = [
            ("SLARule", "MATCH (n:SLARule) RETURN count(n) as count"),
            ("Lane", "MATCH (n:Lane) RETURN count(n) as count"),
            ("Cost", "MATCH (n:Cost) RETURN count(n) as count"),
            ("Lot", "MATCH (n:Lot) RETURN count(n) as count"),
            ("CONTAINS relationships", "MATCH ()-[r:CONTAINS]->() RETURN count(r) as count"),
            ("ColdChainReading", "MATCH (n:ColdChainReading) RETURN count(n) as count"),
            ("Event", "MATCH (n:Event) RETURN count(n) as count"),
            ("IMPACTS relationships", "MATCH ()-[r:IMPACTS]->() RETURN count(r) as count")
        ]

        for label, query in checks:
            result = self.neo4j.execute_cypher(query)
            count = result[0]['count'] if result else 0
            logger.info(f"  {label}: {count}")


def main():
    """Main execution."""
    try:
        logger.info("=" * 60)
        logger.info("PILOT SUPPORTING DATA LOADER")
        logger.info("=" * 60)

        # Initialize loader
        loader = PilotDataLoader()

        # Load all data
        loader.load_all()

        # Verify
        loader.verify_load()

        logger.info("\n" + "=" * 60)
        logger.info("✓ PILOT DATA LOAD COMPLETE")
        logger.info("=" * 60)

        # Close connection
        loader.neo4j.close()

    except Exception as e:
        logger.error(f"Failed to load pilot data: {str(e)}")
        raise


if __name__ == "__main__":
    main()
