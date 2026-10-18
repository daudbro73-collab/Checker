from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import SessionLocal, User, ApiKey
from services.auth import SECRET_KEY, ALGORITHM
import hashlib

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Unified subject: internal user_id
    user = None
    try:
        user_id = int(sub)
        user = db.query(User).filter(User.id == user_id).first()
    except (TypeError, ValueError):
        # Legacy tokens with email subject
        user = db.query(User).filter(User.email == sub).first()

    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_optional_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None


async def get_api_user(
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db),
):
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    record = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.active == True).first()
    if not record:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if record.used_this_month >= record.quota_monthly:
        raise HTTPException(status_code=402, detail="API quota exceeded")
    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user, record
