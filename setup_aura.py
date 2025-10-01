#!/usr/bin/env python3
"""
Setup script for Neo4j Aura - loads initial data
Run this once after creating your Aura instance
"""
import os
import sys
from pathlib import Path

sys.path.append('src')

from data_loader import Neo4jConnection

def load_data_to_aura():
    """Load CSV data to Neo4j Aura instance."""
    
    # Get Aura credentials from environment
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD')
    
    if not uri or not password:
        print("❌ Please set NEO4J_URI and NEO4J_PASSWORD environment variables")
        print("Example:")
        print("  export NEO4J_URI='neo4j+s://xxxxx.databases.neo4j.io'")
        print("  export NEO4J_PASSWORD='your-password'")
        return False
    
    print(f"🔗 Connecting to Neo4j Aura: {uri}")
    
    try:
        neo4j = Neo4jConnection(uri=uri, user=user, password=password)
        
        # Load constraints
        print("📋 Setting up constraints...")
        neo4j.execute_cypher_file('neo4j/constraints.cypher')
        
        # Load data using Python (since Aura doesn't support LOAD CSV from local files)
        print("📊 Loading data...")
        
        import pandas as pd
        
        # Load suppliers
        suppliers_df = pd.read_csv('data/suppliers.csv')
        for _, row in suppliers_df.iterrows():
            neo4j.execute_cypher("""
                MERGE (s:Supplier {supplier_id: $supplier_id})
                SET s.name = $name,
                    s.region = $region,
                    s.reliability_score = toFloat($reliability_score),
                    s.avg_lead_time_days = toInteger($avg_lead_time_days),
                    s.created_at = datetime(),
                    s.updated_at = datetime()
            """, row.to_dict())
        print(f"  ✅ Loaded {len(suppliers_df)} suppliers")
        
        # Load products
        products_df = pd.read_csv('data/products.csv')
        for _, row in products_df.iterrows():
            neo4j.execute_cypher("""
                MERGE (p:Product {product_id: $product_id})
                SET p.product_name = $product_name,
                    p.category = $category,
                    p.safety_stock = toInteger($safety_stock),
                    p.demand_forecast = toInteger($demand_forecast),
                    p.created_at = datetime(),
                    p.updated_at = datetime()
            """, row.to_dict())
        print(f"  ✅ Loaded {len(products_df)} products")
        
        # Load warehouses
        warehouses_df = pd.read_csv('data/warehouses.csv')
        for _, row in warehouses_df.iterrows():
            neo4j.execute_cypher("""
                MERGE (w:Warehouse {warehouse_id: $warehouse_id})
                SET w.location = $location,
                    w.capacity_units = toInteger($capacity_units),
                    w.region = $region,
                    w.created_at = datetime(),
                    w.updated_at = datetime()
            """, row.to_dict())
        print(f"  ✅ Loaded {len(warehouses_df)} warehouses")
        
        # Load customers
        customers_df = pd.read_csv('data/customers.csv')
        for _, row in customers_df.iterrows():
            neo4j.execute_cypher("""
                MERGE (c:Customer {customer_id: $customer_id})
                SET c.name = $name,
                    c.region = $region,
                    c.avg_demand_units = toInteger($avg_demand_units),
                    c.created_at = datetime(),
                    c.updated_at = datetime()
            """, row.to_dict())
        print(f"  ✅ Loaded {len(customers_df)} customers")
        
        # Load shipments and relationships
        shipments_df = pd.read_csv('data/shipments.csv')
        for _, row in shipments_df.iterrows():
            neo4j.execute_cypher("""
                MATCH (s:Supplier {supplier_id: $supplier_id})
                MATCH (p:Product {product_id: $product_id})
                MATCH (w:Warehouse {warehouse_id: $warehouse_id})
                
                CREATE (sh:Shipment {
                    shipment_id: $shipment_id,
                    qty_units: toInteger($qty_units),
                    planned_lead_time_days: toInteger($planned_lead_time_days),
                    actual_lead_time_days: toInteger($planned_lead_time_days),
                    status: $status,
                    created_at: datetime(),
                    updated_at: datetime()
                })
                
                MERGE (s)-[:SUPPLIES {
                    lead_time_days: toInteger($planned_lead_time_days),
                    reliability: s.reliability_score,
                    last_shipment_date: date(),
                    total_volume: toInteger($qty_units)
                }]->(p)
                
                MERGE (p)-[:STOCKED_AT {
                    current_inventory: toInteger($qty_units),
                    last_updated: date(),
                    reorder_point: p.safety_stock,
                    max_capacity: toInteger($qty_units) * 2
                }]->(w)
                
                CREATE (s)-[:CREATES {
                    shipment_date: date(),
                    volume: toInteger($qty_units)
                }]->(sh)
                
                CREATE (sh)-[:CONTAINS {
                    quantity: toInteger($qty_units),
                    unit_cost: 15.0 + (toInteger($qty_units) * 0.01)
                }]->(p)
                
                CREATE (sh)-[:DELIVERED_TO {
                    delivery_date: date() + duration({days: toInteger($planned_lead_time_days)}),
                    transport_mode: 'Ground',
                    tracking_status: $status
                }]->(w)
            """, row.to_dict())
        print(f"  ✅ Loaded {len(shipments_df)} shipments and relationships")
        
        # Create warehouse-customer relationships
        neo4j.execute_cypher("""
            MATCH (w:Warehouse), (c:Customer)
            WHERE w.region = c.region
            MERGE (w)-[:DELIVERS_TO {
                avg_delivery_days: 2,
                shipping_cost: 25.0,
                service_level: 0.95,
                last_delivery: date() - duration({days: toInteger(rand() * 30 + 1)})
            }]->(c)
        """)
        print("  ✅ Created warehouse-customer relationships")
        
        # Verify
        result = neo4j.execute_cypher("MATCH (n) RETURN count(n) as count")
        print(f"\n✅ Data loaded successfully! Total nodes: {result[0]['count']}")
        
        neo4j.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    load_data_to_aura()
