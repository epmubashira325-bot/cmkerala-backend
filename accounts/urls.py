from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CitizenRegisterView,
    CustomLoginView,
    UserProfileView,
    LogoutView,
)

urlpatterns = [
    path('register/', CitizenRegisterView.as_view(), name='auth-register'),
    path('login/', CustomLoginView.as_view(), name='auth-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('me/', UserProfileView.as_view(), name='auth-me'),
]

