"""
Deprecated compatibility module.

The hydrological data now comes from Django models in the `thongsothuyvan`
app, not from Supabase. New code should import from `hydro_data_repository`.
"""

from hydro_data_repository import *  # noqa: F401,F403
