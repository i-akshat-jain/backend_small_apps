"""Views for Sanatan App API."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from .models import Shloka, ShlokaExplanation, User, ReadingLog, ReadingType, Favorite, ChatConversation, ChatMessage, ShlokaReadStatus, UserAchievement
from .serializers import (
    ShlokaSerializer, 
    ExplanationSerializer, 
    SignupSerializer, 
    LoginSerializer,
    UserSerializer,
    ReadingLogSerializer,
    ReadingLogCreateSerializer,
    FavoriteSerializer,
    ChatConversationSerializer,
    ChatMessageSerializer,
    ChatMessageCreateSerializer,
    UserStreakSerializer,
    ProfileUpdateSerializer,
    ChangePasswordSerializer,
    UserAchievementSerializer
)
from core.services.authentication import UUIDJWTAuthentication
from .services.shloka_service import ShlokaService
from .services.stats_service import StatsService
from .services.chatbot_service import ChatbotService
from django.utils import timezone
from datetime import timedelta
import logging
import uuid
import json

logger = logging.getLogger(__name__)


def _format_shloka_response(result: dict, success_message: str = "Shloka retrieved successfully"):
    """
    Format shloka response in a consistent structure.
    
    This helper function ensures all shloka endpoints return the same format:
    {
        'message': str,
        'data': {
            'shloka': {...},
            'explanation': {...} or None,
        },
        'errors': None
    }
    
    Args:
        result: Dictionary from ShlokaService with keys 'shloka', 'explanation'
        success_message: Custom success message (default: "Shloka retrieved successfully")
        
    Returns:
        Formatted response dictionary
    """
    # Serialize the data consistently
    shloka_serializer = ShlokaSerializer(result['shloka'])
    explanation_serializer = ExplanationSerializer(result['explanation']) if result.get('explanation') else None
    
    # Return consistent format
    return {
        'message': success_message,
        'data': {
            'shloka': shloka_serializer.data,
            'explanation': explanation_serializer.data if explanation_serializer else None,
        },
        'errors': None
    }


class RandomShlokaView(APIView):
    """
    Get a random shloka with explanation.
    
    API Path: GET /api/shlokas/random
    
    Explanations are pre-generated and fetched directly from the database.
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
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
        description="Get a random shloka with explanation. Explanations are pre-generated and fetched from the database.",
        summary="Get random shloka",
        tags=["Shlokas"],
    )
    def get(self, request):
        """
        Get a random shloka with explanation.
        
        API Path: GET /api/shlokas/random
        
        Returns a random shloka from all available shlokas in the database.
        Explanations are pre-generated and fetched directly from the database.
        No AI calls are made - this endpoint only queries existing data.
        """
        try:
            # Get a random shloka from all available shlokas
            shloka = Shloka.objects.order_by('?').first()
            
            if shloka is None:
                return Response({
                    'message': 'No shlokas found',
                    'data': None,
                    'errors': {'detail': 'No shlokas available in the database'}
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get explanation directly from database (pre-generated)
            # There's only one explanation per shloka now
            explanation = ShlokaExplanation.objects.filter(
                shloka_id=shloka.id
            ).first()
            
            # Format response using helper function
            result = {
                'shloka': shloka,
                'explanation': explanation,
            }
            response_data = _format_shloka_response(result, 'Random shloka retrieved successfully')
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in RandomShlokaView: {error_message}")
            
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
    Get a specific shloka by ID with explanation.
    
    API Path: GET /api/shlokas/{shloka_id}
    
    Explanations are pre-generated and fetched directly from the database.
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
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
        description="Get a specific shloka by ID with explanation. Explanations are pre-generated and fetched from the database.",
        summary="Get shloka by ID",
        tags=["Shlokas"],
    )
    def get(self, request, shloka_id):
        """
        Get a specific shloka by ID with explanation.
        
        API Path: GET /api/shlokas/{shloka_id}
        
        Explanations are pre-generated and fetched directly from the database.
        """
        try:
            shloka_service = ShlokaService()
            result = shloka_service.get_shloka_by_id(shloka_id)
            
            # Use helper function to ensure consistent format
            response_data = _format_shloka_response(result, 'Shloka retrieved successfully')
            
            # Log the response data for debugging
            response_json = json.dumps(response_data, indent=2, default=str)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
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


class ShlokaByChapterVerseView(APIView):
    """
    Get a specific shloka by book name, chapter number, and verse number.
    
    API Path: GET /api/shlokas/by-chapter-verse?book_name=Bhagavad Gita&chapter=3&verse=30
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='book_name',
                description='Name of the book (e.g., "Bhagavad Gita")',
                required=True,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY
            ),
            OpenApiParameter(
                name='chapter',
                description='Chapter number',
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY
            ),
            OpenApiParameter(
                name='verse',
                description='Verse number',
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY
            ),
        ],
        responses={
            200: inline_serializer(
                name='ShlokaByChapterVerseResponse',
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
        },
        description="Get a specific shloka by book name, chapter number, and verse number.",
        summary="Get shloka by chapter and verse",
        tags=["Shlokas"],
    )
    def get(self, request):
        """
        Get a specific shloka by book name, chapter number, and verse number.
        """
        try:
            book_name = request.query_params.get('book_name', 'Bhagavad Gita')
            chapter_number = request.query_params.get('chapter')
            verse_number = request.query_params.get('verse')
            
            if not chapter_number or not verse_number:
                return Response({
                    'message': 'Missing required parameters',
                    'data': None,
                    'errors': {'detail': 'Both chapter and verse parameters are required'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                chapter_number = int(chapter_number)
                verse_number = int(verse_number)
            except ValueError:
                return Response({
                    'message': 'Invalid parameters',
                    'data': None,
                    'errors': {'detail': 'Chapter and verse must be valid integers'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            shloka_service = ShlokaService()
            result = shloka_service.get_shloka_by_chapter_verse(
                book_name=book_name,
                chapter_number=chapter_number,
                verse_number=verse_number
            )
            
            # Use helper function to ensure consistent format
            response_data = _format_shloka_response(result, 'Shloka retrieved successfully')
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in get_shloka_by_chapter_verse: {error_message}")
            
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
    permission_classes = [AllowAny]
    authentication_classes = []
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
    permission_classes = [AllowAny]
    authentication_classes = []
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
    permission_classes = [AllowAny]
    authentication_classes = []
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
                access_token = refresh.access_token
                
                # Calculate token expiration times
                access_token_expires_at = timezone.now() + api_settings.ACCESS_TOKEN_LIFETIME
                refresh_token_expires_at = timezone.now() + api_settings.REFRESH_TOKEN_LIFETIME
                
                # Save tokens to user model
                user.update_tokens(
                    access_token=str(access_token),
                    refresh_token=str(refresh),
                    access_token_expires_at=access_token_expires_at,
                    refresh_token_expires_at=refresh_token_expires_at
                )
                
                # Serialize user data (without password)
                user_serializer = UserSerializer(user)
                
                return Response({
                    'message': 'User created successfully',
                    'data': {
                        'user': user_serializer.data,
                        'tokens': {
                            'access': str(access_token),
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
    permission_classes = [AllowAny] 
    authentication_classes = []
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
            access_token = refresh.access_token
            
            # Calculate token expiration times
            access_token_expires_at = timezone.now() + api_settings.ACCESS_TOKEN_LIFETIME
            refresh_token_expires_at = timezone.now() + api_settings.REFRESH_TOKEN_LIFETIME
            
            # Save tokens to user model
            user.update_tokens(
                access_token=str(access_token),
                refresh_token=str(refresh),
                access_token_expires_at=access_token_expires_at,
                refresh_token_expires_at=refresh_token_expires_at
            )
            
            # Serialize user data (without password)
            user_serializer = UserSerializer(user)
            
            return Response({
                'message': 'Login successful',
                'data': {
                    'user': user_serializer.data,
                    'tokens': {
                        'access': str(access_token),
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
    permission_classes = [AllowAny]
    authentication_classes = []
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
                
                # Get user from token
                user_id = refresh[api_settings.USER_ID_CLAIM]
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return Response({
                        'message': 'User not found',
                        'data': None,
                        'errors': {'detail': 'User associated with token not found'}
                    }, status=status.HTTP_401_UNAUTHORIZED)
                
                # Check if token rotation is enabled (refresh token is rotated)
                new_refresh_token = None
                if api_settings.ROTATE_REFRESH_TOKENS:
                    # Blacklist the old refresh token (if blacklist app is available)
                    try:
                        refresh.blacklist()
                    except (AttributeError, NotImplementedError):
                        # Blacklist app not installed, skip blacklisting
                        logger.warning("Token blacklist app not installed, skipping blacklist")
                    except Exception as e:
                        # Log but don't fail if blacklisting fails
                        logger.warning(f"Failed to blacklist token: {str(e)}")
                    # Generate new refresh token
                    new_refresh = RefreshToken.for_user(user)
                    new_refresh_token = str(new_refresh)
                else:
                    # Use the same refresh token
                    new_refresh_token = str(refresh)
                
                # Extend refresh token expiry to 30 days from now (every time refresh is called)
                refresh_token_expires_at = timezone.now() + api_settings.REFRESH_TOKEN_LIFETIME
                
                # Calculate access token expiration (1 hour from now)
                access_token_expires_at = timezone.now() + api_settings.ACCESS_TOKEN_LIFETIME
                
                # Update tokens in user model
                user.update_tokens(
                    access_token=str(access_token),
                    refresh_token=new_refresh_token,
                    access_token_expires_at=access_token_expires_at,
                    refresh_token_expires_at=refresh_token_expires_at
                )
                
                response_data = {
                    'access': str(access_token),
                }
                
                # Include new refresh token if rotated
                if new_refresh_token and api_settings.ROTATE_REFRESH_TOKENS:
                    response_data['refresh'] = new_refresh_token
                
                return Response({
                    'message': 'Token refreshed successfully',
                    'data': response_data,
                    'errors': None
                }, status=status.HTTP_200_OK)
            except (TokenError, InvalidToken) as e:
                logger.error(f"Token validation error: {str(e)}")
                return Response({
                    'message': 'Invalid refresh token',
                    'data': None,
                    'errors': {'detail': f'Invalid or expired refresh token: {str(e)}'}
                }, status=status.HTTP_401_UNAUTHORIZED)
            except Exception as e:
                logger.error(f"Unexpected error in token refresh: {str(e)}")
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


class UserStatsView(APIView):
    """
    Get user statistics.
    
    API Path: GET /api/user/stats
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='UserStatsResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Get user statistics including level, experience, streak, and reading counts",
        summary="Get user stats",
        tags=["User"],
    )
    def get(self, request):
        """
        Get user statistics.
        
        API Path: GET /api/user/stats
        """
        try:
            stats = StatsService.get_user_stats(request.user)
            
            return Response({
                'message': 'User statistics retrieved successfully',
                'data': stats,
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error getting user stats: {error_message}")
            return Response({
                'message': 'Failed to retrieve user statistics',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserStreakView(APIView):
    """
    Get user streak information.
    
    API Path: GET /api/user/streak
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='UserStreakResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Get user streak information including current streak, longest streak, and freeze status",
        summary="Get user streak",
        tags=["User"],
    )
    def get(self, request):
        """
        Get user streak information.
        
        API Path: GET /api/user/streak
        """
        try:
            from .models import UserStreak
            streak_data, created = UserStreak.objects.get_or_create(user=request.user)
            
            # Update streak calculation
            StatsService.calculate_streak(request.user, update_streak_data=True)
            
            # Refresh from DB
            streak_data.refresh_from_db()
            
            serializer = UserStreakSerializer(streak_data)
            
            return Response({
                'message': 'User streak retrieved successfully',
                'data': serializer.data,
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error getting user streak: {error_message}")
            return Response({
                'message': 'Failed to retrieve user streak',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserStreakFreezeView(APIView):
    """
    Use streak freeze to prevent streak from breaking.
    
    API Path: POST /api/user/streak/freeze
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='StreakFreezeResponse',
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
        description="Use streak freeze to protect your streak from breaking (1 per month)",
        summary="Use streak freeze",
        tags=["User"],
    )
    def post(self, request):
        """
        Use streak freeze to prevent streak from breaking.
        
        API Path: POST /api/user/streak/freeze
        """
        try:
            result = StatsService.use_streak_freeze(request.user)
            
            if result['success']:
                return Response({
                    'message': result['message'],
                    'data': {
                        'freeze_used': True,
                        'freeze_available': result['freeze_available'],
                        'current_streak': result.get('current_streak', 0)
                    },
                    'errors': None
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'message': result['message'],
                    'data': {
                        'freeze_used': False,
                        'freeze_available': result.get('freeze_available', False)
                    },
                    'errors': {'detail': result['message']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error using streak freeze: {error_message}")
            return Response({
                'message': 'Failed to use streak freeze',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserStreakHistoryView(APIView):
    """
    Get user streak history and milestones.
    
    API Path: GET /api/user/streak/history
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='StreakHistoryResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Get user streak history including milestones reached",
        summary="Get streak history",
        tags=["User"],
    )
    def get(self, request):
        """
        Get user streak history and milestones.
        
        API Path: GET /api/user/streak/history
        """
        try:
            from .models import UserStreak
            streak_data, created = UserStreak.objects.get_or_create(user=request.user)
            
            # Check for milestones
            milestones = StatsService.check_streak_milestones(request.user)
            
            # Get recent reading dates for streak visualization
            from django.db.models import Count
            from django.utils import timezone
            from datetime import timedelta
            
            # Get last 30 days of reading activity
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_readings = ShlokaReadStatus.objects.filter(
                user=request.user,
                marked_read_at__gte=thirty_days_ago
            ).extra(
                select={'date': 'DATE(marked_read_at)'}
            ).values('date').annotate(
                count=Count('id')
            ).order_by('-date')
            
            # Format dates as YYYY-MM-DD strings for consistent frontend handling
            formatted_recent_activity = []
            for item in recent_readings:
                date_value = item['date']
                # Handle both date objects and strings
                if hasattr(date_value, 'strftime'):
                    # It's a date/datetime object
                    formatted_date = date_value.strftime('%Y-%m-%d')
                elif isinstance(date_value, str):
                    # It's already a string, ensure it's in YYYY-MM-DD format
                    formatted_date = date_value.split('T')[0].split(' ')[0]
                else:
                    # Fallback: convert to string and extract date part
                    formatted_date = str(date_value).split('T')[0].split(' ')[0]
                
                formatted_recent_activity.append({
                    'date': formatted_date,
                    'count': item['count']
                })
            
            return Response({
                'message': 'Streak history retrieved successfully',
                'data': {
                    'current_streak': streak_data.current_streak,
                    'longest_streak': streak_data.longest_streak,
                    'total_streak_days': streak_data.total_streak_days,
                    'last_streak_date': streak_data.last_streak_date.isoformat() if streak_data.last_streak_date else None,
                    'milestones_reached': milestones,
                    'recent_activity': formatted_recent_activity
                },
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error getting streak history: {error_message}")
            return Response({
                'message': 'Failed to retrieve streak history',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReadingLogView(APIView):
    """
    Create a reading log entry.
    
    API Path: POST /api/reading-logs
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=ReadingLogCreateSerializer,
        responses={
            201: inline_serializer(
                name='ReadingLogResponse',
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
            404: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Log a reading of a shloka",
        summary="Create reading log",
        tags=["Reading Logs"],
    )
    def post(self, request):
        """
        Create a reading log entry.
        
        API Path: POST /api/reading-logs
        """
        try:
            serializer = ReadingLogCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'message': 'Validation error',
                    'data': None,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            shloka_id = serializer.validated_data['shloka_id']
            reading_type = serializer.validated_data['reading_type']
            
            # Verify shloka exists
            try:
                shloka = Shloka.objects.get(id=shloka_id)
            except Shloka.DoesNotExist:
                return Response({
                    'message': 'Shloka not found',
                    'data': None,
                    'errors': {'detail': f'Shloka with ID {shloka_id} not found'}
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create reading log entry
            reading_log = ReadingLog.objects.create(
                user=request.user,
                shloka=shloka,
                reading_type=reading_type
            )
            
            # Serialize the response
            log_serializer = ReadingLogSerializer(reading_log)
            
            return Response({
                'message': 'Reading log created successfully',
                'data': log_serializer.data,
                'errors': None
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error creating reading log: {error_message}")
            return Response({
                'message': 'Failed to create reading log',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FavoriteView(APIView):
    """
    Manage user's favorite shlokas.
    
    API Path: GET /api/favorites - List all favorites
    API Path: POST /api/favorites - Add a favorite (requires shloka_id in body)
    API Path: DELETE /api/favorites?shloka_id=<uuid> - Remove a favorite
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='FavoriteListResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Get all favorite shlokas for the authenticated user",
        summary="List favorites",
        tags=["Favorites"],
    )
    def get(self, request):
        """List all favorite shlokas for the authenticated user."""
        try:
            favorites = Favorite.objects.filter(user=request.user).order_by('-created_at')
            serializer = FavoriteSerializer(favorites, many=True)
            return Response({
                'message': 'Favorites retrieved successfully',
                'data': serializer.data,
                'errors': None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error getting favorites: {str(e)}")
            return Response({
                'message': 'Failed to retrieve favorites',
                'data': None,
                'errors': {'detail': str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        request=inline_serializer(
            name='FavoriteCreateRequest',
            fields={
                'shloka_id': OpenApiTypes.UUID,
            }
        ),
        responses={
            201: inline_serializer(
                name='FavoriteCreateResponse',
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
            404: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Add a shloka to favorites",
        summary="Add favorite",
        tags=["Favorites"],
    )
    def post(self, request):
        """Add a shloka to favorites."""
        try:
            shloka_id = request.data.get('shloka_id')
            if not shloka_id:
                return Response({
                    'message': 'shloka_id is required',
                    'data': None,
                    'errors': {'detail': 'shloka_id is required'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                shloka = Shloka.objects.get(id=shloka_id)
            except Shloka.DoesNotExist:
                return Response({
                    'message': 'Shloka not found',
                    'data': None,
                    'errors': {'detail': f'Shloka with ID {shloka_id} not found'}
                }, status=status.HTTP_404_NOT_FOUND)
            
            favorite, created = Favorite.objects.get_or_create(user=request.user, shloka=shloka)
            serializer = FavoriteSerializer(favorite)
            
            return Response({
                'message': 'Favorite added successfully' if created else 'Shloka already in favorites',
                'data': serializer.data,
                'errors': None
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error adding favorite: {str(e)}")
            return Response({
                'message': 'Failed to add favorite',
                'data': None,
                'errors': {'detail': str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='shloka_id',
                description='UUID of the shloka to remove from favorites',
                required=True,
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY
            ),
        ],
        responses={
            200: inline_serializer(
                name='FavoriteDeleteResponse',
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
            404: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Remove a shloka from favorites using query parameter",
        summary="Remove favorite",
        tags=["Favorites"],
    )
    def delete(self, request):
        """Remove a shloka from favorites using query parameter."""
        try:
            shloka_id = request.query_params.get('shloka_id')
            if not shloka_id:
                return Response({
                    'message': 'shloka_id query parameter is required',
                    'data': None,
                    'errors': {'detail': 'shloka_id query parameter is required'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                # Validate UUID format
                uuid.UUID(shloka_id)
            except (ValueError, TypeError):
                return Response({
                    'message': 'Invalid shloka_id format',
                    'data': None,
                    'errors': {'detail': 'shloka_id must be a valid UUID'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            favorite = Favorite.objects.filter(user=request.user, shloka_id=shloka_id).first()
            if not favorite:
                return Response({
                    'message': 'Favorite not found',
                    'data': None,
                    'errors': {'detail': 'Shloka is not in favorites'}
                }, status=status.HTTP_404_NOT_FOUND)
            
            favorite.delete()
            return Response({
                'message': 'Favorite removed successfully',
                'data': None,
                'errors': None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error removing favorite: {str(e)}")
            return Response({
                'message': 'Failed to remove favorite',
                'data': None,
                'errors': {'detail': str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MarkShlokaReadView(APIView):
    """Mark a shloka as read or unmark it."""
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=inline_serializer(
            name='MarkShlokaReadRequest',
            fields={
                'shloka_id': OpenApiTypes.UUID,
                'marked': OpenApiTypes.BOOL,
            }
        ),
        responses={
            200: inline_serializer(
                name='MarkShlokaReadResponse',
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
            404: inline_serializer(
                name='ErrorResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Mark a shloka as read or unmark it",
        summary="Mark shloka as read",
        tags=["Shlokas"],
    )
    def post(self, request):
        """Mark or unmark a shloka as read."""
        try:
            shloka_id = request.data.get('shloka_id')
            marked = request.data.get('marked', True)  # Default to True (mark as read)
            
            if not shloka_id:
                return Response({
                        'message': 'shloka_id is required',
                        'data': None,
                        'errors': {'detail': 'shloka_id is required'}
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            shloka_service = ShlokaService()
            
            if marked:
                # Mark as read
                read_status = shloka_service.mark_shloka_as_read(request.user, shloka_id)
                
                # Update streak after marking as read
                from .services.stats_service import StatsService
                StatsService.calculate_streak(request.user, update_streak_data=True)
                
                return Response({
                    'message': 'Shloka marked as read successfully',
                    'data': {
                        'shloka_id': str(shloka_id),
                        'marked': True,
                        'marked_at': read_status.marked_read_at.isoformat()
                    },
                'errors': None
            }, status=status.HTTP_200_OK)
            else:
                # Unmark as read
                removed = shloka_service.unmark_shloka_as_read(request.user, shloka_id)
                if removed:
                    # Update streak after unmarking as read
                    from .services.stats_service import StatsService
                    StatsService.calculate_streak(request.user, update_streak_data=True)
                    
                    return Response({
                        'message': 'Shloka unmarked successfully',
                        'data': {
                            'shloka_id': str(shloka_id),
                            'marked': False
                        },
                        'errors': None
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'message': 'Shloka was not marked as read',
                        'data': None,
                        'errors': {'detail': 'Shloka was not in read list'}
                    }, status=status.HTTP_404_NOT_FOUND)
                    
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error marking shloka as read: {error_message}")
            
            if "not found" in error_message.lower():
                return Response({
                        'message': 'Shloka not found',
                    'data': None,
                        'errors': {'detail': error_message}
                    }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'message': 'Failed to mark shloka as read',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AchievementsView(APIView):
    """
    Get user's achievements.
    
    API Path: GET /api/achievements
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='AchievementsResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Get all achievements unlocked by the user",
        summary="Get user achievements",
        tags=["User"],
    )
    def get(self, request):
        """
        Get user's achievements.
        
        API Path: GET /api/achievements
        """
        try:
            user_achievements = UserAchievement.objects.filter(
                user=request.user
            ).select_related('achievement').order_by('-unlocked_at')
            
            serializer = UserAchievementSerializer(user_achievements, many=True)
            
            return Response({
                'message': 'Achievements retrieved successfully',
                'data': serializer.data,
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error getting achievements: {error_message}")
            return Response({
                'message': 'Failed to retrieve achievements',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatConversationListView(APIView):
    """List user's chat conversations."""
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            conversations = ChatConversation.objects.filter(user=request.user).order_by('-updated_at')
            serializer = ChatConversationSerializer(conversations, many=True)
            return Response({
                'message': 'Conversations retrieved successfully',
                'data': serializer.data,
                'errors': None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error getting conversations: {str(e)}")
            return Response({
                'message': 'Failed to retrieve conversations',
                'data': None,
                'errors': {'detail': str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatMessageView(APIView):
    """Send a message and get AI response."""
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            serializer = ChatMessageCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'message': 'Validation error',
                    'data': None,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_message = serializer.validated_data['message']
            conversation_id = serializer.validated_data.get('conversation_id')
            
            chatbot_service = ChatbotService()
            
            # Get or create conversation
            if conversation_id:
                try:
                    conversation = ChatConversation.objects.get(id=conversation_id, user=request.user)
                except ChatConversation.DoesNotExist:
                    return Response({
                        'message': 'Conversation not found',
                        'data': None,
                        'errors': {'detail': 'Conversation not found'}
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # Create new conversation
                conversation = chatbot_service.create_conversation(request.user)
            
            # Add user message
            chatbot_service.add_message(conversation, 'user', user_message)
            
            # Get conversation history
            history = chatbot_service.get_conversation_messages(conversation)
            
            # Generate AI response
            ai_response = chatbot_service.generate_response(
                user_message,
                history[:-1],  # Exclude the current message
                request.user
            )
            
            # Add AI response
            chatbot_service.add_message(conversation, 'assistant', ai_response)
            
            # Get updated conversation
            conversation_serializer = ChatConversationSerializer(conversation)
            
            return Response({
                'message': 'Message sent successfully',
                'data': {
                    'conversation': conversation_serializer.data,
                    'response': ai_response
                },
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in chat message: {str(e)}")
            return Response({
                'message': 'Failed to process message',
                'data': None,
                'errors': {'detail': str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserProfileView(APIView):
    """
    Update user profile.
    
    API Path: PATCH /api/user/profile
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=ProfileUpdateSerializer,
        responses={
            200: inline_serializer(
                name='ProfileUpdateResponse',
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
        description="Update user profile information (name and/or email)",
        summary="Update profile",
        tags=["User"],
    )
    def patch(self, request):
        """
        Update user profile.
        
        API Path: PATCH /api/user/profile
        """
        try:
            serializer = ProfileUpdateSerializer(data=request.data, context={'user': request.user})
            
            if not serializer.is_valid():
                return Response({
                    'message': 'Validation error',
                    'data': None,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = request.user
            validated_data = serializer.validated_data
            
            # Update name if provided
            if 'name' in validated_data:
                user.name = validated_data['name']
            
            # Update email if provided
            if 'email' in validated_data:
                user.email = validated_data['email']
            
            user.save()
            
            # Serialize updated user
            user_serializer = UserSerializer(user)
            
            return Response({
                'message': 'Profile updated successfully',
                'data': user_serializer.data,
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error updating profile: {error_message}")
            return Response({
                'message': 'Failed to update profile',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChangePasswordView(APIView):
    """
    Change user password.
    
    API Path: POST /api/user/change-password
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=ChangePasswordSerializer,
        responses={
            200: inline_serializer(
                name='ChangePasswordResponse',
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
        description="Change user password",
        summary="Change password",
        tags=["User"],
    )
    def post(self, request):
        """
        Change user password.
        
        API Path: POST /api/user/change-password
        """
        try:
            serializer = ChangePasswordSerializer(data=request.data)
            
            if not serializer.is_valid():
                return Response({
                    'message': 'Validation error',
                    'data': None,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = request.user
            current_password = serializer.validated_data['current_password']
            new_password = serializer.validated_data['new_password']
            
            # Verify current password
            if not user.check_password(current_password):
                return Response({
                    'message': 'Invalid current password',
                    'data': None,
                    'errors': {'current_password': 'Current password is incorrect'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if new password is same as current
            if user.check_password(new_password):
                return Response({
                    'message': 'New password must be different from current password',
                    'data': None,
                    'errors': {'new_password': 'New password must be different from current password'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Set new password
            user.set_password(new_password)
            user.save()
            
            return Response({
                'message': 'Password changed successfully',
                'data': None,
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error changing password: {error_message}")
            return Response({
                'message': 'Failed to change password',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeleteAccountView(APIView):
    """
    Delete user account.
    
    API Path: DELETE /api/user/delete-account
    """
    authentication_classes = [UUIDJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={
            200: inline_serializer(
                name='DeleteAccountResponse',
                fields={
                    'message': OpenApiTypes.STR,
                    'data': OpenApiTypes.OBJECT,
                    'errors': OpenApiTypes.OBJECT,
                }
            ),
        },
        description="Permanently delete user account and all associated data",
        summary="Delete account",
        tags=["User"],
    )
    def delete(self, request):
        """
        Delete user account.
        
        API Path: DELETE /api/user/delete-account
        """
        try:
            user = request.user
            user_email = user.email  # Store email for logging before deletion
            
            # Delete all associated data
            # Note: This will cascade delete related records if foreign keys are set up with CASCADE
            # If not, we may need to manually delete related records
            
            # Delete user (this should cascade to related records)
            user.delete()
            
            logger.info(f"User account deleted: {user_email}")
            
            return Response({
                'message': 'Account deleted successfully',
                'data': None,
                'errors': None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error deleting account: {error_message}")
            return Response({
                'message': 'Failed to delete account',
                'data': None,
                'errors': {'detail': error_message}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
