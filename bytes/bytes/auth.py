from datetime import datetime, timedelta, timezone

import jwt
import structlog
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from starlette import status

from bytes.config import get_settings

logger = structlog.get_logger(__name__)

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: str


def get_access_token(form_data: OAuth2PasswordRequestForm) -> tuple[str, datetime]:
    settings = get_settings()
    system_username = settings.username
    hashed_password = pwd_context.hash(settings.password)

    authenticated = form_data.username == system_username and pwd_context.verify(form_data.password, hashed_password)

    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _create_access_token(form_data, settings.secret, settings.access_token_expire_minutes)


def authenticate_token(token: str = Depends(oauth2_scheme)) -> str:
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.secret, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise credentials_exception

        return str(username)
    except InvalidTokenError as error:
        raise credentials_exception from error


def _create_access_token(
    form_data: OAuth2PasswordRequestForm, secret: str, access_token_expire_minutes: float
) -> tuple[str, datetime]:
    expire_time = _get_expire_time(access_token_expire_minutes)
    data = {"sub": form_data.username, "exp": expire_time}

    access_token = jwt.encode(data.copy(), secret, algorithm=ALGORITHM)

    return access_token, expire_time


def _get_expire_time(access_token_expire_minutes: float) -> datetime:
    access_token_expires = timedelta(minutes=access_token_expire_minutes)

    return datetime.now(timezone.utc) + access_token_expires
