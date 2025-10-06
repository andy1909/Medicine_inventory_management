from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.index, name='dashboard-index'),
    
    path('staff/', views.staff, name='dashboard-staff'),
    path('staff/detail/<int:pk>/', views.staff_detail, name='dashboard-staff-detail'),
    
    path('product/', views.product, name='dashboard-product'),
    path('product/add/', views.product_add, name='dashboard-product-add'),
    path('product/delete/<int:pk>/', views.product_delete, name='dashboard-product-delete'),
    path('product/update/<int:pk>/', views.product_update, name='dashboard-product-update'),
    
    path('order/', views.order, name='dashboard-order'),
    
    path('prescription/', views.prescription, name='dashboard-prescription'),
    # path('prescription/complete/<int:pk>/', views.complete_prescription, name='complete-prescription'),

    path('patient/', views.patient_list, name='dashboard-patient-list'),
    path('patient/add/', views.patient_add, name='dashboard-patient-add'),
    path('patient/update/<int:pk>/', views.patient_update, name='dashboard-patient-update'),
    path('patient/delete/<int:pk>/', views.patient_delete, name='dashboard-patient-delete'),

    # URLs cho module Lấy Thuốc
    path('dispense/', views.dispense_list, name='dispense-list'),
    path('dispense/process/<int:pk>/', views.dispense_process, name='dispense-process'),

    # URL CHO TRANG BÁO CÁO
    path('report/', views.report, name='dashboard-report')
]