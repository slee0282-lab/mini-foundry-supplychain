"""
Base Connector Interface

Abstract base class for all database connectors, defining common interface
for SAP, Oracle, and other enterprise data sources.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """Enumeration of supported data source types."""
    SAP_S4HANA = "sap_s4hana"
    ORACLE = "oracle"
    CSV = "csv"
    API = "api"
    KAFKA = "kafka"


@dataclass
class ConnectionConfig:
    """Configuration for database connection."""
    source_type: DataSourceType
    host: str
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    service_name: Optional[str] = None
    client: Optional[str] = None  # SAP client number
    system_id: Optional[str] = None  # SAP system ID
    connection_pool_size: int = 5
    connection_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    extra_params: Optional[Dict[str, Any]] = None


class BaseConnector(ABC):
    """Abstract base class for all database connectors."""

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connection = None
        self.is_connected = False
        self.last_sync_time: Optional[datetime] = None
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the data source.

        Returns:
            bool: True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection to the data source.

        Returns:
            bool: True if disconnection successful, False otherwise
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if connection is alive and responsive.

        Returns:
            bool: True if connection is healthy, False otherwise
        """
        pass

    @abstractmethod
    def fetch_suppliers(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch supplier data from the source.

        Args:
            filters: Optional filters to apply to the query

        Returns:
            List of supplier dictionaries
        """
        pass

    @abstractmethod
    def fetch_products(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch product data from the source.

        Args:
            filters: Optional filters to apply to the query

        Returns:
            List of product dictionaries
        """
        pass

    @abstractmethod
    def fetch_warehouses(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch warehouse data from the source.

        Args:
            filters: Optional filters to apply to the query

        Returns:
            List of warehouse dictionaries
        """
        pass

    @abstractmethod
    def fetch_shipments(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch shipment/order data from the source.

        Args:
            filters: Optional filters to apply to the query

        Returns:
            List of shipment dictionaries
        """
        pass

    def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information.

        Returns:
            Dictionary with connection status and metadata
        """
        return {
            'source_type': self.config.source_type.value,
            'host': self.config.host,
            'is_connected': self.is_connected,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'connection_pool_size': self.config.connection_pool_size,
        }

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def _retry_operation(self, operation, *args, **kwargs):
        """Retry an operation with exponential backoff.

        Args:
            operation: Function to retry
            *args, **kwargs: Arguments to pass to the operation

        Returns:
            Operation result

        Raises:
            Last exception if all retries fail
        """
        import time

        last_exception = None
        for attempt in range(self.config.retry_attempts):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.config.retry_attempts - 1:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Operation failed (attempt {attempt + 1}/{self.config.retry_attempts}): {str(e)}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(
                        f"Operation failed after {self.config.retry_attempts} attempts: {str(e)}"
                    )

        raise last_exception
