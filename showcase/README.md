<div align="center">

# 🛡️ AML Guard
### Crypto Wallet AML Risk Analysis Platform

**Production SaaS · Telegram Mini App · Multi-chain · Self-hosted**

[![Status](https://img.shields.io/badge/Status-Live%20in%20Production-brightgreen?style=for-the-badge)](https://t.me/YOUR_BOT)
[![Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20Python%203.12-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Chains](https://img.shields.io/badge/Chains-ETH%20%7C%20TRON%20%7C%20BSC%20%7C%20SOL%20%7C%20TON-blue?style=for-the-badge)](https://github.com/daudbro73-collab/aml-guard)
[![License](https://img.shields.io/badge/License-Commercial%20%28Proprietary%29-red?style=for-the-badge)](LICENSE)

> ⚠️ **This is a showcase repository.** Source code is proprietary. This repo contains architecture documentation, API reference, and product demo materials.

</div>

---

## 🎯 What is AML Guard?

**AML Guard** is a production-ready Anti-Money Laundering (AML) compliance platform for crypto wallets. It gives individuals, exchanges, and compliance teams instant risk verdicts on blockchain addresses — across 5 major chains — in seconds.

The product is delivered as a **Telegram Mini App** with a full-featured backend API, PDF report generation, address monitoring, and a complete payment infrastructure.

---

## 📱 Product Demo

<div align="center">

> 🔴 **[Live Demo →](https://t.me/YOUR_BOT)** · Open in Telegram

</div>

---

## ✨ Core Features

### 🔎 Multi-Chain AML Screening
Real-time analysis of wallet addresses across **Ethereum, TRON, BNB Smart Chain, Solana, and TON** through a single unified API. Auto-detects chain from address format.

### ⚖️ Proprietary Risk Scoring Engine
Custom **exposure-weighted scoring algorithm** (v2) that evaluates:
- Direct & indirect counterparty exposure
- OFAC + custom sanctions list matching
- Mixer / tumbler pattern detection
- Fake asset (counterfeit USDT/USDC) identification
- Dust attack filtering (< $10 / < 0.5% volume)
- Behavioral clustering heuristics

Outputs a **0–100 risk score** with labeled confidence levels per signal.

### 📊 Interactive Transaction Graph
Multi-hop transaction flow visualization — shows funds flow across up to 3 hops with mixer detection and sanction flagging.

### 📄 PDF Compliance Reports
Branded, verifiable PDF reports with:
- SHA-256 content hash for tamper detection
- Unique report ID (AG-XXXXXX format)
- Public verification URL + QR code
- Arabic/RTL language support

### 💳 Payment Infrastructure
- **Telegram Stars** ⭐️ — native one-click payment inside Telegram
- **USDT multi-chain** — TRC-20, ERC-20, BEP-20, SPL
- Rotating deposit pool with pre-sweep AML screening
- Idempotent payment fulfillment

### 👁️ Address Monitoring
Subscribe to any address for automated re-screening at configurable intervals.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Telegram Clients                           │
│           Bot (aiogram 3)    +    Mini App (TWA)                │
└────────────────────┬────────────────────┬───────────────────────┘
                     │                    │
          Webhook / Long Poll      HTTPS REST API
                     │                    │
┌────────────────────▼────────────────────▼───────────────────────┐
│                      FastAPI Backend                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   /auth  │  │/payments │  │ /account │  │/monitors │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Services Layer                          │   │
│  │  risk_engine · chain · sanctions · graph · report_v2    │   │
│  │  billing · deposit_pool · payment_providers · workers   │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────┬─────────────────────────────────┬───────────────────┘
            │                                 │
     ┌──────▼──────┐                 ┌────────▼──────────┐
     │  PostgreSQL  │                 │      Redis 7      │
     │  SQLAlchemy  │                 │  Rate · Counters  │
     └─────────────┘                 └───────────────────┘
```

**Deployment:** Docker Compose · Cloudflare Tunnel (zero-trust HTTPS)
**Monitoring:** Sentry SDK · SlowAPI rate limiting (Cloudflare real-IP aware)

---

## 📊 Risk Score Breakdown

| Score | Level | CEX Verdict |
|-------|-------|-------------|
| 0–19 | ✅ **LOW** | Tier-1 eligible — free deposit |
| 20–39 | ⚠️ **CAUTION** | Enhanced Due Diligence (EDD) |
| 40–74 | 🚫 **HIGH** | Manual compliance review |
| 75–100 | ❌ **CRITICAL** | Block / Hard Reject |

Each risk factor includes signal type, confidence level (`low/medium/high`), and source attribution.

---

## 🌐 Supported Blockchains

| Chain | Auto-detect | Native | USDT | Tokens | Tx Graph | Sanctions |
|-------|:-----------:|:------:|:----:|:------:|:--------:|:---------:|
| Ethereum | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| TRON | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| BNB Smart Chain | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Solana | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| TON | ✅ | ✅ | ✅ | ✅ | — | ✅ |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Email registration → JWT |
| `POST` | `/auth/token` | Login → JWT |
| `POST` | `/auth/telegram` | Telegram initData → JWT |
| `GET` | `/auth/me` | User profile + permissions |
| `POST` | `/check` | Run AML check (1 credit) |
| `GET` | `/history` | Check history |
| `POST` | `/payments/create` | Create payment (Stars / USDT) |
| `POST` | `/payments/stars/webhook` | Stars fulfillment callback |
| `POST` | `/monitors/` | Add address to monitoring |
| `GET` | `/api/v1/verify/{id}` | Public report verification (JSON) |
| `GET` | `/p/{report_id}` | Shareable report page |

---

## 🛡️ Security Highlights

- **JWT** authentication (python-jose) with configurable expiry
- **Telegram `initData` HMAC** validation — prevents fake auth
- **Bcrypt** password hashing (passlib)
- **Rate limiting** per real IP — Cloudflare + X-Forwarded-For aware
- **OFAC pre-screening** on all incoming USDT deposits before crediting
- **Rotating deposit pool** — addresses cycled to prevent tracking
- **Report SHA-256 hashing** for tamper-proof verification

---

## 💡 Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Framework | FastAPI 0.111 |
| ORM | SQLAlchemy 2.0 |
| DB | SQLite (dev) / PostgreSQL 16 (prod) |
| Cache | Redis 7 |
| Bot | aiogram 3 |
| PDF | ReportLab 4 |
| Graph | Cytoscape.js |
| Auth | JWT + Telegram OAuth |
| Payments | Telegram Stars API + USDT multi-chain |
| Deployment | Docker Compose + Cloudflare Tunnel |
| Monitoring | Sentry SDK |
| Migrations | Alembic |
| Tests | pytest + pytest-asyncio |

---

## 📈 Pricing

| Tier | Price | Credits |
|------|-------|---------|
| Single Check | $1 / 50 ⭐️ | 1 |
| Pack 10 | $7 / 350 ⭐️ | 10 (-30%) |
| **Pack 20** | **$10 / 500 ⭐️** | **20 (HIT · $0.50/check)** |
| Balance top-up | Custom | Custom |

---

## 📬 Contact

**Built by Rustam Berheev**

- 💬 Telegram: `@YOUR_HANDLE`
- 🤖 Try it live: [t.me/YOUR_BOT](https://t.me/YOUR_BOT)

---

<div align="center">

*Source code is proprietary and not publicly available.*
*This repository is a portfolio showcase.*

</div>
