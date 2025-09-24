# Data Schemas & Ontology Modeling Guide

## 📊 Mock Dataset Schemas

### 1. Suppliers Dataset (`suppliers.csv`)

| Column Name | Data Type | Description | Example Value |
|-------------|-----------|-------------|---------------|
| supplier_id | String | Unique identifier for supplier | S1 |
| name | String | Supplier company name | BioChemCo |
| region | String | Geographic region | APAC |
| reliability_score | Float | Historical reliability (0-1) | 0.92 |
| avg_lead_time_days | Integer | Average delivery time | 7 |

**Purpose**: Models supplier characteristics and performance metrics
**Key Relationships**: Supplier → Product (via shipments)

---

### 2. Products Dataset (`products.csv`)

| Column Name | Data Type | Description | Example Value |
|-------------|-----------|-------------|---------------|
| product_id | String | Unique product identifier | P1 |
| product_name | String | Product name | Vaccine A |
| category | String | Product category | Pharma |
| safety_stock | Integer | Minimum inventory level | 500 |
| demand_forecast | Integer | Predicted monthly demand | 1200 |

**Purpose**: Connects demand forecasting with supply availability
**Key Relationships**: Product ← Supplier, Product → Warehouse

---

### 3. Warehouses Dataset (`warehouses.csv`)

| Column Name | Data Type | Description | Example Value |
|-------------|-----------|-------------|---------------|
| warehouse_id | String | Unique warehouse identifier | W1 |
| location | String | Warehouse location | Singapore |
| capacity_units | Integer | Maximum storage capacity | 10000 |
| region | String | Geographic region | APAC |

**Purpose**: Distribution and storage nodes in supply network
**Key Relationships**: Warehouse ← Product, Warehouse → Customer

---

### 4. Shipments Dataset (`shipments.csv`)

| Column Name | Data Type | Description | Example Value |
|-------------|-----------|-------------|---------------|
| shipment_id | String | Unique shipment identifier | SH1 |
| supplier_id | String | Source supplier | S1 |
| product_id | String | Product being shipped | P1 |
| warehouse_id | String | Destination warehouse | W1 |
| qty_units | Integer | Quantity shipped | 400 |
| planned_lead_time_days | Integer | Expected delivery time | 7 |
| status | String | Current shipment status | On-Time |

**Purpose**: Captures actual logistics flows and performance
**Key Relationships**: Links Supplier → Product → Warehouse

---

### 5. Customers Dataset (`customers.csv`) [Optional]

| Column Name | Data Type | Description | Example Value |
|-------------|-----------|-------------|---------------|
| customer_id | String | Unique customer identifier | C1 |
| name | String | Customer organization | Hospital SG |
| region | String | Geographic region | APAC |
| avg_demand_units | Integer | Average monthly demand | 300 |

**Purpose**: Extends ontology to end customers
**Key Relationships**: Customer ← Warehouse

---

## 🕸️ Neo4j Graph Ontology Design

### Node Types (Entities)

#### Supplier Node
```cypher
CREATE (s:Supplier {
    supplier_id: "S1",
    name: "BioChemCo",
    region: "APAC",
    reliability_score: 0.92,
    avg_lead_time_days: 7
})
```

#### Product Node
```cypher
CREATE (p:Product {
    product_id: "P1",
    product_name: "Vaccine A",
    category: "Pharma",
    safety_stock: 500,
    demand_forecast: 1200
})
```

#### Warehouse Node
```cypher
CREATE (w:Warehouse {
    warehouse_id: "W1",
    location: "Singapore",
    capacity_units: 10000,
    region: "APAC"
})
```

#### Customer Node
```cypher
CREATE (c:Customer {
    customer_id: "C1",
    name: "Hospital SG",
    region: "APAC",
    avg_demand_units: 300
})
```

#### Shipment Node
```cypher
CREATE (sh:Shipment {
    shipment_id: "SH1",
    qty_units: 400,
    planned_lead_time_days: 7,
    status: "On-Time"
})
```

### Relationship Types (Edges)

#### SUPPLIES Relationship
```cypher
// Supplier supplies Product
(Supplier)-[:SUPPLIES {
    lead_time_days: 7,
    reliability: 0.92,
    cost_per_unit: 15.50
}]->(Product)
```

#### STOCKED_AT Relationship
```cypher
// Product stocked at Warehouse
(Product)-[:STOCKED_AT {
    current_inventory: 800,
    last_updated: "2024-01-15",
    reorder_point: 300
}]->(Warehouse)
```

#### DELIVERS_TO Relationship
```cypher
// Warehouse delivers to Customer
(Warehouse)-[:DELIVERS_TO {
    avg_delivery_days: 2,
    shipping_cost: 25.00,
    service_level: 0.95
}]->(Customer)
```

#### CREATES Relationship
```cypher
// Supplier creates Shipment
(Supplier)-[:CREATES]->(Shipment)
// Shipment delivered to Warehouse
(Shipment)-[:DELIVERED_TO]->(Warehouse)
// Shipment contains Product
(Shipment)-[:CONTAINS]->(Product)
```

---

## 🔗 Complete Ontology Schema

### Graph Structure
```
Supplier ──[SUPPLIES]──> Product ──[STOCKED_AT]──> Warehouse ──[DELIVERS_TO]──> Customer
    │                       │                          │
    └──[CREATES]──> Shipment ──[CONTAINS]──────────────┘
                       │
                       └──[DELIVERED_TO]──> Warehouse
```

### Constraint Creation
```cypher
-- Ensure unique identifiers
CREATE CONSTRAINT ON (s:Supplier) ASSERT s.supplier_id IS UNIQUE;
CREATE CONSTRAINT ON (p:Product) ASSERT p.product_id IS UNIQUE;
CREATE CONSTRAINT ON (w:Warehouse) ASSERT w.warehouse_id IS UNIQUE;
CREATE CONSTRAINT ON (c:Customer) ASSERT c.customer_id IS UNIQUE;
CREATE CONSTRAINT ON (sh:Shipment) ASSERT sh.shipment_id IS UNIQUE;

-- Create indexes for performance
CREATE INDEX ON :Supplier(region);
CREATE INDEX ON :Warehouse(region);
CREATE INDEX ON :Product(category);
```

---

## 📝 Data Import Scripts

### CSV Import Template
```cypher
-- Load suppliers
LOAD CSV WITH HEADERS FROM 'file:///suppliers.csv' AS row
MERGE (s:Supplier {supplier_id: row.supplier_id})
SET s.name = row.name,
    s.region = row.region,
    s.reliability_score = toFloat(row.reliability_score),
    s.avg_lead_time_days = toInteger(row.avg_lead_time_days);

-- Load products
LOAD CSV WITH HEADERS FROM 'file:///products.csv' AS row
MERGE (p:Product {product_id: row.product_id})
SET p.product_name = row.product_name,
    p.category = row.category,
    p.safety_stock = toInteger(row.safety_stock),
    p.demand_forecast = toInteger(row.demand_forecast);

-- Create relationships from shipments
LOAD CSV WITH HEADERS FROM 'file:///shipments.csv' AS row
MATCH (s:Supplier {supplier_id: row.supplier_id})
MATCH (p:Product {product_id: row.product_id})
MATCH (w:Warehouse {warehouse_id: row.warehouse_id})
MERGE (s)-[:SUPPLIES]->(p)
MERGE (p)-[:STOCKED_AT]->(w)
CREATE (sh:Shipment {
    shipment_id: row.shipment_id,
    qty_units: toInteger(row.qty_units),
    planned_lead_time_days: toInteger(row.planned_lead_time_days),
    status: row.status
})
CREATE (s)-[:CREATES]->(sh)
CREATE (sh)-[:CONTAINS]->(p)
CREATE (sh)-[:DELIVERED_TO]->(w);
```

---

## 🔍 Essential Cypher Queries

### Basic Ontology Queries

#### Find all suppliers for a product
```cypher
MATCH (s:Supplier)-[:SUPPLIES]->(p:Product {product_id: 'P1'})
RETURN s.name, s.region, s.reliability_score
ORDER BY s.reliability_score DESC;
```

#### Trace supply chain path
```cypher
MATCH path = (s:Supplier)-[:SUPPLIES]->(p:Product)-[:STOCKED_AT]->(w:Warehouse)
WHERE s.supplier_id = 'S1'
RETURN path;
```

#### Find bottleneck warehouses
```cypher
MATCH (w:Warehouse)<-[:STOCKED_AT]-(p:Product)
WITH w, count(p) as product_count
WHERE product_count > 5
RETURN w.location, w.region, product_count
ORDER BY product_count DESC;
```

### Analytics Queries

#### Supplier risk assessment
```cypher
MATCH (s:Supplier)-[:CREATES]->(sh:Shipment)
WITH s, count(sh) as total_shipments,
     count(CASE WHEN sh.status = 'Delayed' THEN 1 END) as delayed_shipments
RETURN s.name, s.region,
       total_shipments,
       delayed_shipments,
       round(100.0 * delayed_shipments / total_shipments, 2) as delay_rate
ORDER BY delay_rate DESC;
```

#### Regional demand vs supply analysis
```cypher
MATCH (w:Warehouse)-[:STOCKED_AT]-(p:Product)
OPTIONAL MATCH (w)-[:DELIVERS_TO]->(c:Customer)
RETURN w.region,
       sum(p.demand_forecast) as total_demand,
       sum(w.capacity_units) as total_capacity,
       count(DISTINCT c) as customer_count;
```

---

## 📈 Simulation Data Preparation

### Mock Data Generation Guidelines

#### Realistic Data Distributions
- **Reliability Scores**: Normal distribution (μ=0.85, σ=0.15)
- **Lead Times**: Log-normal distribution (2-21 days)
- **Demand Forecasts**: Seasonal patterns with random variance
- **Geographic Distribution**: 40% APAC, 35% EU, 25% NA

#### Data Relationships
- Each supplier provides 2-5 different products
- Each product stocked at 2-4 warehouses
- Each warehouse serves 3-8 customers
- 70% of shipments on-time, 20% delayed, 10% critical delays

#### Sample Data Volume
- **Suppliers**: 20-30 entities
- **Products**: 30-50 entities
- **Warehouses**: 15-20 entities
- **Customers**: 25-40 entities
- **Shipments**: 100-200 records (historical + planned)

This creates a rich enough dataset to demonstrate meaningful disruption propagation while remaining manageable for the MVP.