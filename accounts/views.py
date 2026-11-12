from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import User
from .serializers import (
    CitizenRegistrationSerializer,
    CustomTokenObtainPairSerializer,
    UserPublicSerializer,
    LogoutSerializer,
)


class CitizenRegisterView(generics.CreateAPIView):
    """
    Register a new citizen account.
    Public registration strictly creates CITIZEN role accounts.
    """
    queryset = User.objects.all()
    serializer_class = CitizenRegistrationSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new citizen account",
        responses={
            201: UserPublicSerializer,
            400: OpenApiResponse(description="Validation error in submitted fields"),
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        response_data = {
            'user': UserPublicSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': 'Citizen account successfully registered.'
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


class CustomLoginView(TokenObtainPairView):
    """
    Authenticate using email and password, returning JWT access & refresh tokens.
    """
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="User Login (Email and Password)",
        description="Authenticates citizen, officer, or CMO admin and returns JWT tokens with user profile."
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class UserProfileView(generics.RetrieveAPIView):
    """
    Retrieve authenticated user profile.
    """
    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get current user profile")
    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    """
    Invalidate refresh token and perform secure logout.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(
        summary="User Logout",
        request=LogoutSerializer,
        responses={
            200: OpenApiResponse(description="Successfully logged out"),
            400: OpenApiResponse(description="Invalid or expired token"),
        }
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh_token = serializer.validated_data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out and token invalidated."},
                status=status.HTTP_200_OK
            )
        except TokenError as e:
            return Response(
                {"detail": "Token is invalid or already expired."},
                status=status.HTTP_400_BAD_REQUEST
            )
