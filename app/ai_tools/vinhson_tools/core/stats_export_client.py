"""
Google Sheets client with write access for statistics export
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, Tuple
from ..config.settings import GS_CONFIG
from .retry import retry_with_backoff
from ai_tools.data_sources.db_stats import (
    DbBackedSpreadsheet,
    DbBackedWorksheet,
    make_vinhson_stats_spreadsheet,
)
from .sheets_client import _fetch_vinhson_operational


def get_stats_export_client(spreadsheet_id: str) -> Tuple[Optional[gspread.Client], Optional[gspread.Spreadsheet]]:
    """Get Google Sheets client with write access for statistics export"""
    if spreadsheet_id is None:
        stats = make_vinhson_stats_spreadsheet().worksheets()[0]
        return None, DbBackedSpreadsheet(
            title="DB Combined - Vinh Son",
            worksheets=[
                stats,
                DbBackedWorksheet(
                    GS_CONFIG.worksheet_operational,
                    _fetch_vinhson_operational,
                ),
            ],
        )

    if spreadsheet_id == GS_CONFIG.stats_export_spreadsheet_id:
        return None, make_vinhson_stats_spreadsheet()

    if spreadsheet_id == GS_CONFIG.spreadsheet_id:
        return None, DbBackedSpreadsheet(
            title="DB Operational - Vinh Son",
            worksheets=[
                DbBackedWorksheet(
                    GS_CONFIG.worksheet_operational,
                    _fetch_vinhson_operational,
                )
            ],
        )

    try:
        if not os.path.exists(GS_CONFIG.service_account_file):
            print(f"[ERROR] Service account file not found: {GS_CONFIG.service_account_file}", flush=True)
            return None, None
        print(f"[INFO] Loading credentials for stats export from: {GS_CONFIG.service_account_file}", flush=True)
        credentials = Credentials.from_service_account_file(
            GS_CONFIG.service_account_file, scopes=GS_CONFIG.scopes_write
        )
        def authorize():
            print(f"[INFO] Authorizing Google Sheets client for write access...", flush=True)
            return gspread.authorize(credentials)
        client = retry_with_backoff(authorize, max_retries=3, initial_delay=2)
        def open_spreadsheet():
            print(f"[INFO] Opening spreadsheet for export: {spreadsheet_id}", flush=True)
            return client.open_by_key(spreadsheet_id)
        spreadsheet = retry_with_backoff(open_spreadsheet, max_retries=3, initial_delay=2)
        print(f"[OK] Connected to export spreadsheet: {spreadsheet.title}", flush=True)
        return client, spreadsheet
    except Exception as e:
        print(f"[ERROR] Failed to connect to export spreadsheet: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None, None
