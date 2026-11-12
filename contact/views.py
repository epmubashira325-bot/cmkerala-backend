from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import ContactEnquiry
from .serializers import ContactEnquirySerializer


class ContactEnquiryCreateView(generics.CreateAPIView):
    """
    Public endpoint to submit general contact enquiries.
    """
    queryset = ContactEnquiry.objects.all()
    serializer_class = ContactEnquirySerializer
    permission_classes = [AllowAny]

    @extend_schema(summary="Public: Submit general contact enquiry")
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enquiry = serializer.save()
        return Response(
            {
                "message": "Your enquiry has been received successfully. Our helpdesk team will review it.",
                "enquiry": ContactEnquirySerializer(enquiry).data
            },
            status=status.HTTP_201_CREATED
        )
