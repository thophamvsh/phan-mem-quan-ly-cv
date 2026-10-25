# Lịch sử VRAIN: triển khai song song và kiểm chứng nguồn

Ngày: 25/10/2026. Chưa deploy hoặc bật lịch thu thập trên Orange Pi.

## Phạm vi đã triển khai

- Migration 0024: trạm, nhật ký đồng bộ và bằng chứng nguồn đã lọc, mẫu nguồn, revision, khoảng mưa, khóa tác vụ và công việc tải bù.
- Seed 9 mã hiện đang xuất hiện trong phản hồi. `957833` được giữ riêng và tắt; không gộp/cộng với `036606`. Không ghi đè trạm đã tồn tại.
- Mẫu được định danh bởi trạm + timestamp; cùng mẫu không tạo revision mới, thay đổi giá trị tạo revision mới. first_received_at không thay đổi khi sửa số đo.
- `source_as_of(station, timestamp, known_at)` đọc phiên bản thực sự đã biết tại thời điểm T, không dùng bản sửa nhận sau T.
- Nhập liệu có khóa database 5 phút, kiểm tra quyền sở hữu trước commit, transaction và unique constraint. Không lưu credential, header hoặc exception thô.
- Thu cửa sổ gần nhất một giờ, trễ giả định 2 phút; lịch đề xuất 02/12/22/32/42/52. Trễ và kích thước cửa sổ là chính sách thử nghiệm, chưa phải cam kết của VRAIN.
- Mỗi HTTP có connect timeout 5 giây/read timeout mặc định 20 giây; tối đa 3 lần cho lỗi kết nối/429/5xx chọn lọc. 401/403 không retry. Retry-After dạng số tối đa 30 giây được tôn trọng; giá trị dài hoặc HTTP-date trả retry_deferred, không retry sớm.
- Tải bù theo job có cursor bền vững, tối đa 7 ngày/job và một giờ/request. Lịch ưu tiên lượt hiện tại, sau đó tối đa một cửa sổ tải bù. Lượt thiếu/lỗi chuyển job sang blocked, không tự bỏ qua; người vận hành kiểm tra và resume lại.
- Không thay đổi bảng mưa ngày, lịch 07:00, công thức Qvề hoặc frontend hiện có.

## Cổng xác minh bắt buộc

Hai biến mặc định false, có trong `.env.prod.example`:

```dotenv
VRAIN_HISTORY_ENABLED=false
VRAIN_INTERVAL_CONTRACT_VERIFIED=false
```

`VRAIN_HISTORY_ENABLED=true` chỉ cho phép lịch thu bằng chứng nguồn. Khi `VRAIN_INTERVAL_CONTRACT_VERIFIED=false`, dữ liệu có trạng thái captured_unverified; không tạo VrainRainfallInterval, không cung cấp tổng mưa 10 phút. Không tự bật cổng thứ hai chỉ vì thấy timestamp cách nhau 10 phút.

Cổng thứ hai chỉ bật sau khi nhà cung cấp và mẫu đối chiếu xác nhận toàn bộ: depth là mm trong 10 phút trước time_point; time_point là cuối khoảng, theo UTC+7; quy tắc biên và khoảng truy vấn; cách nhận biết mẫu thiếu/hiệu chỉnh. Parser hiện hỗ trợ đúng hợp đồng đó, không hỗ trợ bộ đếm lũy kế hoặc timestamp đầu khoảng. Nếu nguồn khác hợp đồng, cần sửa parser và tăng phiên bản trước khi bật.

Timestamp nguồn đang được diễn giải theo UTC+7 để lập chỉ mục bằng chứng; chuỗi gốc vẫn giữ trong mẫu/revision. Đây chưa phải xác nhận múi giờ từ nhà cung cấp. Không dùng các mẫu chưa xác minh làm dataset huấn luyện.

Khi cổng được xác nhận: chỉ tạo khoảng [time_point-10 phút, time_point); giá trị 0 hợp lệ giữ là 0; thiếu/âm/NaN/không hợp lệ để NULL với trạng thái/cờ. Không làm tròn timestamp lệch biên. Mẫu ngoài cửa sổ chỉ giữ trong bằng chứng, không ghi vào chuỗi chuẩn hóa. Mẫu trùng cùng giá trị được gộp; mẫu trùng khác giá trị trong một phản hồi làm rollback nhập liệu, vẫn giữ bằng chứng an toàn.

## Bằng chứng nguồn thực ngày 25/10/2026

Đã gọi endpoint hiện có `https://kttv-open.vrain.vn/v1/stations/stats` bằng cấu hình cục bộ, không xuất key.

- HTTP 200 với cấu trúc `Data -> station_id -> value[] -> time_point/depth`; timestamp có đầy đủ năm, ví dụ `2026-10-25 12:10:00`.
- Cửa sổ yêu cầu 12:40–12:50 trả cho 036620 và 036604 5 mẫu từ 12:10 đến 12:50, thay vì chỉ mẫu trong khoảng yêu cầu.
- Cửa sổ liền kề 12:50–13:00 tiếp tục trả mẫu từ 12:10; 036620 có mẫu 13:00 nhưng 036604 mới đến 12:50.
- Truy vấn 24/10 13:00 đến 25/10 13:00 trả HTTP 400. Chưa xác định được giới hạn/cách diễn giải start_time của endpoint hiện hành.
- Phản hồi có 9 mã: 036620, 036604, 036616, 036605, 036606, 036617, 036618, 036607, 036608; không thấy 957833. Điều này không chứng minh mã cũ không có lịch sử.
- Các mẫu đã xem là 0 mm; chưa có bộ mẫu mưa dương đối chiếu để xác định depth là lượng trong khoảng hay lũy kế.

Tài liệu công khai https://dev.vrain.vn/ mô tả một endpoint/shape cũ, khác phản hồi hiện hành; chưa đủ xác nhận hợp đồng hiện tại. Orbit không tìm thấy hợp đồng VRAIN công khai; tìm owner mock trên Postman không thực hiện được vì chưa đăng nhập. Mock cục bộ dùng shape đã quan sát, số liệu tổng hợp, không được coi là xác minh nghiệp vụ.

## API đọc mới

Tất cả yêu cầu đăng nhập, quyền realtime và quyền nhà máy ở backend. Response private/no-store; GET không gọi VRAIN.

- `GET /api/v1/thongsothuyvan/vrain-sync-status/?plant=songhinh|vinhson`: cờ thu thập/cổng xác minh, timestamp nguồn và nhận mới nhất từng trạm; trạng thái unavailable/stale/fresh. Ngưỡng stale thử nghiệm 40 phút. fresh chỉ nói về độ mới của bằng chứng, không xác nhận ý nghĩa khoảng đo.
- `GET /api/v1/thongsothuyvan/vrain-intervals/?plant=...&start=...&end=...&station=...&page=1`: 500 dòng/trang, có has_more; station tùy chọn. start/end ISO có múi giờ, đúng biên 10 phút, quá khứ và không quá 7 ngày.
- `GET /api/v1/thongsothuyvan/vrain-summary/?plant=...&start=...&end=...`: cùng cửa sổ, tổng riêng từng trạm; expected_intervals, valid_intervals, coverage_ratio, complete, data_end. rainfall_mm chỉ có khi đủ; thiếu thì NULL, partial_rainfall_mm là tổng một phần, không phải tổng đầy đủ. Không cộng các trạm thành mưa lưu vực.

Hai endpoint khoảng/tổng trả 409 code contract_unverified khi cổng chưa được xác nhận. Tham số sai 400, nhà máy không có quyền 403, trạm không thuộc phạm vi 404. API cũ giữ nguyên.

## Lệnh vận hành sau khi review và backup

```bash
python manage.py migrate --noinput
# Một lượt thủ công, không cần bật lịch:
python manage.py sync_vrain_history
# Cửa sổ chỉ định, tối đa một giờ:
python manage.py sync_vrain_history --start '2026-10-25T12:00:00+07:00' --end '2026-10-25T13:00:00+07:00'
# Tạo job, chưa tự chạy mạng:
python manage.py sync_vrain_history --backfill --start '2026-10-24T12:00:00+07:00' --end '2026-10-25T12:00:00+07:00'
# Thực hiện lại một cửa sổ; dùng ID do lệnh tạo job trả về:
python manage.py sync_vrain_history --resume 1
```

Trong Docker dùng `docker compose -f docker-compose.prod.yml exec app` trước `python ...`. Bật lịch bằng VRAIN_HISTORY_ENABLED sau khi kiểm tra hạn mức; recreate app/worker/Beat. Chỉ một Beat chủ động. Không bật trên production trong tác vụ triển khai mã nguồn này. Rollback bằng tắt VRAIN_HISTORY_ENABLED, giữ bảng và lịch sử; không reverse migration để xóa dữ liệu đã thu.

## Kiểm thử và phần còn lại

```bash
python manage.py test thongsothuyvan.tests.test_vrain_history thongsothuyvan.tests.test_vrain_daily_sync thongsothuyvan.tests.test_vrain_errors thongsothuyvan.tests.test_rain_forecast
python manage.py makemigrations --check --dry-run
postman simulation run postman/simulations/vrain-history.sim.yaml --port 4920 --output ndjson --no-history
# terminal khác, trong app/:
python -m thongsothuyvan.tests.vrain_http_probe
python -m thongsothuyvan.tests.vrain_ingestion_probe
```

HTTP probe đã kiểm tra 200, HTML 500, 429, 401, timeout và refused connection qua HTTP thật với số liệu/key tổng hợp. Ingestion probe dùng SQLite trong bộ nhớ, chứng minh HTTP -> bằng chứng -> mẫu/revision idempotent và 401 không xóa mẫu cũ. Các probe không ghi database production.

Chưa nghiệm thu dữ liệu 10 phút thực tế. Còn cần tài liệu/xác nhận VRAIN, mẫu có mưa dương, đối chiếu tổng ngày/mốc 19:00, đo độ trễ/hạn mức, chạy song song 1–2 tuần, thử tải bù thật và giám sát bên ngoài. Chuyển frontend, export Parquet/R2, kiểm khôi phục kho lịch sử và huấn luyện Qvề là giai đoạn sau, chưa được tuyên bố hoàn thành.

## Nội dung cần hỏi VRAIN

Endpoint hiện hành đang nhận start_time/end_time theo định dạng nào, vì sao truy vấn 12:40–12:50 trả từ 12:10 và truy vấn 24 giờ trả 400? depth là mưa của khoảng bao nhiêu phút hay lũy kế? time_point là đầu/cuối khoảng, múi giờ nào? Không có mẫu/trạm có nghĩa thiếu hay không mưa? Giới hạn thời gian, lịch sử, request và cơ chế sửa số đo là gì? 957833 liên hệ thế nào với 036606? Cần ví dụ đã xác nhận cho một trận có mưa và hai cửa sổ liền kề.

K?t qu? ki?m tra 25/10/2026: 38 test VRAIN l?ch s?/ng?y/l?i v? d? b?o Open-Meteo ??u ??t; migration chain ch?y tr?n SQLite t?m; makemigrations --check --dry-run kh?ng c? thay ??i; Django system check kh?ng c? l?i. PostgreSQL concurrency v? v?n h?nh d?i ng?y tr?n Orange Pi ch?a ???c ki?m ch?ng trong l?n ch?y n?y.

B? sung ki?m tra cu?i: 4 test adapter/l?nh qu?n tr? ??t (g?m m?t test m?i ki?m tra tham s? thi?u v? timestamp kh?ng c? m?i gi?); ki?m tra c? ph?p compileall ??t. Kh?ng c?n database ho?c g?i m?ng cho nh?m ki?m tra tham s? n?y.

## Local activation check: 2026-10-25

Enabled VRAIN_HISTORY_ENABLED=true locally; VRAIN_INTERVAL_CONTRACT_VERIFIED remains false. Migration was already applied. Recreated local app/worker/Beat. Beat log confirmed dispatch of capture-vrain-history. Manual capture and a queued Celery worker run returned captured_unverified with 63 in-window samples, zero new/revised duplicates and 36 outside-window samples retained only as evidence. Database held 63 source samples and 63 revisions across nine stations, and zero normalized intervals. No Orange Pi deployment or setting was changed.

## Modal chi tiết trong card VRAIN (25/10/2026)

Frontend realtime VSH có nút Chi tiết trong footer card VRAIN. Modal tái sử dụng Modal của dự án, chọn SH/VS theo quyền, trạm, 1/6/24 giờ hoặc ngày Việt Nam; bảng cuộn ngang giữ cột thời gian, phân trang 50 mốc nguồn, nhãn đang kiểm chứng, trạng thái từng trạm và giờ nhận. 0 giữ là 0, thiếu/không hợp lệ hiện dấu gạch. Không cộng tổng hoặc gọi dữ liệu này là mưa theo khoảng đã xác minh. Trang mới nhất tự dịch cửa sổ mỗi hai phút; trang quá khứ giữ cửa sổ để tránh nhảy khi đọc. Đóng modal dừng polling. API client dùng cơ chế cookie/access-token refresh hiện có.

API mới: `GET /api/v1/thongsothuyvan/vrain-source-samples/?plant=songhinh|vinhson&start=<ISO aware>&end=<ISO aware>&station=<optional code>&page=1`. Cửa sổ nguồn [start,end), tối đa 24 giờ, không nhận thời gian tương lai; không bắt buộc biên 10 phút vì đây là timestamp nguồn, không phải khoảng đã chuẩn hóa. Mỗi trang chứa trọn các trạm ở 50 timestamp, thứ tự mới nhất trước. Response có plant, data_kind=source_samples, interval_verified=false, stations, results[{time_point,samples}], total_timestamps, has_more, latest_source_timestamp, last_received_at. Chỉ trả trường số đo/thời gian cho UI; không lộ payload thô, key hoặc log lỗi. Mỗi request kiểm tra đăng nhập/quyền realtime/nhà máy; cache private/no-store. GET chỉ đọc database.

Xác minh: 17 test lịch sử VRAIN đạt trên PostgreSQL test local, gồm quyền API nguồn, 0/thiếu/âm, phân trang nguyên timestamp và biên truy vấn. Bộ frontend 13 test modal/dự báo/quyền nhà máy đạt; test modal kiểm tra chưa mở thì không gọi API, đổi trạm/nhà máy và phân trang đúng, không giữ bảng nhà máy trước, 403 ẩn bảng, Escape và trả focus về nút mở. Các test modal đã chạy lại sau tích hợp auth/polling. Lint và build frontend đạt. Kiểm tra route thật qua APIClient với superuser local trả 200, 6 trạm SH/3 trạm VS, và không gọi nguồn ngoài. Không phát sinh migration mới cho modal, chưa push hoặc deploy lên Orange Pi/Vercel.
