# Project Structure & Setup Guide

## 📂 Repository Structure

```
mini-foundry-supplychain/
│
├── README.md                    # Project overview and setup instructions
├── requirements.txt             # Python dependencies
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore file
│
├── data/                       # Mock datasets (CSV files)
│   ├── suppliers.csv
│   ├── products.csv
│   ├── warehouses.csv
│   ├── customers.csv
│   └── shipments.csv
│
├── neo4j/                      # Neo4j database scripts
│   ├── constraints.cypher      # Database constraints
│   ├── load_data.cypher       # Data import scripts
│   └── queries.cypher         # Common query library
│
├── src/                        # Python source code
│   ├── __init__.py
│   ├── data_loader.py         # CSV loading functions
│   ├── graph_builder.py       # NetworkX graph construction
│   ├── simulator.py           # Disruption simulation engine
│   ├── analytics.py           # Advanced analytics functions
│   └── utils.py               # Utility functions
│
├── dashboard/                  # Streamlit application
│   ├── app.py                 # Main dashboard application
│   ├── components/            # Dashboard components
│   │   ├── __init__.py
│   │   ├── network_viz.py     # Network visualization
│   │   ├── kpi_cards.py       # KPI display components
│   │   └── simulation_panel.py # Simulation control panel
│   └── assets/                # Static assets (images, styles)
│       └── style.css
│
├── notebooks/                  # Jupyter notebooks for analysis
│   ├── data_exploration.ipynb # Initial data exploration
│   ├── ontology_analysis.ipynb # Graph analysis
│   └── simulation_testing.ipynb # Simulation validation
│
├── tests/                      # Unit tests
│   ├── __init__.py
│   ├── test_data_loader.py
│   ├── test_simulator.py
│   └── test_analytics.py
│
├── docs/                       # Additional documentation
│   ├── api_reference.md
│   ├── user_guide.md
│   └── deployment.md
│
└── scripts/                    # Utility scripts
    ├── setup_neo4j.py         # Neo4j setup automation
    ├── generate_mock_data.py   # Mock data generation
    └── run_tests.py           # Test runner
```

---

## 🚀 Quick Start Setup

### Prerequisites
- **Python 3.8+** with pip
- **Neo4j Desktop** (recommended) or Docker
- **Git** for version control
- **8GB RAM** minimum (16GB recommended)

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/mini-foundry-supplychain.git
cd mini-foundry-supplychain
```

### 2. Python Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Neo4j Database Setup

#### Option A: Neo4j Desktop (Recommended)
1. Download and install [Neo4j Desktop](https://neo4j.com/download/)
2. Create a new project
3. Create a new database with password
4. Start the database
5. Note the connection details (typically `bolt://localhost:7687`)

#### Option B: Docker
```bash
docker run \
    --name neo4j-supplychain \
    -p7474:7474 -p7687:7687 \
    -d \
    -v $HOME/neo4j/data:/data \
    -v $HOME/neo4j/logs:/logs \
    -v $HOME/neo4j/import:/var/lib/neo4j/import \
    -v $HOME/neo4j/plugins:/plugins \
    --env NEO4J_AUTH=neo4j/password \
    neo4j:latest
```

### 4. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### 5. Initialize Database
```bash
# Run setup script
python scripts/setup_neo4j.py

# Or manually in Neo4j Browser:
# Load each .cypher file from neo4j/ directory
```

### 6. Load Sample Data
```bash
# Generate mock data (if not provided)
python scripts/generate_mock_data.py

# Load data into Neo4j
python src/data_loader.py
```

### 7. Launch Dashboard
```bash
# Navigate to dashboard directory
cd dashboard

# Run Streamlit app
streamlit run app.py
```

---

## 📋 Requirements.txt
```txt
# Core data processing
pandas>=1.5.0
numpy>=1.21.0
networkx>=2.8.0

# Neo4j connectivity
py2neo>=2021.2.3
neo4j>=5.0.0

# Visualization and dashboard
streamlit>=1.25.0
matplotlib>=3.5.0
plotly>=5.15.0
seaborn>=0.11.0

# Machine learning and analytics
scikit-learn>=1.1.0
scipy>=1.9.0

# Jupyter notebooks
jupyter>=1.0.0
notebook>=6.4.0

# Testing
pytest>=7.0.0
pytest-cov>=3.0.0

# Development tools
black>=22.0.0
flake8>=5.0.0
pre-commit>=2.20.0

# Environment management
python-dotenv>=0.19.0

# Date and time handling
python-dateutil>=2.8.0
```

---

## 📄 Complete README.md Template

```markdown
# Mini Foundry Supply Chain Control Tower

🚀 **A lightweight open-source prototype inspired by Palantir Foundry**
Demonstrates ontology-driven supply chain analytics and disruption simulation in 2 weeks.

![Dashboard Screenshot](docs/screenshots/dashboard.png)

---

## 🎯 Project Overview

This project builds a **supply chain digital twin** that:
- Integrates supply chain data from multiple sources
- Models relationships using graph databases (Neo4j)
- Simulates disruption scenarios and impact propagation
- Provides interactive dashboards for decision-making

**Demo Scenario**: "Delay Supplier A by 5 days → APAC delivery SLA drops by 12%"

---

## 🏗️ Architecture

```
Streamlit Dashboard  ←→  Python Analytics  ←→  Neo4j Graph DB  ←  CSV Data
```

- **Data Layer**: CSV files → Neo4j graph database
- **Ontology Layer**: Suppliers, Products, Warehouses, Customers
- **Analytics Layer**: Python + NetworkX for simulation
- **Visualization**: Streamlit interactive dashboard

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.8+, Neo4j Desktop, 8GB RAM

### 2. Setup
```bash
# Clone and setup
git clone https://github.com/yourusername/mini-foundry-supplychain.git
cd mini-foundry-supplychain
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure Neo4j
cp .env.example .env
# Edit .env with your Neo4j credentials

# Initialize database
python scripts/setup_neo4j.py
python src/data_loader.py

# Launch dashboard
cd dashboard && streamlit run app.py
```

### 3. Access
- **Dashboard**: http://localhost:8501
- **Neo4j Browser**: http://localhost:7474

---

## 📊 Demo Use Case

1. **Select Supplier**: Choose supplier from dropdown
2. **Set Delay**: Adjust delay duration (1-21 days)
3. **Simulate**: Click "Simulate Disruption"
4. **View Impact**: See SLA drops, affected paths, regional impact

**Example Result**: 5-day delay in "MedGlobal" → 14% SLA drop in EU region

---

## 📁 Repository Structure

- `data/` → Mock CSV datasets
- `neo4j/` → Database scripts (Cypher queries)
- `src/` → Python simulation engine
- `dashboard/` → Streamlit application
- `notebooks/` → Jupyter analysis notebooks

---

## 🔧 Tech Stack

- **Database**: Neo4j (graph ontology)
- **Analytics**: Python + Pandas + NetworkX
- **Visualization**: Streamlit + Plotly + Matplotlib
- **Data**: CSV files (suppliers, products, warehouses, shipments)

---

## 📈 Key Features

### ✅ Completed (MVP)
- [x] Graph-based supply chain ontology
- [x] Disruption simulation engine
- [x] Interactive dashboard with KPIs
- [x] Regional impact analysis
- [x] Supplier risk scoring

### 🚀 Future Enhancements
- [ ] Real-time data integration (Kafka, APIs)
- [ ] ML-based demand forecasting
- [ ] Advanced optimization algorithms
- [ ] Multi-user authentication
- [ ] API endpoints for integration

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=src/

# Test specific component
python -m pytest tests/test_simulator.py -v
```

---

## 📚 Documentation

- [Technical Architecture](docs/architecture.md)
- [API Reference](docs/api_reference.md)
- [User Guide](docs/user_guide.md)
- [Deployment Guide](docs/deployment.md)

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

---

## 🙏 Acknowledgments

- Inspired by **Palantir Foundry's** ontology-driven approach
- Built with open-source tools: Neo4j, Python, Streamlit
- Mock data generation using realistic supply chain patterns

---

## 📞 Contact

**Project Maintainer**: Your Name
**Email**: your.email@example.com
**LinkedIn**: [Your Profile](https://linkedin.com/in/yourprofile)

---

*⭐ Star this repo if you find it helpful!*
```

---

## 🔧 Development Scripts

### setup_neo4j.py
```python
#!/usr/bin/env python3
"""
Neo4j database setup and configuration script
"""
import os
from py2neo import Graph
from dotenv import load_dotenv

load_dotenv()

def setup_neo4j():
    """Setup Neo4j database with constraints and indexes"""
    # Connect to Neo4j
    graph = Graph(
        os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        auth=(
            os.getenv('NEO4J_USER', 'neo4j'),
            os.getenv('NEO4J_PASSWORD', 'password')
        )
    )

    # Read and execute constraint file
    with open('neo4j/constraints.cypher', 'r') as f:
        constraints = f.read().split(';')
        for constraint in constraints:
            if constraint.strip():
                try:
                    graph.run(constraint)
                    print(f"✅ Executed: {constraint.strip()[:50]}...")
                except Exception as e:
                    print(f"❌ Failed: {constraint.strip()[:50]}... - {str(e)}")

    print("🎉 Neo4j setup complete!")

if __name__ == "__main__":
    setup_neo4j()
```

### generate_mock_data.py
```python
#!/usr/bin/env python3
"""
Generate realistic mock data for supply chain simulation
"""
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def generate_suppliers(n=25):
    """Generate suppliers dataset"""
    regions = ['APAC', 'EU', 'NA']
    companies = ['BioChemCo', 'MedGlobal', 'PharmaLink', 'SupplyMax', 'ChemCore']

    data = []
    for i in range(n):
        data.append({
            'supplier_id': f'S{i+1:02d}',
            'name': f"{random.choice(companies)}-{i+1:02d}",
            'region': np.random.choice(regions, p=[0.4, 0.35, 0.25]),
            'reliability_score': max(0.5, min(0.99, np.random.normal(0.85, 0.12))),
            'avg_lead_time_days': max(3, int(np.random.lognormal(2, 0.5)))
        })

    return pd.DataFrame(data)

def generate_mock_datasets():
    """Generate all mock datasets"""
    # Generate data
    suppliers_df = generate_suppliers(25)
    # ... (add other generation functions)

    # Save to CSV
    suppliers_df.to_csv('data/suppliers.csv', index=False)
    print("✅ Mock data generated successfully!")

if __name__ == "__main__":
    generate_mock_datasets()
```

---

## 🐳 Docker Configuration

### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Set environment variables
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Run dashboard
CMD ["streamlit", "run", "dashboard/app.py"]
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:latest
    container_name: neo4j-supplychain
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - neo4j_data:/data
      - ./data:/var/lib/neo4j/import

  app:
    build: .
    container_name: supply-chain-app
    ports:
      - "8501:8501"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
    depends_on:
      - neo4j
    volumes:
      - ./data:/app/data

volumes:
  neo4j_data:
```

This comprehensive setup guide provides everything needed to get the project running locally or in containerized environments.