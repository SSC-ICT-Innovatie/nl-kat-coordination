from datetime import datetime, timedelta
from typing import Any

import jwt
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from jwt import InvalidTokenError, PyJWTError
from rest_framework.authentication import TokenAuthentication


class JWTTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        try:
            return AnonymousUser(), jwt.decode(
                key, settings.JWT_KEY, algorithms=[settings.JWT_ALGORITHM], options={"require": ["exp", "iat"]}
            )
        except PyJWTError:
            return None

    @staticmethod
    def generate(
        permissions: dict[str, dict[str, Any]] | None = None,
        additional: dict | None = None,
        timeout: int = settings.PLUGIN_TIMEOUT,
    ) -> str:
        if not settings.JWT_KEY:
            raise InvalidTokenError("No JWT key set in settings")

        now = datetime.now()
        token_data = {
            "permissions": permissions,
            "iat": now.timestamp(),
            "exp": (now + timedelta(minutes=timeout)).timestamp(),
        } | (additional or {})
        return jwt.encode(token_data, settings.JWT_KEY, algorithm=settings.JWT_ALGORITHM)
