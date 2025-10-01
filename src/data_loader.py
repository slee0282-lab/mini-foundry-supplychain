"""
Data Loader Module for Supply Chain Ontology

Handles CSV data loading, Neo4j connectivity, and data validation.
"""

import os
import pandas as pd
import logging
from typing import Dict, List, Optional, Any
from py2neo import Graph, Node, Relationship
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import datetime
import traceback

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def get_env_or_secret(key: str, default: str = None) -> str:
    """Get value from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return os.getenv(key, default)


class Neo4jConnection:
    """Manages Neo4j database connections and operations."""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or get_env_or_secret('NEO4J_URI', 'bolt://localhost:7687')
        self.user = user or get_env_or_secret('NEO4J_USER', 'neo4j')
        self.password = password or get_env_or_secret('NEO4J_PASSWORD', 'password')

        # Debug logging
        logger.info(f"Neo4j connection config: URI={self.uri}, USER={self.user}")

        self.driver = None
        self.graph = None
        self._connect()

    def _connect(self):
        """Establish connection to Neo4j database."""
        try:
            # Connect with neo4j driver
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )

            # Connect with py2neo for easier operations (only for local/non-Aura)
            if not self.uri.startswith('neo4j+s://'):
                try:
                    self.graph = Graph(self.uri, auth=(self.user, self.password))
                except:
                    self.graph = None
                    logger.warning("py2neo connection failed, using driver only")
            else:
                self.graph = None
                logger.info("Using Neo4j driver only (Aura mode)")

            # Test connection
            self.driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j at {self.uri}")

        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise

    def close(self):
        """Close database connections."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def execute_cypher(self, query: str, parameters: Dict = None) -> List[Dict]:
        """Execute a Cypher query and return results."""
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Error executing Cypher query: {str(e)}")
            logger.error(f"Query: {query}")
            raise

    def execute_cypher_file(self, file_path: str) -> bool:
        """Execute Cypher queries from a file."""
        try:
            with open(file_path, 'r') as file:
                content = file.read()

            # Split by semicolon and execute each query
            queries = [q.strip() for q in content.split(';') if q.strip()]

            for query in queries:
                if query and not query.startswith('//'):  # Skip comments
                    self.execute_cypher(query)

            logger.info(f"Successfully executed queries from {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error executing Cypher file {file_path}: {str(e)}")
            return False

    def clear_database(self) -> bool:
        """Clear all data from the database (use with caution)."""
        try:
            self.execute_cypher("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing database: {str(e)}")
            return False


class DataLoader:
    """Loads CSV data into Neo4j and manages data operations."""

    def __init__(self, neo4j_connection: Neo4jConnection = None):
        self.neo4j = neo4j_connection or Neo4jConnection()
        self.data_path = get_env_or_secret('DATA_PATH', './data')
        self.csv_files = {
            'suppliers': 'suppliers.csv',
            'products': 'products.csv',
            'warehouses': 'warehouses.csv',
            'customers': 'customers.csv',
            'shipments': 'shipments.csv'
        }

    def validate_csv_files(self) -> Dict[str, bool]:
        """Validate that all required CSV files exist."""
        validation_results = {}

        for name, filename in self.csv_files.items():
            file_path = os.path.join(self.data_path, filename)
            exists = os.path.exists(file_path)
            validation_results[name] = exists

            if exists:
                logger.info(f"✓ Found {filename}")
            else:
                logger.warning(f"✗ Missing {filename}")

        return validation_results

    def load_csv_data(self) -> Dict[str, pd.DataFrame]:
        """Load all CSV files into pandas DataFrames."""
        data = {}

        for name, filename in self.csv_files.items():
            file_path = os.path.join(self.data_path, filename)

            try:
                df = pd.read_csv(file_path)
                data[name] = df
                logger.info(f"Loaded {filename}: {len(df)} records")

            except Exception as e:
                logger.error(f"Error loading {filename}: {str(e)}")
                raise

        return data

    def validate_data_integrity(self, data: Dict[str, pd.DataFrame]) -> Dict[str, List[str]]:
        """Validate data integrity and relationships."""
        issues = {
            'suppliers': [],
            'products': [],
            'warehouses': [],
            'customers': [],
            'shipments': []
        }

        # Check for required columns
        required_columns = {
            'suppliers': ['supplier_id', 'name', 'region', 'reliability_score'],
            'products': ['product_id', 'product_name', 'category'],
            'warehouses': ['warehouse_id', 'location', 'region'],
            'customers': ['customer_id', 'name', 'region'],
            'shipments': ['shipment_id', 'supplier_id', 'product_id', 'warehouse_id']
        }

        for table, columns in required_columns.items():
            if table in data:
                missing_cols = set(columns) - set(data[table].columns)
                if missing_cols:
                    issues[table].append(f"Missing columns: {missing_cols}")

        # Check for referential integrity in shipments
        if all(table in data for table in ['shipments', 'suppliers', 'products', 'warehouses']):
            shipments = data['shipments']

            # Check supplier references
            invalid_suppliers = set(shipments['supplier_id']) - set(data['suppliers']['supplier_id'])
            if invalid_suppliers:
                issues['shipments'].append(f"Invalid supplier IDs: {invalid_suppliers}")

            # Check product references
            invalid_products = set(shipments['product_id']) - set(data['products']['product_id'])
            if invalid_products:
                issues['shipments'].append(f"Invalid product IDs: {invalid_products}")

            # Check warehouse references
            invalid_warehouses = set(shipments['warehouse_id']) - set(data['warehouses']['warehouse_id'])
            if invalid_warehouses:
                issues['shipments'].append(f"Invalid warehouse IDs: {invalid_warehouses}")

        return issues

    def setup_database_schema(self) -> bool:
        """Set up Neo4j constraints and indexes."""
        try:
            constraints_file = os.path.join('neo4j', 'constraints.cypher')
            if os.path.exists(constraints_file):
                return self.neo4j.execute_cypher_file(constraints_file)
            else:
                logger.warning(f"Constraints file not found: {constraints_file}")
                return False
        except Exception as e:
            logger.error(f"Error setting up database schema: {str(e)}")
            return False

    def load_data_to_neo4j(self, data: Dict[str, pd.DataFrame] = None) -> bool:
        """Load CSV data into Neo4j database."""
        try:
            if data is None:
                data = self.load_csv_data()

            # Validate data first
            issues = self.validate_data_integrity(data)
            for table, table_issues in issues.items():
                if table_issues:
                    logger.warning(f"Data issues in {table}: {table_issues}")

            # Load data using Cypher script
            load_script = os.path.join('neo4j', 'load_data.cypher')
            if os.path.exists(load_script):
                # Copy CSV files to Neo4j import directory if needed
                self._prepare_csv_for_import()

                success = self.neo4j.execute_cypher_file(load_script)
                if success:
                    logger.info("Data loaded successfully into Neo4j")
                    self._log_database_stats()
                return success
            else:
                logger.error(f"Load script not found: {load_script}")
                return False

        except Exception as e:
            logger.error(f"Error loading data to Neo4j: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _prepare_csv_for_import(self):
        """Prepare CSV files for Neo4j import."""
        # Note: This is a simplified version
        # In production, you might need to copy files to Neo4j import directory
        logger.info("CSV files prepared for import")

    def _log_database_stats(self):
        """Log statistics about loaded data."""
        stats_queries = {
            'Suppliers': 'MATCH (s:Supplier) RETURN count(s) as count',
            'Products': 'MATCH (p:Product) RETURN count(p) as count',
            'Warehouses': 'MATCH (w:Warehouse) RETURN count(w) as count',
            'Customers': 'MATCH (c:Customer) RETURN count(c) as count',
            'Shipments': 'MATCH (sh:Shipment) RETURN count(sh) as count',
        }

        logger.info("=== Database Statistics ===")
        for entity, query in stats_queries.items():
            try:
                result = self.neo4j.execute_cypher(query)
                count = result[0]['count'] if result else 0
                logger.info(f"{entity}: {count}")
            except Exception as e:
                logger.error(f"Error getting {entity} count: {str(e)}")

    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        stats = {}
        stats_queries = {
            'suppliers': 'MATCH (s:Supplier) RETURN count(s) as count',
            'products': 'MATCH (p:Product) RETURN count(p) as count',
            'warehouses': 'MATCH (w:Warehouse) RETURN count(w) as count',
            'customers': 'MATCH (c:Customer) RETURN count(c) as count',
            'shipments': 'MATCH (sh:Shipment) RETURN count(sh) as count',
            'supplies_relationships': 'MATCH ()-[r:SUPPLIES]-() RETURN count(r) as count',
            'stocked_relationships': 'MATCH ()-[r:STOCKED_AT]-() RETURN count(r) as count',
        }

        for name, query in stats_queries.items():
            try:
                result = self.neo4j.execute_cypher(query)
                stats[name] = result[0]['count'] if result else 0
            except Exception as e:
                logger.error(f"Error getting {name} stats: {str(e)}")
                stats[name] = 0

        return stats

    def export_to_dataframes(self) -> Dict[str, pd.DataFrame]:
        """Export Neo4j data back to pandas DataFrames."""
        export_queries = {
            'suppliers': """
                MATCH (s:Supplier)
                RETURN s.supplier_id as supplier_id, s.name as name,
                       s.region as region, s.reliability_score as reliability_score,
                       s.avg_lead_time_days as avg_lead_time_days
            """,
            'products': """
                MATCH (p:Product)
                RETURN p.product_id as product_id, p.product_name as product_name,
                       p.category as category, p.safety_stock as safety_stock,
                       p.demand_forecast as demand_forecast
            """,
            'warehouses': """
                MATCH (w:Warehouse)
                RETURN w.warehouse_id as warehouse_id, w.location as location,
                       w.region as region, w.capacity_units as capacity_units
            """,
            'supply_relationships': """
                MATCH (s:Supplier)-[r:SUPPLIES]->(p:Product)
                RETURN s.supplier_id as supplier_id, p.product_id as product_id,
                       r.lead_time_days as lead_time_days, r.reliability as reliability
            """
        }

        dataframes = {}
        for name, query in export_queries.items():
            try:
                result = self.neo4j.execute_cypher(query)
                dataframes[name] = pd.DataFrame(result)
                logger.info(f"Exported {name}: {len(result)} records")
            except Exception as e:
                logger.error(f"Error exporting {name}: {str(e)}")
                dataframes[name] = pd.DataFrame()

        return dataframes


def main():
    """Main function for testing data loading."""
    logging.basicConfig(level=logging.INFO)

    try:
        # Initialize data loader
        loader = DataLoader()

        # Validate CSV files
        logger.info("=== Validating CSV Files ===")
        validation = loader.validate_csv_files()
        all_valid = all(validation.values())

        if not all_valid:
            logger.error("Some CSV files are missing. Please check the data directory.")
            return False

        # Load and validate data
        logger.info("=== Loading CSV Data ===")
        data = loader.load_csv_data()

        logger.info("=== Validating Data Integrity ===")
        issues = loader.validate_data_integrity(data)

        # Setup database schema
        logger.info("=== Setting up Database Schema ===")
        schema_success = loader.setup_database_schema()

        if not schema_success:
            logger.error("Failed to setup database schema")
            return False

        # Load data to Neo4j
        logger.info("=== Loading Data to Neo4j ===")
        load_success = loader.load_data_to_neo4j(data)

        if load_success:
            logger.info("✓ Data loading completed successfully!")
            return True
        else:
            logger.error("✗ Data loading failed")
            return False

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        logger.error(traceback.format_exc())
        return False
    finally:
        if 'loader' in locals():
            loader.neo4j.close()


if __name__ == "__main__":
    main()