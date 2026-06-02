# Cấu trúc và Kiến trúc của `songhinh_tools`

## Tổng quan

Package `songhinh_tools` là một hệ thống tích hợp với Google Sheets để lấy và xử lý dữ liệu vận hành của Thủy điện Sông Hinh. Package được tổ chức theo mô hình layered architecture với các module riêng biệt cho từng chức năng.

## Cấu trúc thư mục

```
songhinh_tools/
├── __init__.py                 # Entry point - export SONGHINH_TOOLS và handle_songhinh_tool_calls
├── config/                     # Cấu hình và constants
│   ├── __init__.py
│   ├── settings.py             # Google Sheets configuration (GS_CONFIG)
│   └── columns.py              # Column indices cho Google Sheets (OP_COLS, H_COLS)
├── core/                       # Core utilities và client managers
│   ├── __init__.py
│   ├── retry.py                # Retry logic với exponential backoff
│   ├── sheets_client.py        # GoogleSheetsClientManager (singleton pattern)
│   └── stats_export_client.py  # Client cho statistics export spreadsheet
├── utils/                      # Utility functions
│   ├── __init__.py
│   ├── dates.py                # Date parsing và normalization
│   └── numbers.py              # Number parsing và formatting
├── services/                   # Business logic services
│   ├── __init__.py
│   ├── hours_service.py        # Xử lý dữ liệu giờ phát điện
│   ├── operational_service.py  # Xử lý dữ liệu vận hành
│   ├── comparative_service.py  # Phân tích so sánh
│   ├── hierarchical_service.py # Thống kê phân cấp (Qve, mực nước)
│   └── rainfall_service.py     # Thống kê lượng mưa
└── openai/                     # OpenAI tool integration
    ├── __init__.py
    ├── tool_definitions.py     # Định nghĩa OpenAI function tools
    └── tool_handler.py         # Xử lý tool calls từ OpenAI
```

## Luồng dữ liệu (Data Flow)

### 1. Entry Point

```
app.py hoặc client code
    ↓
songhinh_tools/__init__.py
    ↓
openai/tool_handler.py
    ↓
services/*.py (business logic)
    ↓
core/sheets_client.py (Google Sheets API)
```

### 2. Chi tiết luồng xử lý

```
┌─────────────────────────────────────────────────────────────┐
│                    External Client (app.py)                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              songhinh_tools/__init__.py                     │
│  - Export: SONGHINH_TOOLS, handle_songhinh_tool_calls      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              openai/tool_handler.py                         │
│  - Khởi tạo service instances                               │
│  - Định nghĩa SONGHINH_TOOLS list                          │
│  - handle_songhinh_tool_calls() routes đến service phù hợp │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ↓                   ↓                   ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Operational  │  │ Hierarchical │  │  Rainfall   │
│   Service    │  │   Service    │  │   Service   │
└──────┬───────┘  └──────┬───────┘  └──────┬──────┘
       │                 │                  │
       └─────────────────┼──────────────────┘
                         │
                         ↓
        ┌────────────────────────────────────┐
        │   core/sheets_client.py            │
        │   GoogleSheetsClientManager         │
        │   - Singleton pattern              │
        │   - TTL cache                      │
        │   - Read/Write clients             │
        └────────────────┬───────────────────┘
                         │
                         ↓
        ┌────────────────────────────────────┐
        │      Google Sheets API              │
        │      (gspread library)              │
        └─────────────────────────────────────┘
```

## Mô tả các Module

### 1. `config/` - Cấu hình

#### `settings.py`

- **Mục đích**: Lưu trữ cấu hình Google Sheets
- **Export**: `GS_CONFIG` (dataclass)
- **Nội dung**:
  - Service account file path
  - Spreadsheet IDs (operational, statistics export)
  - OAuth scopes (read, write)
  - Worksheet names

#### `columns.py`

- **Mục đích**: Định nghĩa column indices cho Google Sheets
- **Export**:
  - `OP_COLS` (OperationalCols dataclass) - cho sheet "Sản lượng"
  - `H_COLS` (HoursCols dataclass) - cho sheet "Giờ phát"
  - Individual column constants (COL_DATE, COL_WATER_LEVEL, etc.)
- **Sử dụng**: Services sử dụng để truy cập đúng cột trong Google Sheets

### 2. `core/` - Core Utilities

#### `retry.py`

- **Mục đích**: Retry logic với exponential backoff
- **Export**: `retry_with_backoff()`
- **Sử dụng**: Tất cả các service khi gọi Google Sheets API

#### `sheets_client.py`

- **Mục đích**: Quản lý kết nối Google Sheets (Singleton pattern)
- **Export**:
  - `GoogleSheetsClientManager` (class)
  - `TTLCache` (class)
  - `get_sheets_client_manager()` (factory function)
  - `reset_google_sheets_client()` (reset function)
- **Tính năng**:
  - Singleton pattern để tái sử dụng connection
  - TTL cache cho `get_all_values()` (30 giây)
  - Quản lý read client (operational data) và write client (statistics export)
  - Tự động retry với exponential backoff

#### `stats_export_client.py`

- **Mục đích**: Client riêng cho statistics export spreadsheet
- **Export**: `get_stats_export_client()`
- **Sử dụng**: `HierarchicalStatisticsService` để đọc dữ liệu thống kê

### 3. `utils/` - Utility Functions

#### `dates.py`

- **Mục đích**: Xử lý và parse dates
- **Export**:
  - `parse_dmy_to_date()` - Parse DD/MM/YYYY
  - `normalize_date()` - Normalize date strings
  - `parse_date()` - Generic date parser
- **Sử dụng**: Tất cả services cần parse dates từ Google Sheets

#### `numbers.py`

- **Mục đích**: Parse và format numbers
- **Export**:
  - `parse_float_loose()` - Parse float với nhiều format (comma, dot)
  - `parse_number()` - Alias cho parse_float_loose
  - `fmt_pct()` - Format percentage
  - `safe_cell()` - Lấy cell value an toàn từ row
- **Sử dụng**: Services parse số từ Google Sheets cells

### 4. `services/` - Business Logic

#### `hours_service.py`

- **Mục đích**: Xử lý dữ liệu giờ phát điện
- **Class**: `HoursService`
- **Dependencies**:
  - `GoogleSheetsClientManager` (injected)
  - `H_COLS` (column definitions)
- **Sử dụng bởi**: `OperationalService`

#### `operational_service.py`

- **Mục đích**: Lấy và xử lý dữ liệu vận hành
- **Class**: `OperationalService`
- **Dependencies**:
  - `GoogleSheetsClientManager` (injected)
  - `OP_COLS` (column definitions)
  - `HoursService` (injected, optional)
- **Methods**:
  - `get_operational_data()` - Lấy dữ liệu vận hành theo date/range
- **Sử dụng**: `tool_handler.py` → `get_songinh_operational_data`

#### `comparative_service.py`

- **Mục đích**: Phân tích so sánh giữa các khoảng thời gian
- **Class**: `ComparativeAnalysisService`
- **Dependencies**:
  - `GoogleSheetsClientManager` (injected)
  - `OP_COLS` (column definitions)
- **Methods**:
  - `get_comparative_analysis()` - So sánh năm nay vs năm trước
- **Sử dụng**: `tool_handler.py` → `get_songhinh_comparative_analysis`

#### `hierarchical_service.py`

- **Mục đích**: Thống kê phân cấp Qve và mực nước (năm→tháng→tuần→ngày)
- **Class**: `HierarchicalStatisticsService`
- **Dependencies**:
  - `GS_CONFIG` (settings)
  - `get_sheets_client_manager()` (core)
  - `safe_cell`, `parse_float_loose` (utils)
- **Methods**:
  - `get_hierarchical_statistics()` - Thống kê theo year/month/week hoặc date range
  - `_get_date_range_statistics()` - Thống kê theo ngày cho date range
- **Sử dụng**: `tool_handler.py` → `get_songhinh_hierarchical_statistics`
- **Đặc biệt**:
  - Hỗ trợ date range (start_date, end_date) để trả về thống kê theo ngày
  - Đọc từ statistics export spreadsheet (khác với operational data)

#### `rainfall_service.py`

- **Mục đích**: Thống kê lượng mưa
- **Class**: `RainfallService`
- **Dependencies**:
  - `hydro_data_repository` / `thuyvan_data_client` - Query rainfall data từ Django models trong app `thongsothuyvan`
  - `parse_date` (utils)
- **Methods**:
  - `get_rainfall_statistics()` - Thống kê theo year/month/week
  - `get_rainfall_range_statistics()` - Thống kê theo tháng range
  - `get_rainfall_daily_statistics()` - Thống kê theo ngày range
- **Sử dụng**: `tool_handler.py` → `get_songhinh_rainfall_statistics`

### 5. `openai/` - OpenAI Integration

#### `tool_definitions.py`

- **Mục đích**: Định nghĩa OpenAI function tools
- **Export**:
  - `operational_data_function`
  - `comparative_analysis_function`
  - `hierarchical_statistics_function`
  - `rainfall_statistics_function`
  - `rainfall_range_statistics_function`
  - `rainfall_daily_statistics_function`
- **Nội dung**: JSON schemas cho OpenAI function calling

#### `tool_handler.py`

- **Mục đích**: Xử lý tool calls từ OpenAI
- **Export**:
  - `SONGHINH_TOOLS` (list of tool definitions)
  - `handle_songhinh_tool_calls()` (function)
- **Chức năng**:
  - Khởi tạo service instances (singleton)
  - Route tool calls đến service phù hợp
  - Parse arguments và gọi service methods
  - Trả về kết quả dạng markdown

## Dependencies Graph

```
┌─────────────────────────────────────────────────────────────┐
│                    External Dependencies                     │
│  - gspread (Google Sheets API)                              │
│  - google.oauth2.service_account                            │
│  - hydro_data_repository / thuyvan_data_client (rainfall)   │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │
┌─────────────────────────────────────────────────────────────┐
│                      songhinh_tools/                        │
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │   config/    │      │    core/     │                   │
│  │              │      │              │                   │
│  │ settings.py  │──────│ sheets_client│                   │
│  │ columns.py   │      │ retry.py     │                   │
│  └──────┬───────┘      └──────┬───────┘                   │
│         │                     │                            │
│         │                     │                            │
│  ┌──────▼─────────────────────▼───────┐                   │
│  │           services/                 │                   │
│  │                                     │                   │
│  │  operational_service.py            │                   │
│  │  comparative_service.py             │                   │
│  │  hierarchical_service.py           │                   │
│  │  rainfall_service.py                │                   │
│  │  hours_service.py                   │                   │
│  └──────┬──────────────────────────────┘                   │
│         │                                                   │
│  ┌──────▼──────────┐                                       │
│  │    utils/       │                                       │
│  │                 │                                       │
│  │  dates.py       │                                       │
│  │  numbers.py     │                                       │
│  └─────────────────┘                                       │
│         │                                                   │
│  ┌──────▼──────────┐                                       │
│  │    openai/      │                                       │
│  │                 │                                       │
│  │ tool_definitions│                                       │
│  │ tool_handler.py │                                       │
│  └─────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

## Dependency Rules

1. **config/** → Không phụ thuộc module khác (trừ standard library)
2. **core/** → Chỉ phụ thuộc `config/` và standard library
3. **utils/** → Không phụ thuộc module khác (trừ standard library)
4. **services/** → Có thể phụ thuộc `config/`, `core/`, `utils/`, và các service khác
5. **openai/** → Phụ thuộc `services/`, `config/`, `core/`
6. ****init**.py** → Chỉ phụ thuộc `openai/`

## Service Initialization Flow

```python
# Trong tool_handler.py

# 1. Lấy singleton manager
_manager = get_sheets_client_manager()

# 2. Khởi tạo HoursService (dependency của OperationalService)
_hours_service = HoursService(_manager, H_COLS)

# 3. Khởi tạo các services
_operational_service = OperationalService(_manager, OP_COLS, _hours_service)
_comparative_service = ComparativeAnalysisService(_manager, OP_COLS)
_hierarchical_service = HierarchicalStatisticsService()  # Tự tạo manager bên trong
_rainfall_service = RainfallService()  # Không cần manager
```

## Tool Call Flow Example

### Ví dụ: "Thống kê lưu lượng về Sông Hinh từ 1/1/2026 đến 13/1/2026"

```
1. app.py nhận user query
   ↓
2. OpenAI API chọn tool: get_songhinh_hierarchical_statistics
   ↓
3. app.py gọi handle_songhinh_tool_calls(tool_call)
   ↓
4. tool_handler.py:
   - Parse arguments: start_date="1/1/2026", end_date="13/1/2026"
   - Gọi _hierarchical_service.get_hierarchical_statistics(
       period_type=None,
       period_value=None,
       start_date="1/1/2026",
       end_date="13/1/2026"
     )
   ↓
5. hierarchical_service.py:
   - Detect có start_date và end_date
   - Gọi _get_date_range_statistics()
   - Lấy manager từ get_sheets_client_manager()
   - Mở statistics export spreadsheet
   - Parse dates và tạo danh sách ngày
   - Query data từ Google Sheets cho từng ngày
   - Format kết quả thành markdown table
   ↓
6. Trả về markdown string cho app.py
```

## Key Design Patterns

### 1. Singleton Pattern

- `GoogleSheetsClientManager`: Đảm bảo chỉ có 1 instance, tái sử dụng connection

### 2. Dependency Injection

- Services nhận dependencies qua constructor (manager, column definitions)
- Dễ dàng test và mock

### 3. Factory Pattern

- `get_sheets_client_manager()`: Factory function tạo/trả về singleton instance

### 4. Strategy Pattern

- `tool_handler.py`: Route tool calls đến service phù hợp dựa trên tool name

### 5. Cache Pattern

- `TTLCache`: Cache worksheet data với TTL 30 giây để giảm API calls

## Best Practices

1. **Separation of Concerns**: Mỗi module có trách nhiệm rõ ràng
2. **Single Responsibility**: Mỗi service chỉ xử lý một domain cụ thể
3. **Dependency Injection**: Services nhận dependencies, không tự tạo
4. **Error Handling**: Tất cả API calls đều có retry logic
5. **Type Hints**: Sử dụng type hints để code rõ ràng hơn
6. **Documentation**: Mỗi module có docstrings mô tả mục đích

## Extension Points

### Thêm Service mới:

1. Tạo file trong `services/`
2. Import và export trong `services/__init__.py`
3. Định nghĩa tool trong `openai/tool_definitions.py`
4. Thêm handler trong `openai/tool_handler.py`
5. Thêm vào `SONGHINH_TOOLS` list

### Thêm Utility mới:

1. Tạo function trong `utils/` (dates.py hoặc numbers.py)
2. Export trong `utils/__init__.py`
3. Import và sử dụng trong services

### Thay đổi cấu hình:

1. Cập nhật `config/settings.py` hoặc `config/columns.py`
2. Services sẽ tự động sử dụng cấu hình mới

## Testing Strategy

- **Unit Tests**: Test từng service riêng biệt với mocked dependencies
- **Integration Tests**: Test với real Google Sheets (cần credentials)
- **Mock Strategy**: Mock `GoogleSheetsClientManager` và `gspread` responses

## Notes

- Package được thiết kế để dễ dàng mở rộng và bảo trì
- Tất cả Google Sheets operations đều có retry logic
- Cache được sử dụng để tối ưu performance
- Error messages được format thành markdown để hiển thị đẹp trong chat interface
