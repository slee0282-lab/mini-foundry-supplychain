"""
Utility functions for the Supply Chain Control Tower.

Provides configuration loading, logging setup, and common helper functions.
"""

import os
import logging
import sys
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

# Load environment variables
load_dotenv()


def get_env_or_secret(key: str, default: str = None) -> str:
    """Get value from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return os.getenv(key, default)


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    config = {
        # Neo4j Configuration
        'neo4j': {
            'uri': get_env_or_secret('NEO4J_URI', 'bolt://localhost:7687'),
            'user': get_env_or_secret('NEO4J_USER', 'neo4j'),
            'password': get_env_or_secret('NEO4J_PASSWORD', 'password')
        },

        # Application Configuration
        'app': {
            'name': os.getenv('APP_NAME', 'Mini Foundry Supply Chain Control Tower'),
            'version': os.getenv('APP_VERSION', '1.0.0'),
            'debug': os.getenv('DEBUG', 'True').lower() == 'true'
        },

        # Streamlit Configuration
        'streamlit': {
            'port': int(os.getenv('STREAMLIT_PORT', 8501)),
            'host': os.getenv('STREAMLIT_HOST', 'localhost')
        },

        # Data Configuration
        'data': {
            'path': os.getenv('DATA_PATH', './data'),
            'csv_import_path': os.getenv('CSV_IMPORT_PATH', '/var/lib/neo4j/import')
        },

        # Simulation Parameters
        'simulation': {
            'default_delay_days': int(os.getenv('DEFAULT_SIMULATION_DELAY_DAYS', 5)),
            'max_delay_days': int(os.getenv('MAX_SIMULATION_DELAY_DAYS', 21)),
            'sla_threshold_days': int(os.getenv('DEFAULT_SLA_THRESHOLD_DAYS', 10))
        },

        # Cache Configuration
        'cache': {
            'enabled': os.getenv('ENABLE_CACHING', 'True').lower() == 'true',
            'ttl_seconds': int(os.getenv('CACHE_TTL_SECONDS', 300))
        },

        # Logging Configuration
        'logging': {
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'file': os.getenv('LOG_FILE', 'logs/supply_chain.log')
        }
    }

    return config


def setup_logging(level: str = None, log_file: str = None) -> logging.Logger:
    """Set up logging configuration."""
    config = load_config()

    # Use provided values or fall back to config
    log_level = level or config['logging']['level']
    log_file_path = log_file or config['logging']['file']

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure logging
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file_path) if log_file_path else logging.NullHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {log_level}, File: {log_file_path}")

    return logger


def format_currency(amount: float, currency: str = 'USD') -> str:
    """Format currency amounts."""
    if currency == 'USD':
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """Format percentage values."""
    return f"{value:.{decimal_places}f}%"


def format_large_number(number: int) -> str:
    """Format large numbers with appropriate suffixes."""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number / 1_000:.1f}K"
    else:
        return str(number)


def calculate_business_days(start_date: datetime, days: int) -> datetime:
    """Calculate business days (excluding weekends)."""
    current_date = start_date
    days_added = 0

    while days_added < days:
        current_date += timedelta(days=1)
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        if current_date.weekday() < 5:
            days_added += 1

    return current_date


def validate_data_types(data: Dict[str, Any], schema: Dict[str, type]) -> Dict[str, str]:
    """Validate data types against a schema."""
    errors = {}

    for field, expected_type in schema.items():
        if field in data:
            if not isinstance(data[field], expected_type):
                errors[field] = f"Expected {expected_type.__name__}, got {type(data[field]).__name__}"
        else:
            errors[field] = "Field is missing"

    return errors


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def calculate_sla_impact(lead_time: int, quantity: int, sla_threshold: int = 10) -> float:
    """Calculate SLA impact based on lead time and quantity."""
    if lead_time <= sla_threshold:
        return 0.0

    # Progressive impact based on how much the lead time exceeds SLA
    excess_days = lead_time - sla_threshold
    base_impact = min(excess_days / 7.0, 1.0)  # Max 100% impact

    # Scale by quantity (more quantity = more impact)
    quantity_factor = min(quantity / 1000.0, 2.0)  # Max 2x multiplier

    return base_impact * quantity_factor * 100  # Return as percentage


def generate_risk_score(reliability: float, lead_time: int, volume: int) -> float:
    """Generate a risk score based on supplier characteristics."""
    # Risk factors (lower is better for reliability, higher is worse for lead time and volume)
    reliability_risk = (1 - reliability) * 50  # 0-50 points
    lead_time_risk = min(lead_time / 30.0, 1.0) * 30  # 0-30 points
    volume_risk = min(volume / 1000.0, 1.0) * 20  # 0-20 points

    total_risk = reliability_risk + lead_time_risk + volume_risk
    return min(total_risk, 100.0)  # Cap at 100


def export_to_json(data: Dict[str, Any], file_path: str) -> bool:
    """Export data to JSON file."""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logging.error(f"Error exporting to JSON: {str(e)}")
        return False


def load_from_json(file_path: str) -> Optional[Dict[str, Any]]:
    """Load data from JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading from JSON: {str(e)}")
        return None


def create_directory_structure():
    """Create necessary directory structure for the application."""
    directories = [
        'logs',
        'data',
        'exports',
        'cache'
    ]

    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logging.info(f"Created directory: {directory}")


def get_system_info() -> Dict[str, str]:
    """Get system information for debugging."""
    import platform
    import psutil

    return {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'python_version': platform.python_version(),
        'cpu_count': str(psutil.cpu_count()),
        'memory_gb': f"{psutil.virtual_memory().total / (1024**3):.1f}",
        'disk_free_gb': f"{psutil.disk_usage('/').free / (1024**3):.1f}"
    }


class Timer:
    """Simple context manager for timing operations."""

    def __init__(self, description: str = "Operation"):
        self.description = description
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        logging.info(f"Starting: {self.description}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        duration = self.end_time - self.start_time
        logging.info(f"Completed: {self.description} in {duration.total_seconds():.2f} seconds")

    @property
    def duration(self) -> Optional[timedelta]:
        """Get the duration of the timed operation."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class SupplyChainMetrics:
    """Common supply chain metrics calculations."""

    @staticmethod
    def calculate_fill_rate(orders_filled: int, total_orders: int) -> float:
        """Calculate fill rate percentage."""
        return safe_divide(orders_filled, total_orders) * 100

    @staticmethod
    def calculate_inventory_turnover(cost_of_goods_sold: float, average_inventory: float) -> float:
        """Calculate inventory turnover ratio."""
        return safe_divide(cost_of_goods_sold, average_inventory)

    @staticmethod
    def calculate_lead_time_variance(actual_lead_times: list, planned_lead_time: float) -> float:
        """Calculate lead time variance."""
        if not actual_lead_times:
            return 0.0

        import statistics
        actual_avg = statistics.mean(actual_lead_times)
        return abs(actual_avg - planned_lead_time) / planned_lead_time * 100

    @staticmethod
    def calculate_supplier_reliability(on_time_deliveries: int, total_deliveries: int) -> float:
        """Calculate supplier reliability percentage."""
        return safe_divide(on_time_deliveries, total_deliveries) * 100


# Global configuration instance
_config = None


def get_config() -> Dict[str, Any]:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def refresh_config():
    """Refresh global configuration from environment."""
    global _config
    load_dotenv(override=True)  # Reload environment variables
    _config = load_config()


if __name__ == "__main__":
    # Test utilities
    logger = setup_logging()
    config = load_config()

    logger.info("=== Testing Utilities ===")
    logger.info(f"App Name: {config['app']['name']}")
    logger.info(f"Neo4j URI: {config['neo4j']['uri']}")

    # Test formatting functions
    logger.info(f"Currency: {format_currency(1234567.89)}")
    logger.info(f"Percentage: {format_percentage(87.654)}")
    logger.info(f"Large number: {format_large_number(2500000)}")

    # Test risk score calculation
    risk = generate_risk_score(0.85, 12, 500)
    logger.info(f"Risk score: {risk:.2f}")

    # Test timer
    with Timer("Test operation"):
        import time
        time.sleep(1)

    logger.info("✓ Utilities test completed")