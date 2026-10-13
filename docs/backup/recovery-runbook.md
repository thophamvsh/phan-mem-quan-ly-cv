# Cài backup Orange Pi → R2 và kiểm thử phục hồi

Trạng thái: mã đã được chuẩn bị trong repository; **chưa tạo bucket, chưa upload dữ liệu thật, chưa bật timer trên Orange Pi**. Unit test không thay cho phục hồi thực tế.

Thiết kế: Python 3.10+ chạy trên host, `pg_dump -Fc`, `pg_dumpall --globals-only`, media/log/audit/config → archive độc lập → age → rclone → tải lại kiểm SHA-256. Không cần Django/Celery hoạt động. File `.env` và JSON credential không nằm trong gói mặc định; giữ khóa đang dùng trong kho bí mật riêng trên máy quản trị sạch. Không phục hồi khóa cũ đã thu hồi.

## 1. Cloudflare: tạo nơi lưu trước

Thực hiện trên trình duyệt, tài khoản Cloudflare có MFA:

1. Mở **R2 Object Storage → Overview → Create bucket**. Nếu R2 yêu cầu kích hoạt thanh toán, xem giá/điều kiện trên tài khoản trước khi xác nhận.
2. Tên `vsh-prod-backups`, storage class **Standard**.
3. Trong **Settings**, giữ **Public Development URL / r2.dev disabled**, không thêm Custom Domain. Không cần CORS.
4. **Bucket lock rules → Add rule**: tên `daily-30-days`, prefix `daily/orangepi/`, giữ **30 ngày**. Quy tắc khóa ưu tiên hơn lifecycle.
5. **Object lifecycle rules → Add rule**: cùng prefix, xóa object sau **30 ngày**. Việc xóa diễn ra theo xử lý lifecycle, không nhất thiết đúng giây hết hạn.
6. Tạo bucket thứ hai `vsh-recovery-checkpoints`, private, **không có lifecycle 30 ngày**. Dùng máy quản trị cho bucket này.
7. Trong quản lý R2 API tokens, tạo token riêng `orangepi-backup`, **Object Read & Write**, **chỉ bucket `vsh-prod-backups`**. Lưu Access Key ID, Secret Access Key và S3 endpoint vào password manager. Không gửi vào chat.

Token này vẫn có quyền xóa object khi hết lock; lock không bảo vệ khỏi người quản trị account sửa chính sách. Không đặt credential quản trị bucket/checkpoint trên Orange Pi.

Nguồn: [tạo bucket](https://developers.cloudflare.com/r2/buckets/create-buckets/), [token scoped](https://developers.cloudflare.com/r2/api/tokens/), [lock](https://developers.cloudflare.com/r2/buckets/bucket-locks/), [lifecycle](https://developers.cloudflare.com/r2/buckets/object-lifecycles/).

## 2. Healthchecks.io → Telegram

Trên máy quản trị tạo tài khoản/project tại Healthchecks.io, kiểm tra gói dịch vụ phù hợp trước khi đăng ký:

1. Tạo check `VSH OrangePi backup`, loại **Simple**, Period **1 day**, Grace **2 hours**. Như vậy quá 26 giờ từ success cuối sẽ báo Down.
2. Vào **Integrations**, thêm **Telegram**, làm theo liên kết bot và gán integration cho check này. Thử thông báo Telegram trong giao diện.
3. Lưu ping URL dạng `https://hc-ping.com/<uuid>` vào password manager; trên Pi chỉ lưu trong `/etc/vsh-backup/heartbeat.url`.
4. Job gửi success chỉ sau khi xác minh bản tải về; lỗi gửi `/fail`. Không gửi nội dung SQL/log/token. Không dùng `/start` để thay đổi thời điểm success cuối.
5. Sau lần backup đầu, dùng check thử riêng Period 1 minute + Grace 1 minute, ngừng ping để kiểm tra Telegram thật sự báo quá hạn. Không giả success cho check production.

Theo dõi bên ngoài phát hiện cả mất điện/mất mạng. Không cần watchdog systemd trên chính Pi. [Cơ chế check và ping](https://healthchecks.io/docs/).

## 3. Tạo khóa age trên máy quản trị sạch (Windows PowerShell)

Tải bản Windows chính thức tại [age releases](https://github.com/FiloSottile/age/releases), giải nén `age.exe`, `age-keygen.exe` vào một thư mục công cụ. Mở PowerShell tại thư mục đó:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\VSH-recovery-keys"
.\age-keygen.exe -o "$env:USERPROFILE\VSH-recovery-keys\vsh-age-identity.txt"
.\age-keygen.exe -y "$env:USERPROFILE\VSH-recovery-keys\vsh-age-identity.txt"
```

Lệnh cuối chỉ in public recipient bắt đầu `age1...`; chép dòng này sang Pi. Private identity trong file `vsh-age-identity.txt` giữ ở password manager/ổ offline, hai bản độc lập; không đặt trong repository hoặc gửi lên Pi. Hạn chế quyền thư mục Windows cho tài khoản quản trị. Tạo key một lần, không ghi đè key cũ khi chạy lại hướng dẫn.

## 4. Orange Pi: cài công cụ và file cấu hình

Sau khi mã trong repository đã được commit/push và pull về Pi:

```bash
cd /var/www/backend/phan-mem-quan-ly-cv
sudo apt update
sudo apt install -y python3 age rclone
age --version
rclone version
findmnt /mnt/nvme
sudo docker inspect vsh-prod-app-1 --format '{{json .Mounts}}'
```

Xác minh UUID NVMe là `15adcf22-8515-429d-a01b-99dba45c615e`. Đọc mount `/vol/audit-archives` để điền `audit_archives` chính xác. Không tạo thư mục rỗng để che việc chọn sai dữ liệu nguồn.

```bash
sudo install -d -m 700 /etc/vsh-backup
sudo install -d -m 700 /mnt/nvme/vsh-backup-staging
sudo install -d -m 755 /usr/local/lib/vsh-backup
sudo install -m 644 scripts/backup/backup_daily.py scripts/backup/verify_backup.py /usr/local/lib/vsh-backup/
sudo install -m 600 deploy/backup/backup.ini.example /etc/vsh-backup/backup.ini
sudo install -m 600 deploy/backup/rclone.conf.example /etc/vsh-backup/rclone.conf
sudo nano /etc/vsh-backup/backup.ini
sudo nano /etc/vsh-backup/rclone.conf
sudo nano /etc/vsh-backup/recipients.txt
sudo nano /etc/vsh-backup/heartbeat.url
sudo chmod 600 /etc/vsh-backup/backup.ini /etc/vsh-backup/rclone.conf /etc/vsh-backup/recipients.txt /etc/vsh-backup/heartbeat.url
```

Điền key R2 vào `rclone.conf`, public age recipient vào `recipients.txt`, ping URL vào `heartbeat.url`. Chỉ điền trên máy, không dán credential vào lệnh có shell history. `config_files` là allowlist bắt buộc: chỉnh lại đường dẫn thực tế; nếu thiếu file, job dừng. Khi nâng cấp script chỉ cài lại hai file Python, không ghi đè cấu hình/khóa đang dùng bằng example.

Rclone dùng `copyto --immutable`, tên object UTC ngẫu nhiên cho mỗi lần chạy, không dùng `sync` hoặc remote delete. [Rclone R2](https://developers.cloudflare.com/r2/examples/rclone/).

## 5. Cài unit, chưa bật lịch

```bash
sudo install -m 644 deploy/systemd/vsh-backup.service deploy/systemd/vsh-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/vsh-backup.service /etc/systemd/system/vsh-backup.timer
systemd-analyze calendar '*-*-* 02:30:00 Asia/Ho_Chi_Minh'
sudo python3 /usr/local/lib/vsh-backup/backup_daily.py --check
```

`--check` kiểm tra điều kiện local, không xác nhận quyền R2, recipient đúng người, cấu hình monitor hay khả năng restore.

## 6. Kiểm thử R2 bằng dữ liệu vô hại

Trên Pi tạo file thử nhỏ, dùng tên object duy nhất trong prefix `daily/orangepi/probe/`. Upload/download bằng `rclone --config /etc/vsh-backup/rclone.conf copyto ...`, so SHA-256. Dùng đúng object thử để kiểm tra delete/overwrite bị lock từ chối. Không thử xóa backup thật. Object thử có thể bị giữ 30 ngày, chi phí theo tài khoản.

Kiểm tra bằng token Pi: đọc bucket checkpoint phải bị AccessDenied; bằng cửa sổ không đăng nhập: không có public URL đọc object. Xác nhận lock/lifecycle trong dashboard bằng tài khoản quản trị (token Pi không có quyền sửa cấu hình).

## 7. Chạy backup đầu và tải bản độc lập về máy sạch

```bash
sudo systemctl start --no-block vsh-backup.service
sudo journalctl -u vsh-backup.service -f
```

Ctrl+C chỉ thoát xem log. Kiểm tra sau khi service kết thúc:

```bash
sudo systemctl show vsh-backup.service -p Result -p ExecMainStatus
sudo cat /mnt/nvme/vsh-backup-staging/last-success.json
```

Cần Result=success, ExecMainStatus=0, Telegram/Healthchecks Up và receipt có remote/SHA/bytes. Receipt phản ánh upload + download hash, **chưa phải nghiệm thu restore**. Dùng máy sạch tải object trong receipt từ R2, lưu riêng SHA-256. Không cần mở port mới trên router.

Staging thành công giữ archive mã hóa tối thiểu đến lượt cleanup sau 3 ngày; plaintext đã xóa sau xác minh remote. Staging lỗi được giữ quyền700 để xử lý; không tự xóa. Mỗi lần chạy cần tối thiểu5GiB dự phòng cộng 4 lần kích thước nguồn+DB, nên kiểm tra dung lượng thực tế.

## 8. Giải mã, phục hồi thử trên Windows sạch

Đặt age.exe vào PATH của phiên PowerShell hoặc dùng terminal nhận diện được `age`. Checkout mã nguồn tin cậy, không thực thi script từ backup:

```powershell
cd E:\SangKien\phan-mem-quan-ly-cv
python scripts/backup/verify_backup.py "E:\SangKien\backups\r2\BACKUP.tar.gz.age" --identity "$env:USERPROFILE\VSH-recovery-keys\vsh-age-identity.txt" --sha256 "SHA256_TRONG_RECEIPT" --output "E:\SangKien\backups\r2-restore-new"
```

Thay placeholder bằng tên thật, output phải chưa tồn tại. Script giải mã, chặn path traversal/link trong tar, so tất cả checksum và giải nén media. Không thực thi globals/config. Đặt quyền thư mục output trước khi dùng vì Linux mode700 không thay ACL Windows.

Khôi phục dữ liệu vào container test mới (Docker Desktop):

```powershell
$restoreName = "vsh-r2-restore-" + [guid]::NewGuid().ToString("N").Substring(0,8)
$env:POSTGRES_PASSWORD = [guid]::NewGuid().ToString("N")
docker run -d --name $restoreName --network none -e POSTGRES_PASSWORD -e POSTGRES_DB=vsh_restore_test pgvector/pgvector:pg16
Remove-Item Env:POSTGRES_PASSWORD
docker exec $restoreName pg_isready -U postgres -d vsh_restore_test
```

Chờ `accepting connections`, sau đó:

```powershell
docker cp "E:\SangKien\backups\r2-restore-new\payload\database.dump" "${restoreName}:/tmp/database.dump"
docker exec $restoreName pg_restore --exit-on-error --no-owner --no-privileges -U postgres -d vsh_restore_test /tmp/database.dump
if ($LASTEXITCODE -ne 0) { throw "Restore failed" }
docker exec $restoreName psql -U postgres -d vsh_restore_test -c "SELECT count(*) FROM core_user; SELECT count(*) FROM core_user_profile; SELECT count(*) FROM django_migrations;"
```

Đối chiếu số lượng/bảng/ngày/tổng nghiệp vụ với manifest và dữ liệu nguồn; so media với các trường FileField của DB. Lệnh trên chỉ kiểm tra **dữ liệu**. Để nghiệm thu roles/quyền: review `globals.sql` bằng máy sạch, tạo cluster test khác, áp dụng có chọn lọc roles/tablespaces được phép rồi restore giữ owner/privileges. Không chạy globals mù quáng hoặc chạy SQL khôi phục vào production. DB dump có thể chứa mã SQL, nên container thử không có mạng, host mount hay credential production.

Sau kiểm tra, xác nhận đúng `$restoreName` mới xóa container thử bằng `docker rm -fv $restoreName`; thao tác này xóa dữ liệu test/volume của container đó. Giữ archive gốc và báo cáo phục hồi.

## 9. Checkpoint và bật lịch

Để có checkpoint nhất quán DB/media: chọn khoảng bảo trì, ngừng ghi và worker/beat, giữ DB chạy; chạy backup rồi bật lại các dịch vụ kể cả backup lỗi. Script hiện chạy live, **không tự dừng production**. Không gọi bản live là snapshot nguyên tử.

Sau giải mã/restore/đối chiếu đạt, máy quản trị upload gói vào `vsh-recovery-checkpoints` bằng credential riêng, tải lại và xác minh. Giữ báo cáo và ít nhất một bản offline. Chỉ thay/xóa checkpoint cũ sau khi checkpoint mới đạt; backup thường được lifecycle xóa sau30 ngày.

Chỉ bật lịch khi đã nghiệm thu bản đầu:

```bash
sudo systemctl enable --now vsh-backup.timer
sudo systemctl list-timers vsh-backup.timer --all
```

`Persistent=true` có thể kích hoạt lần bị lỡ ngay lúc bật timer. Chạy reboot có kế hoạch rồi kiểm tra mount, timer, backend health và log backup. Theo dõi hai lần chạy đầu và lịch test restore hằng tháng. Kiểm tra Healthchecks Telegram với cả lỗi chủ động/check thử quá hạn trước khi kết thúc nghiệm thu.

## 10. Giới hạn và xử lý lỗi

- Hash tải lại chứng minh object khớp lúc backup, không chứng minh dữ liệu nguồn sạch.
- `pg_restore --list` không chứng minh restore toàn bộ được; phải thử restore.
- Source chứa symlink/special file hoặc media/audit liên tục đổi: dừng, giữ staging và cảnh báo. Log đang ghi có warning rõ ràng trong manifest/receipt.
- Hiện chỉ dump DB ứng dụng. Nếu phát hiện DB khác ngoài DB ứng dụng và maintenance `postgres`, job dừng để mở rộng scope. Nếu có dữ liệu nghiệp vụ trong `postgres`, phải thêm backup trước khi nghiệm thu.
- Chưa tự kiểm tra mọi FileField liên kết media; đây là gate của restore/checkpoint. Chưa tự backup cấu hình PostgreSQL tùy chỉnh; quản trị cần khai báo nếu có.
- `last-success.json` chỉ tồn tại trên host; lưu SHA/checkpoint ngoài Pi. Không xóa tay failed staging trước khi xác nhận bản tốt khác.
- Không có bucket/token/recipient/heartbeat thật thì chưa thể nghiệm thu upload, lock, retention, Telegram và ARM64 runtime.

Test local không cần Django/database:

```powershell
python -m unittest discover -s tests/backup -v
```

Test flock chạy đầy đủ trên Linux/CI. Mã backup chỉ cài trên host, không cần rebuild image backend.
