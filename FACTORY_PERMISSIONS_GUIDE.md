# 🏭 Hướng Dẫn Hệ Thống Phân Quyền Nhà Máy

## 📋 Tổng Quan

Hệ thống phân quyền nhà máy cho phép kiểm soát quyền truy cập của user theo từng nhà máy cụ thể. User chỉ có thể xem và thao tác với dữ liệu của nhà máy được phân quyền.

## 🏗️ Kiến Trúc Hệ Thống

### 1. Models

- **UserProfile**: Thêm 2 fields mới
  - `nha_may`: ForeignKey đến Bang_nha_may (nhà máy cụ thể)
  - `is_all_factories`: Boolean (quyền truy cập tất cả nhà máy)

### 2. Permissions

- **HasFactoryAccess**: Kiểm tra quyền truy cập nhà máy
- **HasSpecificFactoryAccess**: Kiểm tra quyền nhà máy cụ thể
- **IsAdminOrReadOnly**: Chỉ admin được edit

### 3. Nhà Máy Hiện Tại

- **SH**: Sông Hinh
- **VS**: Vĩnh Sơn
- **TKT**: Thượng Kon Tum

## 👥 Các Loại Quyền

### 1. Superuser/Staff

- ✅ Truy cập tất cả nhà máy
- ✅ Không bị giới hạn bởi permissions
- ✅ Có thể quản lý tất cả dữ liệu

### 2. User có quyền tất cả nhà máy

- ✅ `is_all_factories = True`
- ✅ Truy cập mọi nhà máy
- ✅ Xem tất cả vật tư, kiểm kê, đề nghị

### 3. User có quyền nhà máy cụ thể

- ✅ `is_all_factories = False`
- ✅ `nha_may` được gán cụ thể
- ✅ Chỉ xem dữ liệu của nhà máy được gán

### 4. User chưa được gán

- ❌ Không có quyền truy cập
- ❌ Không thể xem dữ liệu nào

## 🔧 Hướng Dẫn Django Admin

### 1. Truy Cập

```
URL: http://localhost:8000/admin/
Login: admin@example.com
```

### 2. Quản Lý User Profiles

1. Vào **Core** → **Hồ sơ người dùng**
2. Sẽ thấy các cột mới:
   - **Nhà máy**: Hiển thị nhà máy của user
   - **Is all factories**: Hiển thị quyền tất cả nhà máy

### 3. Gán Nhà Máy Cho User

1. Click vào user profile cần chỉnh sửa
2. Trong section **"Phân quyền nhà máy"**:
   - **Nhà máy**: Chọn từ dropdown
   - **Tất cả nhà máy**: Tick nếu muốn user có quyền tất cả nhà máy
3. Click **Save**

### 4. Filter và Search

- **Filter**: Có thể filter theo nhà máy và quyền tất cả nhà máy
- **Search**: Có thể tìm theo tên nhà máy

## 📱 Hướng Dẫn VshMobile

### 1. Chọn Nhà Máy

1. Mở app VshMobile
2. Vào **Profile** (tab người dùng)
3. Chọn tab **"Nhà máy"**
4. Chọn nhà máy từ danh sách
5. Nhấn **"Cập nhật nhà máy"**

### 2. Xem Nhà Máy Hiện Tại

- Trong tab **"Thông tin"** sẽ hiển thị nhà máy hiện tại
- Dạng: "Mã - Tên" (VD: SH - Sông Hinh)

## 🌐 API Endpoints

### 1. Lấy Danh Sách Nhà Máy

```http
GET /api/khovattu/auth/nha-may/
Authorization: Bearer <token>
```

**Response:**

```json
{
  "success": true,
  "nha_mays": [
    {
      "id": 1,
      "ma_nha_may": "SH",
      "ten_nha_may": "Sông Hinh"
    }
  ]
}
```

### 2. Cập Nhật Profile (Bao Gồm Nhà Máy)

```http
POST /api/khovattu/auth/profile/update/
Authorization: Bearer <token>
Content-Type: application/json

{
  "nha_may": 1,
  "first_name": "Tên",
  "last_name": "Họ"
}
```

### 3. Lấy Vật Tư (Tự Động Filter)

```http
GET /api/khovattu/vat-tu/?ma_nha_may=SH
Authorization: Bearer <token>
```

**Lưu ý:** API tự động filter theo quyền nhà máy của user

## 🔒 Cách Hoạt Động Permissions

### 1. Kiểm Tra Quyền

```python
# Trong permissions.py
def has_permission(self, request, view):
    # Superuser/staff có quyền tất cả
    if request.user.is_superuser or request.user.is_staff:
        return True

    # Kiểm tra UserProfile
    profile = request.user.profile
    if profile.is_all_factories:
        return True

    # Kiểm tra nhà máy cụ thể
    if profile.nha_may:
        return True

    return False
```

### 2. Filter Dữ Liệu

```python
# Trong views.py
def get_queryset(self):
    qs = Bang_vat_tu.objects.all()

    if self.request.user.is_authenticated:
        profile = self.request.user.profile
        if not profile.is_all_factories and profile.nha_may:
            # Chỉ lấy vật tư của nhà máy được gán
            qs = qs.filter(bang_nha_may=profile.nha_may)

    return qs
```

## 📊 Ví Dụ Thực Tế

### 1. User thoph

- **Email**: thovsh@gmail.com
- **Nhà máy**: SH (Sông Hinh)
- **Quyền**: Chỉ xem vật tư của nhà máy SH
- **API Response**: Chỉ trả về vật tư có `bang_nha_may.ma_nha_may = "SH"`

### 2. Admin

- **Email**: admin@example.com
- **Quyền**: Tất cả nhà máy
- **API Response**: Trả về tất cả vật tư không bị filter

### 3. User mới

- **Nhà máy**: Chưa gán
- **Quyền**: Không có quyền truy cập
- **API Response**: Empty list hoặc 403 Forbidden

## 🚀 Triển Khai

### 1. Database Migration

```bash
# Đã chạy migration
python manage.py makemigrations core
python manage.py migrate
```

### 2. Cấu Hình

- ✅ Permissions đã được thêm vào views
- ✅ Serializers đã được cập nhật
- ✅ Django Admin đã được cấu hình

### 3. Test

```bash
# Test permissions
python test_factory_permissions.py

# Gán nhà máy cho user
python assign_factory_to_user.py
```

## ⚠️ Lưu Ý Quan Trọng

### 1. Backward Compatibility

- User cũ không có nhà máy sẽ không có quyền truy cập
- Cần gán nhà máy cho tất cả user hiện tại

### 2. Security

- Permissions được check ở backend level
- Frontend không thể bypass permissions
- Tất cả API đều có kiểm tra quyền

### 3. Performance

- Filter được thực hiện ở database level
- Không load toàn bộ dữ liệu rồi filter ở Python

## 🔧 Troubleshooting

### 1. User không thấy dữ liệu

- Kiểm tra UserProfile có `nha_may` không
- Kiểm tra `is_all_factories` có đúng không
- Kiểm tra token authentication

### 2. API trả về empty

- Kiểm tra permissions
- Kiểm tra filter logic
- Kiểm tra database có dữ liệu không

### 3. Django Admin không hiển thị

- Restart server sau khi thay đổi admin.py
- Kiểm tra migration đã chạy chưa
- Kiểm tra import statements

## 📞 Support

Nếu gặp vấn đề, hãy kiểm tra:

1. Django Admin → Core → Hồ sơ người dùng
2. Logs trong console
3. Database có đúng dữ liệu không
4. API response có đúng format không

## 🆕 Cập Nhật Mới (28/09/2025)

### 1. Toast Thông Báo Cho User Chưa Có Quyền

#### VshProject (Web App)

- ✅ **Hook `useFactoryPermission`**: Kiểm tra quyền và hiển thị toast
- ✅ **Trang Kho Vật Tư**: Toast khi user chưa được gán nhà máy
- ✅ **Trang Kiểm Kê**: Toast khi user chưa được gán nhà máy
- ✅ **Thông báo**: "🚫 Bạn chưa được gán nhà máy. Vui lòng liên hệ admin để được cấp quyền truy cập dữ liệu."

#### VshMobile (Mobile App)

- ✅ **Hook `useFactoryPermission`**: Kiểm tra quyền và hiển thị Alert
- ✅ **HomeScreen**: Alert khi user chưa được gán nhà máy
- ✅ **MaterialDetailScreen**: Alert khi user chưa được gán nhà máy
- ✅ **Thông báo**: "🚫 Chưa có quyền truy cập - Bạn chưa được gán nhà máy. Vui lòng liên hệ admin để được cấp quyền truy cập dữ liệu."

### 2. Cập Nhật Toàn Bộ API Permissions

#### Trước Khi Cập Nhật:

```python
# Tất cả API đều cho phép truy cập tự do
permission_classes = [permissions.AllowAny]
```

#### Sau Khi Cập Nhật:

```python
# API cần quyền nhà máy
permission_classes = [HasFactoryAccess]

# API không cần quyền nhà máy (hệ thống, vị trí)
permission_classes = [IsAuthenticated]
```

#### Danh Sách API Đã Cập Nhật:

- ✅ **VatTuListAPIView** - Danh sách vật tư
- ✅ **KiemKeListAPIView** - Danh sách kiểm kê
- ✅ **DeNghiNhapListAPIView** - Danh sách đề nghị nhập
- ✅ **DeNghiXuatListAPIView** - Danh sách đề nghị xuất
- ✅ **VatTuDetailByIdAPIView** - Chi tiết vật tư theo ID
- ✅ **VatTuDetailByBravoAPIView** - Chi tiết vật tư theo mã Bravo
- ✅ **UploadMaterialImageView** - Upload hình ảnh vật tư
- ✅ **Tất cả API import/export, stats, update**

#### API Không Cần Quyền Nhà Máy:

- ✅ **HeThongListAPIView** - Danh sách hệ thống
- ✅ **ViTriListAPIView** - Danh sách vị trí
- ✅ **ViTriDetailAPIView** - Chi tiết vị trí

### 3. Factory Filtering Logic

#### KiemKeListAPIView:

```python
def get_queryset(self):
    qs = Bang_kiem_ke.objects.select_related('vat_tu__bang_nha_may')

    # Filter theo quyền nhà máy của user
    if self.request.user.is_authenticated:
        try:
            profile = self.request.user.profile
            if not profile.is_all_factories and profile.nha_may:
                # User chỉ có quyền truy cập nhà máy cụ thể
                qs = qs.filter(ma_nha_may=profile.nha_may.ma_nha_may)
        except:
            # Nếu không có profile, không cho phép truy cập
            qs = qs.none()

    return qs.order_by('id')
```

#### DeNghiNhapListAPIView & DeNghiXuatListAPIView:

```python
def get_queryset(self):
    qs = Bang_de_nghi_nhap.objects.select_related("vat_tu", "vat_tu__bang_nha_may")

    # Filter theo quyền nhà máy của user
    if self.request.user.is_authenticated:
        try:
            profile = self.request.user.profile
            if not profile.is_all_factories and profile.nha_may:
                # User chỉ có quyền truy cập nhà máy cụ thể
                qs = qs.filter(vat_tu__bang_nha_may=profile.nha_may)
        except:
            # Nếu không có profile, không cho phép truy cập
            qs = qs.none()

    return qs
```

### 4. Kết Quả Test Permissions

#### User KHÔNG có quyền nhà máy:

```
✅ Vat tu list: 403 FORBIDDEN
✅ Kiem ke list: 403 FORBIDDEN
✅ De nghi nhap list: 403 FORBIDDEN
✅ De nghi xuat list: 403 FORBIDDEN
✅ He thong list: 200 OK (24 items)
✅ Vi tri list: 200 OK (28 items)
```

#### User CÓ quyền nhà máy (SH - Sông Hinh):

```
✅ Vat tu list: 200 OK (10 items - filtered)
✅ Kiem ke list: 200 OK (20 items - filtered)
✅ De nghi nhap list: 200 OK (2 items - filtered)
✅ De nghi xuat list: 200 OK (1 item - filtered)
✅ He thong list: 200 OK (24 items)
✅ Vi tri list: 200 OK (28 items)
```

### 5. Hiển Thị Nhà Máy Trong UI

#### VshProject (Web App):

- ✅ **UserAvatar**: Hiển thị nhà máy dưới tên user
- ✅ **UpdateUserDataForm**: Hiển thị nhà máy trong form thông tin (read-only)
- ✅ **Format**: "🏭 Tất cả nhà máy" hoặc "🏭 SH - Sông Hinh"

#### VshMobile (Mobile App):

- ✅ **ProfileScreen**: Hiển thị nhà máy trong thông tin user
- ✅ **Format**: "Mã - Tên" (VD: "SH - Sông Hinh")
- ✅ **Chỉ hiển thị**: Không cho phép chọn nhà máy khác

### 6. Toast Thông Báo Khi Chọn Nhà Máy Khác Trong Bộ Lọc

#### VshProject (Web App):

- ✅ **VatTuOperations**: Kiểm tra quyền khi user chọn nhà máy khác trong bộ lọc vật tư
- ✅ **KiemKeOperations**: Kiểm tra quyền khi user chọn nhà máy khác trong bộ lọc kiểm kê
- ✅ **Logic**:
  - User có quyền nhà máy cụ thể (VD: SH - Sông Hinh)
  - Khi chọn nhà máy khác (VD: VS - Vĩnh Sơn) → Hiển thị toast error
  - Không thay đổi filter, giữ nguyên giá trị cũ
- ✅ **Thông báo**: "🚫 Bạn không có quyền xem dữ liệu nhà máy VS. Bạn chỉ được phép xem nhà máy SH."

#### Ví Dụ Hoạt Động:

```
User được gán quyền: SH - Sông Hinh
User chọn bộ lọc: VS - Vĩnh Sơn
→ Toast hiển thị: "🚫 Bạn không có quyền xem dữ liệu nhà máy VS. Bạn chỉ được phép xem nhà máy SH."
→ Filter không thay đổi, vẫn hiển thị "SH - Sông Hinh"
```

#### User Có Quyền Tất Cả Nhà Máy:

```
User có quyền: is_all_factories = true
→ Có thể chọn bất kỳ nhà máy nào trong bộ lọc
→ Không hiển thị toast thông báo
```

---

**Tạo bởi**: AI Assistant
**Ngày**: 28/09/2025
**Version**: 2.1 - Added Factory Filter Permission Checks
