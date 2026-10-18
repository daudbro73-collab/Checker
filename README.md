<div align="center">
  <h1>🛡️ AML Guard</h1>
  <p><strong>Production-ready Anti-Money Laundering API for crypto compliance</strong><br/>
  Analyzes wallets across 5 blockchains · Scores risk 0–100 · Generates PDF reports · Runs inside Telegram</p>

  [![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
  [![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
  [![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
  [![Telegram](https://img.shields.io/badge/Telegram-Mini_App-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://core.telegram.org/bots/webapps)
  [![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
</div>

---

## What Is This?

AML Guard is a **full-stack compliance service** built for crypto exchanges, payment processors, and compliance teams who need to screen blockchain addresses before accepting deposits.

You submit a wallet address → the system fetches on-chain data across **5 networks** in parallel → runs it through a **custom risk scoring engine** (OFAC sanctions, counterparty exposure, behavioral heuristics) → returns a score from 0 to 100 with a detailed breakdown → optionally generates a signed **PDF report** for auditors.

The whole thing is exposed as a **REST API** and embedded as a **Telegram Mini App** with a credit-based billing system.

```
  Wallet Address
       │
       ▼
┌──────────────────────────────────────────────────┐
│  Chain Fetcher (async, parallel)                  │
│  ETH · TRON · BNB · Solana · TON                 │
└─────────────────────┬────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│  Risk Engine                                      │
│  ├─ OFAC sanctions scan      → score 0 or 100    │
│  ├─ Counterparty exposure    → weighted by volume │
│  ├─ Behavioral heuristics    → mixer / tumbler    │
│  ├─ Fake asset detection     → counterfeit USDT   │
│  └─ Label database 10k+      → CEX / DEX / dark  │
└─────────────────────┬────────────────────────────┘
                      │
                      ▼
        Risk Score  0 ──────────────────── 100
                   LOW   CAUTION  HIGH  CRITICAL
                      │
             ┌────────┴────────┐
             ▼                 ▼
         JSON API          PDF Report
      + Telegram         (ReportLab 4,
       Mini App           signed hash)
```

---

## Risk Levels

| Score | Label | Action |
|------:|-------|--------|
| **0 – 19** | ✅ LOW | Safe to proceed — Tier-1 CEX eligible |
| **20 – 39** | ⚠️ CAUTION | Enhanced Due Diligence recommended |
| **40 – 74** | 🚫 HIGH | Compliance review required before processing |
| **75 – 100** | ❌ CRITICAL | Hard block — OFAC hit or confirmed mixer |

---

## Supported Blockchains

| Chain | Native | USDT | Tokens | Tx Graph | Deep Graph |
|-------|:------:|:----:|:------:|:--------:|:----------:|
| Ethereum | ✅ | ✅ | ✅ | ✅ | ✅ |
| TRON | ✅ | ✅ | ✅ | ✅ | ✅ |
| BNB Smart Chain | ✅ | ✅ | ✅ | ✅ | ✅ |
| Solana | ✅ | ✅ | ✅ | ✅ | ✅ |
| TON | ✅ | ✅ | ✅ | ✅ | — |

---

## Key Features

- **Multi-hop graph expansion** — traces funds up to N hops deep, identifies indirect exposure to sanctioned entities
- **Rotating USDT deposit pool** — each user gets a unique deposit address, auto-screened against OFAC before crediting
- **Telegram Stars payments** — one-click credit purchases inside Telegram with idempotency guarantees
- **Background monitoring workers** — async Celery-style workers track flagged wallets continuously
- **Alembic migrations** — full schema versioning, zero-downtime upgrades
- **Rate limiting** — SlowAPI with Cloudflare real-IP awareness, per-user limits
- **Signed PDF reports** — each report has a unique verification URL (`/api/v1/verify/{id}`)
- **pytest test suite** — 12+ test modules covering payments, auth, graph, billing

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| API | FastAPI + uvicorn | Async, auto-OpenAPI, fastest Python framework |
| ORM | SQLAlchemy 2.0 | Async sessions, type-safe queries |
| DB | PostgreSQL 16 | JSONB for flexible tx data, full ACID |
| Cache | Redis 7 | Rate limiting, daily counters, dedup |
| Auth | JWT + HMAC (Telegram initData) | Dual auth: web + Telegram |
| PDF | ReportLab 4 | Full control over layout, fonts, charts |
| Graph UI | Cytoscape.js | Interactive transaction graph in browser |
| Payments | Telegram Stars + USDT (multi-chain) | No card required for users |
| Deploy | Docker Compose + Cloudflare Tunnel | Zero-port-exposure production setup |
| Migrations | Alembic | Versioned, reversible schema changes |
| Tests | pytest + pytest-asyncio | Async-native test runner |

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/auth/register` | — | Create account |
| `POST` | `/auth/token` | — | JWT login |
| `POST` | `/auth/telegram` | — | Telegram OAuth via initData HMAC |
| `GET` | `/auth/me` | 🔒 | Current user & credit balance |
| `POST` | `/check` | 🔒 | Run AML check (costs 1 credit) |
| `GET` | `/history` | 🔒 | Paginated check history |
| `POST` | `/payments/create` | 🔒 | Create Stars/USDT payment session |
| `POST` | `/payments/stars/webhook` | HMAC | Telegram Stars fulfillment callback |
| `GET` | `/api/v1/verify/{id}` | — | Public report verification |
| `GET` | `/graph/deep` | 🔒 | Multi-hop graph (depth, filters) |
| `POST` | `/monitors/` | 🔒 | Subscribe to wallet monitoring |

Full interactive docs: `http://localhost:8000/docs`

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/daudbro73-collab/Checker.git
cd Checker

# 2. Configure
cp .env.example backend/.env
# Edit: SECRET_KEY, BOT_TOKEN, OPENAI_API_KEY, blockchain API keys

# 3. Install
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Init DB
python -c "from database import init_db; init_db()"
python scripts/seed_admin.py

# 5. Run
uvicorn main:app --reload --port 8000
```

| URL | What |
|-----|------|
| `localhost:8000` | Landing page |
| `localhost:8000/webapp` | Telegram Mini App UI |
| `localhost:8000/docs` | Swagger / OpenAPI |

### Docker (Production)

```bash
cp .env.example .env   # fill all secrets
docker compose up -d   # starts api + postgres + redis + worker
```

---

## Project Structure

```
Checker/
├── backend/
│   ├── main.py               # FastAPI entry, lifespan, CORS
│   ├── config.py             # Pydantic Settings (env-driven)
│   ├── database.py           # SQLAlchemy models + init_db
│   ├── dependencies.py       # JWT guard, get_current_user
│   ├── routers/
│   │   ├── auth.py           # Register, login, Telegram OAuth
│   │   ├── payments.py       # Stars webhook, USDT, deposit pool
│   │   ├── account.py        # Profile, history, credit balance
│   │   └── monitors.py       # Wallet monitoring CRUD
│   ├── services/
│   │   ├── risk_engine.py    # ⭐ Core scoring (800+ lines)
│   │   ├── chain.py          # Async multi-chain fetcher
│   │   ├── sanctions.py      # OFAC + custom blocklist
│   │   ├── graph.py          # 1-hop transaction graph
│   │   ├── deep_graph.py     # N-hop recursive expansion
│   │   ├── report_v2.py      # PDF generator + signer
│   │   ├── billing.py        # Credit deduction + refunds
│   │   ├── deposit_pool.py   # Rotating address pool
│   │   └── payments/         # Stars + provider adapters
│   ├── alembic/              # DB migrations (versioned)
│   ├── tests/                # 12 pytest modules
│   └── templates/
│       ├── webapp.html       # Telegram Mini App (Cytoscape)
│       └── index.html        # Public landing page
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Security

- JWT tokens (python-jose) with configurable expiry + refresh
- Telegram `initData` validated via HMAC-SHA256 (bot token as key)
- Bcrypt password hashing (passlib, rounds=12)
- Rate limiting per real IP (SlowAPI + Cloudflare CF-Connecting-IP header)
- CORS restricted to explicit origin list
- All secrets via environment variables — nothing hardcoded
- OFAC screen runs **before** crediting any crypto deposit

---

## Tests

```bash
cd backend && pytest tests/ -v --tb=short
```

Covers: Stars fulfillment idempotency · Stars↔USD conversion · USDT payment sessions · JWT auth flow · HMAC Telegram validation · graph expansion depth · deposit pool rotation · billing deductions

---

<div align="center">
  <strong>Built by Rustam Berheev</strong><br/>
  <a href="https://github.com/daudbro73-collab">github.com/daudbro73-collab</a>
</div>
