# =======================================================
#               KHAI BÁO THƯ VIỆN (IMPORTS)
# =======================================================
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views import View
from django import forms

# Decorators & Authentication
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView as BasePasswordResetView

# Models & Forms
from .models import Product, Order, Prescription, PrescriptionDetail, Patient
from .forms import (
    ProductForm, OrderForm, PrescriptionForm,
    PrescriptionDetailForm, PatientForm
)

# Utilities
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist


# =======================================================
#               CÁC VIEW CHÍNH & DASHBOARD
# =======================================================

# -------------------------------------------------------
#   VIEW: TRANG CHỦ (DASHBOARD)
#   - Phân luồng người dùng: Admin xem dashboard,
#     Bác sĩ được chuyển hướng đến trang kê đơn.
# -------------------------------------------------------
@login_required
def index(request):
    if request.user.is_staff or request.user.is_superuser:
        orders = Order.objects.all()
        products = Product.objects.all()
        context = {
            'orders': orders,
            'products': products,
            'workers_count': User.objects.all().count(),
            'orders_count': orders.count(),
            'products_count': products.count(),
        }
        return render(request, 'dashboard/index.html', context)
    else:
        return redirect('dashboard-prescription')


# -------------------------------------------------------
#   VIEW: TRANG LỊCH SỬ ĐƠN HÀNG (DÀNH CHO ADMIN)
#   - Hiển thị tất cả các giao dịch xuất kho.
# -------------------------------------------------------
@login_required
def order(request):
    orders = Order.objects.all().order_by('-date')
    context = {
        'orders': orders,
        'workers_count': User.objects.all().count(),
        'orders_count': orders.count(),
        'products_count': Product.objects.all().count(),
    }
    return render(request, 'dashboard/order.html', context)


# =======================================================
#               QUẢN LÝ KÊ ĐƠN (PRESCRIPTION)
# =======================================================

# -------------------------------------------------------
#   VIEW: TRANG KÊ ĐƠN THUỐC
#   - Xử lý việc tạo toa thuốc mới, kiểm tra kho,
#     và cập nhật lịch sử.
# -------------------------------------------------------
@login_required
def prescription(request):
    if request.method == 'POST':
        prescription_form = PrescriptionForm(request.POST)
        if prescription_form.is_valid():
            try:
                with transaction.atomic():
                    # --- BƯỚC 1: Xử lý form chính và gán bác sĩ ---
                    # Tạo một đối tượng prescription trong bộ nhớ, chưa lưu vào DB
                    new_prescription = prescription_form.save(commit=False)
                    
                    # <-- THAY ĐỔI QUAN TRỌNG: Gán bác sĩ là người dùng đang đăng nhập
                    new_prescription.doctor = request.user
                    
                    # --- BƯỚC 2: Kiểm tra và xử lý các chi tiết thuốc ---
                    form_count = int(request.POST.get('form_count', 0))
                    if form_count == 0 or not any(request.POST.get(f'details-{i}-product') for i in range(form_count)):
                        messages.error(request, 'Toa thuốc phải có ít nhất một loại thuốc.')
                        return redirect('dashboard-prescription')

                    details_to_process = []
                    for i in range(form_count):
                        product_id = request.POST.get(f'details-{i}-product')
                        quantity_str = request.POST.get(f'details-{i}-quantity')
                        if product_id and quantity_str and int(quantity_str) > 0:
                            product = Product.objects.get(id=int(product_id))
                            quantity = int(quantity_str)
                            if product.quantity < quantity:
                                messages.error(request, f"Không đủ thuốc '{product.name}'. Tồn kho: {product.quantity}.")
                                return redirect('dashboard-prescription')
                            details_to_process.append({'product': product, 'quantity': quantity})
                    
                    # --- BƯỚC 3: Nếu mọi thứ hợp lệ, tiến hành lưu tất cả ---
                    new_prescription.save()  # Bây giờ mới lưu toa thuốc chính vào DB
                    
                    for item in details_to_process:
                        product = item['product']
                        quantity = item['quantity']
                        PrescriptionDetail.objects.create(
                            prescription=new_prescription,
                            product=product,
                            quantity=quantity,
                            is_collected=True)
                        product.quantity -= quantity
                        product.save()
                        Order.objects.create(
                            product=product,
                            order_quantity=quantity,
                            staff=request.user,
                            prescription=new_prescription)
                    
                    new_prescription.completed_at = timezone.now()
                    new_prescription.save()
                    messages.success(request, f'Hoàn tất toa thuốc cho bệnh nhân {new_prescription.patient.full_name}!')
                    return redirect('dashboard-prescription')
            
            except Exception as e:
                messages.error(request, f'Đã có lỗi không mong muốn xảy ra: {e}')
        
        else: # Nếu form không hợp lệ (ví dụ: chưa chọn bệnh nhân)
            messages.error(request, 'Vui lòng kiểm tra lại thông tin, bạn có thể đã chưa chọn bệnh nhân.')
    
    # Logic cho phương thức GET: Chỉ cần tạo một form trống
    prescription_form = PrescriptionForm()
    
    if request.user.is_staff or request.user.is_superuser:
        prescriptions = Prescription.objects.all().order_by('-created_at')
    else:
        prescriptions = Prescription.objects.filter(doctor=request.user).order_by('-created_at')
        
    context = {
        'prescription_form': prescription_form,
        'prescriptions': prescriptions,
        'products': Product.objects.all(),
    }
    return render(request, 'dashboard/prescription.html', context)


# =======================================================
#               QUẢN LÝ SẢN PHẨM (PRODUCT CRUD)
# =======================================================

# -------------------------------------------------------
#   VIEW: DANH SÁCH SẢN PHẨM (READ)
#   - Hiển thị và tìm kiếm tất cả sản phẩm.
# -------------------------------------------------------
@login_required
def product(request):
    search_query = request.GET.get('search', '')
    if search_query:
        items = Product.objects.filter(
            Q(name__icontains=search_query) | 
            Q(category__icontains=search_query) | 
            Q(code__icontains=search_query)
        )
    else:
        items = Product.objects.all()
    context = {
        'items': items,
        'search_query': search_query,
        'workers_count': User.objects.all().count(),
        'orders_count': Order.objects.all().count(),
        'products_count': items.count(),
    }
    return render(request, 'dashboard/product.html', context)


# -------------------------------------------------------
#   VIEW: THÊM SẢN PHẨM (CREATE)
# -------------------------------------------------------
@login_required
def product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            product_name = form.cleaned_data.get('name')
            messages.success(request, f'Thêm thuốc "{product_name}" thành công!')
            return redirect('dashboard-product')
    else:
        form = ProductForm()
    context = {'form': form}
    return render(request, 'dashboard/product_add.html', context)


# -------------------------------------------------------
#   VIEW: CẬP NHẬT SẢN PHẨM (UPDATE)
# -------------------------------------------------------
@login_required
def product_update(request, pk):
    item = Product.objects.get(id=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cập nhật thuốc "{item.name}" thành công!')
            return redirect('dashboard-product')
    else:
        form = ProductForm(instance=item)
    context = {'form': form}
    return render(request, 'dashboard/product_update.html', context)


# -------------------------------------------------------
#   VIEW: XÓA SẢN PHẨM (DELETE)
# -------------------------------------------------------
@login_required
def product_delete(request, pk):
    item = Product.objects.get(id=pk)
    if request.method == 'POST':
        item.delete()
        messages.success(request, f'Đã xóa thuốc "{item.name}".')
        return redirect('dashboard-product')
    context = {'item': item}
    return render(request, 'dashboard/product_delete.html', context)


# =======================================================
#               QUẢN LÝ BỆNH NHÂN (PATIENT CRUD)
# =======================================================

# -------------------------------------------------------
#   VIEW: DANH SÁCH BỆNH NHÂN (READ)
# -------------------------------------------------------
@login_required
def patient_list(request):
    search_query = request.GET.get('search', '')
    if search_query:
        patients = Patient.objects.filter(full_name__icontains=search_query)
    else:
        patients = Patient.objects.all()
    context = {
        'patients': patients,
        'search_query': search_query,
        'workers_count': User.objects.all().count(),
        'orders_count': Order.objects.all().count(),
        'products_count': Product.objects.all().count(),
    }
    return render(request, 'dashboard/patient_list.html', context)


# -------------------------------------------------------
#   VIEW: THÊM BỆNH NHÂN (CREATE)
# -------------------------------------------------------
@login_required
def patient_add(request):
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã thêm hồ sơ bệnh nhân mới thành công.')
            return redirect('dashboard-patient-list')
    else:
        form = PatientForm()
    context = {'form': form, 'title': 'Thêm Hồ Sơ Bệnh Nhân'}
    return render(request, 'dashboard/patient_form.html', context)


# -------------------------------------------------------
#   VIEW: CẬP NHẬT BỆNH NHÂN (UPDATE)
# -------------------------------------------------------
@login_required
def patient_update(request, pk):
    patient = Patient.objects.get(id=pk)
    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, f'Đã cập nhật hồ sơ cho bệnh nhân {patient.full_name}.')
            return redirect('dashboard-patient-list')
    else:
        form = PatientForm(instance=patient)
    context = {'form': form, 'title': 'Cập Nhật Hồ Sơ Bệnh Nhân'}
    return render(request, 'dashboard/patient_form.html', context)


# -------------------------------------------------------
#   VIEW: XÓA BỆNH NHÂN (DELETE)
# -------------------------------------------------------
@login_required
def patient_delete(request, pk):
    patient = Patient.objects.get(id=pk)
    if request.method == 'POST':
        patient.delete()
        messages.success(request, f'Đã xóa hồ sơ của bệnh nhân {patient.full_name}.')
        return redirect('dashboard-patient-list')
    context = {'item': patient}
    return render(request, 'dashboard/patient_confirm_delete.html', context)


# =======================================================
#               QUẢN LÝ NHÂN VIÊN (STAFF)
# =======================================================

# -------------------------------------------------------
#   VIEW: DANH SÁCH NHÂN VIÊN
# -------------------------------------------------------
@login_required
def staff(request):
    workers = User.objects.all()
    context = {
        'workers': workers,
        'workers_count': workers.count(),
        'orders_count': Order.objects.all().count(),
        'products_count': Product.objects.all().count(),
    }
    return render(request, 'dashboard/staff.html', context)


# -------------------------------------------------------
#   VIEW: CHI TIẾT NHÂN VIÊN
# -------------------------------------------------------
@login_required
def staff_detail(request, pk):
    worker = User.objects.get(id=pk)
    context = {'worker': worker}
    return render(request, 'dashboard/staff_detail.html', context)


# =======================================================
#           CÁC VIEW/CLASS XỬ LÝ MẬT KHẨU
#   (Đây là các chức năng phụ, có thể để ở cuối file)
# =======================================================
class UsernameResetForm(forms.Form):
    username = forms.CharField(max_length=150, label="Enter your username")

class UsernameResetView(View):
    template_name = 'user/username_reset.html'
    def get(self, request):
        return render(request, self.template_name, {'form': UsernameResetForm()})
    def post(self, request):
        form = UsernameResetForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            try:
                User.objects.get(username=username)
                request.session['reset_username'] = username
                return redirect('password_reset')
            except User.DoesNotExist:
                messages.error(request, "Username does not exist.")
        return render(request, self.template_name, {'form': form})

class CustomPasswordResetView(BasePasswordResetView):
    template_name = 'user/password_reset_form.html'
    def post(self, request, *args, **kwargs):
        username = request.session.get('reset_username')
        if not username:
            messages.error(request, "Please enter your username first.")
            return redirect('username-reset')
        try:
            user = User.objects.get(username=username)
            request.POST = request.POST.copy()
            request.POST['email'] = user.email
            return super().post(request, *args, **kwargs)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('username-reset')

# -------------------------------------------------------
#   HÀM HELPER (nếu có, ví dụ: format_price)
#   (Lưu ý: hàm này hiện không được sử dụng ở đâu)
# -------------------------------------------------------
def format_price(value):
    if value is not None:
        return "{:,.0f}".format(float(value)).replace(',', '.')
    return "N/A"