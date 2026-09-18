from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0006_document_module_guide_and_active"),
    ]

    operations = [
        migrations.AlterField(
            model_name="moduleguide",
            name="module_code",
            field=models.CharField(
                choices=[
                    ("so_giao_nhan_ca_vh", "Sổ giao nhận ca vận hành"),
                    ("so_giao_nhan_ca_hc", "Sổ giao nhận ca hành chính"),
                    ("so_chuyen_doi_tuan", "Sổ chuyển đổi thiết bị tuần"),
                    ("so_chuyen_doi_thang", "Sổ chuyển đổi thiết bị đầu tháng"),
                    ("so_an_toan_dau_gio", "Sổ theo dõi an toàn đầu giờ"),
                    ("so_bchc_song_hinh", "Sổ báo cáo hồ chứa Sông Hinh"),
                    ("so_nhat_ky_diesel", "Sổ nhật ký vận hành Diesel"),
                    ("so_nhat_ky_van_hanh", "Sổ nhật ký vận hành chung"),
                    ("nhat_ky_su_kien", "Nhật ký sự kiện"),
                    ("quan_ly_thiet_bi", "Quản lý thiết bị"),
                    ("thong_so_van_hanh", "Thông số vận hành"),
                    ("dashboard_nha_may", "Dashboard nhà máy"),
                    ("cai_dat_he_thong", "Cài đặt hệ thống"),
                    ("quan_ly_tai_khoan", "Quản lý tài khoản"),
                    ("quan_ly_ca_truc", "Quản lý ca trực"),
                    ("nhat_ky_kiem_toan", "Nhật ký kiểm toán"),
                    ("quan_ly_tai_lieu", "Quản lý tài liệu"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
    ]
