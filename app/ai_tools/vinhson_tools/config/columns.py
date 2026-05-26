"""
Column indices (0-based) for Google Sheets - Vĩnh Sơn
"""

# Column indices (0-based) cho Google Sheets - Sheet "Sản lượng"
COL_DATE = 1                # B: Ngày
COL_RESERVOIR = 2           # C: Hồ chứa (Vinh Son -A, -B, -C)
COL_PLAN_LEVEL = 3          # D: Mực nước kế hoạch
COL_PLAN_INFLOW = 4         # E: Lưu lượng nước về kế hoạch
COL_DEAD_LEVEL = 5          # F: Mực nước chết
COL_WATER_LEVEL = 6         # G: Mức nước thượng lưu lúc 24h00'
COL_VOLUME = 7              # H: Dung tích hữu ích hồ chứa lúc 24h00'
COL_INFLOW = 8              # I: Lưu lượng trung bình ngày nước về tính toán (Qv)
COL_TURBINE = 9             # J: Lưu lượng trung bình ngày qua máy tính toán (Qcm)
COL_SPILLWAY = 10           # K: Lưu lượng xả lũ (Qxl)
COL_QC_DAY = 11             # L: Sản lượng Qc ngày
COL_OUTPUT_DAY = 12         # M: Sản lượng điện đầu cực ngày
COL_COMMERCIAL_DAY = 13     # N: Sản lượng điện thương phẩm ngày
COL_QC_MONTH_PLAN = 14      # O: Sản lượng Qc Ao giao tháng
COL_QC_MONTH_ACC = 15       # P: Sản lượng Qc lũy kế tháng
COL_OUTPUT_MONTH = 16       # Q: Sản lượng điện đầu cực tháng
COL_COMMERCIAL_MONTH = 17   # R: Sản lượng điện thương phẩm tháng
COL_QC_YEAR_PLAN = 18       # S: Sản lượng Qc năm Ao giao
COL_QC_YEAR_ACC = 19        # T: Sản lượng Qc lũy kế năm
COL_OUTPUT_YEAR = 20        # U: Sản lượng điện đầu cực năm
COL_COMMERCIAL_YEAR = 21    # V: Sản lượng điện thương phẩm năm
COL_PLAN_YEAR = 22          # W: Sản lượng kế hoạch năm
COL_SELF_USE = 23           # X: Sản lượng tự dùng ngày

# Column indices (0-based) cho Google Sheets - Sheet "Giờ phát"
COL_HOURS_DATE = 1          # B: Ngày
COL_HOURS_UNIT = 2          # C: Tổ máy (H1, H2, H3, H4, H5, H6)
COL_HOURS_OPERATING = 3     # D: Tổng số giờ phát điện
COL_HOURS_STOPPED = 4       # E: Tổng số giờ ngừng
