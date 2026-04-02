from datetime import datetime, timedelta
from typing import Literal

import jwt


class JwtLogic:
    GITHUB_APP_ALGORITHM: str = "RS256"

    @classmethod
    def _encode_jwt(
        cls,
        secret: str,
        exp_sec: int,
        algorithm: Literal["RS256"] = "RS256",
        claims: dict[str, str | int] | None = None,
    ) -> str:
        payload: dict[str, str | int] = {
            "iat": int(datetime.now().timestamp()),
            "exp": int((datetime.now() + timedelta(seconds=exp_sec)).timestamp()),
        }

        if claims:
            payload.update(claims)

        return jwt.encode(payload, secret, algorithm=algorithm)

    @classmethod
    def create_github_app_jwt(
        cls,
        app_id: str,
        private_key: str,
        expire_seconds: int = 600,
    ) -> str:
        if not app_id:
            raise ValueError("app_id is required for GitHub App JWT creation")
        if not private_key:
            raise ValueError("private_key is required for GitHub App JWT creation")

        return cls._encode_jwt(
            secret=private_key,
            exp_sec=expire_seconds,
            algorithm=cls.GITHUB_APP_ALGORITHM,
            claims={"iss": app_id},
        )
