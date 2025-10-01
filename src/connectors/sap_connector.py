"""
SAP S/4HANA Connector

Implements connection to SAP S/4HANA using OData APIs and RFC.
Supports both cloud and on-premise deployments.
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from .base_connector import BaseConnector, ConnectionConfig, DataSourceType

logger = logging.getLogger(__name__)


class SAPConnector(BaseConnector):
    """SAP S/4HANA connector using OData API."""

    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.session: Optional[requests.Session] = None
        self.base_url = f"https://{config.host}"
        if config.port:
            self.base_url += f":{config.port}"

        # OData service endpoints
        self.odata_endpoints = {
            'suppliers': '/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_Supplier',
            'materials': '/sap/opu/odata/sap/API_PRODUCT_SRV/A_Product',
            'plants': '/sap/opu/odata/sap/API_PLANT_SRV/A_Plant',
            'purchase_orders': '/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder',
        }

    def connect(self) -> bool:
        """Establish connection to SAP S/4HANA."""
        try:
            self.session = requests.Session()
            self.session.auth = HTTPBasicAuth(
                self.config.username,
                self.config.password
            )

            # Set common headers
            self.session.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'sap-client': self.config.client or '100',
            })

            # Test connection
            if self.test_connection():
                self.is_connected = True
                self.logger.info(f"Successfully connected to SAP S/4HANA at {self.config.host}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to connect to SAP S/4HANA: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """Close SAP S/4HANA connection."""
        try:
            if self.session:
                self.session.close()
                self.session = None
            self.is_connected = False
            self.logger.info("Disconnected from SAP S/4HANA")
            return True
        except Exception as e:
            self.logger.error(f"Error disconnecting from SAP: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """Test SAP connection by fetching service metadata."""
        try:
            # Test with a simple metadata request
            response = self.session.get(
                f"{self.base_url}{self.odata_endpoints['suppliers']}/$metadata",
                timeout=self.config.connection_timeout
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def _execute_odata_query(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute OData query and return results.

        Args:
            endpoint: OData endpoint path
            params: Query parameters ($filter, $select, $expand, etc.)

        Returns:
            List of result dictionaries
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to SAP. Call connect() first.")

        try:
            url = f"{self.base_url}{endpoint}"
            response = self._retry_operation(
                self.session.get,
                url,
                params=params,
                timeout=self.config.connection_timeout
            )

            response.raise_for_status()
            data = response.json()

            # OData results are typically in 'd' or 'value' key
            if 'value' in data:
                return data['value']
            elif 'd' in data:
                return data['d'].get('results', [])

            return []

        except Exception as e:
            self.logger.error(f"OData query failed: {str(e)}")
            raise

    def fetch_suppliers(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch supplier data from SAP (LFA1/A_Supplier).

        Maps SAP fields to supply chain ontology:
        - Supplier ID: SupplierID or Lifnr
        - Name: SupplierName
        - Region: Country
        - Reliability: Custom calculation or KPI field
        """
        try:
            # Build OData query parameters
            params = {
                '$select': 'Supplier,SupplierName,Country,Region,PostalCode,SupplierAccountGroup',
                '$top': filters.get('limit', 1000) if filters else 1000,
            }

            # Add filter if specified
            if filters and 'filter' in filters:
                params['$filter'] = filters['filter']

            results = self._execute_odata_query(self.odata_endpoints['suppliers'], params)

            # Transform to standard format
            suppliers = []
            for sap_supplier in results:
                supplier = {
                    'supplier_id': sap_supplier.get('Supplier'),
                    'name': sap_supplier.get('SupplierName'),
                    'region': sap_supplier.get('Country'),
                    'reliability_score': self._calculate_supplier_reliability(sap_supplier),
                    'avg_lead_time_days': self._get_supplier_lead_time(sap_supplier.get('Supplier')),
                    'source_system': 'SAP_S4HANA',
                    'last_updated': datetime.now().isoformat(),
                }
                suppliers.append(supplier)

            self.last_sync_time = datetime.now()
            self.logger.info(f"Fetched {len(suppliers)} suppliers from SAP")
            return suppliers

        except Exception as e:
            self.logger.error(f"Error fetching suppliers from SAP: {str(e)}")
            return []

    def fetch_products(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch product/material data from SAP (MARA/A_Product)."""
        try:
            params = {
                '$select': 'Product,ProductType,ProductGroup,BaseUnit,Division',
                '$top': filters.get('limit', 1000) if filters else 1000,
            }

            if filters and 'filter' in filters:
                params['$filter'] = filters['filter']

            results = self._execute_odata_query(self.odata_endpoints['materials'], params)

            products = []
            for sap_product in results:
                product = {
                    'product_id': sap_product.get('Product'),
                    'product_name': sap_product.get('Product'),  # May need lookup for description
                    'category': sap_product.get('ProductGroup'),
                    'unit': sap_product.get('BaseUnit'),
                    'source_system': 'SAP_S4HANA',
                    'last_updated': datetime.now().isoformat(),
                }
                products.append(product)

            self.last_sync_time = datetime.now()
            self.logger.info(f"Fetched {len(products)} products from SAP")
            return products

        except Exception as e:
            self.logger.error(f"Error fetching products from SAP: {str(e)}")
            return []

    def fetch_warehouses(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch plant/storage location data from SAP (T001L/A_Plant)."""
        try:
            params = {
                '$select': 'Plant,PlantName,Country,Region',
                '$top': filters.get('limit', 1000) if filters else 1000,
            }

            if filters and 'filter' in filters:
                params['$filter'] = filters['filter']

            results = self._execute_odata_query(self.odata_endpoints['plants'], params)

            warehouses = []
            for sap_plant in results:
                warehouse = {
                    'warehouse_id': sap_plant.get('Plant'),
                    'location': sap_plant.get('PlantName'),
                    'region': sap_plant.get('Country'),
                    'capacity_units': None,  # May need separate query
                    'source_system': 'SAP_S4HANA',
                    'last_updated': datetime.now().isoformat(),
                }
                warehouses.append(warehouse)

            self.last_sync_time = datetime.now()
            self.logger.info(f"Fetched {len(warehouses)} warehouses from SAP")
            return warehouses

        except Exception as e:
            self.logger.error(f"Error fetching warehouses from SAP: {str(e)}")
            return []

    def fetch_shipments(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch purchase order data from SAP (EKKO/EKPO/A_PurchaseOrder)."""
        try:
            params = {
                '$select': 'PurchaseOrder,Supplier,PurchaseOrderDate,DocumentCurrency',
                '$expand': 'to_PurchaseOrderItem',
                '$top': filters.get('limit', 1000) if filters else 1000,
            }

            if filters and 'filter' in filters:
                params['$filter'] = filters['filter']

            results = self._execute_odata_query(self.odata_endpoints['purchase_orders'], params)

            shipments = []
            for sap_po in results:
                # Process purchase order items
                items = sap_po.get('to_PurchaseOrderItem', {}).get('results', [])

                for item in items:
                    shipment = {
                        'shipment_id': f"{sap_po.get('PurchaseOrder')}_{item.get('PurchaseOrderItem')}",
                        'supplier_id': sap_po.get('Supplier'),
                        'product_id': item.get('Material'),
                        'warehouse_id': item.get('Plant'),
                        'qty_units': item.get('OrderQuantity'),
                        'planned_lead_time_days': self._calculate_po_lead_time(item),
                        'status': self._map_po_status(item.get('PurchaseOrderItemCategory')),
                        'source_system': 'SAP_S4HANA',
                        'last_updated': datetime.now().isoformat(),
                    }
                    shipments.append(shipment)

            self.last_sync_time = datetime.now()
            self.logger.info(f"Fetched {len(shipments)} shipments from SAP")
            return shipments

        except Exception as e:
            self.logger.error(f"Error fetching shipments from SAP: {str(e)}")
            return []

    def _calculate_supplier_reliability(self, supplier_data: Dict) -> float:
        """Calculate supplier reliability score.

        In real implementation, this would query SAP vendor evaluation data.
        """
        # Placeholder - would query actual KPI data
        return 0.90

    def _get_supplier_lead_time(self, supplier_id: str) -> int:
        """Get average lead time for a supplier.

        Would query purchasing info records (EINA/EINE) in real implementation.
        """
        # Placeholder
        return 7

    def _calculate_po_lead_time(self, po_item: Dict) -> int:
        """Calculate lead time from purchase order item."""
        # Would use delivery date - order date
        return 10

    def _map_po_status(self, item_category: str) -> str:
        """Map SAP PO item category to shipment status."""
        status_mapping = {
            '0': 'On-Time',
            '1': 'In-Transit',
            '9': 'Delayed',
        }
        return status_mapping.get(item_category, 'Unknown')


class SAPRFCConnector(BaseConnector):
    """SAP connector using RFC (for legacy systems or direct function calls).

    Note: Requires pyrfc library and SAP NetWeaver RFC SDK.
    This is a placeholder - implementation requires SAP connection details.
    """

    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.rfc_connection = None

    def connect(self) -> bool:
        """Establish RFC connection to SAP."""
        try:
            # Requires pyrfc
            # from pyrfc import Connection
            # self.rfc_connection = Connection(
            #     user=self.config.username,
            #     passwd=self.config.password,
            #     ashost=self.config.host,
            #     sysnr=self.config.system_id,
            #     client=self.config.client,
            # )
            self.logger.info("RFC connection established (placeholder)")
            self.is_connected = True
            return True
        except Exception as e:
            self.logger.error(f"RFC connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """Close RFC connection."""
        if self.rfc_connection:
            self.rfc_connection.close()
        self.is_connected = False
        return True

    def test_connection(self) -> bool:
        """Test RFC connection."""
        return self.is_connected

    def fetch_suppliers(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch suppliers via RFC function module."""
        # Would call custom or standard RFC function
        return []

    def fetch_products(self, filters: Optional[Dict] = None) -> List[Dict]:
        return []

    def fetch_warehouses(self, filters: Optional[Dict] = None) -> List[Dict]:
        return []

    def fetch_shipments(self, filters: Optional[Dict] = None) -> List[Dict]:
        return []
