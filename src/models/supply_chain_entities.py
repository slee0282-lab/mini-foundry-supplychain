"""
Supply Chain Entity Models

Pydantic models for supply chain entities with validation and transformation.
Provides unified data model across SAP, Oracle, and other data sources.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class DataSource(str, Enum):
    """Data source enumeration."""
    SAP_S4HANA = "SAP_S4HANA"
    ORACLE = "ORACLE"
    CSV = "CSV"
    API = "API"
    MANUAL = "MANUAL"


class ShipmentStatus(str, Enum):
    """Shipment status enumeration."""
    ON_TIME = "On-Time"
    IN_TRANSIT = "In-Transit"
    DELAYED = "Delayed"
    DELIVERED = "Delivered"
    CANCELLED = "Cancelled"
    UNKNOWN = "Unknown"


class SupplyChainEntity(BaseModel):
    """Base class for all supply chain entities."""

    source_system: DataSource = Field(default=DataSource.CSV, description="Source system")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class Supplier(SupplyChainEntity):
    """Supplier/Vendor entity model."""

    supplier_id: str = Field(..., description="Unique supplier identifier")
    name: str = Field(..., description="Supplier name")
    region: str = Field(..., description="Geographic region")
    country: Optional[str] = Field(None, description="Country")
    city: Optional[str] = Field(None, description="City")
    postal_code: Optional[str] = Field(None, description="Postal code")

    reliability_score: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Reliability score (0-1)"
    )
    avg_lead_time_days: int = Field(
        default=7,
        ge=0,
        description="Average lead time in days"
    )

    contact_email: Optional[str] = Field(None, description="Contact email")
    contact_phone: Optional[str] = Field(None, description="Contact phone")

    @validator('supplier_id')
    def validate_supplier_id(cls, v):
        if not v or v.strip() == '':
            raise ValueError('Supplier ID cannot be empty')
        return v.strip()

    @validator('reliability_score', pre=True)
    def coerce_reliability_score(cls, v):
        """Convert various formats to float 0-1."""
        if isinstance(v, str):
            v = float(v.strip('%')) / 100 if '%' in v else float(v)
        return min(max(float(v), 0.0), 1.0)

    def to_neo4j_dict(self) -> Dict[str, Any]:
        """Convert to Neo4j node properties."""
        return {
            'supplier_id': self.supplier_id,
            'name': self.name,
            'region': self.region,
            'country': self.country,
            'reliability_score': self.reliability_score,
            'avg_lead_time_days': self.avg_lead_time_days,
            'source_system': self.source_system,
            'last_updated': self.last_updated.isoformat(),
        }


class Product(SupplyChainEntity):
    """Product/Material entity model."""

    product_id: str = Field(..., description="Unique product identifier")
    product_name: str = Field(..., description="Product name/description")
    category: str = Field(..., description="Product category")
    subcategory: Optional[str] = Field(None, description="Product subcategory")

    unit: Optional[str] = Field(None, description="Unit of measure")
    safety_stock: Optional[int] = Field(None, ge=0, description="Safety stock level")
    demand_forecast: Optional[int] = Field(None, ge=0, description="Demand forecast")

    unit_price: Optional[float] = Field(None, ge=0, description="Unit price")
    currency: Optional[str] = Field(default="USD", description="Currency code")

    @validator('product_id')
    def validate_product_id(cls, v):
        if not v or v.strip() == '':
            raise ValueError('Product ID cannot be empty')
        return v.strip()

    def to_neo4j_dict(self) -> Dict[str, Any]:
        """Convert to Neo4j node properties."""
        return {
            'product_id': self.product_id,
            'product_name': self.product_name,
            'category': self.category,
            'subcategory': self.subcategory,
            'unit': self.unit,
            'safety_stock': self.safety_stock,
            'demand_forecast': self.demand_forecast,
            'source_system': self.source_system,
            'last_updated': self.last_updated.isoformat(),
        }


class Warehouse(SupplyChainEntity):
    """Warehouse/Distribution Center entity model."""

    warehouse_id: str = Field(..., description="Unique warehouse identifier")
    location: str = Field(..., description="Warehouse location/name")
    region: str = Field(..., description="Geographic region")
    country: Optional[str] = Field(None, description="Country")

    capacity_units: Optional[int] = Field(None, ge=0, description="Total capacity")
    available_capacity: Optional[int] = Field(None, ge=0, description="Available capacity")
    utilization_rate: Optional[float] = Field(None, ge=0, le=100, description="Utilization percentage")

    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude")

    @validator('warehouse_id')
    def validate_warehouse_id(cls, v):
        if not v or v.strip() == '':
            raise ValueError('Warehouse ID cannot be empty')
        return v.strip()

    def to_neo4j_dict(self) -> Dict[str, Any]:
        """Convert to Neo4j node properties."""
        return {
            'warehouse_id': self.warehouse_id,
            'location': self.location,
            'region': self.region,
            'country': self.country,
            'capacity_units': self.capacity_units,
            'available_capacity': self.available_capacity,
            'source_system': self.source_system,
            'last_updated': self.last_updated.isoformat(),
        }


class Shipment(SupplyChainEntity):
    """Shipment/Order entity model."""

    shipment_id: str = Field(..., description="Unique shipment identifier")
    order_id: Optional[str] = Field(None, description="Related order ID")

    supplier_id: str = Field(..., description="Supplier identifier")
    product_id: str = Field(..., description="Product identifier")
    warehouse_id: str = Field(..., description="Destination warehouse identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")

    qty_units: int = Field(..., ge=0, description="Quantity")
    planned_lead_time_days: int = Field(..., ge=0, description="Planned lead time")
    actual_lead_time_days: Optional[int] = Field(None, ge=0, description="Actual lead time")

    status: ShipmentStatus = Field(default=ShipmentStatus.UNKNOWN, description="Shipment status")

    order_date: Optional[datetime] = Field(None, description="Order date")
    expected_delivery_date: Optional[datetime] = Field(None, description="Expected delivery")
    actual_delivery_date: Optional[datetime] = Field(None, description="Actual delivery")

    unit_price: Optional[float] = Field(None, ge=0, description="Unit price")
    total_value: Optional[float] = Field(None, ge=0, description="Total order value")

    @validator('shipment_id')
    def validate_shipment_id(cls, v):
        if not v or v.strip() == '':
            raise ValueError('Shipment ID cannot be empty')
        return v.strip()

    @validator('total_value', always=True)
    def calculate_total_value(cls, v, values):
        """Auto-calculate total value if not provided."""
        if v is None and 'qty_units' in values and 'unit_price' in values:
            if values['unit_price'] is not None:
                return values['qty_units'] * values['unit_price']
        return v

    def to_neo4j_dict(self) -> Dict[str, Any]:
        """Convert to Neo4j node properties."""
        return {
            'shipment_id': self.shipment_id,
            'order_id': self.order_id,
            'qty_units': self.qty_units,
            'planned_lead_time_days': self.planned_lead_time_days,
            'actual_lead_time_days': self.actual_lead_time_days,
            'status': self.status,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'expected_delivery_date': self.expected_delivery_date.isoformat() if self.expected_delivery_date else None,
            'actual_delivery_date': self.actual_delivery_date.isoformat() if self.actual_delivery_date else None,
            'total_value': self.total_value,
            'source_system': self.source_system,
            'last_updated': self.last_updated.isoformat(),
        }


class Customer(SupplyChainEntity):
    """Customer entity model."""

    customer_id: str = Field(..., description="Unique customer identifier")
    name: str = Field(..., description="Customer name")
    region: str = Field(..., description="Geographic region")
    country: Optional[str] = Field(None, description="Country")

    customer_type: Optional[str] = Field(None, description="Customer type/category")
    credit_rating: Optional[str] = Field(None, description="Credit rating")

    @validator('customer_id')
    def validate_customer_id(cls, v):
        if not v or v.strip() == '':
            raise ValueError('Customer ID cannot be empty')
        return v.strip()

    def to_neo4j_dict(self) -> Dict[str, Any]:
        """Convert to Neo4j node properties."""
        return {
            'customer_id': self.customer_id,
            'name': self.name,
            'region': self.region,
            'country': self.country,
            'customer_type': self.customer_type,
            'source_system': self.source_system,
            'last_updated': self.last_updated.isoformat(),
        }


# Mapper functions for transforming raw data to Pydantic models

def map_to_supplier(data: Dict[str, Any], source: DataSource) -> Supplier:
    """Map raw data dictionary to Supplier model."""
    return Supplier(
        supplier_id=data.get('supplier_id') or data.get('SUPPLIER_ID') or data.get('Supplier'),
        name=data.get('name') or data.get('SUPPLIER_NAME') or data.get('SupplierName'),
        region=data.get('region') or data.get('REGION') or data.get('Country'),
        country=data.get('country') or data.get('COUNTRY'),
        reliability_score=data.get('reliability_score', 0.90),
        avg_lead_time_days=data.get('avg_lead_time_days', 7),
        source_system=source,
    )


def map_to_product(data: Dict[str, Any], source: DataSource) -> Product:
    """Map raw data dictionary to Product model."""
    return Product(
        product_id=data.get('product_id') or data.get('PRODUCT_ID') or data.get('Product'),
        product_name=data.get('product_name') or data.get('PRODUCT_NAME') or data.get('ProductDescription'),
        category=data.get('category') or data.get('CATEGORY') or data.get('ProductGroup', 'General'),
        subcategory=data.get('subcategory') or data.get('SUBCATEGORY'),
        unit=data.get('unit') or data.get('UNIT_OF_MEASURE'),
        source_system=source,
    )


def map_to_warehouse(data: Dict[str, Any], source: DataSource) -> Warehouse:
    """Map raw data dictionary to Warehouse model."""
    return Warehouse(
        warehouse_id=data.get('warehouse_id') or data.get('WAREHOUSE_ID') or data.get('Plant'),
        location=data.get('location') or data.get('LOCATION') or data.get('PlantName'),
        region=data.get('region') or data.get('REGION') or data.get('Country'),
        country=data.get('country') or data.get('COUNTRY'),
        capacity_units=data.get('capacity_units'),
        source_system=source,
    )


def map_to_shipment(data: Dict[str, Any], source: DataSource) -> Shipment:
    """Map raw data dictionary to Shipment model."""
    return Shipment(
        shipment_id=data.get('shipment_id') or data.get('SHIPMENT_ID') or data.get('PurchaseOrder'),
        supplier_id=data.get('supplier_id') or data.get('SUPPLIER_ID'),
        product_id=data.get('product_id') or data.get('PRODUCT_ID'),
        warehouse_id=data.get('warehouse_id') or data.get('WAREHOUSE_ID'),
        qty_units=data.get('qty_units') or data.get('QUANTITY', 0),
        planned_lead_time_days=data.get('planned_lead_time_days', 7),
        status=data.get('status', ShipmentStatus.UNKNOWN),
        source_system=source,
    )
