# phan-mem-quan-ly-cv

Backend Django cho quản lý kho vật tư và quản lý vận hành.

Tài liệu nhanh:

- Cấu trúc repo: [docs/REPO_STRUCTURE.md](docs/REPO_STRUCTURE.md)
- API vận hành: [app/quanlyvanhanh/API_DOCUMENTATION.md](app/quanlyvanhanh/API_DOCUMENTATION.md)
- README vận hành: [app/quanlyvanhanh/README.md](app/quanlyvanhanh/README.md)

## API versioning (nhẹ, tương thích ngược)

- Route hiện tại (`/api/...`) vẫn giữ nguyên để không làm vỡ client cũ.
- Đã bổ sung route version hóa song song tại `/api/v1/...`.
- Khuyến nghị client mới chuyển dần sang `/api/v1/...`.
- Ví dụ:
  - Cũ: `/api/auth/login/`
  - Mới: `/api/v1/auth/login/`
