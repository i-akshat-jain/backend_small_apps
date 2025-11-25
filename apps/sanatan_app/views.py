"""Views for Sanatan App API."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from .models import Shloka, ShlokaExplanation, User
from .serializers import (
    ShlokaSerializer, 
    ExplanationSerializer, 
    SignupSerializer, 
    LoginSerializer,
    UserSerializer
)
from .services import ShlokaService
import logging

logger = logging.getLogger(__name__)


class RandomShlokaView(APIView):
    """
    Get a random shloka with both summary and detailed explanations.
    
    API Path: GET /api/shlokas/random
    
    If explanations don't exist, they will be generated on-demand using AI.
    """
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='RandomShlokaResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
            404: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
            500: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Get a random shloka with both summary and detailed explanations. If explanations don't exist, they will be generated on-demand.",
        summary="Get random shloka",
        tags=["Shlokas"],
    )
    def get(self, request):
        """
        Get a random shloka with both summary and detailed explanations.
        
        API Path: GET /api/shlokas/random
        """
        try:
            shloka_service = ShlokaService()
            result = shloka_service.get_random_shloka()
            
            # Serialize the data
            shloka_serializer = ShlokaSerializer(result['shloka'])
            summary_serializer = ExplanationSerializer(result['summary']) if result.get('summary') else None
            detailed_serializer = ExplanationSerializer(result['detailed']) if result.get('detailed') else None
            
            return Response({
                'message': 'Random shloka retrieved successfully',
                'data': {
                    'shloka': shloka_serializer.data,
                    'summary': summary_serializer.data if summary_serializer else None,
                    'detailed': detailed_serializer.data if detailed_serializer else None,
                },
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in get_random_shloka: {error_message}")
            
            if "not found" in error_message.lower() or "no shlokas" in error_message.lower():
                return Response({
                    'message': 'No shlokas found',
                    'data': None,
                    'errors': {'detail': error_message}
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'message': 'Failed to retrieve random shloka',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ShlokaDetailView(APIView):
    """
    Get a specific shloka by ID with both summary and detailed explanations.
    
    API Path: GET /api/shlokas/{shloka_id}
    
    If explanations don't exist, they will be generated on-demand using AI.
    """
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='shloka_id',
                description='UUID of the shloka',
                required=True,
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH
            ),
        ],
        responses={
            200: inline_serializer(
                name='ShlokaDetailResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
            404: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
            500: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Get a specific shloka by ID with both summary and detailed explanations. If explanations don't exist, they will be generated on-demand.",
        summary="Get shloka by ID",
        tags=["Shlokas"],
    )
    def get(self, request, shloka_id):
        """
        Get a specific shloka by ID with both summary and detailed explanations.
        
        API Path: GET /api/shlokas/{shloka_id}
        """
        try:
            shloka_service = ShlokaService()
            result = shloka_service.get_shloka_by_id(shloka_id)
            
            # Serialize the data
            shloka_serializer = ShlokaSerializer(result['shloka'])
            summary_serializer = ExplanationSerializer(result['summary']) if result.get('summary') else None
            detailed_serializer = ExplanationSerializer(result['detailed']) if result.get('detailed') else None
            
            return Response({
                'message': 'Shloka retrieved successfully',
                'data': {
                    'shloka': shloka_serializer.data,
                    'summary': summary_serializer.data if summary_serializer else None,
                    'detailed': detailed_serializer.data if detailed_serializer else None,
                },
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in get_shloka_by_id: {error_message}")
            
            if "not found" in error_message.lower():
                return Response({
                    'message': 'Shloka not found',
                    'data': None,
                    'errors': {'detail': error_message}
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'message': 'Failed to retrieve shloka',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HealthCheckView(APIView):
    """
    Health check endpoint.
    
    API Path: GET /health
    """
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='HealthCheckResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Check if the API is running and healthy",
        summary="Health check",
        tags=["Health"],
    )
    def get(self, request):
        """
        Health check endpoint.
        
        API Path: GET /health
        """
        return Response({
            'message': 'API is healthy',
            'data': {
                'status': 'healthy'
            },
            'errors': None
        }, status=status.HTTP_200_OK)


class RootView(APIView):
    """
    Root endpoint with API information.
    
    API Path: GET /
    """
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='RootResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Get basic API information",
        summary="Root endpoint",
        tags=["Root"],
    )
    def get(self, request):
        """
        Root endpoint with API information.
        
        API Path: GET /
        """
        return Response({
            'message': 'Sanatan App API',
            'data': {
                'version': '1.0.0',
                'status': 'running'
            },
            'errors': None
        }, status=status.HTTP_200_OK)


class SignupView(APIView):
    """
    User signup endpoint.
    
    API Path: POST /api/auth/signup
    """
    
    @extend_schema(
        request=SignupSerializer,
        responses={
            201: inline_serializer(
                name='SignupResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
            400: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Create a new user account",
        summary="User signup",
        tags=["Authentication"],
    )
    def post(self, request):
        """
        Create a new user account.
        
        API Path: POST /api/auth/signup
        """
        try:
            serializer = SignupSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                
                # Serialize user data (without password)
                user_serializer = UserSerializer(user)
                
                return Response({
                    'message': 'User created successfully',
                    'data': {
                        'user': user_serializer.data,
                        'tokens': {
                            'access': str(refresh.access_token),
                            'refresh': str(refresh),
                        }
                    },
                    'errors': None
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'message': 'Validation error',
                    'data': None,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in signup: {error_message}")
            return Response({
                'message': 'Failed to create user',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginView(APIView):
    """
    User login endpoint.
    
    API Path: POST /api/auth/login
    """
    
    @extend_schema(
        request=LoginSerializer,
        responses={
            200: inline_serializer(
                name='LoginResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
            401: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Login with email and password to get JWT tokens",
        summary="User login",
        tags=["Authentication"],
    )
    def post(self, request):
        """
        Login with email and password.
        
        API Path: POST /api/auth/login
        """
        try:
            serializer = LoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'message': 'Validation error',
                    'data': None,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'message': 'Invalid credentials',
                    'data': None,
                    'errors': {'detail': 'Invalid email or password'}
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Check password
            if not user.check_password(password):
                return Response({
                    'message': 'Invalid credentials',
                    'data': None,
                    'errors': {'detail': 'Invalid email or password'}
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Serialize user data (without password)
            user_serializer = UserSerializer(user)
            
            return Response({
                'message': 'Login successful',
                'data': {
                    'user': user_serializer.data,
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                    }
                },
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in login: {error_message}")
            return Response({
                'message': 'Failed to login',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TokenRefreshView(APIView):
    """
    Refresh JWT access token.
    
    API Path: POST /api/auth/refresh
    """
    
    @extend_schema(
        request=inline_serializer(
            name='TokenRefreshRequest',
            fields={
                'refresh': OpenApiTypes.STR,
            }
        ),
        responses={
            200: inline_serializer(
                name='TokenRefreshResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
            401: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Refresh access token using refresh token",
        summary="Refresh token",
        tags=["Authentication"],
    )
    def post(self, request):
        """
        Refresh access token.
        
        API Path: POST /api/auth/refresh
        """
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({
                    'message': 'Refresh token is required',
                    'data': None,
                    'errors': {'detail': 'Refresh token is required'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                refresh = RefreshToken(refresh_token)
                access_token = refresh.access_token
                
                return Response({
                    'message': 'Token refreshed successfully',
                    'data': {
                        'access': str(access_token),
                    },
                    'errors': None
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'message': 'Invalid refresh token',
                    'data': None,
                    'errors': {'detail': 'Invalid or expired refresh token'}
                }, status=status.HTTP_401_UNAUTHORIZED)
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in token refresh: {error_message}")
            return Response({
                'message': 'Failed to refresh token',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
