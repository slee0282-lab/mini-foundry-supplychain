# Technical Implementation Examples & Code Snippets

## 🟢 Neo4j Cypher Implementation

### Database Setup & Constraints
```cypher
// Create unique constraints for all entity types
CREATE CONSTRAINT supplier_id ON (s:Supplier) ASSERT s.supplier_id IS UNIQUE;
CREATE CONSTRAINT product_id ON (p:Product) ASSERT p.product_id IS UNIQUE;
CREATE CONSTRAINT warehouse_id ON (w:Warehouse) ASSERT w.warehouse_id IS UNIQUE;
CREATE CONSTRAINT customer_id ON (c:Customer) ASSERT c.customer_id IS UNIQUE;
CREATE CONSTRAINT shipment_id ON (sh:Shipment) ASSERT sh.shipment_id IS UNIQUE;

// Create performance indexes
CREATE INDEX supplier_region ON :Supplier(region);
CREATE INDEX warehouse_region ON :Warehouse(region);
CREATE INDEX product_category ON :Product(category);
CREATE INDEX shipment_status ON :Shipment(status);
```

### Data Loading Scripts
```cypher
// Load suppliers from CSV
LOAD CSV WITH HEADERS FROM 'file:///suppliers.csv' AS row
MERGE (s:Supplier {supplier_id: row.supplier_id})
SET s.name = row.name,
    s.region = row.region,
    s.reliability_score = toFloat(row.reliability_score),
    s.avg_lead_time_days = toInteger(row.avg_lead_time_days);

// Load products from CSV
LOAD CSV WITH HEADERS FROM 'file:///products.csv' AS row
MERGE (p:Product {product_id: row.product_id})
SET p.product_name = row.product_name,
    p.category = row.category,
    p.safety_stock = toInteger(row.safety_stock),
    p.demand_forecast = toInteger(row.demand_forecast);

// Load warehouses from CSV
LOAD CSV WITH HEADERS FROM 'file:///warehouses.csv' AS row
MERGE (w:Warehouse {warehouse_id: row.warehouse_id})
SET w.location = row.location,
    w.capacity_units = toInteger(row.capacity_units),
    w.region = row.region;

// Load customers from CSV
LOAD CSV WITH HEADERS FROM 'file:///customers.csv' AS row
MERGE (c:Customer {customer_id: row.customer_id})
SET c.name = row.name,
    c.region = row.region,
    c.avg_demand_units = toInteger(row.avg_demand_units);

// Create relationships from shipments data
LOAD CSV WITH HEADERS FROM 'file:///shipments.csv' AS row
MATCH (s:Supplier {supplier_id: row.supplier_id})
MATCH (p:Product {product_id: row.product_id})
MATCH (w:Warehouse {warehouse_id: row.warehouse_id})
MERGE (s)-[:SUPPLIES {lead_time: toInteger(row.planned_lead_time_days)}]->(p)
MERGE (p)-[:STOCKED_AT {qty_available: toInteger(row.qty_units)}]->(w)
CREATE (sh:Shipment {
    shipment_id: row.shipment_id,
    qty_units: toInteger(row.qty_units),
    planned_lead_time_days: toInteger(row.planned_lead_time_days),
    status: row.status,
    created_date: date()
})
CREATE (s)-[:CREATES]->(sh)
CREATE (sh)-[:CONTAINS]->(p)
CREATE (sh)-[:DELIVERED_TO]->(w);
```

### Advanced Analytics Queries
```cypher
// Find critical path suppliers (highest impact if delayed)
MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)-[:STOCKED_AT]->(w:Warehouse)
WITH s, count(DISTINCT p) as products_supplied, count(DISTINCT w) as warehouses_served
WHERE products_supplied >= 3 AND warehouses_served >= 2
RETURN s.name, s.region, s.reliability_score, products_supplied, warehouses_served
ORDER BY (products_supplied * warehouses_served) DESC
LIMIT 10;

// Regional supply chain risk assessment
MATCH (s:Supplier)-[:CREATES]->(sh:Shipment)-[:DELIVERED_TO]->(w:Warehouse)
WITH w.region as region,
     count(sh) as total_shipments,
     count(CASE WHEN sh.status = 'Delayed' THEN 1 END) as delayed_shipments
RETURN region,
       total_shipments,
       delayed_shipments,
       round(100.0 * delayed_shipments / total_shipments, 2) as risk_percentage
ORDER BY risk_percentage DESC;
```

---

## 🟠 Python ETL & Simulation Engine

### Data Loading and Connection Setup
```python
import pandas as pd
import networkx as nx
from py2neo import Graph, Node, Relationship
import numpy as np
from datetime import datetime, timedelta

# Neo4j connection
def connect_to_neo4j():
    """Establish connection to Neo4j database"""
    graph = Graph("bolt://localhost:7687", auth=("neo4j", "password"))
    return graph

# Data loading functions
def load_csv_data():
    """Load all CSV files into pandas DataFrames"""
    data = {
        'suppliers': pd.read_csv("data/suppliers.csv"),
        'products': pd.read_csv("data/products.csv"),
        'warehouses': pd.read_csv("data/warehouses.csv"),
        'customers': pd.read_csv("data/customers.csv"),
        'shipments': pd.read_csv("data/shipments.csv")
    }
    return data

# Graph construction
def build_supply_chain_graph(data):
    """Build NetworkX graph from loaded data"""
    G = nx.DiGraph()

    # Add nodes
    for _, supplier in data['suppliers'].iterrows():
        G.add_node(supplier['supplier_id'],
                  node_type='supplier',
                  name=supplier['name'],
                  region=supplier['region'],
                  reliability=supplier['reliability_score'])

    for _, product in data['products'].iterrows():
        G.add_node(product['product_id'],
                  node_type='product',
                  name=product['product_name'],
                  category=product['category'],
                  demand=product['demand_forecast'])

    for _, warehouse in data['warehouses'].iterrows():
        G.add_node(warehouse['warehouse_id'],
                  node_type='warehouse',
                  location=warehouse['location'],
                  region=warehouse['region'],
                  capacity=warehouse['capacity_units'])

    # Add edges from shipments
    for _, shipment in data['shipments'].iterrows():
        # Supplier to Product
        G.add_edge(shipment['supplier_id'],
                  shipment['product_id'],
                  edge_type='supplies',
                  lead_time=shipment['planned_lead_time_days'],
                  quantity=shipment['qty_units'])

        # Product to Warehouse
        G.add_edge(shipment['product_id'],
                  shipment['warehouse_id'],
                  edge_type='stocked_at',
                  quantity=shipment['qty_units'])

    return G
```

### Disruption Simulation Engine
```python
class SupplyChainSimulator:
    def __init__(self, graph):
        self.graph = graph.copy()
        self.original_graph = graph.copy()
        self.simulation_results = {}

    def simulate_supplier_delay(self, supplier_id, delay_days):
        """Simulate delay propagation from a specific supplier"""
        affected_paths = []
        total_impact = 0

        # Find all paths starting from the delayed supplier
        for node in self.graph.successors(supplier_id):
            if self.graph.nodes[node]['node_type'] == 'product':
                for warehouse in self.graph.successors(node):
                    if self.graph.nodes[warehouse]['node_type'] == 'warehouse':
                        # Calculate impact on this path
                        original_lead_time = self.graph[supplier_id][node]['lead_time']
                        new_lead_time = original_lead_time + delay_days

                        # Update edge with new lead time
                        self.graph[supplier_id][node]['lead_time'] = new_lead_time

                        # Calculate business impact
                        quantity = self.graph[supplier_id][node]['quantity']
                        impact_score = self.calculate_sla_impact(new_lead_time, quantity)
                        total_impact += impact_score

                        affected_paths.append({
                            'supplier': supplier_id,
                            'product': node,
                            'warehouse': warehouse,
                            'original_lead_time': original_lead_time,
                            'new_lead_time': new_lead_time,
                            'quantity_affected': quantity,
                            'impact_score': impact_score
                        })

        self.simulation_results[supplier_id] = {
            'delay_days': delay_days,
            'affected_paths': affected_paths,
            'total_impact': total_impact,
            'timestamp': datetime.now()
        }

        return self.simulation_results[supplier_id]

    def calculate_sla_impact(self, lead_time, quantity):
        """Calculate SLA impact based on lead time and quantity"""
        # Simple impact calculation - can be enhanced with business rules
        if lead_time > 14:
            return quantity * 0.8  # High impact
        elif lead_time > 10:
            return quantity * 0.5  # Medium impact
        elif lead_time > 7:
            return quantity * 0.2  # Low impact
        else:
            return 0  # No impact

    def calculate_regional_sla_drop(self, region=None):
        """Calculate overall SLA drop percentage"""
        total_orders = 0
        delayed_orders = 0

        for supplier_id in self.graph.nodes():
            if self.graph.nodes[supplier_id]['node_type'] == 'supplier':
                if region and self.graph.nodes[supplier_id]['region'] != region:
                    continue

                for product in self.graph.successors(supplier_id):
                    edge_data = self.graph[supplier_id][product]
                    quantity = edge_data.get('quantity', 0)
                    lead_time = edge_data.get('lead_time', 0)

                    total_orders += quantity
                    if lead_time > 10:  # Assuming 10 days is SLA threshold
                        delayed_orders += quantity

        if total_orders == 0:
            return 0

        return round((delayed_orders / total_orders) * 100, 2)

    def reset_simulation(self):
        """Reset graph to original state"""
        self.graph = self.original_graph.copy()
        self.simulation_results = {}

# Usage example
def run_simulation_example():
    # Load data and build graph
    data = load_csv_data()
    G = build_supply_chain_graph(data)

    # Create simulator
    simulator = SupplyChainSimulator(G)

    # Simulate supplier delay
    results = simulator.simulate_supplier_delay('S2', 5)

    # Calculate regional impact
    apac_sla_drop = simulator.calculate_regional_sla_drop('APAC')

    print(f"Supplier S2 delayed by 5 days")
    print(f"APAC SLA drop: {apac_sla_drop}%")
    print(f"Total affected paths: {len(results['affected_paths'])}")

    return results
```

### Advanced Analytics Functions
```python
def calculate_supplier_risk_scores(graph):
    """Calculate risk scores for all suppliers"""
    risk_scores = {}

    for supplier_id in graph.nodes():
        if graph.nodes[supplier_id]['node_type'] == 'supplier':
            # Factors: reliability, number of products, centrality
            reliability = graph.nodes[supplier_id]['reliability']
            product_count = len(list(graph.successors(supplier_id)))
            centrality = nx.degree_centrality(graph)[supplier_id]

            # Risk score: lower reliability + higher centrality = higher risk
            risk_score = ((1 - reliability) * 0.5 + centrality * 0.5) * 100
            risk_scores[supplier_id] = {
                'supplier_id': supplier_id,
                'risk_score': round(risk_score, 2),
                'reliability': reliability,
                'product_count': product_count,
                'centrality': round(centrality, 3)
            }

    return sorted(risk_scores.values(), key=lambda x: x['risk_score'], reverse=True)

def identify_critical_paths(graph):
    """Identify most critical supply chain paths"""
    critical_paths = []

    # Find paths from suppliers to warehouses through products
    for supplier in graph.nodes():
        if graph.nodes[supplier]['node_type'] == 'supplier':
            for product in graph.successors(supplier):
                for warehouse in graph.successors(product):
                    path_data = {
                        'supplier': supplier,
                        'product': product,
                        'warehouse': warehouse,
                        'total_quantity': graph[supplier][product]['quantity'],
                        'lead_time': graph[supplier][product]['lead_time'],
                        'supplier_reliability': graph.nodes[supplier]['reliability']
                    }

                    # Criticality score: high quantity + low reliability + long lead time
                    criticality = (
                        path_data['total_quantity'] * 0.4 +
                        (1 - path_data['supplier_reliability']) * 1000 * 0.4 +
                        path_data['lead_time'] * 50 * 0.2
                    )
                    path_data['criticality_score'] = round(criticality, 2)
                    critical_paths.append(path_data)

    return sorted(critical_paths, key=lambda x: x['criticality_score'], reverse=True)[:10]
```

---

## 🔵 Streamlit Dashboard Implementation

### Main Dashboard Application
```python
import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Import our simulation functions
from supply_chain_simulator import SupplyChainSimulator, load_csv_data, build_supply_chain_graph

# Page configuration
st.set_page_config(
    page_title="Supply Chain Control Tower",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dashboard title
st.title("🚀 Mini Foundry Supply Chain Control Tower")
st.markdown("*Ontology-driven supply chain analytics and disruption simulation*")

# Sidebar controls
st.sidebar.header("🎛️ Simulation Controls")

@st.cache_data
def load_and_process_data():
    """Load data and create graph (cached for performance)"""
    data = load_csv_data()
    graph = build_supply_chain_graph(data)
    return data, graph

# Load data
try:
    data, G = load_and_process_data()
    simulator = SupplyChainSimulator(G)

    # Sidebar inputs
    supplier_options = [node for node in G.nodes() if G.nodes[node]['node_type'] == 'supplier']
    selected_supplier = st.sidebar.selectbox("Select Supplier to Delay", supplier_options)
    delay_days = st.sidebar.slider("Delay Duration (days)", 1, 21, 5)

    # Simulation trigger
    if st.sidebar.button("🔴 Simulate Disruption", type="primary"):
        # Run simulation
        results = simulator.simulate_supplier_delay(selected_supplier, delay_days)
        st.session_state['simulation_results'] = results
        st.session_state['simulator'] = simulator

    # Reset button
    if st.sidebar.button("🔄 Reset Simulation"):
        simulator.reset_simulation()
        if 'simulation_results' in st.session_state:
            del st.session_state['simulation_results']

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📊 Supply Chain Network")

        # Create network visualization
        fig, ax = plt.subplots(figsize=(12, 8))

        # Position nodes using spring layout
        pos = nx.spring_layout(G, seed=42, k=3, iterations=50)

        # Color nodes by type
        node_colors = []
        node_sizes = []
        for node in G.nodes():
            if G.nodes[node]['node_type'] == 'supplier':
                node_colors.append('lightblue')
                node_sizes.append(800)
            elif G.nodes[node]['node_type'] == 'product':
                node_colors.append('lightgreen')
                node_sizes.append(600)
            elif G.nodes[node]['node_type'] == 'warehouse':
                node_colors.append('orange')
                node_sizes.append(700)

        # Draw the network
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, ax=ax)
        nx.draw_networkx_labels(G, pos, font_size=8, ax=ax)
        nx.draw_networkx_edges(G, pos, alpha=0.6, arrows=True, arrowsize=20, ax=ax)

        # Highlight selected supplier if simulation is running
        if 'simulation_results' in st.session_state:
            supplier_pos = pos[selected_supplier]
            ax.scatter([supplier_pos[0]], [supplier_pos[1]], s=1000, c='red', alpha=0.7, marker='o')

        ax.set_title("Supply Chain Network Graph", fontsize=14, fontweight='bold')
        ax.axis('off')
        st.pyplot(fig)

    with col2:
        st.subheader("📈 Key Performance Indicators")

        # Calculate baseline metrics
        total_suppliers = len([n for n in G.nodes() if G.nodes[n]['node_type'] == 'supplier'])
        total_products = len([n for n in G.nodes() if G.nodes[n]['node_type'] == 'product'])
        total_warehouses = len([n for n in G.nodes() if G.nodes[n]['node_type'] == 'warehouse'])

        # Display basic metrics
        st.metric("Total Suppliers", total_suppliers)
        st.metric("Total Products", total_products)
        st.metric("Total Warehouses", total_warehouses)

        # Show simulation results if available
        if 'simulation_results' in st.session_state:
            results = st.session_state['simulation_results']
            simulator = st.session_state['simulator']

            st.markdown("---")
            st.subheader("🔥 Disruption Impact")

            # Calculate SLA impact
            sla_drop = simulator.calculate_regional_sla_drop()
            affected_paths = len(results['affected_paths'])
            total_impact = results['total_impact']

            st.metric("SLA Impact", f"{sla_drop}%", delta=f"-{sla_drop}%")
            st.metric("Affected Paths", affected_paths)
            st.metric("Impact Score", f"{total_impact:.0f}")

            # Show affected paths details
            if results['affected_paths']:
                st.markdown("**Affected Supply Paths:**")
                for path in results['affected_paths'][:5]:  # Show top 5
                    st.markdown(f"• {path['product']} → {path['warehouse']} (+{path['new_lead_time'] - path['original_lead_time']} days)")

    # Bottom section: Detailed Analytics
    st.markdown("---")
    st.subheader("🔍 Advanced Analytics")

    tab1, tab2, tab3 = st.tabs(["📊 Supplier Risk Analysis", "🛣️ Critical Paths", "🌐 Regional Overview"])

    with tab1:
        # Calculate and display supplier risk scores
        from supply_chain_simulator import calculate_supplier_risk_scores
        risk_scores = calculate_supplier_risk_scores(G)

        risk_df = pd.DataFrame(risk_scores)
        st.dataframe(risk_df, use_container_width=True)

        # Risk score chart
        fig = px.bar(risk_df.head(10), x='supplier_id', y='risk_score',
                    title="Top 10 Highest Risk Suppliers")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # Show critical supply chain paths
        from supply_chain_simulator import identify_critical_paths
        critical_paths = identify_critical_paths(G)

        critical_df = pd.DataFrame(critical_paths)
        st.dataframe(critical_df, use_container_width=True)

    with tab3:
        # Regional analysis
        regions = set(G.nodes[n]['region'] for n in G.nodes() if 'region' in G.nodes[n])
        regional_data = []

        for region in regions:
            suppliers = len([n for n in G.nodes() if G.nodes[n].get('node_type') == 'supplier' and G.nodes[n].get('region') == region])
            warehouses = len([n for n in G.nodes() if G.nodes[n].get('node_type') == 'warehouse' and G.nodes[n].get('region') == region])
            regional_data.append({
                'Region': region,
                'Suppliers': suppliers,
                'Warehouses': warehouses
            })

        regional_df = pd.DataFrame(regional_data)

        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(regional_df, values='Suppliers', names='Region', title="Suppliers by Region")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.pie(regional_df, values='Warehouses', names='Region', title="Warehouses by Region")
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.info("Please ensure data files are in the correct location and Neo4j is running.")

# Footer
st.markdown("---")
st.markdown("*Built with Streamlit • Powered by Neo4j and NetworkX*")
```

### Performance Optimization
```python
# Caching strategies for better performance
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_graph_data():
    """Load and cache graph data"""
    return load_csv_data(), build_supply_chain_graph()

@st.cache_data
def calculate_network_metrics(graph_data):
    """Calculate and cache expensive network metrics"""
    G = graph_data
    return {
        'density': nx.density(G),
        'average_clustering': nx.average_clustering(G.to_undirected()),
        'diameter': nx.diameter(G.to_undirected()) if nx.is_connected(G.to_undirected()) else "N/A"
    }
```

This implementation provides a complete working example of the supply chain digital twin with all core functionality for disruption simulation and visualization.