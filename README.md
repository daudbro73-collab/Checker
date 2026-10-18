<div align="center">

# 🛡️ AML Guard

**Crypto wallet AML checker with risk scoring, transaction graph, and PDF reports**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

[🚀 Live Demo](#) · [📖 API Docs](#) · [🤖 Telegram Bot](#)

</div>

---

## 📋 Overview

**AML Guard** is a production-grade Anti-Money Laundering service for crypto compliance teams and exchanges. It analyzes blockchain wallet addresses across 5 networks, scores them by risk level using a proprietary engine, and generates professional PDF reports — all accessible via a Telegram Mini App or REST API.

```
Input: crypto wallet address
  ↓
Multi-chain data fetch (ETH / TRON / BNB / SOL / TON)
  ↓
Risk Engine: OFAC scan + counterparty exposure + behavioral heuristics
  ↓
Risk Score 0–100 → LOW / CAUTION / HIGH / CRITICAL
  ↓
Output: JSON response + PDF report + Telegram notification
```

---

## ⚡ Risk Score Levels

| Score | Level | Meaning |
|-------|-------|---------|
| 0–19 | ✅ **LOW** | Clean — Tier-1 CEX eligible |
| 20–39 | ⚠️ **CAUTION** | Enhanced Due Diligence recommended |
| 40–74 | 🚫 **HIGH** | Manual Compliance / EDD required |
| 75–100 | ❌ **CRITICAL** | Block / Hard Reject |

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

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Telegram Mini App                      │
│              (webapp.html — Cytoscape.js)               │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTPS
┌─────────────────────▼───────────────────────────────────┐
│                    FastAPI Backend                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │   auth   │  │ payments │  │ account  │  │monitor │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Services Layer                        │  │
│  │  risk_engine │ chain │ sanctions │ graph │ report  │  │
│  └───────────────────────────────────────────────────┘  │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
    ┌──────▼──────┐              ┌────────▼────────┐
    │  PostgreSQL │              │      Redis       │
    │  SQLAlchemy │              │  (rate limiting) │
    └─────────────┘              └─────────────────┘
```

---

## 🔬 Risk Engine Details

- **Counterparty exposure** — weighted by transaction volume, not raw counts
- **Dust filtering** — ignores airdrops < $10 / < 0.5% of wallet volume
- **OFAC sanctions matching** — direct hits score 100 (instant CRITICAL)
- **Fake asset detection** — identifies counterfeit USDT/USDC tokens
- **Behavioral heuristics** — mixer/tumbler patterns, round-amount clustering, rapid chaining
- **Label-based scoring** — 10 000+ known entities (CEX, DEX, bridges, darknet markets)
- **Signal confidence levels** — `low / medium / high` with source attribution

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Redis
- Docker + Docker Compose (for production)

### 1. Clone & setup

```bash
git clone https://github.com/daudbro73-collab/Checker.git
cd Checker
cp .env.example backend/.env
# Edit backend/.env with your API keys
```

### 2. Install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Initialize DB

```bash
python -c "from database import init_db; init_db()"
python scripts/seed_admin.py
```

### 4. Run

```bash
uvicorn main:app --reload --port 8000
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Landing page |
| `http://localhost:8000/webapp` | Telegram Mini App |
| `http://localhost:8000/docs` | Swagger API docs |

---

## 🐳 Docker Compose (Production)

```bash
cp .env.example .env
# Fill: SECRET_KEY, BOT_TOKEN, OPENAI_API_KEY, payment addresses

docker compose up -d
```

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8002 | FastAPI application |
| `postgres` | 5432 | PostgreSQL 16 database |
| `redis` | 6379 | Redis 7 cache |
| `worker` | — | Background sync worker |

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

Full Swagger docs at `/docs`.

---

## 💡 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.12 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Cache | Redis 7 |
| Auth | JWT (python-jose), Telegram Bot API |
| PDF Reports | ReportLab 4 |
| Graph | Cytoscape.js |
| Payments | Telegram Stars, USDT multi-chain |
| Deployment | Docker Compose, Cloudflare Tunnel |
| Migrations | Alembic |
| Tests | pytest, pytest-asyncio |

---

## 📁 Project Structure

```
Checker/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Environment-driven settings
│   ├── database.py             # SQLAlchemy models
│   ├── dependencies.py         # Auth guards, DI
│   ├── routers/
│   │   ├── auth.py             # JWT + Telegram OAuth
│   │   ├── payments.py         # Stars, USDT, deposit pool
│   │   ├── account.py          # History, profile
│   │   └── monitors.py         # Wallet monitoring
│   ├── services/
│   │   ├── risk_engine.py      # ⭐ Core AML scoring engine
│   │   ├── chain.py            # Multi-chain data fetcher
│   │   ├── sanctions.py        # OFAC + blocklist matching
│   │   ├── graph.py            # Transaction graph builder
│   │   ├── deep_graph.py       # Multi-hop graph expansion
│   │   ├── report_v2.py        # PDF report generator
│   │   ├── billing.py          # Credit system
│   │   └── deposit_pool.py     # Rotating USDT deposit pool
│   ├── templates/
│   │   ├── webapp.html         # Telegram Mini App UI
│   │   └── index.html          # Landing page
│   ├── alembic/                # DB migrations
│   └── tests/                  # pytest test suite
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 🛡️ Security

- **JWT** authentication with configurable expiry
- **HMAC validation** of Telegram `initData`
- **Bcrypt** password hashing (passlib)
- **Rate limiting** via SlowAPI (Cloudflare-aware real IP)
- **CORS** restricted to known origins
- **No hardcoded secrets** — 100% environment variables
- **OFAC screening** before crediting any deposit

---

## 🧪 Tests

```bash
cd backend && pytest tests/ -v
```

Covers: Stars payment fulfillment, Stars↔USD conversion, payment provider sessions, auth flows, graph expansion, deposit pool logic.

---

<div align="center">

Built with ❤️ by **Rustam Berheev**

[![GitHub](https://img.shields.io/badge/GitHub-daudbro73--collab-181717?style=flat-square&logo=github)](https://github.com/daudbro73-collab)

</div>
