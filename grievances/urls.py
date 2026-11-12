from django.urls import path
from .views import (
    # Citizen
    CitizenGrievanceListCreateView,
    CitizenGrievanceDetailView,
    CitizenFeedbackSubmitView,
    PublicGrievanceTrackView,

    # CMO
    CMOGrievanceListView,
    CMOGrievanceDetailView,
    CMOAssignGrievanceView,
    CMOAddRemarkView,
    CMOEscalateView,
    CMOReviewReportView,

    # Officer
    OfficerGrievanceListView,
    OfficerGrievanceDetailView,
    OfficerAddRemarkView,
    OfficerSubmitReportView,
)

urlpatterns = [
    # Public Tracking
    path('grievances/track/', PublicGrievanceTrackView.as_view(), name='grievance-track'),

    # Citizen Endpoints
    path('citizen/grievances/', CitizenGrievanceListCreateView.as_view(), name='citizen-grievance-list-create'),
    path('citizen/grievances/<uuid:pk>/', CitizenGrievanceDetailView.as_view(), name='citizen-grievance-detail'),
    path('citizen/grievances/<uuid:pk>/feedback/', CitizenFeedbackSubmitView.as_view(), name='citizen-feedback-submit'),

    # CMO Endpoints
    path('cmo/grievances/', CMOGrievanceListView.as_view(), name='cmo-grievance-list'),
    path('cmo/grievances/<uuid:pk>/', CMOGrievanceDetailView.as_view(), name='cmo-grievance-detail'),
    path('cmo/grievances/<uuid:pk>/assign/', CMOAssignGrievanceView.as_view(), name='cmo-grievance-assign'),
    path('cmo/grievances/<uuid:pk>/remarks/', CMOAddRemarkView.as_view(), name='cmo-grievance-remark'),
    path('cmo/grievances/<uuid:pk>/escalate/', CMOEscalateView.as_view(), name='cmo-grievance-escalate'),
    path('cmo/reports/<uuid:pk>/review/', CMOReviewReportView.as_view(), name='cmo-report-review'),

    # Officer Endpoints
    path('officer/grievances/', OfficerGrievanceListView.as_view(), name='officer-grievance-list'),
    path('officer/grievances/<uuid:pk>/', OfficerGrievanceDetailView.as_view(), name='officer-grievance-detail'),
    path('officer/grievances/<uuid:pk>/remarks/', OfficerAddRemarkView.as_view(), name='officer-grievance-remark'),
    path('officer/grievances/<uuid:pk>/reports/', OfficerSubmitReportView.as_view(), name='officer-report-submit'),
]

