import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import gspread
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from google.oauth2.service_account import Credentials

from .models import ThongSoThuyVanThucTe, ThongsoGioPhat, ThongsoSanxuat
from .plants import normalize_plant_code

logger = logging.getLogger(__name__)

SAN_LUONG_SYNC_FIELDS = (
    "cot_c",
    "cot_d",
    "cot_f",
    "cot_g",
    "cot_h",
    "cot_i",
    "cot_j",
    "cot_k",
    "cot_l",
    "cot_m",
    "cot_n",
    "cot_o",
    "cot_p",
    "cot_q",
    "cot_r",
    "cot_s",
    "cot_t",
    "cot_u",
    "cot_v",
    "cot_w",
    "cot_x",
)
MIN_SAN_LUONG_FILLED_FIELDS = 8
INSUFFICIENT_SAN_LUONG_MESSAGE = (
    "Dữ liệu không đủ để đồng bộ. Vui lòng kiểm tra Google Sheet."
)
INVALID_SYNC_DATE_MESSAGE = "Không được đồng bộ dữ liệu vượt quá ngày D-1."
GOOGLE_SHEET_SYNC_START_DATE = datetime(2023, 1, 1).date()
GOOGLE_SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
THUC_TE_SYNC_FIELDS = (
    "muc_nuoc_ho",
    "qve",
    "muc_nuoc_ho_a",
    "muc_nuoc_ho_b",
    "muc_nuoc_ho_c",
    "qve_ho_a",
    "qve_ho_b",
    "qve_ho_c",
    "qve_tong",
)
THUC_TE_SHEET_CONFIG = {
    "songhinh": {
        "spreadsheet_env": "SONGHINH_STATS_EXPORT_SPREADSHEET_ID",
        "sheet_name": "2023",
        "start_row": 8,
        "range_end_col": "F",
    },
    "vinhson": {
        "spreadsheet_env": "VINHSON_STATS_EXPORT_SPREADSHEET_ID",
        "sheet_name": "2023 ngày",
        "start_row": 6,
        "range_end_col": "H",
    },
}


class GoogleSheetSyncError(Exception):
    user_message = "Không thể lấy dữ liệu từ Google Sheet. Vui lòng thử lại sau."

    def __init__(self, user_message=None):
        if user_message:
            self.user_message = user_message
        super().__init__(self.user_message)


@dataclass
class ParsedSheetResult:
    data: list[dict] = field(default_factory=list)
    skipped_rows: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_range: str = ""


@dataclass
class SaveResult:
    saved_count: int = 0
    updated_count: int = 0


@dataclass
class SyncRangeResult:
    saved_count: int = 0
    updated_count: int = 0
    parsed_count: int = 0
    skipped_count: int = 0
    source_range: str = ""
    warnings: list[str] = field(default_factory=list)


def get_env_value(name):
    value = os.environ.get(name)
    if value:
        return value

    env_path = os.path.join(settings.BASE_DIR.parent, ".env")
    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, raw_value = line.split("=", 1)
            if key.strip() == name:
                return raw_value.strip().strip('"').strip("'")

    return None


def get_gspread_client(nhamay="songhinh"):
    nhamay = normalize_plant_code(nhamay)
    credential_file = get_env_value(f"{nhamay.upper()}_GOOGLE_CREDENTIALS")
    if not credential_file:
        credential_file = (
            "vinhson-account-key.json"
            if nhamay == "vinhson"
            else "ai-project-484022-8239457b26bb.json"
        )
    creds_path = os.path.join(settings.BASE_DIR, credential_file)

    if not os.path.exists(creds_path):
        raise GoogleSheetSyncError("Chưa cấu hình Google Sheet credentials.")

    creds = Credentials.from_service_account_file(creds_path, scopes=[GOOGLE_SHEETS_READONLY_SCOPE])
    return gspread.authorize(creds)


def parse_date(date_str):
    if not date_str:
        return None

    date_str = str(date_str).strip()
    formats = (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    )

    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            if timezone.is_naive(parsed_date):
                return timezone.make_aware(parsed_date)
            return parsed_date
        except ValueError:
            pass

    return None


def parse_filter_date(date_str):
    if not date_str:
        return None

    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def get_allowed_sync_date():
    return timezone.localdate() - timedelta(days=1)


def get_sync_date_error(filter_date_str, filter_date):
    allowed_date = get_allowed_sync_date()
    if not filter_date_str:
        return None
    if filter_date > allowed_date:
        return {
            "error": INVALID_SYNC_DATE_MESSAGE,
            "max_allowed_date": str(allowed_date),
        }
    return None


def parse_item_date(value):
    if not value:
        return None
    if hasattr(value, "date"):
        return value.date()

    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        parsed_datetime = parse_date(text)
        return parsed_datetime.date() if parsed_datetime else None


def is_date_after_allowed(value, allowed_date):
    parsed_date = parse_item_date(value)
    return parsed_date is not None and parsed_date > allowed_date


def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.strip().replace(" ", "")
            if not val:
                return None

            has_comma = "," in val
            has_dot = "." in val

            if has_comma and has_dot:
                if val.rfind(",") > val.rfind("."):
                    val = val.replace(".", "").replace(",", ".")
                else:
                    val = val.replace(",", "")
            elif has_comma:
                parts = val.split(",")
                if len(parts) == 2 and len(parts[1]) in (1, 2):
                    val = val.replace(",", ".")
                else:
                    val = val.replace(",", "")
            elif has_dot:
                parts = val.split(".")
                if len(parts) > 2:
                    val = val.replace(".", "")
        return float(val)
    except (TypeError, ValueError):
        return None


def safe_float_decimal_comma(val):
    try:
        if isinstance(val, str):
            val = val.strip().replace(" ", "")
            if not val:
                return None

            has_comma = "," in val
            has_dot = "." in val

            if has_comma and has_dot:
                if val.rfind(",") > val.rfind("."):
                    val = val.replace(".", "").replace(",", ".")
                else:
                    val = val.replace(",", "")
            elif has_comma:
                val = val.replace(",", ".")
            elif val.count(".") > 1:
                val = val.replace(".", "")
        return float(val)
    except (TypeError, ValueError):
        return None


def safe_int_vinhson(val):
    try:
        if isinstance(val, (int, float)):
            return float(int(val))
        if isinstance(val, str):
            val = val.strip().replace(" ", "")
            if not val:
                return None
            val = val.replace(".", "").replace(",", "")
            return float(int(val))
        return None
    except (TypeError, ValueError):
        return None


def safe_float_vinhson_decimal(val):
    res = safe_float(val)
    if res is not None:
        return round(res, 2)
    return None


def parse_to_may(val):
    text = str(val or "").strip().upper()
    if text.startswith("H"):
        text = text[1:]
    return int(text) if text.isdigit() else None


def parse_cot_c(val, nhamay):
    nhamay = normalize_plant_code(nhamay)
    if nhamay == "vinhson":
        return "vinhson"

    if val is None:
        return None

    val = str(val).strip()
    return val or None


def has_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def count_san_luong_filled_fields(item):
    return sum(1 for field in SAN_LUONG_SYNC_FIELDS if has_value(item.get(field)))


def is_san_luong_row_complete_enough(item):
    return count_san_luong_filled_fields(item) >= MIN_SAN_LUONG_FILLED_FIELDS


def get_spreadsheet_id(nhamay):
    nhamay = normalize_plant_code(nhamay)
    if nhamay == "songhinh":
        return get_env_value("SONGHINH_SPREADSHEET_ID")
    if nhamay == "vinhson":
        return get_env_value("VINHSON_SPREADSHEET_ID")
    return get_env_value(f"{nhamay.upper()}_SPREADSHEET_ID")


def get_stats_export_spreadsheet_id(nhamay):
    config = THUC_TE_SHEET_CONFIG.get(normalize_plant_code(nhamay))
    if not config:
        return None
    return get_env_value(config["spreadsheet_env"])


def get_san_luong_sheet_row_number(filter_date):
    if not filter_date or filter_date < GOOGLE_SHEET_SYNC_START_DATE:
        return None
    return (filter_date - GOOGLE_SHEET_SYNC_START_DATE).days + 2


def get_gio_phat_sheet_row_number(filter_date):
    if not filter_date or filter_date < GOOGLE_SHEET_SYNC_START_DATE:
        return None
    return (filter_date - GOOGLE_SHEET_SYNC_START_DATE).days * 2 + 3


def get_thuc_te_sheet_row_number(nhamay, filter_date):
    config = THUC_TE_SHEET_CONFIG.get(normalize_plant_code(nhamay))
    if not config or not filter_date or filter_date < GOOGLE_SHEET_SYNC_START_DATE:
        return None
    return config["start_row"] + (filter_date - GOOGLE_SHEET_SYNC_START_DATE).days


def prefix_sheet_range_rows(rows):
    return [["", *row] for row in (rows or [])]


def normalize_worksheet_title(value):
    return " ".join(str(value or "").strip().lower().split())


def get_worksheet_by_title(spreadsheet, expected_title):
    try:
        return spreadsheet.worksheet(expected_title)
    except gspread.exceptions.WorksheetNotFound:
        expected_normalized = normalize_worksheet_title(expected_title)
        try:
            worksheets = spreadsheet.worksheets()
        except Exception as exc:
            raise GoogleSheetSyncError(f"Không tìm thấy tab Google Sheet: {expected_title}") from exc

        for worksheet in worksheets:
            if normalize_worksheet_title(getattr(worksheet, "title", "")) == expected_normalized:
                return worksheet

        available_titles = ", ".join(getattr(worksheet, "title", "") for worksheet in worksheets) or "không có tab nào"
        raise GoogleSheetSyncError(
            f"Không tìm thấy tab Google Sheet '{expected_title}'. Các tab hiện có: {available_titles}."
        )


def get_san_luong_rows(worksheet, filter_date=None):
    row_number = get_san_luong_sheet_row_number(filter_date)
    if row_number:
        return prefix_sheet_range_rows(worksheet.get(f"B{row_number}:X{row_number}"))

    return worksheet.get_all_values()[1:]


def get_gio_phat_rows(worksheet, filter_date=None):
    row_number = get_gio_phat_sheet_row_number(filter_date)
    if row_number:
        start_row = max(3, row_number - 2)
        end_row = row_number + 3
        return prefix_sheet_range_rows(worksheet.get(f"B{start_row}:E{end_row}"))

    return worksheet.get_all_values()


def get_thuc_te_rows(worksheet, nhamay, filter_date=None):
    nhamay = normalize_plant_code(nhamay)
    config = THUC_TE_SHEET_CONFIG.get(nhamay)
    if not config:
        return []

    row_number = get_thuc_te_sheet_row_number(nhamay, filter_date)
    if row_number:
        return worksheet.get(f"A{row_number}:{config['range_end_col']}{row_number}")

    return worksheet.get_all_values()[config["start_row"] - 1:]


def get_thuc_te_rows_for_date_range(worksheet, nhamay, start_date, end_date):
    nhamay = normalize_plant_code(nhamay)
    config = THUC_TE_SHEET_CONFIG.get(nhamay)
    if not config:
        return []

    start_row = get_thuc_te_sheet_row_number(nhamay, start_date)
    end_row = get_thuc_te_sheet_row_number(nhamay, end_date)
    if not start_row or not end_row:
        return worksheet.get_all_values()[config["start_row"] - 1:]

    return worksheet.get(f"A{start_row}:{config['range_end_col']}{end_row}")


def iter_dates(start_date, end_date):
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def parsed_result_covers_date_range(result, start_date, end_date):
    if not start_date or not end_date:
        return True

    expected_dates = set(iter_dates(start_date, end_date))
    parsed_dates = {
        parsed_date
        for parsed_date in (parse_item_date(item.get("ngay")) for item in result.data)
        if parsed_date is not None
    }
    return expected_dates.issubset(parsed_dates)


def parse_san_luong_records_with_metadata(rows, nhamay, filter_date=None, source_range=""):
    parsed_data = []
    skipped_rows = []
    nhamay = normalize_plant_code(nhamay)

    for index, row in enumerate(rows or [], start=1):
        padded_row = row + [""] * (24 - len(row))

        thoi_gian_str = padded_row[1]
        if not thoi_gian_str:
            skipped_rows.append({"row": index, "reason": "missing_date"})
            continue

        thoi_gian = parse_date(thoi_gian_str)
        if not thoi_gian:
            skipped_rows.append({"row": index, "reason": "invalid_date", "value": thoi_gian_str})
            continue

        if thoi_gian.year < 2023:
            skipped_rows.append({"row": index, "reason": "before_supported_year", "value": thoi_gian_str})
            continue
        if thoi_gian.date() > get_allowed_sync_date():
            skipped_rows.append({"row": index, "reason": "after_allowed_date", "value": thoi_gian_str})
            continue
        if filter_date and thoi_gian.date() != filter_date:
            skipped_rows.append({"row": index, "reason": "outside_filter_date", "value": thoi_gian_str})
            continue

        if nhamay == "vinhson":
            record = {
                "thoi_gian": thoi_gian,
                "thoi_gian_str": thoi_gian_str,
                "cot_c": parse_cot_c(padded_row[2], nhamay),
                "cot_d": safe_float_vinhson_decimal(padded_row[3]),
                "cot_f": safe_float_vinhson_decimal(padded_row[5]),
                "cot_g": safe_float_vinhson_decimal(padded_row[6]),
                "cot_h": safe_float_vinhson_decimal(padded_row[7]),
                "cot_i": safe_float_vinhson_decimal(padded_row[8]),
                "cot_j": safe_float_vinhson_decimal(padded_row[9]),
                "cot_k": safe_float_vinhson_decimal(padded_row[10]),
                "cot_l": safe_int_vinhson(padded_row[11]),
                "cot_m": safe_int_vinhson(padded_row[12]),
                "cot_n": safe_int_vinhson(padded_row[13]),
                "cot_o": safe_int_vinhson(padded_row[14]),
                "cot_p": safe_int_vinhson(padded_row[15]),
                "cot_q": safe_int_vinhson(padded_row[16]),
                "cot_r": safe_int_vinhson(padded_row[17]),
                "cot_s": safe_int_vinhson(padded_row[18]),
                "cot_t": safe_int_vinhson(padded_row[19]),
                "cot_u": safe_int_vinhson(padded_row[20]),
                "cot_v": safe_int_vinhson(padded_row[21]),
                "cot_w": safe_int_vinhson(padded_row[22]),
                "cot_x": safe_int_vinhson(padded_row[23]),
            }
        else:
            record = {
                "thoi_gian": thoi_gian,
                "thoi_gian_str": thoi_gian_str,
                "cot_c": parse_cot_c(padded_row[2], nhamay),
                "cot_d": safe_float(padded_row[3]),
                "cot_f": safe_float(padded_row[5]),
                "cot_g": safe_float(padded_row[6]),
                "cot_h": safe_float(padded_row[7]),
                "cot_i": safe_float(padded_row[8]),
                "cot_j": safe_float(padded_row[9]),
                "cot_k": safe_float(padded_row[10]),
                "cot_l": safe_float(padded_row[11]),
                "cot_m": safe_float(padded_row[12]),
                "cot_n": safe_float(padded_row[13]),
                "cot_o": safe_float(padded_row[14]),
                "cot_p": safe_float(padded_row[15]),
                "cot_q": safe_float(padded_row[16]),
                "cot_r": safe_float(padded_row[17]),
                "cot_s": safe_float(padded_row[18]),
                "cot_t": safe_float(padded_row[19]),
                "cot_u": safe_float(padded_row[20]),
                "cot_v": safe_float(padded_row[21]),
                "cot_w": safe_float(padded_row[22]),
                "cot_x": safe_float(padded_row[23]),
            }
        parsed_data.append(record)

    return ParsedSheetResult(data=parsed_data, skipped_rows=skipped_rows, source_range=source_range)


def parse_san_luong_records(rows, nhamay, filter_date=None):
    return parse_san_luong_records_with_metadata(rows, nhamay, filter_date).data


def parse_gio_phat_records_with_metadata(rows, filter_date=None, source_range=""):
    parsed_data = []
    skipped_rows = []

    for index, row in enumerate(rows or [], start=1):
        padded_row = row + [""] * (5 - len(row))

        ngay_str = padded_row[1]
        if not ngay_str:
            skipped_rows.append({"row": index, "reason": "missing_date"})
            continue

        parsed_dt = parse_date(ngay_str)
        if not parsed_dt:
            skipped_rows.append({"row": index, "reason": "invalid_date", "value": ngay_str})
            continue
        ngay = parsed_dt.date()

        if ngay.year < 2023:
            skipped_rows.append({"row": index, "reason": "before_supported_year", "value": ngay_str})
            continue
        if ngay > get_allowed_sync_date():
            skipped_rows.append({"row": index, "reason": "after_allowed_date", "value": ngay_str})
            continue
        if filter_date and ngay != filter_date:
            skipped_rows.append({"row": index, "reason": "outside_filter_date", "value": ngay_str})
            continue

        to_may = parse_to_may(padded_row[2])
        if to_may is None:
            skipped_rows.append({"row": index, "reason": "invalid_unit", "value": padded_row[2]})
            continue

        parsed_data.append(
            {
                "ngay": str(ngay),
                "ngay_str": ngay_str,
                "to_may": to_may,
                "gio_phat_dien": safe_float(padded_row[3]),
                "gio_ngung": safe_float(padded_row[4]),
            }
        )

    return ParsedSheetResult(data=parsed_data, skipped_rows=skipped_rows, source_range=source_range)


def parse_gio_phat_records(rows, filter_date=None):
    return parse_gio_phat_records_with_metadata(rows, filter_date).data


def parse_thuc_te_records_with_metadata(rows, nhamay, filter_date=None, source_range="", start_date=None, end_date=None):
    nhamay = normalize_plant_code(nhamay)
    parsed_data = []
    skipped_rows = []

    for index, row in enumerate(rows or [], start=1):
        if nhamay == "vinhson":
            padded_row = row + [""] * (8 - len(row))
            ngay_str = padded_row[0]
        else:
            padded_row = row + [""] * (6 - len(row))
            ngay_str = padded_row[0]

        if not ngay_str:
            skipped_rows.append({"row": index, "reason": "missing_date"})
            continue

        parsed_dt = parse_date(ngay_str)
        if not parsed_dt:
            skipped_rows.append({"row": index, "reason": "invalid_date", "value": ngay_str})
            continue
        ngay = parsed_dt.date()

        if ngay.year < 2023:
            skipped_rows.append({"row": index, "reason": "before_supported_year", "value": ngay_str})
            continue
        if ngay > get_allowed_sync_date():
            skipped_rows.append({"row": index, "reason": "after_allowed_date", "value": ngay_str})
            continue
        if filter_date and ngay != filter_date:
            skipped_rows.append({"row": index, "reason": "outside_filter_date", "value": ngay_str})
            continue
        if start_date and ngay < start_date:
            skipped_rows.append({"row": index, "reason": "outside_filter_range", "value": ngay_str})
            continue
        if end_date and ngay > end_date:
            skipped_rows.append({"row": index, "reason": "outside_filter_range", "value": ngay_str})
            continue

        if nhamay == "vinhson":
            record = {
                "nha_may": nhamay,
                "ngay": str(ngay),
                "ngay_str": ngay_str,
                "muc_nuoc_ho": None,
                "qve": None,
                "muc_nuoc_ho_a": safe_float_decimal_comma(padded_row[1]),
                "muc_nuoc_ho_b": safe_float_decimal_comma(padded_row[2]),
                "muc_nuoc_ho_c": safe_float_decimal_comma(padded_row[3]),
                "qve_ho_a": safe_float_decimal_comma(padded_row[4]),
                "qve_ho_b": safe_float_decimal_comma(padded_row[5]),
                "qve_ho_c": safe_float_decimal_comma(padded_row[6]),
                "qve_tong": safe_float_decimal_comma(padded_row[7]),
            }
        elif nhamay == "songhinh":
            record = {
                "nha_may": nhamay,
                "ngay": str(ngay),
                "ngay_str": ngay_str,
                "muc_nuoc_ho": safe_float_decimal_comma(padded_row[1]),
                "qve": safe_float_decimal_comma(padded_row[5]),
                "muc_nuoc_ho_a": None,
                "muc_nuoc_ho_b": None,
                "muc_nuoc_ho_c": None,
                "qve_ho_a": None,
                "qve_ho_b": None,
                "qve_ho_c": None,
                "qve_tong": None,
            }
        else:
            skipped_rows.append({"row": index, "reason": "unsupported_plant", "value": nhamay})
            continue

        parsed_data.append(record)

    return ParsedSheetResult(data=parsed_data, skipped_rows=skipped_rows, source_range=source_range)


def parse_thuc_te_records(rows, nhamay, filter_date=None):
    return parse_thuc_te_records_with_metadata(rows, nhamay, filter_date).data


class GoogleSheetHydrologyService:
    def __init__(self, client_factory=get_gspread_client, spreadsheet_id_getter=get_spreadsheet_id):
        self.client_factory = client_factory
        self.spreadsheet_id_getter = spreadsheet_id_getter

    def _open_spreadsheet(self, nhamay):
        sheet_id = self.spreadsheet_id_getter(nhamay)
        if not sheet_id:
            raise GoogleSheetSyncError(f"Chưa cấu hình SPREADSHEET_ID cho {nhamay} trong .env")
        client = self.client_factory(nhamay)
        return client.open_by_key(sheet_id)

    def _open_thuc_te_spreadsheet(self, nhamay):
        nhamay = normalize_plant_code(nhamay)
        sheet_id = get_stats_export_spreadsheet_id(nhamay)
        if not sheet_id:
            raise GoogleSheetSyncError(f"Chưa cấu hình STATS_EXPORT_SPREADSHEET_ID cho {nhamay} trong .env")
        client = self.client_factory(nhamay)
        return client.open_by_key(sheet_id)

    def preview_san_luong(self, nhamay, filter_date=None):
        nhamay = normalize_plant_code(nhamay)
        try:
            sheet = self._open_spreadsheet(nhamay)
            worksheet = sheet.worksheet("Sản lượng")
            row_number = get_san_luong_sheet_row_number(filter_date)
            if row_number:
                source_range = f"Sản lượng!B{row_number}:X{row_number}"
            else:
                source_range = "Sản lượng!all_values"

            rows = get_san_luong_rows(worksheet, filter_date)
            result = parse_san_luong_records_with_metadata(rows, nhamay, filter_date, source_range)

            if filter_date and not result.data:
                fallback_rows = worksheet.get_all_values()[1:]
                fallback = parse_san_luong_records_with_metadata(
                    fallback_rows,
                    nhamay,
                    filter_date,
                    "Sản lượng!all_values",
                )
                fallback.warnings.append(
                    f"Không tìm thấy dữ liệu ở {source_range}; đã đọc lại toàn bộ tab Sản lượng."
                )
                return fallback

            return result
        except GoogleSheetSyncError:
            raise
        except Exception as exc:
            logger.exception("Failed to preview hydrology production sheet for plant %s", nhamay)
            raise GoogleSheetSyncError() from exc

    def preview_gio_phat(self, nhamay, filter_date=None):
        nhamay = normalize_plant_code(nhamay)
        try:
            sheet = self._open_spreadsheet(nhamay)
            worksheet = sheet.worksheet("Giờ phát")
            row_number = get_gio_phat_sheet_row_number(filter_date)
            if row_number:
                start_row = max(3, row_number - 2)
                end_row = row_number + 3
                source_range = f"Giờ phát!B{start_row}:E{end_row}"
            else:
                source_range = "Giờ phát!all_values"

            rows = get_gio_phat_rows(worksheet, filter_date)
            result = parse_gio_phat_records_with_metadata(rows, filter_date, source_range)

            if filter_date and not result.data:
                fallback_rows = worksheet.get_all_values()
                fallback = parse_gio_phat_records_with_metadata(
                    fallback_rows,
                    filter_date,
                    "Giờ phát!all_values",
                )
                fallback.warnings.append(
                    f"Không tìm thấy dữ liệu ở {source_range}; đã đọc lại toàn bộ tab Giờ phát."
                )
                return fallback

            return result
        except GoogleSheetSyncError:
            raise
        except Exception as exc:
            logger.exception("Failed to preview hydrology generation-hours sheet for plant %s", nhamay)
            raise GoogleSheetSyncError() from exc

    def preview_thuc_te(self, nhamay, filter_date=None):
        nhamay = normalize_plant_code(nhamay)
        config = THUC_TE_SHEET_CONFIG.get(nhamay)
        if not config:
            raise GoogleSheetSyncError("Nhà máy chưa được hỗ trợ đồng bộ thông số thủy văn thực tế.")

        try:
            sheet = self._open_thuc_te_spreadsheet(nhamay)
            worksheet = get_worksheet_by_title(sheet, config["sheet_name"])
            sheet_title = getattr(worksheet, "title", config["sheet_name"])
            row_number = get_thuc_te_sheet_row_number(nhamay, filter_date)
            if row_number:
                source_range = f"{sheet_title}!A{row_number}:{config['range_end_col']}{row_number}"
            else:
                source_range = f"{sheet_title}!all_values"

            rows = get_thuc_te_rows(worksheet, nhamay, filter_date)
            result = parse_thuc_te_records_with_metadata(rows, nhamay, filter_date, source_range)

            if filter_date and not result.data:
                fallback_rows = worksheet.get_all_values()[config["start_row"] - 1:]
                fallback = parse_thuc_te_records_with_metadata(
                    fallback_rows,
                    nhamay,
                    filter_date,
                    f"{sheet_title}!all_values",
                )
                fallback.warnings.append(
                    f"Không tìm thấy dữ liệu ở {source_range}; đã đọc lại toàn bộ tab {sheet_title}."
                )
                return fallback

            return result
        except GoogleSheetSyncError:
            raise
        except Exception as exc:
            logger.exception("Failed to preview actual hydrology sheet for plant %s", nhamay)
            raise GoogleSheetSyncError() from exc

    def preview_thuc_te_range(self, nhamay, start_date=None, end_date=None):
        nhamay = normalize_plant_code(nhamay)
        config = THUC_TE_SHEET_CONFIG.get(nhamay)
        if not config:
            raise GoogleSheetSyncError("Nhà máy chưa được hỗ trợ đồng bộ thông số thủy văn thực tế.")

        start_date = start_date or GOOGLE_SHEET_SYNC_START_DATE
        end_date = end_date or get_allowed_sync_date()
        if end_date > get_allowed_sync_date():
            end_date = get_allowed_sync_date()
        if start_date < GOOGLE_SHEET_SYNC_START_DATE:
            start_date = GOOGLE_SHEET_SYNC_START_DATE
        if start_date > end_date:
            return ParsedSheetResult(
                warnings=["Khoảng ngày đồng bộ không hợp lệ hoặc chưa có dữ liệu được phép đồng bộ."],
            )

        try:
            sheet = self._open_thuc_te_spreadsheet(nhamay)
            worksheet = get_worksheet_by_title(sheet, config["sheet_name"])
            sheet_title = getattr(worksheet, "title", config["sheet_name"])
            start_row = get_thuc_te_sheet_row_number(nhamay, start_date)
            end_row = get_thuc_te_sheet_row_number(nhamay, end_date)
            if start_row and end_row:
                source_range = f"{sheet_title}!A{start_row}:{config['range_end_col']}{end_row}"
            else:
                source_range = f"{sheet_title}!all_values"

            rows = get_thuc_te_rows_for_date_range(worksheet, nhamay, start_date, end_date)
            result = parse_thuc_te_records_with_metadata(
                rows,
                nhamay,
                source_range=source_range,
                start_date=start_date,
                end_date=end_date,
            )
            if parsed_result_covers_date_range(result, start_date, end_date):
                return result

            fallback = parse_thuc_te_records_with_metadata(
                worksheet.get_all_values()[config["start_row"] - 1:],
                nhamay,
                source_range=f"{sheet_title}!all_values",
                start_date=start_date,
                end_date=end_date,
            )
            fallback.warnings.append(
                f"Khong tim thay du ngay o {source_range}; da doc lai toan bo tab {sheet_title}."
            )
            return fallback
        except GoogleSheetSyncError:
            raise
        except Exception as exc:
            logger.exception("Failed to preview actual hydrology range for plant %s", nhamay)
            raise GoogleSheetSyncError() from exc

    def save_san_luong(self, *, data_list, nhamay, user, can_modify):
        nhamay = normalize_plant_code(nhamay)
        saved_count = 0
        updated_count = 0

        existing_by_time = {}
        for item in data_list:
            thoi_gian = item.get("thoi_gian")
            if not thoi_gian:
                continue
            existing = ThongsoSanxuat.objects.filter(thoi_gian=thoi_gian, nha_may=nhamay).first()
            if existing and not can_modify(user, existing):
                raise PermissionError("Ban chi duoc sua du lieu san xuat do chinh ban cap nhat.")
            existing_by_time[thoi_gian] = existing

        with transaction.atomic():
            for item in data_list:
                thoi_gian = item.get("thoi_gian")
                if not thoi_gian:
                    continue

                existing = existing_by_time.get(thoi_gian)
                _, created = ThongsoSanxuat.objects.update_or_create(
                    thoi_gian=thoi_gian,
                    nha_may=nhamay,
                    defaults={
                        **{field: item.get(field) for field in SAN_LUONG_SYNC_FIELDS},
                        "updated_by": user,
                        **({} if existing and existing.created_by_id else {"created_by": user}),
                    },
                )
                if created:
                    saved_count += 1
                else:
                    updated_count += 1

        return SaveResult(saved_count=saved_count, updated_count=updated_count)

    def save_gio_phat(self, *, data_list, nhamay, user, can_modify):
        nhamay = normalize_plant_code(nhamay)
        saved_count = 0
        updated_count = 0

        existing_by_key = {}
        for item in data_list:
            ngay = item.get("ngay")
            to_may = item.get("to_may")
            if not ngay or to_may is None:
                continue
            key = (ngay, to_may)
            existing = ThongsoGioPhat.objects.filter(ngay=ngay, to_may=to_may, nha_may=nhamay).first()
            if existing and not can_modify(user, existing):
                raise PermissionError("Ban chi duoc sua du lieu gio phat do chinh ban cap nhat.")
            existing_by_key[key] = existing

        with transaction.atomic():
            for item in data_list:
                ngay = item.get("ngay")
                to_may = item.get("to_may")

                if not ngay or to_may is None:
                    continue

                existing = existing_by_key.get((ngay, to_may))
                _, created = ThongsoGioPhat.objects.update_or_create(
                    ngay=ngay,
                    to_may=to_may,
                    nha_may=nhamay,
                    defaults={
                        "gio_phat_dien": item.get("gio_phat_dien"),
                        "gio_ngung": item.get("gio_ngung"),
                        "updated_by": user,
                        **({} if existing and existing.created_by_id else {"created_by": user}),
                    },
                )
                if created:
                    saved_count += 1
                else:
                    updated_count += 1

        return SaveResult(saved_count=saved_count, updated_count=updated_count)

    def save_thuc_te(self, *, data_list, nhamay, user, can_modify):
        nhamay = normalize_plant_code(nhamay)
        saved_count = 0
        updated_count = 0

        existing_by_day = {}
        for item in data_list:
            ngay = item.get("ngay")
            if not ngay:
                continue
            existing = ThongSoThuyVanThucTe.objects.filter(ngay=ngay, nha_may=nhamay).first()
            if existing and not can_modify(user, existing):
                raise PermissionError("Ban chi duoc sua du lieu thuy van thuc te do chinh ban cap nhat.")
            existing_by_day[ngay] = existing

        with transaction.atomic():
            for item in data_list:
                ngay = item.get("ngay")
                if not ngay:
                    continue

                existing = existing_by_day.get(ngay)
                _, created = ThongSoThuyVanThucTe.objects.update_or_create(
                    ngay=ngay,
                    nha_may=nhamay,
                    defaults={
                        **{field: item.get(field) for field in THUC_TE_SYNC_FIELDS},
                        "updated_by": user,
                        **({} if existing and existing.created_by_id else {"created_by": user}),
                    },
                )
                if created:
                    saved_count += 1
                else:
                    updated_count += 1

        return SaveResult(saved_count=saved_count, updated_count=updated_count)

    def sync_thuc_te_range(self, *, nhamay, start_date=None, end_date=None, user, can_modify):
        preview = self.preview_thuc_te_range(nhamay, start_date, end_date)
        save_result = self.save_thuc_te(
            data_list=preview.data,
            nhamay=nhamay,
            user=user,
            can_modify=can_modify,
        )
        return SyncRangeResult(
            saved_count=save_result.saved_count,
            updated_count=save_result.updated_count,
            parsed_count=len(preview.data),
            skipped_count=len(preview.skipped_rows),
            source_range=preview.source_range,
            warnings=preview.warnings,
        )
