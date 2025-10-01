// ======================================================================
// Neo4j Constraints and Indexes for Supply Chain Ontology
// ======================================================================

// Create unique constraints for all entity types
CREATE CONSTRAINT supplier_id_unique IF NOT EXISTS
FOR (s:Supplier) REQUIRE s.supplier_id IS UNIQUE;

CREATE CONSTRAINT product_id_unique IF NOT EXISTS
FOR (p:Product) REQUIRE p.product_id IS UNIQUE;

CREATE CONSTRAINT warehouse_id_unique IF NOT EXISTS
FOR (w:Warehouse) REQUIRE w.warehouse_id IS UNIQUE;

CREATE CONSTRAINT customer_id_unique IF NOT EXISTS
FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE;

CREATE CONSTRAINT shipment_id_unique IF NOT EXISTS
FOR (sh:Shipment) REQUIRE sh.shipment_id IS UNIQUE;

// Create performance indexes for frequent queries
CREATE INDEX supplier_region_idx IF NOT EXISTS
FOR (s:Supplier) ON (s.region);

CREATE INDEX warehouse_region_idx IF NOT EXISTS
FOR (w:Warehouse) ON (w.region);

CREATE INDEX product_category_idx IF NOT EXISTS
FOR (p:Product) ON (p.category);

CREATE INDEX shipment_status_idx IF NOT EXISTS
FOR (sh:Shipment) ON (sh.status);

CREATE INDEX supplier_reliability_idx IF NOT EXISTS
FOR (s:Supplier) ON (s.reliability_score);

CREATE INDEX product_demand_idx IF NOT EXISTS
FOR (p:Product) ON (p.demand_forecast);

CREATE INDEX warehouse_capacity_idx IF NOT EXISTS
FOR (w:Warehouse) ON (w.capacity_units);

// Create composite indexes for complex queries
CREATE INDEX supplier_region_reliability_idx IF NOT EXISTS
FOR (s:Supplier) ON (s.region, s.reliability_score);

CREATE INDEX product_category_demand_idx IF NOT EXISTS
FOR (p:Product) ON (p.category, p.demand_forecast);