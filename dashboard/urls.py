from django.urls import path
from .views import CMODashboardStatsView

urlpatterns = [
    path('cmo/stats/', CMODashboardStatsView.as_view(), name='cmo-stats'),
]

