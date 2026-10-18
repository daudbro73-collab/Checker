<div align="center">

# 🛡️ AML Guard

**Crypto Wallet AML Risk Analysis Platform**

*Professional-grade Anti-Money Laundering screening for blockchain addresses*

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?style=for-the-badge&logo=python&logoColor=white)](https://sqlalchemy.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Telegram](https://img.shields.io/badge/Telegram-Mini_App-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots/webapps)

---

> **AML Guard** is a full-stack crypto compliance platform that performs real-time Anti-Money Laundering (AML) checks on blockchain wallet addresses across multiple chains. It provides risk scoring, transaction graph analysis, PDF compliance reports, and a Telegram Mini App — all self-hosted.

</div>

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔎 **Multi-Chain Analysis** | ETH, TRON, BSC, Solana, TON — one API |
| ⚖️ **Risk Scoring Engine** | Exposure-weighted scoring v2 with dust filtering |
| 🚨 **Sanctions Screening** | OFAC + custom blocklists, real-time |
| 📊 **Transaction Graph** | Interactive multi-hop flow visualization (Cytoscape.js) |
| 📄 **PDF Reports** | Branded compliance PDFs with QR verification |
| 🤖 **Telegram Mini App** | Native Telegram Web App with full UX |
| 💳 **Payments** | Telegram Stars ⭐️ + USDT (TRC-20, ERC-20, SOL, BSC) |
| 👁️ **Address Monitoring** | Automated re-screening with configurable intervals |
| 🔗 **Referral System** | Built-in affiliate tracking |
| 🔐 **Auth** | JWT + Telegram OAuth (init_data HMAC validation) |
| 📤 **Public Verify** | Shareable report links with expiry |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Telegram Mini App                       │
│              (webapp.html — Jinja2 + Vanilla JS)            │
└───────────────────────┬─────────────────────────────────────┘
                        │ REST API (JWT Bearer)
┌───────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   auth   │  │ payments │  │ account  │  │ monitors │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Services Layer                           │  │
│  │  risk_engine │ chain │ sanctions │ graph │ report_v2  │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────┬──────────────────────────────┬───────────────────┘
           │                              │
    ┌──────▼──────┐              ┌────────▼────────┐
    │  SQLite /   │              │      Redis       │
    │ PostgreSQL  │              │  (rate limiting, │
    │  SQLAlchemy │              │   daily counters)│
    └─────────────┘              └─────────────────┘
```

---

## 🔬 Risk Scoring Engine

The core of AML Guard is a custom **exposure-weighted risk engine** (`services/risk_engine.py`):

- **Counterparty exposure analysis** — weighted by transaction volume (not raw counts)
- **Dust filtering** — ignores airdrops < $10 / < 0.5% of wallet volume
- **OFAC sanctions matching** — direct hits score 100 (instant CRITICAL)
- **Fake asset detection** — identifies counterfeit USDT/USDC tokens
- **Behavioral heuristics** — mixer/tumbler patterns, round-amount clustering, rapid chaining
- **Label-based scoring** — uses known entity database (CEX, DEX, bridges, darknet markets)
- **Signal confidence levels** — `low / medium / high` with source attribution

```
Risk levels:
  0–19   →  LOW       (✅ Clean — Tier-1 CEX eligible)
  20–39  →  CAUTION   (⚠️  Enhanced Due Diligence)
  40–74  →  HIGH      (🚫 Manual Compliance / EDD)
  75–100 →  CRITICAL  (❌ Block / Hard Reject)
```

---

## 🌐 Supported Blockchains

| Chain | Native | USDT | Token Scan | Tx Graph |
|-------|--------|------|-----------|---------|
| Ethereum (ETH) | ✅ | ✅ | ✅ | ✅ |
| TRON (TRX) | ✅ | ✅ | ✅ | ✅ |
| BNB Smart Chain | ✅ | ✅ | ✅ | ✅ |
| Solana (SOL) | ✅ | ✅ | ✅ | ✅ |
| TON | ✅ | ✅ | ✅ | — |

---

## 🚀 Quick Start (Local)

### Prerequisites
- Python 3.12+
- Redis (optional for dev)
- Docker + Docker Compose (for prod)

### 1. Clone & setup

```bash
git clone https://github.com/YOUR_USERNAME/aml-guard.git
cd aml-guard

cp .env.example backend/.env
# Edit backend/.env with your settings
```

### 2. Install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Initialize DB & seed admin

```bash
python -c "from database import init_db; init_db()"
python scripts/seed_admin.py
```

### 4. Run

```bash
uvicorn main:app --reload --port 8000
```

Open **http://127.0.0.1:8000** → Landing page  
Open **http://127.0.0.1:8000/webapp** → Mini App  
Open **http://127.0.0.1:8000/docs** → Swagger API docs

---

## 🐳 Docker Compose (Production)

```bash
cp .env.example .env
# Fill in SECRET_KEY, BOT_TOKEN, payment addresses

docker compose up -d
```

Services started:
- `api` — FastAPI on port 8002
- `postgres` — PostgreSQL 16
- `redis` — Redis 7
- `worker` — background sync worker

---

## 📁 Project Structure

```
aml-guard/
├── backend/
│   ├── main.py                 # FastAPI app, routes, startup
│   ├── config.py               # Settings (env-driven)
│   ├── database.py             # SQLAlchemy models
│   ├── dependencies.py         # Auth guards, DI
│   ├── routers/
│   │   ├── auth.py             # JWT + Telegram OAuth
│   │   ├── payments.py         # Stars, USDT, deposit pool
│   │   ├── account.py          # Check history, profile
│   │   └── monitors.py         # Address monitoring
│   ├── services/
│   │   ├── risk_engine.py      # Core AML scoring engine
│   │   ├── chain.py            # Multi-chain data fetcher
│   │   ├── sanctions.py        # OFAC + blocklist matching
│   │   ├── graph.py            # Transaction graph builder
│   │   ├── deep_graph.py       # Multi-hop graph expansion
│   │   ├── report_v2.py        # PDF report generator
│   │   ├── analysis.py         # Analysis orchestration
│   │   ├── billing.py          # Credit system
│   │   ├── deposit_pool.py     # Rotating USDT deposit pool
│   │   └── payments/           # Payment providers
│   ├── templates/
│   │   ├── webapp.html         # Telegram Mini App
│   │   └── index.html          # Landing page
│   ├── scripts/
│   │   └── seed_admin.py       # Admin user setup
│   ├── alembic/                # DB migrations
│   └── tests/                  # pytest test suite
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 🔌 API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Email registration |
| `POST` | `/auth/token` | JWT login |
| `POST` | `/auth/telegram` | Telegram OAuth (init_data) |
| `GET` | `/auth/me` | Current user profile |
| `POST` | `/check` | Run AML check (1 credit) |
| `GET` | `/history` | Check history |
| `POST` | `/payments/create` | Create payment session |
| `POST` | `/payments/stars/webhook` | Telegram Stars callback |
| `GET` | `/api/v1/verify/{id}` | Public report verification |
| `GET` | `/graph/deep` | Multi-hop graph expansion |
| `POST` | `/monitors/` | Add wallet to monitoring |

Full Swagger docs available at `/docs` when running locally.

---

## 🛡️ Security

- **JWT** (python-jose) with configurable expiry
- **HMAC validation** of Telegram `initData`
- **Bcrypt** password hashing (passlib)
- **Rate limiting** via SlowAPI (per real IP, Cloudflare-aware)
- **CORS** restricted to known origins
- **No hardcoded secrets** — all via environment variables
- **OFAC screening** before crediting any deposit

---

## 🧪 Tests

```bash
cd backend
pytest tests/ -v
```

Test coverage includes:
- Telegram Stars payment fulfillment & idempotency
- Stars ↔ USD conversion
- Payment provider checkout sessions
- Auth flows

---

## 💡 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.12 |
| ORM | SQLAlchemy 2.0 |
| DB | SQLite (dev) / PostgreSQL 16 (prod) |
| Cache | Redis 7 |
| Auth | JWT, Telegram Bot API |
| PDF | ReportLab 4 |
| Graph | Cytoscape.js |
| Payments | Telegram Stars, USDT multi-chain |
| Deployment | Docker Compose, Cloudflare Tunnel |
| Monitoring | Sentry |
| Migrations | Alembic |
| Tests | pytest, pytest-asyncio |

---

## 📜 License

MIT — free to use, fork, and build upon.

---

<div align="center">

Built with ❤️ by **Rustam Berheev**

[Telegram Bot](https://t.me/YOUR_BOT) · [Live Demo](https://YOUR_DOMAIN/webapp) · [API Docs](https://YOUR_DOMAIN/docs)

</div>
