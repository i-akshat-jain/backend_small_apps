"""URL configuration for Sanatan App."""
from django.urls import path
from .views import (
    RandomShlokaView, 
    ShlokaDetailView, 
    HealthCheckView, 
    RootView,
    SignupView,
    LoginView,
    TokenRefreshView
)

urlpatterns = [
    path('', RootView.as_view(), name='root'),
    path('health', HealthCheckView.as_view(), name='health'),
    path('api/shlokas/random', RandomShlokaView.as_view(), name='shloka-random'),
    path('api/shlokas/<uuid:shloka_id>', ShlokaDetailView.as_view(), name='shloka-detail'),
    # Authentication endpoints
    path('api/auth/signup', SignupView.as_view(), name='signup'),
    path('api/auth/login', LoginView.as_view(), name='login'),
    path('api/auth/refresh', TokenRefreshView.as_view(), name='token-refresh'),
]

