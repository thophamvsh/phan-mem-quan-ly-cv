from django.apps import AppConfig


class QuanlyvanhanhConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quanlyvanhanh'

    def ready(self):
        from django.db.models import CharField, TextField
        from django.contrib.postgres.lookups import Unaccent
        CharField.register_lookup(Unaccent)
        TextField.register_lookup(Unaccent)

        # Đăng ký auditlog cho các model quan trọng
        from auditlog.registry import auditlog
        from .models import ThietBi, ThongSoVanHanh, ThongSoToMay, ThongSoTram110KV, NguongThongSo

        auditlog.register(ThietBi)
        auditlog.register(ThongSoVanHanh)
        auditlog.register(ThongSoToMay)
        auditlog.register(ThongSoTram110KV)
        auditlog.register(NguongThongSo)

