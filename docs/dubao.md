# 📊 Tài liệu Nguyên lý Dự báo Thủy văn & Sản lượng (Sông Hinh & Vĩnh Sơn)

Tài liệu này trình bày chi tiết nguyên lý toán học, thuật toán và quy trình xử lý dữ liệu được áp dụng để dự báo Lưu lượng nước về ($Q_{ve}$) và Sản lượng điện phát của hai nhà máy thủy điện **Sông Hinh** và **Vĩnh Sơn**.

---

## 1. Phương pháp Tìm Năm Tương Đồng (Analog Year Selection)

Nguyên lý cốt lõi của mô hình dự báo là giả định rằng điều kiện khí hậu và thủy văn có tính chu kỳ và lặp lại. Mô hình tìm kiếm một **năm tương đồng** trong quá khứ dựa trên lượng nước về của tháng sát trước tháng dự báo.

### Quy trình lựa chọn:
1. **Xác định tháng đối chiếu ($M-1$):** Nếu tháng dự báo là tháng $M$, tháng đối chiếu sẽ là tháng $M-1$ (Ví dụ: Dự báo cho tháng `06/2026` thì tháng đối chiếu là `05/2026`).
2. **Thu thập dữ liệu lịch sử:** Lấy giá trị trung bình $Q_{ve}$ của tháng $M-1$ trong 3 năm liền kề gần nhất ($Y-1$, $Y-2$, $Y-3$).
3. **So sánh sai lệch:** Tính toán độ lệch tuyệt đối giữa trung bình $Q_{ve}$ tháng đối chiếu của năm hiện tại so với các năm lịch sử:
   $$\Delta Q_{ve}^{(i)} = |Q_{ve, \text{hiện tại}}^{(M-1)} - Q_{ve, \text{lịch sử } i}^{(M-1)}|$$
4. **Chọn năm tương đồng ($A$):** Năm lịch sử có $\Delta Q_{ve}$ nhỏ nhất sẽ được chọn làm năm tương đồng. 
5. **Xây dựng chuỗi số liệu nền:** Chuỗi số liệu chi tiết 30 ngày của tháng $M$ thuộc năm tương đồng $A$ sẽ được dùng làm dữ liệu cơ sở cho dự báo tháng $M$ năm hiện tại.

---

## 2. Hệ số Độ ẩm Lưu vực (Catchment Wetness Scaling)

Để phản ánh độ ẩm của đất lưu vực (yếu tố quyết định tỷ lệ dòng chảy tràn khi có mưa), mô hình tích hợp dữ liệu mưa thực tế của tháng đối chiếu để hiệu chỉnh lượng nước về.

### Mô hình toán học:
1. **Lấy tổng lượng mưa tháng trước:**
   - $R_{\text{cur}}$: Tổng lượng mưa thực tế tháng $M-1$ của năm hiện tại (được đồng bộ tự động từ hệ thống trạm đo mưa VRAIN).
   - $R_{\text{ana}}$: Tổng lượng mưa tháng $M-1$ của năm tương đồng $A$.
2. **Tính tỷ lệ lượng mưa ($ratio$):**
   $$ratio = \frac{R_{\text{cur}}}{R_{\text{ana}}} \quad (\text{nếu } R_{\text{ana}} > 0, \text{ngược lại } ratio = 1.0)$$
3. **Tính hệ số độ ẩm lưu vực ($wetness\_factor$):**
   $$wetness\_factor = 1.0 + (ratio - 1.0) \times 0.2$$
   *Hệ số này được khống chế giới hạn (capping) để đảm bảo tính an toàn vận hành:*
   $$0.8 \le wetness\_factor \le 1.3$$
4. **Hiệu chỉnh lượng nước về cơ sở:**
   $$Q_{ve, \text{base}}^{(d)} = Q_{ve, \text{lịch sử}}^{(d)} \times wetness\_factor$$

---

## 3. Hiệu chỉnh theo Dự báo Thời tiết Thời gian Thực (Real-time Weather Scaling)

Trong các ngày đầu của kỳ dự báo, mô hình tích hợp lượng mưa dự báo thời gian thực từ API Open-Meteo để điều chỉnh tức thời lưu lượng dòng chảy về.

### Thang hiệu chỉnh dòng chảy theo mưa dự báo hàng ngày:

| Lượng mưa dự báo hàng ngày ($P$, mm) | Hệ số hiệu chỉnh ($factor_{\text{weather}}$) | Ý nghĩa thủy văn |
|:---:|:---:|---|
| $P < 5\text{ mm}$ | **$1.0$** | Mưa nhỏ, thấm hoàn toàn vào đất, không tạo dòng chảy mặt đáng kể. |
| $5\text{ mm} \le P < 15\text{ mm}$ | **$1.2$** | Mưa trung bình, bắt đầu đóng góp dòng chảy mặt nhẹ. |
| $15\text{ mm} \le P < 35\text{ mm}$ | **$1.5$** | Mưa to, tạo dòng chảy mặt rõ rệt đổ về hồ. |
| $P \ge 35\text{ mm}$ | **$2.0$** | Mưa rất to, nguy cơ lũ quét hoặc dòng chảy về hồ tăng vọt. |

Lưu lượng nước về dự báo cuối cùng cho ngày $d$:
$$Q_{ve, \text{final}}^{(d)} = Q_{ve, \text{base}}^{(d)} \times factor_{\text{weather}}^{(d)}$$

---

## 4. Tính toán Cân bằng Nước Hồ chứa (Reservoir Water Balance)

Mô hình thực hiện tính toán cân bằng nước hàng ngày để dự báo mực nước và dung tích hữu ích cuối kỳ của hồ chứa nhằm đưa ra khuyến nghị vận hành.

### Phương trình cân bằng nước:
$$V_{\text{cuối}} = V_{\text{đầu}} + V_{\text{về}} - V_{\text{phát}} \quad (\text{triệu m}^3)$$

Trong đó:
*   $V_{\text{đầu}}$: Dung tích hữu ích đầu kỳ (được tính bằng cách tra mực nước thực tế cuối tháng trước $H_{\text{đầu}}$ và trừ đi dung tích nước chết).
*   $V_{\text{về}}$: Tổng thể tích nước đổ về hồ chứa trong tháng dự báo:
    $$V_{\text{về}} = \frac{\sum_{d=1}^{N} (Q_{ve, \text{final}}^{(d)} \times 86400)}{1,000,000}$$
*   $V_{\text{phát}}$: Tổng thể tích nước chạy máy phát điện tiêu thụ trong tháng dự báo:
    $$V_{\text{phát}} = \frac{\sum_{d=1}^{N} (\text{Sản lượng ngày } (kWh) \times \text{STH})}{1,000,000}$$

### Suất tiêu hao nước (STH) áp dụng:
- **Nhà máy Sông Hinh:** $\text{STH} = 2.74\text{ m}^3/\text{kWh}$
- **Nhà máy Vĩnh Sơn:** $\text{STH} = 0.69\text{ m}^3/\text{kWh}$ (đối với bậc thang tổng thể, và $0.44\text{ m}^3/\text{kWh}$ đối với tổ máy thấp hơn tùy chế độ).

### Bậc thang thủy điện Vĩnh Sơn:
Đối với Vĩnh Sơn, cân bằng nước được tính toán độc lập cho 3 hồ chứa:
- **Hồ A:** $V_{\text{cuối, A}} = V_{\text{đầu, A}} + V_{\text{về, A}} - V_{\text{phát}}$ (Hồ A trực tiếp phát điện xả nước ra hạ lưu).
- **Hồ B:** $V_{\text{cuối, B}} = V_{\text{đầu, B}} + V_{\text{về, B}}$ (Chỉ tích nước hoặc xả tràn tự nhiên).
- **Hồ C:** $V_{\text{cuối, C}} = V_{\text{đầu, C}} + V_{\text{về, C}}$ (Chỉ tích nước hoặc xả tràn tự nhiên).

---

## 5. Cơ chế Cảnh báo Vận hành Tự động (Operational Alerting)

Dựa trên kết quả dung tích cuối kỳ dự báo ($V_{\text{cuối}}$) so với dung tích hữu ích tối đa của hồ chứa ($V_{\text{max}}$), hệ thống tự động đưa ra các cảnh báo vận hành trực quan:

> [!WARNING]
> **Cảnh báo nguy cơ xả lũ ($V_{\text{cuối}} > V_{\text{max}}$):**
> Nước về quá lớn hoặc sản lượng phát điện dự kiến quá thấp dẫn đến hồ chứa dự kiến vượt quá dung tích thiết kế an toàn. Khuyến nghị tăng công suất phát điện để chủ động hạ thấp mực nước hồ.

> [!CAUTION]
> **Cảnh báo thiếu hụt nước ($V_{\text{cuối}} < 0$):**
> Lượng nước đầu kỳ cộng nước về dự báo không đủ đáp ứng nhu cầu phát điện theo kế hoạch (hồ bị hạ xuống dưới mực nước chết). Yêu cầu giảm sản lượng phát điện để giữ mực nước hồ an toàn.

> [!NOTE]
> **Trạng thái hồ chứa an toàn ($0 \le V_{\text{cuối}} \le V_{\text{max}}$):**
> Dung tích hữu ích cuối kỳ nằm trong giới hạn vận hành bình thường. Nhà máy có thể tiếp tục vận hành theo kế hoạch sản xuất hiện tại.
