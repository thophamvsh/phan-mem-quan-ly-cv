"""
Google Sheets client singleton for Vĩnh Sơn with DB interception for Operational and Hours data
"""

import os
import time
import gspread
from google.oauth2.service_account import Credentials
from django.utils import timezone
from typing import Optional, Tuple, List
from ..config.settings import GS_CONFIG
from .retry import retry_with_backoff

_gs_client: Optional[gspread.Client] = None
_gs_worksheet = None
_gs_worksheet_hours = None

# Cache for local DB queries
_cached_operational = None
_cached_operational_time = 0.0
_cached_hours = None
_cached_hours_time = 0.0
CACHE_TTL = 30.0  # 30 seconds

class WorksheetWrapper:
    def __init__(self, real_ws, ws_type):
        self.real_ws = real_ws
        self.ws_type = ws_type
        
    def __getattr__(self, name):
        return getattr(self.real_ws, name)
        
    def get_all_values(self):
        if self.ws_type == "vinhson_operational":
            return _fetch_vinhson_operational()
        elif self.ws_type == "vinhson_hours":
            return _fetch_vinhson_hours()
        else:
            return self.real_ws.get_all_values()

def _fetch_vinhson_operational() -> List[List[str]]:
    global _cached_operational, _cached_operational_time
    if _cached_operational is not None and (time.time() - _cached_operational_time) < CACHE_TTL:
        return _cached_operational
    from thongsothuyvan.models import ThongsoSanxuat, Vinhson_HoA, Vinhson_HoB, Vinhson_Hoc
    from ..config.columns import (
        COL_DATE, COL_RESERVOIR, COL_WATER_LEVEL, COL_VOLUME, COL_INFLOW, 
        COL_TURBINE, COL_SPILLWAY, COL_QC_DAY, COL_OUTPUT_DAY, COL_COMMERCIAL_DAY,
        COL_QC_MONTH_ACC, COL_OUTPUT_MONTH, COL_COMMERCIAL_MONTH,
        COL_QC_YEAR_ACC, COL_OUTPUT_YEAR, COL_COMMERCIAL_YEAR, COL_PLAN_YEAR, COL_SELF_USE
    )
    
    data = [[], []]
    try:
        records = ThongsoSanxuat.objects.filter(nha_may='vinhson').order_by('thoi_gian')
        map_a = {timezone.localtime(r.created_at).date(): r for r in Vinhson_HoA.objects.all() if r.created_at}
        map_b = {timezone.localtime(r.created_at).date(): r for r in Vinhson_HoB.objects.all() if r.created_at}
        map_c = {timezone.localtime(r.created_at).date(): r for r in Vinhson_Hoc.objects.all() if r.created_at}
        
        for rec in records:
            row = [""] * 30
            if not rec.thoi_gian:
                continue
            rec_time = timezone.localtime(rec.thoi_gian)
            rec_date = rec_time.date()
            row[COL_DATE] = rec_time.strftime("%d/%m/%Y")
            
            reservoir = (rec.cot_c or "").strip()
            row[COL_RESERVOIR] = reservoir
            
            sh = None
            res_upper = reservoir.upper()
            if "A" in res_upper:
                sh = map_a.get(rec_date)
            elif "B" in res_upper:
                sh = map_b.get(rec_date)
            elif "C" in res_upper:
                sh = map_c.get(rec_date)
                
            if sh:
                row[COL_WATER_LEVEL] = str(sh.Mucnuoc) if sh.Mucnuoc is not None else ""
                row[COL_VOLUME] = str(sh.dungtich) if sh.dungtich is not None else ""
            else:
                row[COL_WATER_LEVEL] = str(rec.cot_g) if rec.cot_g is not None else ""
                row[COL_VOLUME] = str(rec.cot_h) if rec.cot_h is not None else ""
                
            row[COL_INFLOW] = str(rec.cot_i) if rec.cot_i is not None else ""
            row[COL_TURBINE] = str(rec.cot_j) if rec.cot_j is not None else ""
            row[COL_SPILLWAY] = str(rec.cot_k) if rec.cot_k is not None else ""
            row[COL_QC_DAY] = str(rec.cot_l) if rec.cot_l is not None else ""
            row[COL_OUTPUT_DAY] = str(rec.cot_m) if rec.cot_m is not None else ""
            row[COL_COMMERCIAL_DAY] = str(rec.cot_n) if rec.cot_n is not None else ""
            row[COL_QC_MONTH_ACC] = str(rec.cot_p) if rec.cot_p is not None else ""
            row[COL_OUTPUT_MONTH] = str(rec.cot_q) if rec.cot_q is not None else ""
            row[COL_COMMERCIAL_MONTH] = str(rec.cot_r) if rec.cot_r is not None else ""
            row[COL_QC_YEAR_ACC] = str(rec.cot_t) if rec.cot_t is not None else ""
            row[COL_OUTPUT_YEAR] = str(rec.cot_u) if rec.cot_u is not None else ""
            row[COL_COMMERCIAL_YEAR] = str(rec.cot_v) if rec.cot_v is not None else ""
            row[COL_PLAN_YEAR] = str(rec.cot_w) if rec.cot_w is not None else ""
            row[COL_SELF_USE] = str(rec.cot_x) if rec.cot_x is not None else ""
            
            data.append(row)
    except Exception as e:
        print(f"[ERROR] Failed to fetch ThongsoSanxuat for Vĩnh Sơn: {e}")
    _cached_operational = data
    _cached_operational_time = time.time()
    return data

def _fetch_vinhson_hours() -> List[List[str]]:
    global _cached_hours, _cached_hours_time
    if _cached_hours is not None and (time.time() - _cached_hours_time) < CACHE_TTL:
        return _cached_hours
    from thongsothuyvan.models import ThongsoGioPhat
    from ..config.columns import COL_HOURS_DATE, COL_HOURS_UNIT, COL_HOURS_OPERATING, COL_HOURS_STOPPED
    
    data = [[], []]
    try:
        records = ThongsoGioPhat.objects.filter(nha_may='vinhson').order_by('ngay', 'to_may')
        for rec in records:
            row = [""] * 10
            if not rec.ngay:
                continue
            row[COL_HOURS_DATE] = rec.ngay.strftime("%d/%m/%Y")
            row[COL_HOURS_UNIT] = str(rec.to_may)
            row[COL_HOURS_OPERATING] = str(rec.gio_phat_dien) if rec.gio_phat_dien is not None else ""
            row[COL_HOURS_STOPPED] = str(rec.gio_ngung) if rec.gio_ngung is not None else ""
            data.append(row)
    except Exception as e:
        print(f"[ERROR] Failed to fetch ThongsoGioPhat for Vĩnh Sơn: {e}")
    _cached_hours = data
    _cached_hours_time = time.time()
    return data

class SheetsClient:
    """Singleton Google Sheets client manager"""

    @staticmethod
    def get_client():
        # Trả về Dummy Client và Dummy Worksheets để lấy từ DB
        class DummyClient:
            def open_by_key(self, key):
                return None # Fallback client không có thật, sẽ lỗi nếu gọi stats_ws
                
        class DummyWorksheet(WorksheetWrapper):
            def __init__(self, ws_type):
                self.ws_type = ws_type
                
            def __getattr__(self, name):
                return None
                
            def get_all_values(self):
                if self.ws_type == "vinhson_operational":
                    return _fetch_vinhson_operational()
                elif self.ws_type == "vinhson_hours":
                    return _fetch_vinhson_hours()
                return []

        return DummyClient(), DummyWorksheet("vinhson_operational"), DummyWorksheet("vinhson_hours")


def reset_google_sheets_client():
    global _gs_client, _gs_worksheet, _gs_worksheet_hours, _cached_operational, _cached_hours
    print(f"[INFO] Resetting Google Sheets client cache...", flush=True)
    _gs_client = None
    _gs_worksheet = None
    _gs_worksheet_hours = None
    _cached_operational = None
    _cached_hours = None
