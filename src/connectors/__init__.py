"""
Enterprise Database Connectors

Provides abstract interfaces and concrete implementations for connecting to
enterprise systems like SAP S/4HANA, Oracle, and other data sources.
"""

from .base_connector import BaseConnector, ConnectionConfig, DataSourceType
from .connector_factory import ConnectorFactory

__all__ = [
    'BaseConnector',
    'ConnectionConfig',
    'DataSourceType',
    'ConnectorFactory',
]
