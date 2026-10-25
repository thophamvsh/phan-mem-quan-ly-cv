import os
from django.conf import settings


class VrainConfigError(RuntimeError):
    pass


def _get_api_key():
    api_key = getattr(settings, "VRAIN_API_KEY", os.environ.get("VRAIN_API_KEY"))
    if not api_key:
        raise VrainConfigError("VRAIN_API_KEY chua duoc cau hinh tren server")
    return api_key
