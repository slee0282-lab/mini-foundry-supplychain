// ======================================================================
// Common Cypher Queries for Supply Chain Analysis
// ======================================================================

// ======================================================================
// Basic Ontology Queries
// ======================================================================

// Find all suppliers for a specific product
MATCH (s:Supplier)-[:SUPPLIES]->(p:Product {product_id: 'P1'})
RETURN s.name, s.region, s.reliability_score, s.avg_lead_time_days
ORDER BY s.reliability_score DESC;

// Trace complete supply chain path for a product
MATCH path = (s:Supplier)-[:SUPPLIES]->(p:Product)-[:STOCKED_AT]->(w:Warehouse)-[:DELIVERS_TO]->(c:Customer)
WHERE p.product_id = 'P1'
RETURN path LIMIT 10;

// Find all products stocked at a specific warehouse
MATCH (p:Product)-[r:STOCKED_AT]->(w:Warehouse {warehouse_id: 'W1'})
RETURN p.product_name, p.category, r.current_inventory, p.safety_stock
ORDER BY r.current_inventory DESC;

// Find bottleneck warehouses (high product count)
MATCH (w:Warehouse)<-[:STOCKED_AT]-(p:Product)
WITH w, count(p) as product_count
WHERE product_count > 2
RETURN w.location, w.region, w.capacity_units, product_count
ORDER BY product_count DESC;

// ======================================================================
// Supplier Analysis Queries
// ======================================================================

// Supplier risk assessment based on shipment performance
MATCH (s:Supplier)-[:CREATES]->(sh:Shipment)
WITH s, count(sh) as total_shipments,
     count(CASE WHEN sh.status = 'Delayed' THEN 1 END) as delayed_shipments
RETURN s.name, s.region, s.reliability_score,
       total_shipments,
       delayed_shipments,
       round(100.0 * delayed_shipments / total_shipments, 2) as delay_rate_percent
ORDER BY delay_rate_percent DESC;

// Top suppliers by reliability in each region
MATCH (s:Supplier)
WITH s.region as region, collect(s) as suppliers
UNWIND suppliers as supplier
WITH region, supplier
ORDER BY supplier.reliability_score DESC
WITH region, collect(supplier)[0..3] as top_suppliers
UNWIND top_suppliers as top_supplier
RETURN region, top_supplier.name, top_supplier.reliability_score;

// Suppliers with longest lead times
MATCH (s:Supplier)
RETURN s.name, s.region, s.avg_lead_time_days, s.reliability_score
ORDER BY s.avg_lead_time_days DESC
LIMIT 10;

// ======================================================================
// Regional Analysis Queries
// ======================================================================

// Regional supply chain capacity analysis
MATCH (w:Warehouse)-[:STOCKED_AT]-(p:Product)
OPTIONAL MATCH (w)-[:DELIVERS_TO]->(c:Customer)
RETURN w.region,
       sum(p.demand_forecast) as total_demand,
       sum(w.capacity_units) as total_capacity,
       count(DISTINCT c) as customer_count,
       count(DISTINCT p) as product_count
ORDER BY total_demand DESC;

// Cross-region supply dependencies
MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)-[:STOCKED_AT]->(w:Warehouse)
WHERE s.region <> w.region
RETURN s.region as supplier_region, w.region as warehouse_region,
       count(*) as cross_region_shipments,
       collect(DISTINCT p.product_name) as products
ORDER BY cross_region_shipments DESC;

// ======================================================================
// Performance and Risk Queries
// ======================================================================

// Critical path suppliers (high volume, low reliability)
MATCH (s:Supplier)-[supplies:SUPPLIES]->(p:Product)-[stocked:STOCKED_AT]->(w:Warehouse)
WITH s, p, w, supplies.total_volume as volume
WHERE s.reliability_score < 0.9 AND volume > 300
RETURN s.name as critical_supplier,
       s.region,
       s.reliability_score,
       p.product_name,
       w.location,
       volume
ORDER BY s.reliability_score ASC, volume DESC;

// Supply chain vulnerability assessment
MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)
WITH p, count(s) as supplier_count, collect(s) as suppliers
WHERE supplier_count = 1  // Single-sourced products
UNWIND suppliers as single_supplier
RETURN p.product_name,
       p.category,
       p.demand_forecast,
       single_supplier.name as sole_supplier,
       single_supplier.reliability_score,
       'HIGH RISK - Single Source' as risk_level
ORDER BY p.demand_forecast DESC;

// Lead time analysis by category
MATCH (s:Supplier)-[supplies:SUPPLIES]->(p:Product)
RETURN p.category,
       avg(supplies.lead_time_days) as avg_lead_time,
       min(supplies.lead_time_days) as min_lead_time,
       max(supplies.lead_time_days) as max_lead_time,
       count(*) as supply_relationships
ORDER BY avg_lead_time DESC;

// ======================================================================
// Shipment and Logistics Queries
// ======================================================================

// Current shipment status overview
MATCH (sh:Shipment)
RETURN sh.status,
       count(*) as shipment_count,
       sum(sh.qty_units) as total_volume,
       avg(sh.planned_lead_time_days) as avg_lead_time
ORDER BY shipment_count DESC;

// Delayed shipments impact analysis
MATCH (s:Supplier)-[:CREATES]->(sh:Shipment)-[:DELIVERED_TO]->(w:Warehouse)
WHERE sh.status = 'Delayed'
MATCH (sh)-[:CONTAINS]->(p:Product)
RETURN s.name as supplier,
       s.region as supplier_region,
       p.product_name,
       w.location as destination,
       sh.qty_units as delayed_volume,
       sh.planned_lead_time_days as planned_days
ORDER BY sh.qty_units DESC;

// ======================================================================
// Network Analysis Queries
// ======================================================================

// Find shortest path between supplier and customer
MATCH (s:Supplier {supplier_id: 'S1'}), (c:Customer {customer_id: 'C1'}),
      path = shortestPath((s)-[*]-(c))
RETURN path;

// Supply chain connectivity analysis
MATCH (s:Supplier)
OPTIONAL MATCH (s)-[*2..4]->(c:Customer)
WITH s, count(DISTINCT c) as reachable_customers
RETURN s.name, s.region, reachable_customers
ORDER BY reachable_customers DESC;

// Node centrality analysis (most connected entities)
MATCH (n)
WHERE n:Supplier OR n:Product OR n:Warehouse OR n:Customer
OPTIONAL MATCH (n)-[r]-()
WITH n, count(r) as degree
RETURN labels(n)[0] as node_type,
       coalesce(n.name, n.product_name, n.location) as entity_name,
       degree
ORDER BY degree DESC
LIMIT 20;

// ======================================================================
// Simulation Preparation Queries
// ======================================================================

// Get all supply paths for disruption simulation
MATCH path = (s:Supplier)-[:SUPPLIES]->(p:Product)-[:STOCKED_AT]->(w:Warehouse)
RETURN s.supplier_id, s.name, s.reliability_score,
       p.product_id, p.product_name, p.demand_forecast,
       w.warehouse_id, w.location, w.region
ORDER BY s.supplier_id, p.product_id;

// Calculate baseline SLA performance
MATCH (sh:Shipment)
WITH count(sh) as total_shipments,
     count(CASE WHEN sh.status = 'On-Time' THEN 1 END) as on_time_shipments
RETURN total_shipments,
       on_time_shipments,
       round(100.0 * on_time_shipments / total_shipments, 2) as baseline_sla_percent;