"""
Connector Factory

Factory pattern for creating database connectors based on configuration.
Provides unified interface for managing multiple data sources.
"""

from typing import Optional, Dict
import logging
import os

from .base_connector import BaseConnector, ConnectionConfig, DataSourceType
from .sap_connector import SAPConnector, SAPRFCConnector
from .oracle_connector import OracleConnector

logger = logging.getLogger(__name__)


class ConnectorFactory:
    """Factory for creating and managing database connectors."""

    _connectors: Dict[str, BaseConnector] = {}

    @staticmethod
    def create_connector(config: ConnectionConfig) -> BaseConnector:
        """Create a connector based on configuration.

        Args:
            config: Connection configuration

        Returns:
            Appropriate connector instance

        Raises:
            ValueError: If source type is not supported
        """
        if config.source_type == DataSourceType.SAP_S4HANA:
            # Use OData connector by default
            return SAPConnector(config)

        elif config.source_type == DataSourceType.ORACLE:
            return OracleConnector(config)

        elif config.source_type == DataSourceType.CSV:
            # Could implement CSV connector if needed
            raise NotImplementedError("CSV connector not yet implemented in factory")

        else:
            raise ValueError(f"Unsupported data source type: {config.source_type}")

    @classmethod
    def get_or_create_connector(cls, name: str, config: ConnectionConfig) -> BaseConnector:
        """Get existing connector or create new one.

        Args:
            name: Connector name/identifier
            config: Connection configuration

        Returns:
            Connector instance
        """
        if name not in cls._connectors:
            connector = cls.create_connector(config)
            cls._connectors[name] = connector
            logger.info(f"Created new connector: {name}")

        return cls._connectors[name]

    @classmethod
    def get_connector(cls, name: str) -> Optional[BaseConnector]:
        """Get existing connector by name.

        Args:
            name: Connector name

        Returns:
            Connector instance or None if not found
        """
        return cls._connectors.get(name)

    @classmethod
    def remove_connector(cls, name: str) -> bool:
        """Remove and disconnect a connector.

        Args:
            name: Connector name

        Returns:
            True if removed, False if not found
        """
        if name in cls._connectors:
            connector = cls._connectors[name]
            connector.disconnect()
            del cls._connectors[name]
            logger.info(f"Removed connector: {name}")
            return True
        return False

    @classmethod
    def disconnect_all(cls):
        """Disconnect all active connectors."""
        for name, connector in cls._connectors.items():
            connector.disconnect()
            logger.info(f"Disconnected: {name}")
        cls._connectors.clear()

    @classmethod
    def get_all_connectors(cls) -> Dict[str, BaseConnector]:
        """Get all active connectors.

        Returns:
            Dictionary of connector name to connector instance
        """
        return cls._connectors.copy()

    @staticmethod
    def create_from_env(source_type: DataSourceType) -> BaseConnector:
        """Create connector from environment variables.

        Args:
            source_type: Type of data source

        Returns:
            Configured connector instance
        """
        if source_type == DataSourceType.SAP_S4HANA:
            config = ConnectionConfig(
                source_type=DataSourceType.SAP_S4HANA,
                host=os.getenv('SAP_HOST'),
                port=int(os.getenv('SAP_PORT', 443)),
                username=os.getenv('SAP_USER'),
                password=os.getenv('SAP_PASSWORD'),
                client=os.getenv('SAP_CLIENT', '100'),
                system_id=os.getenv('SAP_SYSTEM_ID'),
            )
            return SAPConnector(config)

        elif source_type == DataSourceType.ORACLE:
            config = ConnectionConfig(
                source_type=DataSourceType.ORACLE,
                host=os.getenv('ORACLE_HOST'),
                port=int(os.getenv('ORACLE_PORT', 1521)),
                username=os.getenv('ORACLE_USER'),
                password=os.getenv('ORACLE_PASSWORD'),
                service_name=os.getenv('ORACLE_SERVICE_NAME'),
                database=os.getenv('ORACLE_SID'),
                schema=os.getenv('ORACLE_SCHEMA'),
            )
            return OracleConnector(config)

        else:
            raise ValueError(f"Cannot create connector from env for: {source_type}")


def get_streamlit_connector(source_type: DataSourceType) -> BaseConnector:
    """Create connector with Streamlit secrets support.

    Args:
        source_type: Type of data source

    Returns:
        Configured connector instance
    """
    try:
        import streamlit as st

        if source_type == DataSourceType.SAP_S4HANA:
            config = ConnectionConfig(
                source_type=DataSourceType.SAP_S4HANA,
                host=st.secrets.get('SAP_HOST', os.getenv('SAP_HOST')),
                port=int(st.secrets.get('SAP_PORT', os.getenv('SAP_PORT', 443))),
                username=st.secrets.get('SAP_USER', os.getenv('SAP_USER')),
                password=st.secrets.get('SAP_PASSWORD', os.getenv('SAP_PASSWORD')),
                client=st.secrets.get('SAP_CLIENT', os.getenv('SAP_CLIENT', '100')),
            )
            return SAPConnector(config)

        elif source_type == DataSourceType.ORACLE:
            config = ConnectionConfig(
                source_type=DataSourceType.ORACLE,
                host=st.secrets.get('ORACLE_HOST', os.getenv('ORACLE_HOST')),
                port=int(st.secrets.get('ORACLE_PORT', os.getenv('ORACLE_PORT', 1521))),
                username=st.secrets.get('ORACLE_USER', os.getenv('ORACLE_USER')),
                password=st.secrets.get('ORACLE_PASSWORD', os.getenv('ORACLE_PASSWORD')),
                service_name=st.secrets.get('ORACLE_SERVICE_NAME', os.getenv('ORACLE_SERVICE_NAME')),
            )
            return OracleConnector(config)

    except ImportError:
        # Streamlit not available, fall back to environment variables
        return ConnectorFactory.create_from_env(source_type)

    raise ValueError(f"Unsupported source type: {source_type}")
