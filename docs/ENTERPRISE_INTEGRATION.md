# Enterprise Database Integration Guide

## 🏢 Overview

This guide covers integrating the Mini Foundry Supply Chain Control Tower with enterprise systems:
- **SAP S/4HANA**: ERP system via OData APIs and RFC
- **Oracle Database**: Direct database connectivity via SQL
- **Neo4j**: Graph analytics layer

## 📋 Table of Contents

1. [Architecture](#architecture)
2. [SAP S/4HANA Integration](#sap-s4hana-integration)
3. [Oracle Database Integration](#oracle-database-integration)
4. [Data Models & Mapping](#data-models--mapping)
5. [Configuration](#configuration)
6. [Usage Examples](#usage-examples)
7. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture

### Multi-Source Integration Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Dashboard                       │
├─────────────────────────────────────────────────────────────┤
│              Analytics & Simulation Layer                    │
├─────────────────────────────────────────────────────────────┤
│                   Neo4j Graph Database                       │
│              (Unified Ontology & Analytics)                  │
├──────────────┬────────────────────┬─────────────────────────┤
│              │                    │                         │
│  SAP S/4HANA │  Oracle Database   │  CSV Files             │
│  (ERP Data)  │  (Warehouse Data)  │  (Mock/Test Data)      │
│              │                    │                         │
│  • Suppliers │  • Shipments       │  • All Entities         │
│  • Materials │  • Inventory       │  • For Testing          │
│  • Plants    │  • Custom Tables   │                         │
│  • POs       │                    │                         │
└──────────────┴────────────────────┴─────────────────────────┘
```

### Data Flow

1. **Extract**: Connectors pull data from SAP/Oracle
2. **Transform**: Pydantic models validate and normalize data
3. **Load**: ETL pipeline writes to Neo4j graph database
4. **Analyze**: Graph algorithms and ML on unified ontology
5. **Visualize**: Streamlit dashboard presents insights

---

## 🔌 SAP S/4HANA Integration

### Overview

SAP connector supports two methods:
- **OData API** (recommended): Modern REST-based API
- **RFC** (legacy): Direct function module calls

### Prerequisites

#### For OData:
- SAP S/4HANA Cloud or On-Premise with OData services enabled
- User account with appropriate authorizations
- Network access to SAP system (HTTPS)

#### For RFC:
- SAP NetWeaver RFC SDK installed
- `pyrfc` Python library
- User account with RFC authorization

### SAP Tables Mapped

| SAP Table/Entity | Purpose | Mapped To |
|------------------|---------|-----------|
| `LFA1` / `A_Supplier` | Vendor master data | Suppliers |
| `MARA`/`MARC` / `A_Product` | Material master | Products |
| `T001L` / `A_Plant` | Plant/storage locations | Warehouses |
| `EKKO`/`EKPO` / `A_PurchaseOrder` | Purchase orders | Shipments |

### Configuration

Add to `.env`:

```bash
# SAP S/4HANA Configuration
SAP_HOST=your-s4hana-host.com
SAP_PORT=443
SAP_USER=your-username
SAP_PASSWORD=your-password
SAP_CLIENT=100
SAP_SYSTEM_ID=S4H

# Choose integration method
SAP_USE_ODATA=true
SAP_USE_RFC=false
```

### Usage Example

```python
from src.connectors import ConnectorFactory, ConnectionConfig, DataSourceType

# Create SAP connector
config = ConnectionConfig(
    source_type=DataSourceType.SAP_S4HANA,
    host="s4hana.example.com",
    port=443,
    username="SAP_USER",
    password="SAP_PASS",
    client="100"
)

sap_connector = ConnectorFactory.create_connector(config)

# Connect and fetch data
with sap_connector:
    # Fetch suppliers
    suppliers = sap_connector.fetch_suppliers(
        filters={'limit': 100}
    )

    # Fetch products/materials
    products = sap_connector.fetch_products(
        filters={'filter': "ProductGroup eq 'MEDICAL'"}
    )

    # Fetch plants/warehouses
    warehouses = sap_connector.fetch_warehouses()

    # Fetch purchase orders
    shipments = sap_connector.fetch_shipments(
        filters={'filter': "PurchaseOrderDate ge 2024-01-01"}
    )
```

### OData Query Examples

```python
# Filter by region
suppliers = sap_connector.fetch_suppliers(
    filters={'filter': "Country eq 'US'"}
)

# Limit results
products = sap_connector.fetch_products(
    filters={'limit': 50}
)

# Complex filter
shipments = sap_connector.fetch_shipments(
    filters={
        'filter': "PurchaseOrderDate ge 2024-01-01 and Supplier eq 'VENDOR001'",
        'expand': 'to_PurchaseOrderItem'
    }
)
```

---

## 🗄️ Oracle Database Integration

### Overview

Oracle connector uses:
- **oracledb**: Modern Oracle database driver (thick/thin modes)
- **SQLAlchemy**: ORM and connection pooling

### Prerequisites

- Oracle Database 11g or higher
- Oracle Instant Client (for thick mode, optional)
- Network access to Oracle database
- User account with SELECT privileges on supply chain tables

### Oracle Schema

Example table structure (customize for your schema):

```sql
-- Suppliers table
CREATE TABLE SUPPLIERS (
    SUPPLIER_ID VARCHAR2(50) PRIMARY KEY,
    SUPPLIER_NAME VARCHAR2(200),
    REGION VARCHAR2(100),
    COUNTRY VARCHAR2(100),
    RELIABILITY_SCORE NUMBER(3,2),
    AVG_LEAD_TIME_DAYS NUMBER(3),
    LAST_UPDATED TIMESTAMP
);

-- Products table
CREATE TABLE PRODUCTS (
    PRODUCT_ID VARCHAR2(50) PRIMARY KEY,
    PRODUCT_NAME VARCHAR2(200),
    CATEGORY VARCHAR2(100),
    SUBCATEGORY VARCHAR2(100),
    UNIT_OF_MEASURE VARCHAR2(20),
    SAFETY_STOCK NUMBER(10),
    DEMAND_FORECAST NUMBER(10)
);

-- Warehouses table
CREATE TABLE WAREHOUSES (
    WAREHOUSE_ID VARCHAR2(50) PRIMARY KEY,
    WAREHOUSE_NAME VARCHAR2(200),
    LOCATION VARCHAR2(200),
    REGION VARCHAR2(100),
    COUNTRY VARCHAR2(100),
    CAPACITY_UNITS NUMBER(10),
    AVAILABLE_CAPACITY NUMBER(10)
);

-- Shipments table
CREATE TABLE SHIPMENTS (
    SHIPMENT_ID VARCHAR2(50) PRIMARY KEY,
    ORDER_ID VARCHAR2(50),
    SUPPLIER_ID VARCHAR2(50),
    PRODUCT_ID VARCHAR2(50),
    WAREHOUSE_ID VARCHAR2(50),
    QUANTITY NUMBER(10),
    PLANNED_LEAD_TIME_DAYS NUMBER(3),
    ACTUAL_LEAD_TIME_DAYS NUMBER(3),
    STATUS VARCHAR2(20),
    ORDER_DATE DATE,
    EXPECTED_DELIVERY_DATE DATE,
    ACTUAL_DELIVERY_DATE DATE,
    FOREIGN KEY (SUPPLIER_ID) REFERENCES SUPPLIERS(SUPPLIER_ID),
    FOREIGN KEY (PRODUCT_ID) REFERENCES PRODUCTS(PRODUCT_ID),
    FOREIGN KEY (WAREHOUSE_ID) REFERENCES WAREHOUSES(WAREHOUSE_ID)
);
```

### Configuration

Add to `.env`:

```bash
# Oracle Database Configuration
ORACLE_HOST=oracle-db.example.com
ORACLE_PORT=1521
ORACLE_USER=supply_chain_user
ORACLE_PASSWORD=your-password

# Use either SERVICE_NAME or SID
ORACLE_SERVICE_NAME=ORCL
# ORACLE_SID=ORCL

ORACLE_SCHEMA=SUPPLY_CHAIN
```

### Usage Example

```python
from src.connectors import OracleConnector, ConnectionConfig, DataSourceType

# Create Oracle connector
config = ConnectionConfig(
    source_type=DataSourceType.ORACLE,
    host="oracle-db.example.com",
    port=1521,
    username="supply_chain_user",
    password="password",
    service_name="ORCL",
    schema="SUPPLY_CHAIN"
)

oracle_connector = OracleConnector(config)

# Connect and fetch data
with oracle_connector:
    # Fetch suppliers from Oracle
    suppliers = oracle_connector.fetch_suppliers(
        filters={'region': 'North America', 'limit': 100}
    )

    # Fetch products
    products = oracle_connector.fetch_products()

    # Fetch warehouses
    warehouses = oracle_connector.fetch_warehouses()

    # Fetch shipments with date filter
    from datetime import datetime, timedelta
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    shipments = oracle_connector.fetch_shipments(
        filters={'start_date': start_date, 'limit': 500}
    )
```

### Custom Queries

```python
# Execute custom SQL query
custom_query = """
    SELECT s.SUPPLIER_NAME, COUNT(sh.SHIPMENT_ID) as total_shipments
    FROM SUPPLIERS s
    JOIN SHIPMENTS sh ON s.SUPPLIER_ID = sh.SUPPLIER_ID
    WHERE sh.ORDER_DATE >= :start_date
    GROUP BY s.SUPPLIER_NAME
    ORDER BY total_shipments DESC
"""

results = oracle_connector.execute_custom_query(
    custom_query,
    params={'start_date': '2024-01-01'}
)
```

---

## 📊 Data Models & Mapping

### Pydantic Models

All entities use Pydantic for validation:

```python
from src.models import Supplier, Product, Warehouse, Shipment, DataSource

# Create validated supplier
supplier = Supplier(
    supplier_id="S001",
    name="BioChemCo",
    region="APAC",
    reliability_score=0.92,
    avg_lead_time_days=7,
    source_system=DataSource.SAP_S4HANA
)

# Automatic validation
supplier.reliability_score = 1.5  # Raises ValidationError (must be 0-1)

# Convert to Neo4j format
neo4j_props = supplier.to_neo4j_dict()
```

### Field Mapping

Connectors automatically map source fields to unified model:

| Unified Field | SAP Field | Oracle Field |
|---------------|-----------|--------------|
| `supplier_id` | `Supplier` / `Lifnr` | `SUPPLIER_ID` |
| `name` | `SupplierName` / `Name1` | `SUPPLIER_NAME` |
| `region` | `Country` / `Land1` | `REGION` |
| `reliability_score` | Calculated | `RELIABILITY_SCORE` |
| `avg_lead_time_days` | From info records | `AVG_LEAD_TIME_DAYS` |

### Mapper Functions

```python
from src.models.supply_chain_entities import map_to_supplier, DataSource

# Map SAP data to Supplier model
sap_data = {
    'Supplier': 'VENDOR001',
    'SupplierName': 'ABC Corp',
    'Country': 'US'
}

supplier = map_to_supplier(sap_data, DataSource.SAP_S4HANA)

# Map Oracle data
oracle_data = {
    'SUPPLIER_ID': 'SUPP001',
    'SUPPLIER_NAME': 'XYZ Inc',
    'REGION': 'Europe',
    'RELIABILITY_SCORE': 0.95
}

supplier = map_to_supplier(oracle_data, DataSource.ORACLE)
```

---

## ⚙️ Configuration

### Environment Variables

See `.env.example` for complete configuration template.

### Streamlit Secrets (Cloud Deployment)

For Streamlit Cloud, add to secrets:

```toml
# SAP S/4HANA
SAP_HOST = "s4hana.example.com"
SAP_USER = "your-username"
SAP_PASSWORD = "your-password"
SAP_CLIENT = "100"

# Oracle
ORACLE_HOST = "oracle.example.com"
ORACLE_USER = "supply_chain_user"
ORACLE_PASSWORD = "your-password"
ORACLE_SERVICE_NAME = "ORCL"

# Data Sources
ENABLED_DATA_SOURCES = "SAP_S4HANA,ORACLE,NEO4J"
```

### Multi-Source Priority

Configure primary source for each entity:

```bash
PRIMARY_SUPPLIER_SOURCE=SAP_S4HANA
PRIMARY_PRODUCT_SOURCE=SAP_S4HANA
PRIMARY_WAREHOUSE_SOURCE=ORACLE
PRIMARY_SHIPMENT_SOURCE=ORACLE
```

---

## 💻 Usage Examples

### Example 1: Sync SAP Suppliers to Neo4j

```python
from src.connectors import ConnectorFactory, DataSourceType
from src.data_loader import Neo4jConnection
from src.models import map_to_supplier, DataSource

# Initialize connectors
sap = ConnectorFactory.create_from_env(DataSourceType.SAP_S4HANA)
neo4j = Neo4jConnection()

# Connect to SAP
sap.connect()

# Fetch suppliers
raw_suppliers = sap.fetch_suppliers(filters={'limit': 100})

# Transform to validated models
suppliers = [
    map_to_supplier(data, DataSource.SAP_S4HANA)
    for data in raw_suppliers
]

# Load to Neo4j
for supplier in suppliers:
    query = """
        MERGE (s:Supplier {supplier_id: $supplier_id})
        SET s += $props
    """
    neo4j.execute_cypher(query, {
        'supplier_id': supplier.supplier_id,
        'props': supplier.to_neo4j_dict()
    })

# Disconnect
sap.disconnect()
neo4j.close()
```

### Example 2: Multi-Source Sync

```python
from src.sync.sync_manager import SyncManager

# Initialize sync manager (will create this in Phase 2)
sync_manager = SyncManager()

# Configure sources
sync_manager.add_source('sap', DataSourceType.SAP_S4HANA)
sync_manager.add_source('oracle', DataSourceType.ORACLE)

# Sync all entities from all sources
results = sync_manager.sync_all()

print(f"Synced {results['suppliers_count']} suppliers")
print(f"Synced {results['products_count']} products")
print(f"Synced {results['shipments_count']} shipments")
```

### Example 3: Real-time Monitoring

```python
# Check connection health
from src.connectors import ConnectorFactory

sap = ConnectorFactory.get_connector('sap')
oracle = ConnectorFactory.get_connector('oracle')

# Health check
sap_healthy = sap.test_connection()
oracle_healthy = oracle.test_connection()

# Get connection info
sap_info = sap.get_connection_info()
print(f"SAP last sync: {sap_info['last_sync_time']}")

oracle_info = oracle.get_connection_info()
print(f"Oracle last sync: {oracle_info['last_sync_time']}")
```

---

## 🔧 Troubleshooting

### SAP Connection Issues

**Problem**: `Failed to connect to SAP S/4HANA`

**Solutions**:
1. Verify SAP host is accessible: `ping your-sap-host.com`
2. Check SAP user has OData authorization (transaction `PFCG`)
3. Ensure OData services are activated (transaction `/IWFND/MAINT_SERVICE`)
4. Check network/firewall rules for port 443 (HTTPS)

**Problem**: `401 Unauthorized`

**Solutions**:
1. Verify username/password are correct
2. Check SAP client number (usually 100, 200, or 300)
3. Ensure user is not locked (transaction `SU01`)

### Oracle Connection Issues

**Problem**: `Failed to connect to Oracle`

**Solutions**:
1. Verify Oracle listener is running: `lsnrctl status`
2. Check TNS configuration (SERVICE_NAME or SID)
3. Test with SQL*Plus: `sqlplus user/password@host:port/service`
4. Ensure Oracle Instant Client is installed (for thick mode)

**Problem**: `ORA-12154: TNS:could not resolve the connect identifier`

**Solutions**:
1. Use SERVICE_NAME instead of SID (or vice versa)
2. Check `tnsnames.ora` file if using TNS names
3. Verify hostname resolution: `nslookup oracle-host.com`

### Data Mapping Issues

**Problem**: Missing or incorrect field mappings

**Solutions**:
1. Check field names in source system (case-sensitive)
2. Update mapper functions in `src/models/supply_chain_entities.py`
3. Add custom field mappings for your schema

**Problem**: Validation errors

**Solutions**:
1. Check Pydantic model constraints (e.g., reliability_score 0-1)
2. Handle null/missing values in source data
3. Add custom validators if needed

---

## 📚 Next Steps

1. **Implement ETL Pipeline** (Phase 2)
   - Automated sync scheduling
   - Incremental updates
   - Error handling and retry logic

2. **Add Monitoring Dashboard** (Phase 2)
   - Real-time sync status
   - Connection health indicators
   - Data quality metrics

3. **Optimize Performance** (Phase 3)
   - Parallel data fetching
   - Connection pooling
   - Caching frequently accessed data

4. **Add More Connectors** (Phase 3)
   - Microsoft Dynamics 365
   - Salesforce
   - REST APIs
   - Kafka streaming

---

## 📞 Support

For issues or questions:
- Check logs in `logs/supply_chain.log`
- Review connector source code in `src/connectors/`
- Consult SAP/Oracle documentation
- Open GitHub issue with error details

---

*Last updated: 2025-01-01*
