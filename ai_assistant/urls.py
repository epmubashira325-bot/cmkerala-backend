from django.urls import path
from .views import AIAnalyzeGrievanceView

urlpatterns = [
    path('ai/analyze/', AIAnalyzeGrievanceView.as_view(), name='ai-analyze-grievance'),
]

