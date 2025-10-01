#!/usr/bin/env python3
"""
Neo4j Setup and Data Loading Script

Automates the setup of Neo4j database with constraints, indexes, and data loading.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from data_loader import DataLoader, Neo4jConnection
from utils import setup_logging, Timer

logger = setup_logging()


def main():
    """Main setup function."""
    logger.info("🚀 Starting Neo4j Setup and Data Loading")

    try:
        # Initialize data loader
        logger.info("Initializing data loader...")
        loader = DataLoader()

        # Test Neo4j connection
        logger.info("Testing Neo4j connection...")
        with Timer("Neo4j connection test"):
            loader.neo4j.execute_cypher("MATCH (n) RETURN count(n) as count LIMIT 1")
        logger.info("✅ Neo4j connection successful")

        # Validate CSV files
        logger.info("Validating CSV files...")
        validation = loader.validate_csv_files()
        missing_files = [name for name, exists in validation.items() if not exists]

        if missing_files:
            logger.error(f"❌ Missing CSV files: {missing_files}")
            logger.info("Please ensure all CSV files are in the data/ directory:")
            for name in missing_files:
                logger.info(f"  - {loader.csv_files[name]}")
            return False

        logger.info("✅ All CSV files found")

        # Load and validate data
        logger.info("Loading CSV data...")
        with Timer("CSV data loading"):
            data = loader.load_csv_data()

        logger.info("Validating data integrity...")
        issues = loader.validate_data_integrity(data)
        has_issues = any(table_issues for table_issues in issues.values())

        if has_issues:
            logger.warning("⚠️ Data integrity issues found:")
            for table, table_issues in issues.items():
                if table_issues:
                    logger.warning(f"  {table}: {table_issues}")
        else:
            logger.info("✅ Data integrity validation passed")

        # Setup database schema
        logger.info("Setting up database schema...")
        with Timer("Database schema setup"):
            schema_success = loader.setup_database_schema()

        if not schema_success:
            logger.error("❌ Failed to setup database schema")
            return False

        logger.info("✅ Database schema setup completed")

        # Load data to Neo4j
        logger.info("Loading data to Neo4j...")
        with Timer("Data loading to Neo4j"):
            load_success = loader.load_data_to_neo4j(data)

        if not load_success:
            logger.error("❌ Failed to load data to Neo4j")
            return False

        logger.info("✅ Data loading completed successfully")

        # Get final statistics
        stats = loader.get_database_stats()
        logger.info("📊 Final Database Statistics:")
        for entity, count in stats.items():
            logger.info(f"  {entity}: {count}")

        logger.info("🎉 Neo4j setup and data loading completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run the dashboard: python main.py")
        logger.info("2. Or directly: streamlit run dashboard/app.py")
        logger.info("3. Open your browser to: http://localhost:8501")

        return True

    except Exception as e:
        logger.error(f"❌ Setup failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        if 'loader' in locals():
            loader.neo4j.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)