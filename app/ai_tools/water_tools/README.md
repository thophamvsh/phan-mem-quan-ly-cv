# Water Tools Module

Hydropower calculation toolkit - refactored modular structure.

## 📂 Structure

```
water_tools/
├── __init__.py                 # Public API exports
├── core/                       # Core calculation functions
│   ├── __init__.py
│   ├── interpolation.py        # H <-> V interpolation & helpers
│   ├── volume.py               # get_water_volume, volume_difference
│   ├── flow.py                 # calculate_flow_rate, calculate_time_needed
│   ├── ramping.py              # ramping discharge calculations
│   └── spillway.py             # spillway discharge & ramping
├── tooldefs/                   # OpenAI function definitions
│   ├── __init__.py
│   ├── schemas.py              # JSON schemas for OpenAI tools
│   └── registry.py             # Tool name -> function mapping
└── runtime/                    # Runtime utilities
    ├── __init__.py
    └── handler.py              # handle_tool_calls (dispatcher)
```

## 🚀 Usage

### Import from top level

```python
from water_tools import TOOLS, handle_tool_calls

# Use in OpenAI API
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    tools=TOOLS
)

# Handle tool calls
if response.tool_calls:
    tool_responses = handle_tool_calls(response)
```

### Import specific functions

```python
from water_tools.core import (
    get_water_volume,
    calculate_flow_rate,
    calculate_spillway_ramping
)

# Use directly
result = get_water_volume(209, "Sông Hinh")
```

## 📦 Modules

### `core/interpolation.py`
- `interpolate_water_level_from_volume()` - Inverse interpolation V → H

### `core/volume.py`
- `get_water_volume()` - Query volume from water level
- `calculate_volume_difference()` - ΔV between two levels

### `core/flow.py`
- `calculate_flow_rate()` - Required flow rate for level change
- `calculate_time_needed()` - Time required for level change

### `core/ramping.py`
- `calculate_ramping_discharge()` - Ramping from start discharge
- `calculate_ramping_from_max()` - Ramping with max constraint
- `calculate_practical_ramping()` - Practical ramping with real constraints

### `core/spillway.py`
- `calculate_spillway_discharge()` - Single Qxa value
- `calculate_spillway_ramping()` - Ramping strategies analysis
- `create_detailed_spillway_schedule()` - Detailed hourly schedule

### `tooldefs/schemas.py`
- All OpenAI function definitions (JSON schemas)
- `TOOLS` list for OpenAI API

### `tooldefs/registry.py`
- `TOOL_REGISTRY` - Maps tool names to functions
- `get_tool_function()` - Get function by name

### `runtime/handler.py`
- `handle_tool_calls()` - Dispatches tool calls to appropriate functions

## 🔧 Refactoring Notes

Original `tools.py` (3100+ lines) was split into:
- **interpolation.py**: 78 lines
- **volume.py**: 217 lines
- **flow.py**: 294 lines
- **ramping.py**: 826 lines
- **spillway.py**: 1244 lines
- **schemas.py**: 564 lines
- **registry.py**: 39 lines
- **handler.py**: 103 lines

**Total: ~3365 lines** (organized into 8 focused modules)

## ✅ Benefits

- **Modularity**: Each file has a single responsibility
- **Maintainability**: Easier to find and modify code
- **Testability**: Each module can be tested independently
- **Scalability**: Easy to add new tools/features
- **Readability**: Smaller files, clearer structure

## 🧪 Testing

To verify the refactoring worked:

```bash
# Test import
python -c "from water_tools import TOOLS, handle_tool_calls; print(f'✅ {len(TOOLS)} tools loaded')"

# Run app
uv run python app.py
```

## 📝 Migration Guide

### Before (old code)
```python
from tools import TOOLS, handle_tool_calls
```

### After (new code)
```python
from water_tools import TOOLS, handle_tool_calls
```

That's it! The API remains the same, only imports changed.
