"""Paramètres de production (sécurisés, PostgreSQL via env)."""
from .base import *  # noqa: F401,F403

DEBUG = False
if SECRET_KEY == "changez-moi":  # pragma: no cover
    raise RuntimeError("SECRET_KEY de production manquante ou invalide.")

# Renforcements production (peuvent être ajustés via .env)
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=True, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if config("USE_X_FORWARDED_PROTO", default=True, cast=bool) else None
