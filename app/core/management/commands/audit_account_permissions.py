"""Read-only default; explicitly repair materialized role flags with --apply."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import Lower
from core.models import User, UserProfile


class Command(BaseCommand):
    help = 'Kiểm kê quyền và định danh tài khoản; mặc định không thay đổi dữ liệu.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Chỉ đồng bộ cờ của hồ sơ có vai trò.')

    def handle(self, *args, **options):
        fields = [f.name for f in UserProfile._meta.fields if f.name.startswith('can_')]
        affected = 0
        with transaction.atomic():
            profiles = UserProfile.objects.select_related('role')
            if options['apply']:
                profiles = profiles.select_for_update(of=('self',))
            for profile in profiles:
                if not profile.role_id:
                    continue
                before = {field: getattr(profile, field) for field in fields}
                profile.apply_role_permissions()
                changed = {field: getattr(profile, field) for field in fields
                           if before[field] != getattr(profile, field)}
                if changed:
                    affected += 1
                    self.stdout.write(f'profile_id={profile.pk}: {sorted(changed)}')
                    if options['apply']:
                        UserProfile.objects.filter(pk=profile.pk).update(**changed)
        self.stdout.write(f'Hồ sơ cần đồng bộ: {affected}; apply={options["apply"]}')
        self.stdout.write(f'Hồ sơ legacy giữ nguyên: {UserProfile.objects.filter(role=None).count()}')
        for field in ('username', 'email'):
            duplicates = User.objects.annotate(normalized=Lower(field)).values('normalized').annotate(
                total=Count('pk')).filter(total__gt=1).count()
            self.stdout.write(f'Nhóm {field} trùng không phân biệt hoa thường: {duplicates}')
