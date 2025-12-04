"""
Achievement service for checking and unlocking user achievements.
"""
from django.db import transaction
from ..models import User, Achievement, UserAchievement, ReadingLog
from .stats_service import StatsService
import logging

logger = logging.getLogger(__name__)


class AchievementService:
    """Service for managing user achievements."""
    
    @staticmethod
    def check_and_unlock_achievements(user: User) -> list:
        """
        Check all achievement conditions and unlock any that the user qualifies for.
        Returns list of newly unlocked achievement IDs.
        """
        newly_unlocked = []
        
        try:
            # Get user stats
            stats = StatsService.get_user_stats(user)
            
            # Get all achievements
            all_achievements = Achievement.objects.all()
            
            # Get already unlocked achievements
            unlocked_achievement_ids = set(
                UserAchievement.objects.filter(user=user)
                .values_list('achievement_id', flat=True)
            )
            
            # Check each achievement
            for achievement in all_achievements:
                # Skip if already unlocked
                if achievement.id in unlocked_achievement_ids:
                    continue
                
                # Check if condition is met
                if AchievementService._check_achievement_condition(achievement, stats, user):
                    # Unlock the achievement
                    with transaction.atomic():
                        UserAchievement.objects.get_or_create(
                            user=user,
                            achievement=achievement
                        )
                    newly_unlocked.append(achievement.id)
                    logger.info(f"Unlocked achievement {achievement.code} for user {user.email}")
            
            return newly_unlocked
            
        except Exception as e:
            logger.error(f"Error checking achievements for user {user.email}: {str(e)}")
            return []
    
    @staticmethod
    def _check_achievement_condition(achievement: Achievement, stats: dict, user: User) -> bool:
        """Check if a specific achievement condition is met."""
        condition_type = achievement.condition_type
        condition_value = achievement.condition_value
        
        if condition_type == 'shlokas_read':
            return stats['total_shlokas_read'] >= condition_value
        
        elif condition_type == 'streak':
            return stats['current_streak'] >= condition_value
        
        elif condition_type == 'level':
            return stats['level'] >= condition_value
        
        elif condition_type == 'readings_total':
            return stats['total_readings'] >= condition_value
        
        elif condition_type == 'readings_week':
            return stats['readings_this_week'] >= condition_value
        
        elif condition_type == 'readings_month':
            return stats['readings_this_month'] >= condition_value
        
        else:
            logger.warning(f"Unknown achievement condition type: {condition_type}")
            return False
    
    @staticmethod
    def check_achievements_after_reading(user: User):
        """
        Convenience method to check achievements after a reading is logged.
        This should be called after creating a ReadingLog entry.
        """
        return AchievementService.check_and_unlock_achievements(user)

