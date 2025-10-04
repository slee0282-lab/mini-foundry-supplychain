# Oracle Database Setup Guide

## 목적

CSV 파일로 프로토타입 검증 후, 실제 엔터프라이즈 데이터베이스(Oracle)와 연결하여 production-ready 시스템으로 전환합니다.

---

## Phase 1: Docker로 Oracle Database 실행

### 1.1 Oracle Container Registry 로그인

Oracle Database는 공식 컨테이너 레지스트리에서 다운로드해야 합니다:

```bash
# Oracle Container Registry 계정 생성
# https://container-registry.oracle.com/

# Docker 로그인
docker login container-registry.oracle.com

# Username: Oracle 계정 이메일
# Password: Oracle 계정 비밀번호
```

### 1.2 Oracle Database 21c XE (Free) 실행

**추천:** Oracle Database 21c Express Edition (무료, 개발용)

```bash
# Oracle 21c XE 이미지 다운로드
docker pull container-registry.oracle.com/database/express:21.3.0-xe

# Oracle Database 컨테이너 실행
docker run -d \
  --name oracle-supply-chain \
  -p 1521:1521 \
  -p 5500:5500 \
  -e ORACLE_PWD=OraclePassword123 \
  -e ORACLE_CHARACTERSET=AL32UTF8 \
  -v oracle-data:/opt/oracle/oradata \
  container-registry.oracle.com/database/express:21.3.0-xe

# 로그 확인 (초기 설정에 3-5분 소요)
docker logs -f oracle-supply-chain
```

**연결 정보:**
- Host: `localhost`
- Port: `1521`
- Service Name: `XEPDB1`
- Username: `SYSTEM`
- Password: `OraclePassword123` (위에서 설정한 ORACLE_PWD)

### 1.3 연결 확인

```bash
# SQL*Plus로 연결 테스트 (컨테이너 내부)
docker exec -it oracle-supply-chain sqlplus system/OraclePassword123@XEPDB1

# 또는 Python으로 테스트
python3 << EOF
import cx_Oracle
conn = cx_Oracle.connect('system', 'OraclePassword123', 'localhost:1521/XEPDB1')
print(f"Oracle version: {conn.version}")
conn.close()
EOF
```

---

## Phase 2: 스키마 생성 및 데이터 로드

### 2.1 Supply Chain 사용자 및 스키마 생성

```sql
-- SQL*Plus 또는 SQL Developer로 실행
-- docker exec -it oracle-supply-chain sqlplus system/OraclePassword123@XEPDB1

-- 사용자 생성
CREATE USER supply_chain IDENTIFIED BY SupplyChain123
DEFAULT TABLESPACE USERS
TEMPORARY TABLESPACE TEMP
QUOTA UNLIMITED ON USERS;

-- 권한 부여
GRANT CONNECT, RESOURCE, CREATE VIEW TO supply_chain;
GRANT CREATE SESSION TO supply_chain;

-- 연결 확인
CONNECT supply_chain/SupplyChain123@XEPDB1
```

### 2.2 테이블 생성 스크립트

```sql
-- suppliers 테이블
CREATE TABLE suppliers (
    supplier_id VARCHAR2(10) PRIMARY KEY,
    name VARCHAR2(100) NOT NULL,
    region VARCHAR2(50) NOT NULL,
    reliability_score NUMBER(3,2),
    avg_lead_time_days NUMBER(3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- products 테이블
CREATE TABLE products (
    product_id VARCHAR2(10) PRIMARY KEY,
    name VARCHAR2(100) NOT NULL,
    category VARCHAR2(50) NOT NULL,
    unit_cost NUMBER(10,2),
    safety_stock_units NUMBER(10),
    storage_condition VARCHAR2(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- warehouses 테이블
CREATE TABLE warehouses (
    warehouse_id VARCHAR2(10) PRIMARY KEY,
    location VARCHAR2(100) NOT NULL,
    region VARCHAR2(50) NOT NULL,
    capacity NUMBER(10),
    current_stock NUMBER(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- customers 테이블
CREATE TABLE customers (
    customer_id VARCHAR2(10) PRIMARY KEY,
    name VARCHAR2(100) NOT NULL,
    region VARCHAR2(50) NOT NULL,
    tier VARCHAR2(20),
    monthly_demand NUMBER(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- shipments 테이블
CREATE TABLE shipments (
    shipment_id VARCHAR2(10) PRIMARY KEY,
    supplier_id VARCHAR2(10) REFERENCES suppliers(supplier_id),
    product_id VARCHAR2(10) REFERENCES products(product_id),
    warehouse_id VARCHAR2(10) REFERENCES warehouses(warehouse_id),
    qty_units NUMBER(10),
    planned_lead_time_days NUMBER(3),
    status VARCHAR2(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- lots 테이블
CREATE TABLE lots (
    lot_id VARCHAR2(20) PRIMARY KEY,
    product_id VARCHAR2(10) REFERENCES products(product_id),
    manufacturing_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    quantity_units NUMBER(10),
    status VARCHAR2(20),
    storage_condition VARCHAR2(50),
    site_id VARCHAR2(50),
    batch_record_id VARCHAR2(50),
    quality_status VARCHAR2(30),
    hold_reason VARCHAR2(100),
    recall_status VARCHAR2(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- shipments_lots 매핑 테이블
CREATE TABLE shipments_lots (
    shipment_lot_id VARCHAR2(20) PRIMARY KEY,
    shipment_id VARCHAR2(10) REFERENCES shipments(shipment_id),
    lot_id VARCHAR2(20) REFERENCES lots(lot_id),
    quantity_units NUMBER(10),
    packing_date DATE,
    shipping_date DATE,
    temperature_monitored CHAR(3),
    notes VARCHAR2(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- cold_chain_readings 테이블
CREATE TABLE cold_chain_readings (
    reading_id VARCHAR2(20) PRIMARY KEY,
    shipment_id VARCHAR2(10) REFERENCES shipments(shipment_id),
    lot_id VARCHAR2(20) REFERENCES lots(lot_id),
    reading_timestamp TIMESTAMP,
    temperature_c NUMBER(5,2),
    humidity_percent NUMBER(5,2),
    location VARCHAR2(50),
    device_id VARCHAR2(20),
    threshold_min_c NUMBER(5,2),
    threshold_max_c NUMBER(5,2),
    excursion_flag CHAR(3),
    excursion_duration_minutes NUMBER(5),
    notes VARCHAR2(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- sla_rules 테이블
CREATE TABLE sla_rules (
    rule_id VARCHAR2(20) PRIMARY KEY,
    region VARCHAR2(50),
    product_category VARCHAR2(50),
    product_id VARCHAR2(10) REFERENCES products(product_id),
    promised_days NUMBER(3),
    priority VARCHAR2(20),
    customer_tier VARCHAR2(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- lanes 테이블
CREATE TABLE lanes (
    lane_id VARCHAR2(20) PRIMARY KEY,
    origin_region VARCHAR2(50),
    dest_region VARCHAR2(50),
    base_lead_time_days NUMBER(3),
    transport_mode VARCHAR2(20),
    distance_km NUMBER(10),
    reliability_score NUMBER(3,2),
    capacity_units_per_week NUMBER(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- events 테이블
CREATE TABLE events (
    event_id VARCHAR2(20) PRIMARY KEY,
    event_type VARCHAR2(50),
    scope_type VARCHAR2(20),
    scope_id VARCHAR2(20),
    impact_value NUMBER(10,2),
    impact_unit VARCHAR2(20),
    start_date DATE,
    end_date DATE,
    severity VARCHAR2(20),
    status VARCHAR2(30),
    description VARCHAR2(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- costs 테이블
CREATE TABLE costs (
    cost_id VARCHAR2(20) PRIMARY KEY,
    cost_type VARCHAR2(50),
    category VARCHAR2(50),
    product_id VARCHAR2(10),
    region VARCHAR2(50),
    customer_tier VARCHAR2(20),
    value NUMBER(12,2),
    currency VARCHAR2(10),
    unit VARCHAR2(50),
    notes VARCHAR2(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성 (성능 최적화)
CREATE INDEX idx_shipments_supplier ON shipments(supplier_id);
CREATE INDEX idx_shipments_product ON shipments(product_id);
CREATE INDEX idx_shipments_warehouse ON shipments(warehouse_id);
CREATE INDEX idx_lots_product ON lots(product_id);
CREATE INDEX idx_lots_status ON lots(status);
CREATE INDEX idx_cold_chain_shipment ON cold_chain_readings(shipment_id);
CREATE INDEX idx_cold_chain_excursion ON cold_chain_readings(excursion_flag);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_scope ON events(scope_type, scope_id);

COMMIT;
```

### 2.3 CSV 데이터 → Oracle 로드

Python 스크립트 사용:

```python
# scripts/csv_to_oracle.py
import pandas as pd
import cx_Oracle
from pathlib import Path

# Oracle 연결
dsn = cx_Oracle.makedsn('localhost', 1521, service_name='XEPDB1')
conn = cx_Oracle.connect('supply_chain', 'SupplyChain123', dsn)

# CSV 파일 경로
data_dir = Path('../data')
pilot_dir = data_dir / 'pilot_missing_supporting_files'

# 데이터 로드 함수
def load_csv_to_oracle(csv_path, table_name):
    df = pd.read_csv(csv_path)
    df.to_sql(table_name, conn, if_exists='append', index=False, method='multi', chunksize=1000)
    print(f"✓ Loaded {len(df)} rows to {table_name}")

# 메인 데이터 로드
load_csv_to_oracle(data_dir / 'suppliers.csv', 'suppliers')
load_csv_to_oracle(data_dir / 'products.csv', 'products')
load_csv_to_oracle(data_dir / 'warehouses.csv', 'warehouses')
load_csv_to_oracle(data_dir / 'customers.csv', 'customers')
load_csv_to_oracle(data_dir / 'shipments.csv', 'shipments')

# Pilot 데이터 로드
load_csv_to_oracle(pilot_dir / 'lots.csv', 'lots')
load_csv_to_oracle(pilot_dir / 'shipments_lots.csv', 'shipments_lots')
load_csv_to_oracle(pilot_dir / 'cold_chain_readings.csv', 'cold_chain_readings')
load_csv_to_oracle(pilot_dir / 'sla_rules.csv', 'sla_rules')
load_csv_to_oracle(pilot_dir / 'lanes.csv', 'lanes')
load_csv_to_oracle(pilot_dir / 'events.csv', 'events')
load_csv_to_oracle(pilot_dir / 'costs.csv', 'costs')

conn.commit()
conn.close()
print("\n✓ All data loaded to Oracle successfully!")
```

---

## Phase 3: 애플리케이션 연결

### 3.1 Python 의존성 설치

```bash
# Oracle Instant Client 설치 필요 (macOS)
brew install instantclient-basic

# Python cx_Oracle 설치
uv add cx-oracle

# 또는
pip install cx-oracle
```

### 3.2 .env 파일 업데이트

```bash
# Oracle 연결 정보 추가
ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=XEPDB1
ORACLE_USER=supply_chain
ORACLE_PASSWORD=SupplyChain123
ORACLE_SCHEMA=supply_chain

# 데이터 소스 설정
ENABLED_DATA_SOURCES=ORACLE,NEO4J
PRIMARY_SUPPLIER_SOURCE=ORACLE
PRIMARY_PRODUCT_SOURCE=ORACLE
PRIMARY_WAREHOUSE_SOURCE=ORACLE
PRIMARY_SHIPMENT_SOURCE=ORACLE
```

### 3.3 Oracle Connector 코드 확인

프로젝트에 이미 구현되어 있음:
- `src/connectors/oracle_connector.py`

사용 예:

```python
from connectors.oracle_connector import OracleConnector

# Oracle에서 데이터 읽기
oracle = OracleConnector()
suppliers = oracle.get_suppliers()
products = oracle.get_products()

# 특정 쿼리 실행
query = """
SELECT s.shipment_id, s.supplier_id, l.lot_id, l.status
FROM shipments s
JOIN shipments_lots sl ON s.shipment_id = sl.shipment_id
JOIN lots l ON sl.lot_id = l.lot_id
WHERE l.recall_status = 'ACTIVE_RECALL'
"""
recalled_shipments = oracle.execute_query(query)
```

---

## Phase 4: Neo4j ↔ Oracle 동기화

### 4.1 동기화 전략

**Option A: Oracle → Neo4j (추천)**
- Oracle을 master data source로 사용
- 주기적으로 Neo4j 그래프 업데이트
- 그래프 분석 및 시각화는 Neo4j

**Option B: 양방향 동기화**
- Neo4j에서 생성된 시뮬레이션 결과를 Oracle에 저장
- Oracle의 실시간 데이터를 Neo4j에 반영

### 4.2 동기화 스크립트

```python
# scripts/sync_oracle_to_neo4j.py
from connectors.oracle_connector import OracleConnector
from data_loader import Neo4jConnection
from graph_builder import SupplyChainGraphBuilder

def sync_oracle_to_neo4j():
    oracle = OracleConnector()
    neo4j = Neo4jConnection()
    builder = SupplyChainGraphBuilder(neo4j)

    # Oracle에서 데이터 읽기
    suppliers = oracle.get_suppliers()
    products = oracle.get_products()
    warehouses = oracle.get_warehouses()
    shipments = oracle.get_shipments()
    lots = oracle.execute_query("SELECT * FROM lots")

    # Neo4j에 로드
    builder.load_suppliers(suppliers)
    builder.load_products(products)
    builder.load_warehouses(warehouses)
    builder.load_shipments(shipments)
    builder.load_lots(lots)

    print("✓ Oracle → Neo4j sync complete")

if __name__ == "__main__":
    sync_oracle_to_neo4j()
```

### 4.3 스케줄링 (선택사항)

```bash
# crontab으로 매일 자정에 동기화
0 0 * * * cd /path/to/project && python scripts/sync_oracle_to_neo4j.py
```

---

## 문제 해결

### Oracle 컨테이너가 시작되지 않음
```bash
# 로그 확인
docker logs oracle-supply-chain

# 볼륨 삭제 후 재시작
docker stop oracle-supply-chain
docker rm oracle-supply-chain
docker volume rm oracle-data
# 위의 docker run 명령어 재실행
```

### cx_Oracle 연결 오류
```bash
# Oracle Instant Client 경로 확인 (macOS)
export DYLD_LIBRARY_PATH=/usr/local/lib

# 연결 테스트
python -c "import cx_Oracle; print(cx_Oracle.clientversion())"
```

### 성능 이슈
```sql
-- Oracle 통계 업데이트
BEGIN
  DBMS_STATS.GATHER_SCHEMA_STATS('SUPPLY_CHAIN');
END;
/
```

---

## 다음 단계

1. ✅ CSV로 프로토타입 검증 완료
2. ✅ Oracle Database 실행 및 스키마 생성
3. ✅ 데이터 로드 및 연결 확인
4. 🎯 **Next:** 실제 SAP/Oracle ERP 시스템 연동 (ENTERPRISE_INTEGRATION.md 참고)

---

## 참고 문서

- [Oracle Database Express Edition](https://www.oracle.com/database/technologies/appdev/xe.html)
- [cx_Oracle Documentation](https://cx-oracle.readthedocs.io/)
- [프로젝트 Enterprise Integration 가이드](ENTERPRISE_INTEGRATION.md)
