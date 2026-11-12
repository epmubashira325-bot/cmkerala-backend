"""
URL configuration for CM Kerala Public Grievance Redressal Portal.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Admin Interface
    path('admin/', admin.site.urls),

    # API Version 1 Endpoints
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/', include('departments.urls')),
    path('api/v1/', include('grievances.urls')),
    path('api/v1/', include('ai_assistant.urls')),
    path('api/v1/', include('contact.urls')),
    path('api/v1/', include('dashboard.urls')),

    # API Documentation (OpenAPI 3.0 / Swagger / Redoc)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
