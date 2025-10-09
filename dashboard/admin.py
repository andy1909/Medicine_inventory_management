from django.contrib import admin
from .models import Product, Order, Patient, Prescription, PrescriptionDetail

# =======================================================
#               TÙY CHỈNH CHUNG CHO TRANG ADMIN
# =======================================================
admin.site.site_header = 'Adoo Medicine - Quản Trị Hệ Thống'
admin.site.site_title = 'Trang Quản Trị Adoo'
admin.site.index_title = 'Chào mừng đến với Bảng Điều Khiển'


# =======================================================
#      TÙY CHỈNH HIỂN THỊ CHO TỪNG MODEL TRONG ADMIN
# =======================================================

# -------------------------------------------------------
#   Model: PRODUCT (Sản phẩm/Thuốc)
#   - Hiển thị các thông tin quan trọng, cho phép lọc
#     theo danh mục và tìm kiếm theo tên/mã thuốc.
# -------------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'sale_price', 'expiry_date')
    list_filter = ('category',)
    search_fields = ('name', 'code')
    ordering = ('name',)


# -------------------------------------------------------
#   Model: PATIENT (Bệnh nhân)
#   - Hiển thị thông tin chính và cho phép tìm kiếm
#     nhanh theo tên, SĐT hoặc CCCD.
# -------------------------------------------------------
@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'age', 'gender', 'phone_number')
    search_fields = ('full_name', 'phone_number', 'citizen_id')
    ordering = ('-created_at',)


# -------------------------------------------------------
#   Inline Model: PRESCRIPTION DETAIL (Chi tiết toa thuốc)
#   - Đây là một "form con" sẽ được nhúng vào bên trong
#     trang quản lý Toa thuốc, giúp chỉnh sửa tại chỗ.
# -------------------------------------------------------
class PrescriptionDetailInline(admin.TabularInline):
    model = PrescriptionDetail
    extra = 1  


# -------------------------------------------------------
#   Model: PRESCRIPTION (Toa thuốc)
#   - Hiển thị thông tin tổng quan về toa thuốc.
#   - Nhúng (inline) các chi tiết thuốc để quản lý tập trung.
# -------------------------------------------------------
@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'doctor', 'created_at')
    search_fields = ('patient__full_name', 'doctor__username')
    ordering = ('-created_at',)
    inlines = [PrescriptionDetailInline]


# -------------------------------------------------------
#   Model: ORDER (Lịch sử xuất kho)
#   - Hiển thị các giao dịch bán hàng/xuất kho, bao gồm
#     cả thông tin bệnh nhân nếu đơn hàng từ toa thuốc.
# -------------------------------------------------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('product', 'order_quantity', 'staff', 'get_patient', 'date')
    list_filter = ('date', 'staff')
    search_fields = ('product__name', 'staff__username', 'prescription__patient__full_name')
    ordering = ('-date',)

    @admin.display(description='Bệnh nhân (từ toa)')
    def get_patient(self, obj):
        if obj.prescription and obj.prescription.patient:
            return obj.prescription.patient.full_name
        return "Bán lẻ / Đơn thủ công"


from django.contrib.auth.models import Group
admin.site.unregister(Group)