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
#   - View này vẫn cần giữ lại context vì nó truyền dữ liệu
#     cho biểu đồ (orders, products).
# -------------------------------------------------------
@login_required
def index(request):
    if request.user.is_staff or request.user.is_superuser:
        orders = Order.objects.all()
        products = Product.objects.all()
        context = {
            'orders': orders,
            'products': products,
        }
        return render(request, 'dashboard/index.html', context)
    else:
        return redirect('dashboard-prescription')


# -------------------------------------------------------
#   VIEW: TRANG LỊCH SỬ ĐƠN HÀNG (DÀNH CHO ADMIN)
#   - Đã xóa bỏ các biến *_count không cần thiết.
# -------------------------------------------------------
@login_required
def order(request):
    orders = Order.objects.all().order_by('-date')
    context = {
        'orders': orders,
    }
    return render(request, 'dashboard/order.html', context)


# =======================================================
#               QUẢN LÝ KÊ ĐƠN (PRESCRIPTION)
# =======================================================

# -------------------------------------------------------
#   VIEW: TRANG KÊ ĐƠN THUỐC
#   - Logic chính giữ nguyên.
# -------------------------------------------------------
@login_required
def prescription(request):
    if request.method == 'POST':
        prescription_form = PrescriptionForm(request.POST)
        if prescription_form.is_valid():
            try:
                with transaction.atomic():
                    new_prescription = prescription_form.save(commit=False)
                    new_prescription.doctor = request.user
                    new_prescription.status = 'Pending'
                    
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
                    
                    # Logic lưu đã được sửa lại cho đúng quy trình mới
                    new_prescription.save()
                    for item in details_to_process:
                        PrescriptionDetail.objects.create(
                            prescription=new_prescription,
                            product=item['product'],
                            quantity=item['quantity'])
                    
                    messages.success(request, f'Đã gửi toa thuốc cho bệnh nhân {new_prescription.patient.full_name} thành công.')
                    return redirect('dashboard-prescription')
            except Exception as e:
                messages.error(request, f'Đã có lỗi xảy ra: {e}')
        else:
            messages.error(request, 'Vui lòng kiểm tra lại thông tin, bạn có thể đã chưa chọn bệnh nhân.')
    
    # Logic cho phương thức GET
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
#               TRANG BÁO CÁO (REPORTS)
# =======================================================

# -------------------------------------------------------
#   VIEW: TRANG BÁO CÁO TỒN KHO VÀ SỬ DỤNG
#   - Cung cấp dữ liệu cho các biểu đồ phân tích.
# -------------------------------------------------------
@login_required
def report(request):
    # Chỉ Admin/Staff mới được xem báo cáo
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('dashboard-index')

    # Thu thập dữ liệu cho các biểu đồ
    products = Product.objects.all().order_by('-quantity') # Sắp xếp sản phẩm theo số lượng tồn kho
    orders = Order.objects.all()

    context = {
        'products': products,
        'orders': orders,
    }
    return render(request, 'dashboard/report.html', context)







# =======================================================
#               MODULE LẤY THUỐC (DISPENSE)
# =======================================================

# -------------------------------------------------------
#   VIEW: DANH SÁCH TOA THUỐC CHỜ LẤY
#   - Đã xóa bỏ các biến *_count không cần thiết.
# -------------------------------------------------------
@login_required
def dispense_list(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('dashboard-index')
        
    pending_prescriptions = Prescription.objects.filter(status='Pending').order_by('created_at')
    context = {
        'prescriptions': pending_prescriptions,
    }
    return render(request, 'dashboard/dispense_list.html', context)

# -------------------------------------------------------
#   VIEW: CHI TIẾT VÀ XỬ LÝ CẤP PHÁT THUỐC
#   - Logic chính giữ nguyên.
# -------------------------------------------------------
@login_required
def dispense_process(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('dashboard-index')

    try:
        prescription = Prescription.objects.get(id=pk, status='Pending')
    except Prescription.DoesNotExist:
        messages.error(request, 'Toa thuốc này không tồn tại hoặc đã được xử lý.')
        return redirect('dispense-list')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                details_to_dispense = request.POST.getlist('details')
                if not details_to_dispense:
                    messages.error(request, 'Bạn phải chọn ít nhất một loại thuốc để cấp phát.')
                    return redirect('dispense-process', pk=pk)
                
                for detail_id in details_to_dispense:
                    detail = PrescriptionDetail.objects.get(id=detail_id, prescription=prescription)
                    product = detail.product
                    if product.quantity < detail.quantity:
                        raise Exception(f"Không đủ thuốc '{product.name}'. Tồn kho: {product.quantity}.")
                    
                    product.quantity -= detail.quantity
                    product.save()
                    detail.is_collected = True
                    detail.save()
                    Order.objects.create(
                        product=product,
                        order_quantity=detail.quantity,
                        staff=request.user,
                        prescription=prescription
                    )
                
                prescription.status = 'Dispensed'
                prescription.completed_at = timezone.now()
                prescription.save()
                messages.success(request, f'Đã cấp phát thuốc thành công cho toa #{prescription.id}.')
                return redirect('dispense-list')

        except Exception as e:
            messages.error(request, f'Lỗi: {e}')
            return redirect('dispense-process', pk=pk)

    context = {'prescription': prescription}
    return render(request, 'dashboard/dispense_process.html', context)


# =======================================================
#               QUẢN LÝ SẢN PHẨM (PRODUCT CRUD)
# =======================================================

# -------------------------------------------------------
#   VIEW: DANH SÁCH SẢN PHẨM (READ)
#   - Đã xóa bỏ các biến *_count không cần thiết.
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
#   - Đã xóa bỏ các biến *_count không cần thiết.
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
#   - Đã xóa bỏ các biến *_count không cần thiết.
# -------------------------------------------------------
@login_required
def staff(request):
    workers = User.objects.all()
    context = {
        'workers': workers,
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