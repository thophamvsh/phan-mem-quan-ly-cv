import uuid
from django.db import models
from django.utils import timezone

class TimestampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

def _lay_chu_ky_profile(user):
    try:
        profile = user.profile
    except Exception:
        return None
    return getattr(profile, "chu_ky", None)

def _current_year():
    return timezone.localdate().year
