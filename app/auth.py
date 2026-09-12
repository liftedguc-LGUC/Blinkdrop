"""Authentication for the admin surface.

Three modes, chosen by ADMIN_AUTH (or derived — see config._resolve_admin_auth):

  iap    verify the JWT Cloud IAP puts in X-Goog-IAP-JWT-Assertion. The
         production target: identity is Google's, the app holds no password.
  basic  HTTP Basic against ADMIN_PASSWORD. A stopgap for deployments without
         the load balancer IAP requires.
  off    no check. Local development only.

Anything else — notably a Firestore-backed deployment with nothing configured —
resolves to "unconfigured" and every admin route returns 503. Failing closed
means a careless deploy cannot serve customer data to the internet.
"""

import base64
import binascii
import secrets

from fastapi import Depends, HTTPException, Request, status

from .config import Settings, get_settings

ADMIN_REALM = 'Basic realm="Blinkdrop admin", charset="UTF-8"'
IAP_HEADER = "X-Goog-IAP-JWT-Assertion"
IAP_ISSUER = "https://cloud.google.com/iap"


class Principal:
    """Who is making an admin request. Recorded on anything it changes."""

    def __init__(self, identity: str, method: str) -> None:
        self.identity = identity
        self.method = method

    def __str__(self) -> str:
        return self.identity


def _unauthorized(detail: str, headers: dict[str, str] | None = None) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers=headers)


def _check_basic(request: Request, settings: Settings) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        raise _unauthorized("authentication required", {"WWW-Authenticate": ADMIN_REALM})

    try:
        user, _, password = base64.b64decode(encoded, validate=True).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError):
        raise _unauthorized("malformed credentials", {"WWW-Authenticate": ADMIN_REALM}) from None

    # Both compared, and always both, so a wrong username costs the same time as
    # a wrong password.
    user_ok = secrets.compare_digest(user, settings.admin_user)
    password_ok = secrets.compare_digest(password, settings.admin_password)
    if not (user_ok and password_ok):
        raise _unauthorized("invalid credentials", {"WWW-Authenticate": ADMIN_REALM})

    return Principal(identity=user, method="basic")


def verify_iap_assertion(token: str, audience: str) -> dict:
    """Split out so tests can substitute a verifier. Real IAP is not reachable here."""
    from google.auth.transport import requests as google_requests  # noqa: PLC0415
    from google.oauth2 import id_token  # noqa: PLC0415

    return id_token.verify_token(
        token,
        google_requests.Request(),
        audience=audience,
        certs_url="https://www.gstatic.com/iap/verify/public_key",
    )


def _check_iap(request: Request, settings: Settings) -> Principal:
    token = request.headers.get(IAP_HEADER, "")
    if not token:
        raise _unauthorized("missing IAP assertion")

    try:
        claims = verify_iap_assertion(token, settings.iap_audience)
    except Exception:
        # The reason belongs in logs, not in a response to an unauthenticated caller.
        raise _unauthorized("invalid IAP assertion") from None

    if claims.get("iss") != IAP_ISSUER:
        raise _unauthorized("invalid IAP assertion")

    email = str(claims.get("email", "")).lower()
    if not email:
        raise _unauthorized("IAP assertion carries no identity")
    if settings.iap_allowed_emails and email not in settings.iap_allowed_emails:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")

    return Principal(identity=email, method="iap")


def require_admin(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Principal:
    mode = settings.admin_auth
    if mode == "off":
        return Principal(identity="local-dev", method="off")
    if mode == "basic":
        return _check_basic(request, settings)
    if mode == "iap":
        return _check_iap(request, settings)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "admin surface is not configured for authentication; "
            "set ADMIN_AUTH with IAP_AUDIENCE or ADMIN_PASSWORD"
        ),
    )
