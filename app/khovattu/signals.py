#!/usr/bin/env python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Bang_xuat_xu

@receiver(post_save, sender=Bang_xuat_xu)
def auto_update_vattu_xuat_xu(sender, instance, created, **kwargs):
    """
    Tự động cập nhật xuất xứ cho các vật tư có country code mới được thêm
    """
    if created:  # Chỉ chạy khi tạo mới
        from .models import Bang_vat_tu

        country_code = instance.ma_country
        print(f"🔍 Mã xuất xứ mới được tạo: {country_code}")

        # Tìm tất cả vật tư có country code này nhưng chưa có xuất xứ
        vattu_list = Bang_vat_tu.objects.filter(
            ma_bravo__contains=f'.{country_code}.',
            xuat_xu__isnull=True
        )

        count = vattu_list.count()
        if count > 0:
            print(f"📊 Tìm thấy {count} vật tư có {country_code} cần cập nhật")

            # Cập nhật tất cả vật tư
            updated = vattu_list.update(xuat_xu=instance)
            print(f"✅ Đã cập nhật {updated} vật tư với xuất xứ {instance.ten_nuoc}")
        else:
            print(f"ℹ️  Không có vật tư nào cần cập nhật cho {country_code}")
