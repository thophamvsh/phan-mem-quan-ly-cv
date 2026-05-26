"""
Google Sheets client with write access for statistics export
"""

from typing import Optional, Tuple
from ..config.settings import GS_CONFIG
from .sheets_client import get_sheets_client_manager


def get_stats_export_client(spreadsheet_id: str) -> Tuple[Optional[object], Optional[object]]:
    """Get Google Sheets client with write access for statistics export"""
    manager = get_sheets_client_manager()
    spreadsheet = manager.get_write_spreadsheet(spreadsheet_id)
    if spreadsheet:
        # Return client and spreadsheet (client is stored in manager)
        return manager._write_client.get(spreadsheet_id), spreadsheet
    return None, None
