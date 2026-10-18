import json
import logging
import os
import secrets
import tempfile
from datetime import datetime, timedelta
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from config import get_settings
from database import CheckHistory, ListSnapshot, User, init_db
from dependencies import get_api_user, get_current_user, get_optional_user, get_db
from routers import auth
from routers import payments
from routers import account
from routers import monitors
from services.analysis import analyze_wallet, serialize_payload
from services.billing import can_afford_check, charge_for_check
from services.address_validation import detect_input_kind
from services.graph_expander import GraphExpanderService
from services.redis_client import count_and_incr_daily, get_redis, peek_daily
from services.report_v2 import create_premium_pdf, compute_report_metadata
from services.translations import get_trans, SUPPORTED_LANGS

settings = get_settings()
ALLOWED_CHAINS = settings.ALLOWED_CHAINS

def get_real_client_ip(request: Request) -> str:
    """
    Safely extract real client IP behind Nginx, Cloudflare, or Docker reverse proxies.
    1. CF-Connecting-IP (Cloudflare)
    2. X-Forwarded-For (leftmost client IP)
    3. X-Real-IP
    4. request.client.host fallback
    """
    if not request:
        return "127.0.0.1"

    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


# Rate limiter — ключ по реальному IP клиента
limiter = Limiter(key_func=get_real_client_ip)

# Optional Sentry
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
    except Exception:
        pass

app = FastAPI(title="AML Guard API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    max_age=3600,
)
init_db()


@app.on_event("startup")
def _bootstrap_deposit_pool():
    """Sync 10 active deposit addresses from env on boot."""
    try:
        from database import SessionLocal
        from services.deposit_pool import sync_all_pools
        db = SessionLocal()
        try:
            sync_all_pools(db)
        finally:
            db.close()
    except Exception as e:
        print(f"deposit pool bootstrap: {e}")


app.include_router(auth.router)
app.include_router(account.router)
app.include_router(monitors.router)
app.include_router(payments.router)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)


@app.get("/health")
def health():
    from database import SessionLocal
    from sqlalchemy import text

    status = {"status": "ok", "checks": {}}

    # Одна сессия — гарантированно закрывается через context manager
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            status["checks"]["database"] = "ok"

            latest = db.query(ListSnapshot).order_by(ListSnapshot.synced_at.desc()).first()
            if latest and latest.synced_at:
                age_h = (datetime.utcnow() - latest.synced_at).total_seconds() / 3600
                status["checks"]["lists_age_hours"] = round(age_h, 1)
                status["checks"]["lists_stale"] = age_h > 48
                if age_h > 168:
                    status["status"] = "degraded"
            else:
                status["checks"]["lists"] = "never_synced"
    except Exception as e:
        status["checks"]["database"] = f"error: {e}"
        status["status"] = "degraded"

    r = get_redis()
    status["checks"]["redis"] = "ok" if r else "fallback_memory"

    status["chains"] = sorted(ALLOWED_CHAINS)
    status["price_per_check"] = settings.PRICE_PER_CHECK
    return status


@app.get("/")
def read_root(request: Request, lang: str = "en"):
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    return templates.TemplateResponse("index.html", {"request": request, "trans": get_trans(lang), "lang": lang})


@app.get("/webapp")
def read_webapp(request: Request, lang: str = "en"):
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    return templates.TemplateResponse("webapp.html", {"request": request, "trans": get_trans(lang), "lang": lang})


@app.get("/privacy")
def privacy_page(request: Request, lang: str = "en"):
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    return templates.TemplateResponse("privacy.html", {"request": request, "trans": get_trans(lang), "lang": lang})


@app.get("/terms")
def terms_page(request: Request, lang: str = "en"):
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    return templates.TemplateResponse("terms.html", {"request": request, "trans": get_trans(lang), "lang": lang})


def _save_check(db: Session, user_id, result: dict, is_free: bool = False) -> CheckHistory:
    share_token = secrets.token_urlsafe(16)
    created_now = datetime.utcnow()
    report_id, sha256_hash, exp_date = compute_report_metadata(
        result.get("chain", "ETH"),
        result.get("address", ""),
        result.get("risk_score", 0),
        created_now,
    )
    result["report_id"] = report_id
    result["sha256"] = sha256_hash
    result["exp_date"] = exp_date

    row = CheckHistory(
        user_id=user_id,
        address=result["address"],
        chain=result["chain"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        payload_json=serialize_payload(result),
        list_versions_json=json.dumps(result.get("list_versions") or {}),
        is_free=is_free,
        share_token=share_token,
        share_expires_at=created_now + timedelta(days=7),
        report_id=report_id,
        sha256_hash=sha256_hash,
        created_at=created_now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/check-free")
@limiter.limit("10/minute")
async def check_wallet_free(
    request: Request,
    address: str = Query(..., max_length=200, description="Wallet address to check"),
    chain: str = Query("ETH", max_length=10),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Trial check (full demo) — limited per IP/day. Not a stripped express mode."""
    client_ip = get_real_client_ip(request)
    remaining_before = peek_daily(f"free:{client_ip}", settings.FREE_CHECKS_PER_DAY)
    if remaining_before <= 0:
        raise HTTPException(status_code=429, detail="FREE_LIMIT_REACHED")

    result = await analyze_wallet(address, chain, db=db)
    allowed, remaining = count_and_incr_daily(f"free:{client_ip}", settings.FREE_CHECKS_PER_DAY)
    if not allowed:
        raise HTTPException(status_code=429, detail="FREE_LIMIT_REACHED")
    user_id = current_user.id if current_user else None
    row = _save_check(db, user_id, result, is_free=True)
    result["free_checks_remaining"] = remaining
    result["trial"] = True
    result["share_token"] = row.share_token
    result["check_id"] = row.id
    return result


@app.get("/detect")
def detect_address(q: str):
    """Auto-detect chain / input kind from pasted text."""
    return detect_input_kind(q)


@app.get("/check")
@limiter.limit("30/minute")
async def check_wallet(
    request: Request,
    address: str = Query(..., max_length=200, description="Wallet address to check"),
    chain: str = Query("ETH", max_length=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_afford_check(current_user):
        raise HTTPException(status_code=402, detail="Insufficient balance. Please top up.")

    # Analyze first — charge only on success
    result = await analyze_wallet(address, chain, db=db)
    method = charge_for_check(db, current_user)
    # Refresh: charge_for_check работает с locked_user — синхронизируем current_user
    db.refresh(current_user)
    row = _save_check(db, current_user.id, result, is_free=False)
    result["billing_method"] = method
    result["check_id"] = row.id
    result["share_token"] = row.share_token
    result["balance"] = current_user.balance
    result["check_credits"] = current_user.check_credits or 0
    return result


@app.get("/v1/check")
@limiter.limit("60/minute")
async def api_check(
    request: Request,
    address: str = Query(..., max_length=200, description="Wallet address to check"),
    chain: str = Query("ETH", max_length=10),
    api_ctx=Depends(get_api_user),
    db: Session = Depends(get_db),
):
    """API beta endpoint — X-API-Key header."""
    user, api_key = api_ctx
    result = await analyze_wallet(address, chain, db=db)
    api_key.used_this_month = (api_key.used_this_month or 0) + 1
    db.add(api_key)
    row = _save_check(db, user.id, result, is_free=False)
    db.commit()
    result["check_id"] = row.id
    result["quota_remaining"] = api_key.quota_monthly - api_key.used_this_month
    return result


@app.get("/graph/expand")
async def expand_graph(
    address: str,
    chain: str = "ETH",
    current_user: User = Depends(get_current_user),
):
    if chain not in ALLOWED_CHAINS:
        raise HTTPException(status_code=400, detail="Unsupported chain")
    try:
        return await GraphExpanderService.expand_graph(chain, address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report")
async def get_report(
    address: str,
    chain: str = "ETH",
    lang: str = "en",
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PDF report — requires auth. Charges one check (or uses credit)."""
    if not can_afford_check(current_user):
        raise HTTPException(status_code=402, detail="Insufficient balance for report")

    if lang not in SUPPORTED_LANGS:
        lang = "en"

    result = await analyze_wallet(address, chain)
    charge_for_check(db, current_user)
    _save_check(db, current_user.id, result, is_free=False)

    # Уникальный временный файл — исключает race condition при параллельных запросах
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    file_path = tmp.name

    try:
        result["lang"] = lang
        create_premium_pdf(file_path, result)
    except Exception as exc:
        os.unlink(file_path)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    safe_address = address.replace("/", "_")[:64]
    if background_tasks is not None:
        background_tasks.add_task(os.unlink, file_path)
    return FileResponse(file_path, media_type="application/pdf", filename=f"AML_Report_{safe_address}.pdf")


@app.get("/share/{token}")
def shared_report(token: str, request: Request, format: str = "html", db: Session = Depends(get_db)):
    row = db.query(CheckHistory).filter(CheckHistory.share_token == token).first()
    if not row:
        raise HTTPException(status_code=404, detail="Share link not found")
    if row.share_expires_at and row.share_expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Share link expired")

    payload = json.loads(row.payload_json) if row.payload_json else {
        "address": row.address,
        "chain": row.chain,
        "risk_score": row.risk_score,
        "risk_level": row.risk_level,
    }
    if format == "json":
        return payload
    return templates.TemplateResponse("share.html", {
        "request": request,
        "data": payload,
        "token": token,
        "expires_at": row.share_expires_at.isoformat() if row.share_expires_at else None,
        "check_id": row.id,
    })


@app.get("/data-status")
def data_status(db: Session = Depends(get_db)):
    rows = db.query(ListSnapshot).order_by(ListSnapshot.synced_at.desc()).all()
    seen = {}
    for r in rows:
        if r.source not in seen:
            age_h = (datetime.utcnow() - r.synced_at).total_seconds() / 3600 if r.synced_at else None
            seen[r.source] = {
                "version": r.version,
                "synced_at": r.synced_at.isoformat() if r.synced_at else None,
                "record_count": r.record_count,
                "age_hours": round(age_h, 1) if age_h is not None else None,
                "stale": bool(age_h and age_h > 168),
            }
    return {"sources": seen, "banner_stale": any(v.get("stale") for v in seen.values())}


@app.get("/p/{report_id}")
def verify_report_page(report_id: str, request: Request, db: Session = Depends(get_db)):
    """Public web verification page for AML Guard reports (/p/AG-...)."""
    clean_id = (report_id or "").strip()
    row = db.query(CheckHistory).filter(
        (CheckHistory.report_id == clean_id) | (CheckHistory.sha256_hash == clean_id)
    ).first()

    if not row:
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "found": False,
            "query": clean_id,
        }, status_code=404)

    is_expired = bool(row.share_expires_at and row.share_expires_at < datetime.utcnow())
    payload = json.loads(row.payload_json) if row.payload_json else {
        "address": row.address,
        "chain": row.chain,
        "risk_score": row.risk_score,
        "risk_level": row.risk_level,
    }

    cex_profile = "Свободный ввод (Tier-1)"
    if row.risk_score >= 75:
        cex_profile = "Блокировка / Hard Reject"
    elif row.risk_score >= 40:
        cex_profile = "Ручной комплаенс / EDD"
    elif row.risk_score >= 20:
        cex_profile = "Повышенное внимание"

    return templates.TemplateResponse("verify.html", {
        "request": request,
        "found": True,
        "expired": is_expired,
        "report_id": row.report_id or clean_id,
        "sha256": row.sha256_hash or "n/a",
        "data": {
            "address": row.address,
            "chain": row.chain,
            "risk_score": row.risk_score,
            "risk_level": row.risk_level,
            "cex_verdict": cex_profile,
        },
        "created_at": row.created_at.strftime("%d.%m.%Y %H:%M") if row.created_at else "n/a",
        "expires_at": row.share_expires_at.strftime("%d.%m.%Y %H:%M") if row.share_expires_at else "n/a",
    })


@app.get("/api/v1/verify/{query}")
def verify_report_api(query: str, db: Session = Depends(get_db)):
    """Public JSON API to verify reports by report_id or SHA-256 for exchanges and merchants."""
    clean_q = (query or "").strip()
    row = db.query(CheckHistory).filter(
        (CheckHistory.report_id == clean_q) | (CheckHistory.sha256_hash == clean_q)
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail={
            "verified": False,
            "status": "NOT_FOUND",
            "message": "Report record not found or forged",
            "query": clean_q,
        })

    is_expired = bool(row.share_expires_at and row.share_expires_at < datetime.utcnow())
    return {
        "verified": True,
        "status": "EXPIRED" if is_expired else "VALID",
        "report_id": row.report_id,
        "sha256": row.sha256_hash,
        "address": row.address,
        "chain": row.chain,
        "risk_score": row.risk_score,
        "risk_level": row.risk_level,
        "issued_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.share_expires_at.isoformat() if row.share_expires_at else None,
        "verification_url": f"{settings.VERIFY_BASE_URL}/{row.report_id}",
    }


@app.get("/graph/deep")
async def get_deep_graph(
    address: str,
    chain: str = "ETH",
    depth: int = 2,
    current_user: User = Depends(get_current_user),
):
    """Deep multi-hop graph expansion (2-hop / 3-hop) with mixer & taint detection."""
    if chain not in ALLOWED_CHAINS:
        raise HTTPException(status_code=400, detail="Unsupported chain")
    depth_bounded = max(1, min(depth, 3))
    try:
        from services.deep_graph import DeepGraphService
        return await DeepGraphService.expand_deep_graph(chain, address, depth=depth_bounded)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
