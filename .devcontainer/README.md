# 🐳 Dev Container 가이드

이 문서는 Mini Foundry Supply Chain 프로젝트를 Dev Container를 통해 개발하는 방법을 설명합니다.

## 📚 목차

1. [Dev Container란?](#dev-container란)
2. [왜 Dev Container를 사용하나요?](#왜-dev-container를-사용하나요)
3. [사전 요구사항](#사전-요구사항)
4. [설정 방법](#설정-방법)
5. [실행 방법](#실행-방법)
6. [환경 구조](#환경-구조)
7. [자주 묻는 질문](#자주-묻는-질문)
8. [문제 해결](#문제-해결)

---

## Dev Container란?

**Dev Container**(Development Container)는 Docker 컨테이너를 사용하여 **일관된 개발 환경**을 제공하는 기술입니다.

### 핵심 개념

```
┌─────────────────────────────────────────────┐
│  VS Code (로컬 환경)                         │
│  ├── 에디터 UI                                │
│  └── Remote - Containers Extension          │
│                  ↓                           │
│  ┌─────────────────────────────────────┐   │
│  │  Docker Container (격리된 환경)       │   │
│  │  ├── Python 3.12                     │   │
│  │  ├── uv (패키지 관리자)               │   │
│  │  ├── 프로젝트 코드 (마운트)           │   │
│  │  ├── Neo4j (데이터베이스)            │   │
│  │  └── 모든 의존성                     │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

- **로컬**에서는 VS Code만 실행
- **코드 실행, 디버깅, 터미널**은 모두 컨테이너 안에서 동작
- 프로젝트 폴더는 컨테이너에 **마운트**되어 실시간 동기화

---

## 왜 Dev Container를 사용하나요?

### ✅ 장점

| 항목 | 로컬 환경 | Dev Container |
|------|-----------|---------------|
| **환경 일관성** | ❌ 개발자마다 다름 | ✅ 모두 동일 |
| **Python 버전** | ❌ 시스템 Python 충돌 가능 | ✅ 3.12 고정 |
| **의존성 관리** | ❌ requirements.txt만 | ✅ uv로 완벽 관리 |
| **Neo4j 연동** | ❌ 별도 설치 필요 | ✅ docker-compose로 자동 |
| **신규 팀원 온보딩** | ❌ 수동 설정 필요 | ✅ 클릭 한 번으로 완료 |
| **환경 격리** | ❌ 시스템 오염 가능 | ✅ 완전 격리 |

### 💡 주요 이점

1. **"내 컴퓨터에서는 되는데..." 문제 해결**
   - 모든 개발자가 동일한 환경에서 작업

2. **Neo4j 자동 설정**
   - `docker-compose`가 Neo4j를 자동으로 시작
   - 연결 설정도 자동 구성

3. **깨끗한 로컬 환경 유지**
   - 로컬 시스템에 Python, 패키지 설치 불필요
   - 컨테이너만 삭제하면 완전히 제거 가능

---

## 사전 요구사항

### 필수 설치

1. **Docker** (Colima를 통해 이미 설치됨 ✅)
   ```bash
   # Colima 상태 확인
   colima status

   # 실행 중이 아니면 시작
   colima start
   ```

2. **Visual Studio Code**
   ```bash
   # Homebrew로 설치
   brew install --cask visual-studio-code
   ```

3. **Dev Containers Extension**
   - VS Code에서 `Cmd+Shift+X`
   - "Dev Containers" 검색 후 설치
   - 또는: https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers

### 확인 방법

```bash
# Docker 동작 확인
docker ps

# VS Code 설치 확인
code --version
```

---

## 설정 방법

### 1️⃣ 환경변수 파일 생성

```bash
# 프로젝트 루트로 이동
cd /Users/seungholee/Workspace/mini-foundry-supplychain

# .env 파일 생성
cp .env.example .env
```

**`.env` 파일 예시:**
```env
# Dev Container용 Neo4j 설정
NEO4J_URI=neo4j://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123

# 기타 설정은 필요에 따라 수정
DEBUG=true
ENVIRONMENT=development
```

### 2️⃣ Colima 확인

Dev Container는 Colima를 Docker 백엔드로 사용합니다.

```bash
# Colima 상태 확인
colima status

# 실행 중이 아니면 시작
colima start

# Docker 연결 확인
docker ps
```

---

## 실행 방법

### 방법 1: VS Code UI 사용 (추천)

1. **프로젝트 열기**
   ```bash
   cd /Users/seungholee/Workspace/mini-foundry-supplychain
   code .
   ```

2. **Dev Container 시작**
   - VS Code 좌측 하단 **초록색 아이콘** 클릭 (><)
   - 또는 `Cmd+Shift+P` → "Dev Containers: Reopen in Container"

3. **자동 진행 과정**
   ```
   ┌─────────────────────────────────────┐
   │ 1. Docker 이미지 빌드 (최초 1회)     │
   │    └─> Python 3.12 + uv 설치        │
   ├─────────────────────────────────────┤
   │ 2. docker-compose 실행              │
   │    ├─> app 컨테이너 시작            │
   │    └─> Neo4j 컨테이너 시작          │
   ├─────────────────────────────────────┤
   │ 3. postCreateCommand 실행           │
   │    └─> uv sync --all-groups         │
   │       (모든 의존성 자동 설치)        │
   ├─────────────────────────────────────┤
   │ 4. VS Code 연결                     │
   │    └─> 컨테이너 내부로 진입         │
   └─────────────────────────────────────┘
   ```

4. **완료!**
   - 터미널에 `✅ Dev Container Ready!` 메시지 표시
   - 프롬프트: `vscode@devcontainer:/workspace$`

### 방법 2: 명령 팔레트 사용

```
Cmd+Shift+P
→ "Dev Containers: Rebuild and Reopen in Container"
```

### 방법 3: CLI 사용

```bash
# VS Code에서 devcontainer CLI 사용
code --folder-uri vscode-remote://dev-container+$(pwd)
```

---

## 환경 구조

### 파일 구조

```
mini-foundry-supplychain/
├── .devcontainer/
│   ├── devcontainer.json      # Dev Container 설정
│   ├── Dockerfile             # 컨테이너 이미지 정의
│   ├── docker-compose.yml     # 멀티 컨테이너 구성
│   └── README.md              # 이 문서
├── .env                       # 환경변수 (git에 포함 안 됨)
├── .env.example               # 환경변수 템플릿
├── pyproject.toml             # uv 프로젝트 설정
└── uv.lock                    # 의존성 잠금 파일
```

### 컨테이너 구성

```yaml
# docker-compose.yml
services:
  app:           # 메인 개발 컨테이너
    - Python 3.12
    - uv 패키지 매니저
    - 프로젝트 코드 (/workspace에 마운트)
    - 포트: 8501 (Streamlit)

  neo4j:         # 데이터베이스 컨테이너
    - Neo4j 5.15 Community
    - 포트: 7474 (Browser), 7687 (Bolt)
    - 자동 인증: neo4j/password123
```

### 볼륨 관리

```yaml
volumes:
  uv-cache:      # uv 캐시 (빠른 재빌드)
  venv:          # Python 가상환경 (.venv)
  neo4j-data:    # Neo4j 데이터 (영구 저장)
  neo4j-logs:    # Neo4j 로그
  neo4j-plugins: # Neo4j 플러그인 (APOC 등)
```

---

## 개발 워크플로우

### 일반적인 작업 흐름

```bash
# 1. Dev Container 시작
# (VS Code에서 "Reopen in Container")

# 2. 컨테이너 내부 터미널에서 작업
vscode@devcontainer:/workspace$

# 3. 의존성 추가 (필요시)
uv add pandas

# 4. 애플리케이션 실행
uv run python main.py
# 또는
uv run streamlit run dashboard/app.py

# 5. Neo4j 브라우저 접속
# http://localhost:7474
# ID: neo4j / PW: password123

# 6. 코드 수정 (VS Code 에디터)
# 파일 저장 시 자동으로 컨테이너에 반영됨
```

### 주요 명령어

```bash
# 의존성 동기화
uv sync

# 개발 도구 포함 동기화
uv sync --all-groups

# 패키지 추가
uv add <package-name>

# 개발 패키지 추가
uv add --dev <package-name>

# Python 실행
uv run python script.py

# Streamlit 실행
uv run streamlit run dashboard/app.py

# 테스트 실행
uv run pytest
```

---

## 포트 포워딩

Dev Container는 자동으로 포트를 로컬에 포워딩합니다:

| 서비스 | 컨테이너 | 로컬 | 용도 |
|--------|----------|------|------|
| Streamlit | 8501 | 8501 | http://localhost:8501 |
| Neo4j Browser | 7474 | 7474 | http://localhost:7474 |
| Neo4j Bolt | 7687 | 7687 | neo4j://localhost:7687 |

### 확인 방법

```bash
# VS Code 하단 "PORTS" 탭에서 확인
# 또는 터미널에서
docker ps
```

---

## VS Code 확장 기능

Dev Container 시작 시 자동으로 설치되는 확장:

- **ms-python.python**: Python 기본 지원
- **ms-python.vscode-pylance**: 타입 체킹, 자동완성
- **ms-python.black-formatter**: 코드 포매팅
- **charliermarsh.ruff**: 린팅
- **neo4j.neo4j**: Neo4j 쿼리 지원
- **ms-azuretools.vscode-docker**: Docker 관리

---

## 자주 묻는 질문

### Q1. 로컬 uv 환경과 충돌하지 않나요?

**A:** 충돌하지 않습니다!
- 로컬 `.venv`와 컨테이너 `.venv`는 별도로 관리됩니다
- 컨테이너 `.venv`는 Docker 볼륨에 저장되어 분리됩니다

### Q2. 기존 로컬 환경 데이터는 어떻게 되나요?

**A:** 영향 없습니다!
- 로컬 Neo4j 데이터베이스와 별개로 동작
- `.env` 파일에서 연결 정보를 구분하여 관리

### Q3. 컨테이너를 종료하면 데이터가 사라지나요?

**A:** 아닙니다!
- Neo4j 데이터는 `neo4j-data` 볼륨에 영구 저장
- `.venv`도 `venv` 볼륨에 보존
- 컨테이너 재시작 시에도 유지됨

### Q4. 로컬과 Dev Container를 번갈아 사용할 수 있나요?

**A:** 가능합니다!
- `.env` 파일에서 `NEO4J_URI`만 변경
- 로컬: `bolt://localhost:7687`
- 컨테이너: `neo4j://neo4j:7687`

### Q5. Colima 대신 Docker Desktop을 사용할 수 있나요?

**A:** 네!
- Colima를 중지하고 Docker Desktop 실행
- Dev Container는 동일하게 동작합니다

### Q6. 빌드가 너무 오래 걸려요

**A:** 최초 빌드는 10-15분 소요될 수 있습니다
```bash
# 캐시 활용하여 재빌드
Cmd+Shift+P → "Dev Containers: Rebuild Container"

# 완전히 새로 빌드 (캐시 무시)
Cmd+Shift+P → "Dev Containers: Rebuild Without Cache"
```

---

## 문제 해결

### ❌ "Cannot connect to the Docker daemon"

**증상:**
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

**해결:**
```bash
# Colima 재시작
colima stop
colima start

# Docker 연결 확인
docker ps
```

### ❌ "Port 8501 is already in use"

**증상:**
```
Error: Port 8501 is already allocated
```

**해결:**
```bash
# 로컬에서 실행 중인 Streamlit 종료
pkill -f streamlit

# 또는 docker-compose 재시작
cd .devcontainer
docker-compose down
docker-compose up -d
```

### ❌ "Neo4j connection failed"

**증상:**
```
Failed to connect to neo4j://neo4j:7687
```

**해결:**
```bash
# Neo4j 컨테이너 상태 확인
docker ps | grep neo4j

# Neo4j 로그 확인
docker logs <neo4j-container-id>

# 컨테이너 재시작
cd .devcontainer
docker-compose restart neo4j
```

### ❌ "uv sync 실패"

**증상:**
```
error: Failed to download distributions
```

**해결:**
```bash
# 컨테이너 내부에서
uv cache clean
uv sync --all-groups

# 또는 컨테이너 재빌드
# VS Code: Cmd+Shift+P → "Rebuild Container"
```

### ❌ VS Code가 컨테이너에 연결되지 않음

**해결 순서:**
1. Colima 재시작
   ```bash
   colima restart
   ```

2. Dev Containers 확장 재설치
   - VS Code에서 확장 제거 → 재설치

3. 컨테이너 완전히 제거 후 재생성
   ```bash
   cd .devcontainer
   docker-compose down -v  # 볼륨까지 삭제
   # VS Code에서 "Rebuild Container"
   ```

---

## 추가 리소스

### 공식 문서
- [Dev Containers 공식 문서](https://containers.dev/)
- [VS Code Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers)
- [uv 문서](https://docs.astral.sh/uv/)

### 유용한 명령어 모음

```bash
# === Dev Container 관리 ===
# VS Code 명령 팔레트 (Cmd+Shift+P)에서:
# - "Dev Containers: Rebuild Container"
# - "Dev Containers: Reopen Folder Locally"
# - "Dev Containers: Show Container Log"

# === Docker 관리 ===
# 컨테이너 목록
docker ps -a

# 이미지 목록
docker images

# 볼륨 목록
docker volume ls

# 디스크 사용량
docker system df

# 정리 (사용하지 않는 리소스)
docker system prune

# === Neo4j ===
# 브라우저 접속
open http://localhost:7474

# 컨테이너 로그
docker logs <container-name>

# Cypher 쿼리 실행 (컨테이너 내부)
docker exec -it <neo4j-container> cypher-shell -u neo4j -p password123
```

---

## 📝 요약

### Dev Container 시작하기

1. **준비**
   ```bash
   colima start
   cp .env.example .env
   code .
   ```

2. **실행**
   - VS Code 좌측 하단 초록 아이콘 클릭
   - "Reopen in Container" 선택

3. **개발**
   ```bash
   uv run streamlit run dashboard/app.py
   ```

4. **접속**
   - Streamlit: http://localhost:8501
   - Neo4j: http://localhost:7474

### 핵심 이점
- ✅ 일관된 Python 3.12 + uv 환경
- ✅ Neo4j 자동 설정 및 연동
- ✅ 로컬 환경 오염 없음
- ✅ 팀 협업 시 환경 문제 제로

---

**문제가 발생하면:**
1. 이 문서의 [문제 해결](#문제-해결) 섹션 참고
2. Colima 재시작: `colima restart`
3. 컨테이너 재빌드: VS Code에서 "Rebuild Container"

**Happy Coding! 🚀**
