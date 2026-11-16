from decouple import config

_env = config("DJANGO_ENV", default="dev").lower()
if _env == "prod":
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
