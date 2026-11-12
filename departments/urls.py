from django.urls import path
from .views import (
    DepartmentListView,
    DepartmentDetailView,
    CMODepartmentListCreateView,
    CMODepartmentRetrieveUpdateView,
    CMODepartmentOfficersListView,
)

urlpatterns = [
    # Public endpoints
    path('departments/', DepartmentListView.as_view(), name='department-list'),
    path('departments/<uuid:pk>/', DepartmentDetailView.as_view(), name='department-detail'),

    # CMO Management endpoints
    path('cmo/departments/', CMODepartmentListCreateView.as_view(), name='cmo-department-list-create'),
    path('cmo/departments/<uuid:pk>/', CMODepartmentRetrieveUpdateView.as_view(), name='cmo-department-detail-update'),
    path('cmo/departments/<uuid:pk>/officers/', CMODepartmentOfficersListView.as_view(), name='cmo-department-officers-list'),
]

