# Cấu trúc liên kết thông số vận hành

Tài liệu này mô tả luồng liên kết chính trong backend `app/quanlyvanhanh` sau khi gom cấu hình nhà máy về một nơi.

## Nguồn cấu hình chung

File trung tâm:

`app/quanlyvanhanh/configs/operation_configs.py`

File này là nơi ưu tiên kiểm soát:

- `DIEN_CONFIGS`: layout thông số vận hành điện theo nhà máy.
- `TRAM_CONFIGS`: layout thông số trạm 110/22kV.
- `TOMAY_PARAM_DEVICE_SUFFIX`: ánh xạ mã thông số tổ máy kiểu Sông Hinh hoặc nhà máy dùng cùng cấu trúc.
- `TOMAY_VS_PARAM_DEVICE_SUFFIX`: ánh xạ mã thông số tổ máy kiểu Vĩnh Sơn.
- `get_dien_factory_config(factory_code)`: trả cấu hình điện cho `SH`, `VS` hoặc tự nhân bản cấu hình `SH` theo prefix nhà máy mới như `TKT`.
- `get_tram_factory_config(factory_code)`: trả cấu hình trạm và đổi prefix thiết bị theo mã nhà máy.
- `get_tomay_device_suffix(factory_code, param_code, machine_code)`: quyết định thiết bị con nhận dữ liệu tổ máy.

## Các file đang sử dụng cấu hình chung

`app/quanlyvanhanh/views_thongso_dien.py`

- API cấu hình và CRUD thông số vận hành điện.
- Hàm cũ `get_factory_config(factory_code)` vẫn còn để tương thích, nhưng bên trong gọi `get_dien_factory_config`.
- Endpoint `config` không còn khóa cứng chỉ `SH/VS`; mã mới được phép dùng cấu hình nhân bản nếu người dùng có quyền nhà máy đó.

`app/quanlyvanhanh/views_excel.py`

- Tạo template và import Excel thông số vận hành điện.
- Dùng `get_dien_factory_config` để flatten layout thành `column_mapping`.
- Import Excel hiện nhận đúng cả template cũ bắt đầu từ cột A và template mới có cột STT/thời gian.

`app/quanlyvanhanh/views_tram.py`

- API cấu hình, import/export và CRUD thông số trạm.
- Hàm cũ `get_factory_config(factory_code)` gọi `get_tram_factory_config`.

`app/quanlyvanhanh/services/thongso_tomay_service.py`

- Service lưu thông số tổ máy.
- Hàm `get_specific_thiet_bi(base_device, param_code)` gọi `get_tomay_device_suffix` để chọn thiết bị con.

`app/quanlyvanhanh/views_tomay_excel.py`

- Tạo và import Excel thông số tổ máy.
- File này vẫn giữ logic đọc template riêng vì template `VS` khác `SH`.
- Khi thêm nhà máy dùng cấu trúc giống Sông Hinh, mã nhà máy khác `VS` sẽ đi theo nhánh Sông Hinh.

## Model dữ liệu liên quan

`app/quanlyvanhanh/models.py`

- `ThongSoVanHanh`: lưu thông số vận hành điện.
- `ThongSoToMay`: lưu thông số cơ/tổ máy.
- `ThongSoTram110KV`: lưu thông số trạm.
- `NguongThongSo`: lưu ngưỡng cảnh báo theo `nha_may`, `thiet_bi`, `ma_thong_so`.
- `ThietBi`: danh mục thiết bị, cần có mã đầy đủ đúng prefix nhà máy, ví dụ `TKT.TB.H1`, `TKT.TB.TPP.110.T1`.

## Quy trình thêm nhà máy mới như TKT

1. Tạo nhà máy trong `Bang_nha_may` với `ma_nha_may = TKT`.
2. Tạo danh mục thiết bị trong `ThietBi` theo cùng quy ước prefix:
   - Điện: `TKT.TB.H1`, `TKT.TB.H2`, `TKT.TB.TPP`.
   - Trạm: các mã con như `TKT.TB.TPP.110.T1`, `TKT.TB.TPP.110.171`.
   - Tổ máy: các thiết bị con theo suffix trong `TOMAY_PARAM_DEVICE_SUFFIX`.
3. Nếu TKT dùng layout giống Sông Hinh, không cần thêm block mới trong `DIEN_CONFIGS` hoặc `TRAM_CONFIGS`.
4. Nếu TKT có layout riêng, thêm key `"TKT"` vào `DIEN_CONFIGS` hoặc `TRAM_CONFIGS`.
5. Nếu TKT có ánh xạ thiết bị tổ máy riêng, thêm map riêng và cập nhật `get_tomay_device_suffix`.
6. Cấu hình quyền người dùng/nhà máy để `ensure_factory_code_allowed` và các filter theo nhà máy cho phép truy cập `TKT`.
7. Chạy kiểm tra:
   - `SQLITE=1 python manage.py check`
   - `SQLITE=1 python manage.py test quanlyvanhanh.tests.test_excel_imports -v 2`

## Lưu ý dữ liệu Excel ngày 09/06/2026

Lỗi lệch thiếu một ô của Sông Hinh xảy ra khi import file template cũ nhưng backend luôn bỏ cột đầu tiên. Backend hiện chỉ bỏ cột đầu nếu cột đó thật sự giống STT/thời gian. Nếu dữ liệu ngày `09/06/2026` đã được import lệch trước khi sửa, cần xóa dữ liệu ngày đó và import lại file Excel đúng.
