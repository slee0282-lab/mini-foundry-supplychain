// ======================================================================
// Data Loading Scripts for Supply Chain Ontology
// ======================================================================
// This script loads CSV data and creates the supply chain graph structure
// Run after setting up constraints and indexes

// Clear existing data (optional - uncomment if needed)
// MATCH (n) DETACH DELETE n;

// ======================================================================
// 1. Load Suppliers
// ======================================================================
LOAD CSV WITH HEADERS FROM 'file:///suppliers.csv' AS row
MERGE (s:Supplier {supplier_id: row.supplier_id})
SET s.name = row.name,
    s.region = row.region,
    s.reliability_score = toFloat(row.reliability_score),
    s.avg_lead_time_days = toInteger(row.avg_lead_time_days),
    s.created_at = datetime(),
    s.updated_at = datetime();

// ======================================================================
// 2. Load Products
// ======================================================================
LOAD CSV WITH HEADERS FROM 'file:///products.csv' AS row
MERGE (p:Product {product_id: row.product_id})
SET p.product_name = row.product_name,
    p.category = row.category,
    p.safety_stock = toInteger(row.safety_stock),
    p.demand_forecast = toInteger(row.demand_forecast),
    p.created_at = datetime(),
    p.updated_at = datetime();

// ======================================================================
// 3. Load Warehouses
// ======================================================================
LOAD CSV WITH HEADERS FROM 'file:///warehouses.csv' AS row
MERGE (w:Warehouse {warehouse_id: row.warehouse_id})
SET w.location = row.location,
    w.capacity_units = toInteger(row.capacity_units),
    w.region = row.region,
    w.created_at = datetime(),
    w.updated_at = datetime();

// ======================================================================
// 4. Load Customers
// ======================================================================
LOAD CSV WITH HEADERS FROM 'file:///customers.csv' AS row
MERGE (c:Customer {customer_id: row.customer_id})
SET c.name = row.name,
    c.region = row.region,
    c.avg_demand_units = toInteger(row.avg_demand_units),
    c.created_at = datetime(),
    c.updated_at = datetime();

// ======================================================================
// 5. Load Shipments and Create Relationships
// ======================================================================
LOAD CSV WITH HEADERS FROM 'file:///shipments.csv' AS row
MATCH (s:Supplier {supplier_id: row.supplier_id})
MATCH (p:Product {product_id: row.product_id})
MATCH (w:Warehouse {warehouse_id: row.warehouse_id})

// Create shipment node
CREATE (sh:Shipment {
    shipment_id: row.shipment_id,
    qty_units: toInteger(row.qty_units),
    planned_lead_time_days: toInteger(row.planned_lead_time_days),
    actual_lead_time_days: toInteger(row.planned_lead_time_days), // Initially same as planned
    status: row.status,
    created_at: datetime(),
    updated_at: datetime()
})

// Create supply chain relationships
MERGE (s)-[:SUPPLIES {
    lead_time_days: toInteger(row.planned_lead_time_days),
    reliability: s.reliability_score,
    last_shipment_date: date(),
    total_volume: toInteger(row.qty_units)
}]->(p)

MERGE (p)-[:STOCKED_AT {
    current_inventory: toInteger(row.qty_units),
    last_updated: date(),
    reorder_point: p.safety_stock,
    max_capacity: toInteger(row.qty_units) * 2
}]->(w)

// Connect shipment to entities
CREATE (s)-[:CREATES {
    shipment_date: date(),
    volume: toInteger(row.qty_units)
}]->(sh)

CREATE (sh)-[:CONTAINS {
    quantity: toInteger(row.qty_units),
    unit_cost: 15.0 + (toInteger(row.qty_units) * 0.01) // Mock cost calculation
}]->(p)

CREATE (sh)-[:DELIVERED_TO {
    delivery_date: date() + duration({days: toInteger(row.planned_lead_time_days)}),
    transport_mode: 'Ground',
    tracking_status: row.status
}]->(w);

// ======================================================================
// 6. Create Additional Warehouse-Customer Relationships
// ======================================================================
// Connect warehouses to customers in the same region
MATCH (w:Warehouse), (c:Customer)
WHERE w.region = c.region
MERGE (w)-[:DELIVERS_TO {
    avg_delivery_days: 2,
    shipping_cost: 25.0,
    service_level: 0.95,
    last_delivery: date() - duration({days: randomInt(1, 30)})
}]->(c);

// ======================================================================
// 7. Data Validation Queries
// ======================================================================
// Verify data loading
MATCH (s:Supplier) RETURN count(s) as supplier_count;
MATCH (p:Product) RETURN count(p) as product_count;
MATCH (w:Warehouse) RETURN count(w) as warehouse_count;
MATCH (c:Customer) RETURN count(c) as customer_count;
MATCH (sh:Shipment) RETURN count(sh) as shipment_count;

// Verify relationships
MATCH ()-[r:SUPPLIES]-() RETURN count(r) as supplies_relationships;
MATCH ()-[r:STOCKED_AT]-() RETURN count(r) as stocked_at_relationships;
MATCH ()-[r:DELIVERS_TO]-() RETURN count(r) as delivers_to_relationships;
MATCH ()-[r:CREATES]-() RETURN count(r) as creates_relationships;
MATCH ()-[r:CONTAINS]-() RETURN count(r) as contains_relationships;
MATCH ()-[r:DELIVERED_TO]-() RETURN count(r) as delivered_to_relationships;