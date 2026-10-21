# Qvề realtime tính toán

Snapshot mới của Sông Hinh và Vĩnh Sơn lưu thêm:

- `qve_tinh_toan`: m³/s, null nếu chưa đủ điều kiện.
- `qve_calculation`: phương pháp, trạng thái, thời gian đầu/cuối, khoảng giây thực tế,
  dung tích từng hồ tại hai đầu, biến động dung tích m³, lưu lượng trung bình và cảnh báo.

Công thức: `(tổng Vcuối - tổng Vđầu) * 1_000_000 / số_giây + Qcm_tb + Qtran_tb`.
Dung tích bảng nội suy là triệu m³. Nội suy lại cả hai đầu theo cùng bảng hiện tại,
không dùng dung tích hiển thị đã làm tròn, không chặn mức ngoài bảng về giá trị biên.
Qcm/Qtran trung bình là trung bình hai đầu mẫu, không phải tích phân đo liên tục.

Sông Hinh dùng một hồ. Vĩnh Sơn dùng tổng A+B+C, Qcm và Qtran chỉ của A.
Nước chuyển nội bộ triệt tiêu trong tổng biến động dung tích. Chưa tính xả ngoài hệ
của B/C, các dòng ra khác, bốc hơi hoặc thấm. Kết quả là ước tính, không thay thế số liệu đo.

Mẫu trước là snapshot có timestamp nguồn lớn nhất đã lưu. Mẫu trùng/lùi thời gian
vẫn được lưu nhưng Qvề null. Mẫu đầu/thiếu bảng/ngoài bảng/giá trị không hợp lệ:
Qvề null kèm lý do. Khoảng >1800 giây và kết quả âm được đánh dấu, không ép về 0.
Lịch 00/30 là lịch kích hoạt, không bảo đảm API cung cấp đúng mẫu tại giây đó.

API snapshot hiện có tự trả hai trường mới; các trường tính toán chỉ đọc.
Chưa thay đổi giao diện dashboard hoặc payload realtime trực tiếp.
Snapshot cũ giữ null và metadata `{}`; không tự tính hồi tố.

## Triển khai

Build mã mới và chạy `python manage.py migrate` trước khi worker/app mới lưu snapshot.
Migration: `0022_realtime_calculated_inflow`. Không xóa dữ liệu cũ.
Chạy một Celery Beat; khởi động lại app/worker/beat theo quy trình triển khai.

## Kiểm thử

```bash
python manage.py test thongsothuyvan.tests.test_realtime_inflow thongsothuyvan.tests.test_realtime_schedule
```

Kiểm tra cả kết quả và metadata trên snapshot mới sau ít nhất hai mẫu hợp lệ.
Không dùng `last_saved_at` hoặc thông báo task thành công làm bằng chứng duy nhất
cho chất lượng Qvề.
