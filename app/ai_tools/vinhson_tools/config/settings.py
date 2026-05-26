"""
Settings and configuration for Vĩnh Sơn Google Sheets integration
"""

import json
import os
import tempfile
from dataclasses import dataclass
from typing import List

_CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Service account file resolution:
#   1. Nếu file JSON tồn tại trên disk → dùng trực tiếp (dev local)
#   2. Nếu không → đọc env VINHSON_SERVICE_ACCOUNT_JSON, ghi ra file tạm
# ---------------------------------------------------------------------------
_SA_FILE_NAME = "vinhson-account-key.json"
_SA_FILE_PATH = os.path.join(_CURRENT_DIR, _SA_FILE_NAME)

if not os.path.isfile(_SA_FILE_PATH):
    _sa_json = os.getenv("VINHSON_SERVICE_ACCOUNT_JSON", "")
    if _sa_json:
        _tmp = os.path.join(tempfile.gettempdir(), _SA_FILE_NAME)
        with open(_tmp, "w", encoding="utf-8") as f:
            f.write(_sa_json)
        _SA_FILE_PATH = _tmp
        pass
    else:
        pass


@dataclass(frozen=True)
class GoogleSheetsConfig:
    """Google Sheets configuration for Vĩnh Sơn"""
    service_account_file: str
    spreadsheet_id: str
    scopes_read: List[str]
    scopes_write: List[str]
    stats_export_spreadsheet_id: str
    worksheet_operational: str = "Sản lượng"
    worksheet_hours: str = "Giờ phát"


GS_CONFIG = GoogleSheetsConfig(
    service_account_file=_SA_FILE_PATH,
    spreadsheet_id=os.getenv('VINHSON_SPREADSHEET_ID'),
    scopes_read=[
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly'
    ],
    scopes_write=[
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ],
    stats_export_spreadsheet_id=os.getenv('VINHSON_STATS_EXPORT_SPREADSHEET_ID'),
    worksheet_operational="Sản lượng",
    worksheet_hours="Giờ phát",
)
