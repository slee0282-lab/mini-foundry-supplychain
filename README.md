# 🏗️ Mini Foundry Supply Chain Control Tower (Pilot)

> A 2-week proof-of-concept demonstrating **ontology-driven supply chain analytics**.
> Inspired by Palantir Foundry, built entirely with **open-source tools** (Neo4j, Python, Streamlit).

---

## 🎯 Executive Summary
Global supply chains are fragile. A single supplier delay can ripple across warehouses, products, and customers — leading to missed SLAs and millions in lost value.

**Palantir Foundry’s core “why”** is enabling organizations to **map their supply chain as an ontology**, simulate disruptions, and make better decisions.

This pilot project validates **80% of that value in 2 weeks**:
- **Data Integration**: Unify suppliers, products, warehouses, shipments.
- **Ontology Modeling**: Graph of entities & relationships in Neo4j.
- **Simulation**: Propagate supplier delays through the network.
- **Decision Support**: Streamlit dashboard showing SLA impact.

---

## 🔑 Problem Statement
- Supply chains lack visibility across multiple tiers.
- Delays at one supplier are hard to trace downstream.
- Stakeholders need an intuitive **“control tower” view**.

---

## 💡 Proposed Solution
1. **Ontology (Neo4j)** → Suppliers, Products, Warehouses, Customers, Shipments.
2. **Simulation Engine (Python)** → Delay Supplier X → calculate SLA drop %.
3. **Control Tower Dashboard (Streamlit)** → Graph visualization + KPIs.

This creates a **digital twin** of the supply chain to explore “what-if” scenarios.

---

## 📊 Success Metrics (End of Week 2 Pilot)
- ✅ Ontology graph correctly represents supply chain flow.
- ✅ Simulation shows disruption propagation (Supplier → Shipment → SLA).
- ✅ Dashboard allows stakeholder to test scenarios interactively.
- ✅ 80% of Palantir Foundry’s “why” validated (integration, ontology, analytics, visualization).

---

## 🚀 Roadmap (Post-Pilot)
- Week 3+: Add demand forecasting (ARIMA/LSTM).
- Week 4+: Add real-time pipelines (Apache NiFi / Kafka).
- Future: Role-based access control, integration with ERP/SCM systems.

---

## 🛠️ Tech Stack
- **Ontology & Graph**: Neo4j
- **Analytics**: Python (Pandas, NetworkX, Scikit-learn)
- **Visualization**: Streamlit
- **ETL (optional)**: Airbyte / NiFi

---

## 🎥 Demo Scenario
**Question:** What happens if Supplier S2 is delayed by 5 days?
- Ontology: `(Supplier)-[:SUPPLIES]->(Product)-[:STOCKED_AT]->(Warehouse)`
- Simulation: Shipment lead times updated.
- Dashboard: SLA drops by **12% in EU region**.

