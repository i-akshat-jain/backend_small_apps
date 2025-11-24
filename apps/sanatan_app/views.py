"""Views for Sanatan App API."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from .models import Shloka, ShlokaExplanation
from .serializers import ShlokaSerializer, ExplanationSerializer
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
