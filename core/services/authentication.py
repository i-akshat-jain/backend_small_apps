"""
Custom JWT Authentication for UUID-based User models.

This module provides a custom authentication class that properly handles
UUID primary keys in JWT tokens, which the default SimpleJWT authentication
does not support out of the box.
"""
import uuid
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from rest_framework_simplejwt.settings import api_settings
from django.utils.translation import gettext_lazy as _
from apps.sanatan_app.models import User


class UUIDJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that properly handles UUID primary keys.
    
    The default JWTAuthentication expects integer primary keys, but this
    class converts UUID strings from JWT tokens to UUID objects before
    querying the database.
    """
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the authentication class with the custom User model.
        """
        super().__init__(*args, **kwargs)
        # Override user_model to use our custom User model
        self.user_model = User
    
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        
        Args:
            validated_token: A validated token containing user identification.
            
        Returns:
            The user associated with the token.
            
        Raises:
            AuthenticationFailed: If the user cannot be found or the token is invalid.
        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken(_('Token contained no recognizable user identification'))

        try:
            # Convert string UUID to UUID object if needed
            if isinstance(user_id, str):
                try:
                    user_id = uuid.UUID(user_id)
                except (ValueError, AttributeError):
                    raise InvalidToken(_('Token contained invalid user identification'))
            
            # Get the user model
            user = self.user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed(_('User not found'), code='user_not_found')
        except (TypeError, ValueError, AttributeError) as e:
            raise AuthenticationFailed(
                _('Invalid token. User identification is invalid.'),
                code='user_not_found'
            )

        # Check if user has is_active attribute (optional, for compatibility)
        if hasattr(user, 'is_active') and not user.is_active:
            raise AuthenticationFailed(_('User is inactive'), code='user_inactive')

        return user

