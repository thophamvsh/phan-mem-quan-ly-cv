# Sông Hinh: lưu dự báo B0 và đối chiếu thực tế hằng ngày

Trạng thái 26/10/2026: đã triển khai và thử trên local; **lịch mặc định tắt**, chưa deploy Orange Pi, chưa có API/frontend mới. Đây là theo dõi baseline thử nghiệm, không phải mô hình đã đạt độ chính xác vận hành và không phát lệnh điều khiển hồ.

## Quy tắc dự báo

B0 = Qvề hợp lệ gần nhất từ `ThongSoThuyVanThucTe.qve`, `nha_may=songhinh`, thuộc ngày đã kết thúc. Nhãn là trung bình ngày 00:00–24:00 giờ Việt Nam, m³/s; nguồn chuẩn do người dùng xác nhận. Bảng hiện không có giờ duyệt riêng, nên chỉ ghi lại created_at/updated_at và thời điểm capture, không tự tuyên bố đã biết giờ duyệt.

Phát hành thực tế vào ngày D, đích là ngày D+1. Lệnh chỉ dùng đồng hồ server hiện tại; không có tùy chọn backdate issue_time hoặc tạo dự báo cho ngày đích quá khứ. `scheduled_for` là mốc 07:30 D; `issued_at` là giờ thực sự phát hành. Lần chạy muộn hơn 07:45 có cờ phát hành muộn, không được đổi ngược về 07:30.

Nguồn phải có created_at và updated_at không muộn hơn thời điểm đọc, qve hữu hạn và không âm; 0 hợp lệ giữ là 0. Độ tuổi tối đa mặc định hai ngày lịch (thường D-1, cho phép D-2 kèm cờ). Không lấy số thực tế của D/D+1. Thiếu/không hợp lệ/quá cũ thì ghi run unavailable, không tạo dự báo 0. Có thể chạy lại sau khi báo cáo đến; chỉ lần có dữ liệu hợp lệ đầu tiên phát hành được một forecast trong ngày.

## Lưu trữ

Migration `0025_inflow_b0_shadow` thêm:

- `InflowB0Forecast`: một dự báo mỗi plant/issue_date/model_version. Lưu Qvề dự báo, giờ phát hành thực tế, ngày/khoảng đích, ảnh chụp nguồn, ID nguồn và checksum. Nội dung dự báo không ghi đè khi retry hoặc nguồn được sửa. Chỉ last_checked_at thay đổi để điều phối kiểm tra.
- `InflowB0Run`: nhật ký publish/reconcile, manual/scheduled, trạng thái, mã lỗi an toàn và số lượng xử lý. Không ghi credential hay exception thô.
- `InflowB0Evaluation`: phiên bản đối chiếu actual. Có trạng thái verified/missing_actual/invalid_actual; giữ actual snapshot, ID nguồn, signed error, absolute error, squared error và volume error. Nguồn thay Qvề hoặc trạng thái thì thêm revision; thay đổi rồi trở về giá trị cũ vẫn tạo revision mới, không gộp mất lịch sử.

Admin cho phép xem ba bảng, không thêm/sửa/xóa thủ công. Nguồn thủy văn không bị thay đổi bởi các service này. Unique constraint, source row lock và get_or_create chống hai publisher tạo dự báo trùng; reconciliation khóa forecast rồi ghi revision theo thứ tự.

## Lệnh thủ công

Tại thư mục backend app/:

```bash
# Chỉ xem đầu vào hiện tại, không ghi forecast hoặc run:
python manage.py publish_inflow_b0_sh --dry-run
# Phát hành B0 cho ngày mai, chạy lại trả already_exists:
python manage.py publish_inflow_b0_sh
# Đối chiếu tối đa 500 forecast có ngày đích đã kết thúc:
python manage.py reconcile_inflow_b0_sh
# Có thể chọn một ngày đích đã kết thúc:
python manage.py reconcile_inflow_b0_sh --target-date 2026-10-27
# Báo cáo chỉ đọc, gồm dự báo còn chờ và điểm đối chiếu:
python manage.py report_inflow_b0_sh
```

Lệnh thủ công được phép chạy dù feature flag tắt; flag chỉ điều khiển lịch tự động. Reconcile với ngày chưa kết thúc bị từ chối; ngày kết thúc mà actual chưa tới được ghi missing_actual và có thể kiểm tra lại. Không chạy ví dụ target-date trước khi ngày đó kết thúc.

Docker local: `docker compose run --rm --no-deps -T -e REALTIME_SNAPSHOT_SCHEDULER_ENABLED=false app python manage.py <command>` khi chỉ database đang chạy. Nếu app đã chạy dùng `docker compose exec app python manage.py <command>`. Production dùng compose prod theo quy trình riêng; chưa thực hiện trong tác vụ này.

## Cấu hình và lịch tùy chọn

```dotenv
INFLOW_B0_SH_ENABLED=false
INFLOW_B0_SH_MAX_SOURCE_AGE_DAYS=2
```

Khi false, không đăng ký hai entry Beat B0; gọi trực tiếp Celery task cũng trả disabled. Khi bật true và recreate app/worker/Beat: phát hành lúc 07:30, đối chiếu lúc 07:45 mỗi ngày theo CELERY_TIMEZONE của dự án (cần giữ Asia/Ho_Chi_Minh). Chỉ một Beat chủ động. Task không gọi Sheet hoặc lấy API nguồn; nó đọc dữ liệu đã đồng bộ. Nếu nguồn đến muộn có thể chạy manual sau đó, giữ đúng giờ thực tế.

Đối chiếu ưu tiên forecast chưa kiểm tra/lần kiểm tra cũ nhất, để giới hạn 500 không làm các forecast mới bị bỏ đói. Dùng --limit trong khoảng 1..5000; các lượt tiếp theo tiếp tục xoay vòng kiểm tra, bao gồm báo cáo cũ có thể được sửa.

Tắt flag và recreate để ngừng lịch; không reverse migration hoặc xóa forecast/evaluation. Run failed/unavailable cần được theo dõi ở worker/admin. Chưa tích hợp kênh cảnh báo bên ngoài trong tính năng này.

## Cách chấm điểm

Chỉ đối chiếu sau target_end và khi Qvề của đúng ngày đích có trong nguồn chuẩn. `signed_error = prediction - actual`; số âm là dự báo thiếu. Với nhãn bình quân ngày 24 giờ, `volume_error_m3 = signed_error × 86.400`.

MAE, RMSE, bias, NSE dùng **revision đối chiếu mới nhất mỗi forecast**, không đếm nhiều bản sửa thành nhiều ví dụ. Actual bị xóa/đổi sang không hợp lệ tạo trạng thái mới và bị loại khỏi điểm hiện tại, nhưng lịch sử điểm trước vẫn còn. Không có mẫu đã đối chiếu thì điểm là NULL; NSE cũng NULL khi actual không có phương sai.

Điểm hiện tại có thể đổi khi thực tế được hiệu chỉnh; muốn tái lập báo cáo theo thời điểm phải dùng các evaluation revision đã lưu, không chỉ nhìn điểm tổng hợp mới nhất. B0 không cải thiện được thông tin về mưa tương lai; theo dõi baseline này là nền để so sánh v2, không phải nghiệm thu dự báo lũ.

## Kiểm chứng local

Đã backup database local trước migration tại `E:/SangKien/backups/b0-local-20261026/before-0025.dump`; kiểm tra đọc được danh mục archive, chưa thực hiện thử restore đầy đủ cho bản backup riêng này.

Migration 0025 đã áp dụng local. Xác nhận flag false và không có lịch B0 trong Beat. Dry-run không ghi dữ liệu. Đã phát hành thủ công một B0 thực sự lúc 15:35:45 ngày 26/10/2026 giờ Việt Nam, đích ngày 27/10/2026, dự báo 19,58 m³/s từ Qvề ngày 25/10. Retry trả cùng forecast_id=1, không đổi giá trị/giờ phát hành. Đối chiếu ngay trả checked=0 vì ngày đích chưa kết thúc. Chưa có sai số vận hành để báo cáo; cần chờ ngày đích kết thúc và báo cáo được đồng bộ.

Bộ test PostgreSQL gồm hành vi tắt lịch/manual, dry-run, dữ liệu tương lai/đến muộn/quá cũ/âm/0, forecast bất biến, retry, hai publisher đồng thời, ngày đích chưa kết thúc, nguồn actual thiếu/sửa/đổi về giá trị cũ, chấm revision mới nhất và fairness khi giới hạn batch. Thay đổi không cài thêm thư viện ML vào backend.

Kết quả kiểm tra cuối: 31 test PostgreSQL (B0 shadow, pipeline đặc trưng, audit và Qvề realtime) đều đạt; makemigrations --check không có thay đổi; Django system check và compileall đạt. Báo cáo local có một forecast đang chờ ngày đích kết thúc, automatic_enabled=false và scored=0.
