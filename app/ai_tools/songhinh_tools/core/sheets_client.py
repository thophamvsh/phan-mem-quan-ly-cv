"""
Google Sheets client singleton for Sông Hinh with DB interception for Operational and Hours data
"""

import os
import time
import gspread
from google.oauth2.service_account import Credentials
from django.utils import timezone
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from ..config.settings import GS_CONFIG
from .retry import retry_with_backoff
from ai_tools.data_sources.db_stats import (
    DbBackedSpreadsheet,
    DbBackedWorksheet,
    make_songhinh_stats_spreadsheet,
)


@dataclass
class SheetCacheEntry:
    values: List[List[str]]
    fetched_at: float


class TTLCache:
    def __init__(self, ttl_seconds: int = 30):
        self.ttl = ttl_seconds
        self._store: Dict[str, SheetCacheEntry] = {}

    def get(self, key: str) -> Optional[List[List[str]]]:
        entry = self._store.get(key)
        if not entry:
            return None
        if (time.time() - entry.fetched_at) > self.ttl:
            self._store.pop(key, None)
            return None
        return entry.values

    def set(self, key: str, values: List[List[str]]) -> None:
        self._store[key] = SheetCacheEntry(values=values, fetched_at=time.time())

    def clear(self) -> None:
        self._store.clear()


class GoogleSheetsClientManager:
    """
    Singleton-like manager:
    - read client + worksheets ("Sản lượng", "Giờ phát")
    - write client + spreadsheet (stats export)
    - caches worksheet.get_all_values() with TTL
    """

    def __init__(self, config):
        self.config = config
        self._read_client: Optional[gspread.Client] = None
        self._read_spreadsheet: Optional[gspread.Spreadsheet] = None
        self._ws_operational: Optional[gspread.Worksheet] = None
        self._ws_hours: Optional[gspread.Worksheet] = None

        self._write_client: Dict[str, gspread.Client] = {}
        self._write_spreadsheet: Dict[str, gspread.Spreadsheet] = {}

        self.cache = TTLCache(ttl_seconds=30)

    def reset(self) -> None:
        print("[INFO] Resetting Google Sheets client cache...", flush=True)
        self._read_client = None
        self._read_spreadsheet = None
        self._ws_operational = None
        self._ws_hours = None
        self._write_client.clear()
        self._write_spreadsheet.clear()
        self.cache.clear()

    def _ensure_service_account_file(self) -> bool:
        if not os.path.exists(self.config.service_account_file):
            print(f"[ERROR] Service account file not found: {self.config.service_account_file}", flush=True)
            return False
        return True

    def _authorize(self, scopes: List[str]) -> Optional[gspread.Client]:
        if not self._ensure_service_account_file():
            return None

        def _do():
            print("[INFO] Authorizing Google Sheets client...", flush=True)
            credentials = Credentials.from_service_account_file(
                self.config.service_account_file, scopes=scopes
            )
            return gspread.authorize(credentials)

        try:
            return retry_with_backoff(_do, max_retries=3, initial_delay=2)
        except Exception as e:
            print(f"[ERROR] Authorize failed: {e}", flush=True)
            return None

    def _open_spreadsheet(self, client: gspread.Client, spreadsheet_id: str) -> Optional[gspread.Spreadsheet]:
        def _do():
            print(f"[INFO] Opening spreadsheet: {spreadsheet_id}", flush=True)
            return client.open_by_key(spreadsheet_id)

        try:
            return retry_with_backoff(_do, max_retries=3, initial_delay=2)
        except gspread.exceptions.SpreadsheetNotFound:
            print("[ERROR] Spreadsheet not found. Check ID / permissions.", flush=True)
            return None
        except gspread.exceptions.APIError as e:
            print(f"[ERROR] Google Sheets API error: {e}", flush=True)
            print("[INFO] Ensure Google Sheets API is enabled in Google Cloud Console.", flush=True)
            return None
        except Exception as e:
            print(f"[ERROR] Could not open spreadsheet: {e}", flush=True)
            return None

    def get_read_worksheets(self) -> Tuple[Optional[gspread.Worksheet], Optional[gspread.Worksheet]]:
        """
        Returns: (worksheet_operational, worksheet_hours)
        """
        # Trả về Dummy Worksheet để bypass lỗi xác thực Google Sheets cho 2 sheet này
        class DummyWorksheet:
            def __init__(self, title):
                self.title = title
        return DummyWorksheet(self.config.worksheet_operational), DummyWorksheet(self.config.worksheet_hours)

    def get_write_spreadsheet(self, spreadsheet_id: str) -> Optional[gspread.Spreadsheet]:
        if spreadsheet_id is None:
            cache_key = "__songhinh_combined_db__"
            if cache_key not in self._write_spreadsheet:
                stats = make_songhinh_stats_spreadsheet().worksheets()[0]
                self._write_spreadsheet[cache_key] = DbBackedSpreadsheet(
                    title="DB Combined - Song Hinh",
                    worksheets=[
                        stats,
                        DbBackedWorksheet(
                            self.config.worksheet_operational,
                            self._fetch_operational_from_db,
                        ),
                    ],
                )
            return self._write_spreadsheet[cache_key]

        if spreadsheet_id == self.config.stats_export_spreadsheet_id_songhinh:
            cache_key = spreadsheet_id or "__songhinh_stats_db__"
            if cache_key not in self._write_spreadsheet:
                self._write_spreadsheet[cache_key] = make_songhinh_stats_spreadsheet()
            return self._write_spreadsheet[cache_key]

        if spreadsheet_id == self.config.spreadsheet_id:
            cache_key = spreadsheet_id or "__songhinh_operational_db__"
            if cache_key not in self._write_spreadsheet:
                self._write_spreadsheet[cache_key] = DbBackedSpreadsheet(
                    title="DB Operational - Song Hinh",
                    worksheets=[
                        DbBackedWorksheet(
                            self.config.worksheet_operational,
                            self._fetch_operational_from_db,
                        )
                    ],
                )
            return self._write_spreadsheet[cache_key]

        if spreadsheet_id in self._write_spreadsheet:
            return self._write_spreadsheet[spreadsheet_id]

        client = self._write_client.get(spreadsheet_id) or self._authorize(self.config.scopes_write)
        if not client:
            return None

        spreadsheet = self._open_spreadsheet(client, spreadsheet_id)
        if not spreadsheet:
            return None

        self._write_client[spreadsheet_id] = client
        self._write_spreadsheet[spreadsheet_id] = spreadsheet
        print(f"[OK] Connected to export spreadsheet: {spreadsheet.title}", flush=True)
        return spreadsheet

    def get_all_values_cached(self, worksheet: gspread.Worksheet, cache_key: str) -> List[List[str]]:
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # INTERCEPT DATA FETCH TO USE DB
        ws_title = getattr(worksheet, 'title', '')
        if ws_title == self.config.worksheet_operational:
            values = self._fetch_operational_from_db()
        elif ws_title == self.config.worksheet_hours:
            values = self._fetch_hours_from_db()
        else:
            # Fallback to real Google Sheets for other sheets like 'Thống kê'
            def _fetch():
                return worksheet.get_all_values()
            values = retry_with_backoff(_fetch, max_retries=3, initial_delay=1)
            
        self.cache.set(cache_key, values)
        return values

    def _fetch_operational_from_db(self) -> List[List[str]]:
        from thongsothuyvan.models import ThongsoSanxuat, SonghinhMnh
        from ..config.columns import OP_COLS
        
        data = [[], []] # headers
        try:
            records = ThongsoSanxuat.objects.filter(nha_may='songhinh').order_by('thoi_gian')
            sh_records = SonghinhMnh.objects.all()
            sh_map = {}
            for sh in sh_records:
                if sh.created_at:
                    sh_map[timezone.localtime(sh.created_at).date()] = sh
                    
            for rec in records:
                row = [""] * 30
                if not rec.thoi_gian:
                    continue
                rec_time = timezone.localtime(rec.thoi_gian)
                rec_date = rec_time.date()
                sh = sh_map.get(rec_date)
                
                row[OP_COLS.COL_DATE] = rec_time.strftime("%d/%m/%Y")
                row[OP_COLS.COL_RESERVOIR] = "songhinh"
                
                if sh:
                    row[OP_COLS.COL_WATER_LEVEL] = str(sh.Mucnuoc) if sh.Mucnuoc is not None else ""
                    row[OP_COLS.COL_VOLUME] = str(sh.dungtich) if sh.dungtich is not None else ""
                else:
                    row[OP_COLS.COL_WATER_LEVEL] = str(rec.cot_g) if rec.cot_g is not None else ""
                    row[OP_COLS.COL_VOLUME] = str(rec.cot_h) if rec.cot_h is not None else ""
                    
                row[OP_COLS.COL_INFLOW] = str(rec.cot_i) if rec.cot_i is not None else ""
                row[OP_COLS.COL_TURBINE] = str(rec.cot_j) if rec.cot_j is not None else ""
                row[OP_COLS.COL_SPILLWAY] = str(rec.cot_k) if rec.cot_k is not None else ""
                row[OP_COLS.COL_QC_DAY] = str(rec.cot_l) if rec.cot_l is not None else ""
                row[OP_COLS.COL_OUTPUT_DAY] = str(rec.cot_m) if rec.cot_m is not None else ""
                row[OP_COLS.COL_COMMERCIAL_DAY] = str(rec.cot_n) if rec.cot_n is not None else ""
                
                row[OP_COLS.COL_QC_MONTH_ACC] = str(rec.cot_p) if rec.cot_p is not None else ""
                row[OP_COLS.COL_OUTPUT_MONTH] = str(rec.cot_q) if rec.cot_q is not None else ""
                row[OP_COLS.COL_COMMERCIAL_MONTH] = str(rec.cot_r) if rec.cot_r is not None else ""
                
                row[OP_COLS.COL_QC_YEAR_ACC] = str(rec.cot_t) if rec.cot_t is not None else ""
                row[OP_COLS.COL_OUTPUT_YEAR] = str(rec.cot_u) if rec.cot_u is not None else ""
                row[OP_COLS.COL_COMMERCIAL_YEAR] = str(rec.cot_v) if rec.cot_v is not None else ""
                row[OP_COLS.COL_PLAN_YEAR] = str(rec.cot_w) if rec.cot_w is not None else ""
                row[OP_COLS.COL_SELF_USE] = str(rec.cot_x) if rec.cot_x is not None else ""
                
                data.append(row)
        except Exception as e:
            print(f"[ERROR] Failed to fetch ThongsoSanxuat for Sông Hinh: {e}")
        return data

    def _fetch_hours_from_db(self) -> List[List[str]]:
        from thongsothuyvan.models import ThongsoGioPhat
        from ..config.columns import H_COLS
        
        data = [[], []] # headers
        try:
            records = ThongsoGioPhat.objects.filter(nha_may='songhinh').order_by('ngay', 'to_may')
            for rec in records:
                row = [""] * 10
                if not rec.ngay:
                    continue
                row[H_COLS.COL_HOURS_DATE] = rec.ngay.strftime("%d/%m/%Y")
                row[H_COLS.COL_HOURS_UNIT] = str(rec.to_may)
                row[H_COLS.COL_HOURS_OPERATING] = str(rec.gio_phat_dien) if rec.gio_phat_dien is not None else ""
                row[H_COLS.COL_HOURS_STOPPED] = str(rec.gio_ngung) if rec.gio_ngung is not None else ""
                data.append(row)
        except Exception as e:
            print(f"[ERROR] Failed to fetch ThongsoGioPhat for Sông Hinh: {e}")
        return data


# Global manager instance
_sheets_client_manager: Optional[GoogleSheetsClientManager] = None


def get_sheets_client_manager() -> GoogleSheetsClientManager:
    """Get or create the global sheets client manager"""
    global _sheets_client_manager
    if _sheets_client_manager is None:
        _sheets_client_manager = GoogleSheetsClientManager(GS_CONFIG)
    return _sheets_client_manager


def reset_google_sheets_client() -> None:
    """Backward-compatible entrypoint."""
    get_sheets_client_manager().reset()
