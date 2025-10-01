"""
Oracle Database Connector

Implements connection to Oracle databases using oracledb (cx_Oracle successor).
Supports both thick and thin modes.
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime
import oracledb
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from .base_connector import BaseConnector, ConnectionConfig, DataSourceType

logger = logging.getLogger(__name__)


class OracleConnector(BaseConnector):
    """Oracle Database connector using oracledb and SQLAlchemy."""

    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.engine = None
        self.session_maker = None

        # Build connection string
        if config.service_name:
            # Service name connection
            self.dsn = oracledb.makedsn(
                config.host,
                config.port or 1521,
                service_name=config.service_name
            )
        else:
            # SID connection
            self.dsn = oracledb.makedsn(
                config.host,
                config.port or 1521,
                sid=config.database
            )

        # SQLAlchemy connection string
        self.connection_string = (
            f"oracle+oracledb://{config.username}:{config.password}@{self.dsn}"
        )

    def connect(self) -> bool:
        """Establish connection to Oracle database."""
        try:
            # Create SQLAlchemy engine with connection pooling
            self.engine = create_engine(
                self.connection_string,
                poolclass=QueuePool,
                pool_size=self.config.connection_pool_size,
                max_overflow=10,
                pool_timeout=self.config.connection_timeout,
                echo=False,  # Set to True for SQL logging
            )

            # Create session maker
            self.session_maker = sessionmaker(bind=self.engine)

            # Test connection
            if self.test_connection():
                self.is_connected = True
                self.logger.info(f"Successfully connected to Oracle at {self.config.host}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to connect to Oracle: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """Close Oracle connection."""
        try:
            if self.engine:
                self.engine.dispose()
                self.engine = None
            self.session_maker = None
            self.is_connected = False
            self.logger.info("Disconnected from Oracle")
            return True
        except Exception as e:
            self.logger.error(f"Error disconnecting from Oracle: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """Test Oracle connection."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1 FROM DUAL"))
                return result.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def _execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute SQL query and return results as list of dictionaries.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of row dictionaries
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to Oracle. Call connect() first.")

        try:
            with self.engine.connect() as conn:
                result = self._retry_operation(
                    conn.execute,
                    text(query),
                    params or {}
                )

                # Convert rows to dictionaries
                columns = result.keys()
                rows = [dict(zip(columns, row)) for row in result.fetchall()]

                return rows

        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            raise

    def fetch_suppliers(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch supplier data from Oracle.

        Assumes a SUPPLIERS table with standard columns.
        Customize table/column names based on your schema.
        """
        try:
            # Build query - customize based on your Oracle schema
            query = """
                SELECT
                    SUPPLIER_ID,
                    SUPPLIER_NAME,
                    REGION,
                    COUNTRY,
                    RELIABILITY_SCORE,
                    AVG_LEAD_TIME_DAYS,
                    LAST_UPDATED
                FROM SUPPLIERS
                WHERE 1=1
            """

            params = {}

            # Add filters if specified
            if filters:
                if 'region' in filters:
                    query += " AND REGION = :region"
                    params['region'] = filters['region']

                if 'limit' in filters:
                    query += f" AND ROWNUM <= :limit"
                    params['limit'] = filters['limit']
                else:
                    query += " AND ROWNUM <= 1000"

            results = self._execute_query(query, params)

            # Transform to standard format
            suppliers = []
            for row in results:
                supplier = {
                    'supplier_id': row.get('SUPPLIER_ID'),
                    'name': row.get('SUPPLIER_NAME'),
                    'region': row.get('REGION') or row.get('COUNTRY'),
                    'reliability_score': float(row.get('RELIABILITY_SCORE', 0.9)),
                    'avg_lead_time_days': int(row.get('AVG_LEAD_TIME_DAYS', 7)),
                    'source_system': 'ORACLE',
                    'last_updated': datetime.now().isoformat(),
                }
                suppliers.append(supplier)

            self.last_sync_time = datetime.now()
            self.logger.info(f"Fetched {len(suppliers)} suppliers from Oracle")
            return suppliers

        except Exception as e:
            self.logger.error(f"Error fetching suppliers from Oracle: {str(e)}")
            return []

    def fetch_products(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch product data from Oracle."""
        try:
            query = """
                SELECT
                    PRODUCT_ID,
                    PRODUCT_NAME,
                    CATEGORY,
                    SUBCATEGORY,
                    UNIT_OF_MEASURE,
                    SAFETY_STOCK,
                    DEMAND_FORECAST
                FROM PRODUCTS
                WHERE ROWNUM <= :limit
            """

            params = {'limit': filters.get('limit', 1000) if filters else 1000}
            results = self._execute_query(query, params)

            products = []
            for row in results:
                product = {
                    'product_id': row.get('PRODUCT_ID'),
                    'product_name': row.get('PRODUCT_NAME'),
                    'category': row.get('CATEGORY'),
                    'subcategory': row.get('SUBCATEGORY'),
                    'unit': row.get('UNIT_OF_MEASURE'),
                    'safety_stock': row.get('SAFETY_STOCK'),
                    'demand_forecast': row.get('DEMAND_FORECAST'),
                    'source_system': 'ORACLE',
                    'last_updated': datetime.now().isoformat(),
                }
                products.append(product)

            self.last_sync_time = datetime.now()
            self.logger.info(f"Fetched {len(products)} products from Oracle")
            return products

        except Exception as e:
            self.logger.error(f"Error fetching products from Oracle: {str(e)}")
            return []

    def fetch_warehouses(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch warehouse data from Oracle."""
        try:
            query = """
                SELECT
                    WAREHOUSE_ID,
                    WAREHOUSE_NAME,
                    LOCATION,
                    REGION,
                    COUNTRY,
                    CAPACITY_UNITS,
                    AVAILABLE_CAPACITY
                FROM WAREHOUSES
                WHERE ROWNUM <= :limit
            """

            params = {'limit': filters.get('limit', 1000) if filters else 1000}
            results = self._execute_query(query, params)

            warehouses = []
            for row in results:
                warehouse = {
                    'warehouse_id': row.get('WAREHOUSE_ID'),
                    'location': row.get('WAREHOUSE_NAME') or row.get('LOCATION'),
                    'region': row.get('REGION') or row.get('COUNTRY'),
                    'capacity_units': row.get('CAPACITY_UNITS'),
                    'available_capacity': row.get('AVAILABLE_CAPACITY'),
                    'source_system': 'ORACLE',
                    'last_updated': datetime.now().isoformat(),
                }
                warehouses.append(warehouse)

            self.last_sync_time = datetime.now()
            self.logger.info(f"Fetched {len(warehouses)} warehouses from Oracle")
            return warehouses

        except Exception as e:
            self.logger.error(f"Error fetching warehouses from Oracle: {str(e)}")
            return []

    def fetch_shipments(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch shipment/order data from Oracle."""
        try:
            query = """
                SELECT
                    SHIPMENT_ID,
                    ORDER_ID,
                    SUPPLIER_ID,
                    PRODUCT_ID,
                    WAREHOUSE_ID,
                    QUANTITY,
                    PLANNED_LEAD_TIME_DAYS,
                    ACTUAL_LEAD_TIME_DAYS,
                    STATUS,
                    ORDER_DATE,
                    EXPECTED_DELIVERY_DATE,
                    ACTUAL_DELIVERY_DATE
                FROM SHIPMENTS
                WHERE 1=1
            """

            params = {}

            # Add date filter if specified
            if filters and 'start_date' in filters:
                query += " AND ORDER_DATE >= :start_date"
                params['start_date'] = filters['start_date']

            if filters and 'limit' in filters:
                query += " AND ROWNUM <= :limit"
                params['limit'] = filters['limit']
            else:
                query += " AND ROWNUM <= 1000"

            results = self._execute_query(query, params)

            shipments = []
            for row in results:
                shipment = {
                    'shipment_id': row.get('SHIPMENT_ID') or row.get('ORDER_ID'),
                    'supplier_id': row.get('SUPPLIER_ID'),
                    'product_id': row.get('PRODUCT_ID'),
                    'warehouse_id': row.get('WAREHOUSE_ID'),
                    'qty_units': row.get('QUANTITY'),
                    'planned_lead_time_days': row.get('PLANNED_LEAD_TIME_DAYS'),
                    'actual_lead_time_days': row.get('ACTUAL_LEAD_TIME_DAYS'),
                    'status': self._map_shipment_status(row.get('STATUS')),
                    'order_date': row.get('ORDER_DATE'),
                    'expected_delivery': row.get('EXPECTED_DELIVERY_DATE'),
                    'actual_delivery': row.get('ACTUAL_DELIVERY_DATE'),
                    'source_system': 'ORACLE',
                    'last_updated': datetime.now().isoformat(),
                }
                shipments.append(shipment)

            self.last_sync_time = datetime.now()
            self.logger.info(f"Fetched {len(shipments)} shipments from Oracle")
            return shipments

        except Exception as e:
            self.logger.error(f"Error fetching shipments from Oracle: {str(e)}")
            return []

    def _map_shipment_status(self, oracle_status: str) -> str:
        """Map Oracle status codes to standard shipment status."""
        if not oracle_status:
            return 'Unknown'

        status_mapping = {
            'ORDERED': 'On-Time',
            'SHIPPED': 'In-Transit',
            'IN_TRANSIT': 'In-Transit',
            'DELIVERED': 'On-Time',
            'DELAYED': 'Delayed',
            'CANCELLED': 'Cancelled',
        }

        return status_mapping.get(oracle_status.upper(), oracle_status)

    def execute_custom_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute a custom SQL query.

        Args:
            query: Custom SQL query
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        return self._execute_query(query, params)

    def bulk_insert(self, table_name: str, data: List[Dict]) -> int:
        """Bulk insert data into Oracle table.

        Args:
            table_name: Target table name
            data: List of row dictionaries

        Returns:
            Number of rows inserted
        """
        if not data:
            return 0

        try:
            with self.session_maker() as session:
                # Build insert statement
                columns = list(data[0].keys())
                placeholders = ', '.join([f':{col}' for col in columns])
                query = f"""
                    INSERT INTO {table_name} ({', '.join(columns)})
                    VALUES ({placeholders})
                """

                # Execute bulk insert
                session.execute(text(query), data)
                session.commit()

                self.logger.info(f"Inserted {len(data)} rows into {table_name}")
                return len(data)

        except Exception as e:
            self.logger.error(f"Bulk insert failed: {str(e)}")
            raise
