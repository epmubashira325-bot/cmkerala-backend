from django.urls import path
from .views import ContactEnquiryCreateView

urlpatterns = [
    path('public/contact/', ContactEnquiryCreateView.as_view(), name='public-contact'),
]

