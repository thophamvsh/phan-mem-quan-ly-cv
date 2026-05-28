import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

for u in User.objects.all():
    profile = getattr(u, 'profile', None)
    can_view = getattr(profile, 'can_view_shift_handover_directives', None)
    can_create = getattr(profile, 'can_create_shift_handover_directives', None)
    print(f"User: {u.username} | Superuser: {u.is_superuser} | can_view_directives: {can_view} | can_create_directives: {can_create}")
