"""URL configuration for Sanatan App."""
from django.urls import path
from .views import (
    RandomShlokaView, 
    ShlokaDetailView, 
    HealthCheckView, 
    RootView,
    SignupView,
    LoginView,
    TokenRefreshView,
    ReadingLogView,
    UserStatsView,
    UserStreakView,
    UserStreakFreezeView,
    UserStreakHistoryView,
    FavoriteView,
    MarkShlokaReadView,
    ChatConversationListView,
    ChatMessageView,
    UserProfileView,
    ChangePasswordView,
    DeleteAccountView,
    AchievementsView
)

urlpatterns = [
    path('', RootView.as_view(), name='root'),
    path('health', HealthCheckView.as_view(), name='health'),
    path('api/shlokas/random', RandomShlokaView.as_view(), name='shloka-random'),
    path('api/shlokas/mark-read', MarkShlokaReadView.as_view(), name='shloka-mark-read'),
    path('api/shlokas/<uuid:shloka_id>', ShlokaDetailView.as_view(), name='shloka-detail'),
    # Authentication endpoints
    path('api/auth/signup', SignupView.as_view(), name='signup'),
    path('api/auth/login', LoginView.as_view(), name='login'),
    path('api/auth/refresh', TokenRefreshView.as_view(), name='token-refresh'),
    # Reading log endpoints
    path('api/reading-logs', ReadingLogView.as_view(), name='reading-log-create'),
    # User endpoints
    path('api/user/stats', UserStatsView.as_view(), name='user-stats'),
    path('api/user/streak', UserStreakView.as_view(), name='user-streak'),
    path('api/user/streak/freeze', UserStreakFreezeView.as_view(), name='user-streak-freeze'),
    path('api/user/streak/history', UserStreakHistoryView.as_view(), name='user-streak-history'),
    path('api/user/profile', UserProfileView.as_view(), name='user-profile'),
    path('api/user/change-password', ChangePasswordView.as_view(), name='user-change-password'),
    path('api/user/delete-account', DeleteAccountView.as_view(), name='user-delete-account'),
    path('api/achievements', AchievementsView.as_view(), name='achievements'),
    # Favorites endpoints - GET to list, POST to add, DELETE with query param to remove
    path('api/favorites', FavoriteView.as_view(), name='favorites'),
    # Chatbot endpoints
    path('api/chat/conversations', ChatConversationListView.as_view(), name='chat-conversations'),
    path('api/chat/message', ChatMessageView.as_view(), name='chat-message'),
]

