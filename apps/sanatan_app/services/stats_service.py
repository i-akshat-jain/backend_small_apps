"""
Statistics service for calculating user stats from reading logs.
"""
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Count, Q
from ..models import ReadingLog, User, ShlokaReadStatus


class StatsService:
    """Service for calculating user statistics."""
    
    # XP calculation constants
    XP_PER_SHLOKA = 10
    XP_PER_STREAK_DAY = 5
    BASE_LEVEL_XP = 100
    LEVEL_XP_MULTIPLIER = 1.5
    
    @staticmethod
    def calculate_level(experience: int) -> int:
        """Calculate user level from experience points."""
        if experience < StatsService.BASE_LEVEL_XP:
            return 1
        
        level = 1
        xp_required = StatsService.BASE_LEVEL_XP
        
        while experience >= xp_required:
            experience -= xp_required
            level += 1
            xp_required = int(StatsService.BASE_LEVEL_XP * (StatsService.LEVEL_XP_MULTIPLIER ** (level - 1)))
        
        return level
    
    @staticmethod
    def calculate_xp_for_next_level(level: int) -> int:
        """Calculate XP required for next level."""
        return int(StatsService.BASE_LEVEL_XP * (StatsService.LEVEL_XP_MULTIPLIER ** (level - 1)))
    
    @staticmethod
    def calculate_experience(user: User) -> int:
        """Calculate total experience points for a user."""
        # Base XP from marking shlokas as read
        # Records only exist when marked as read (deleted when unmarked)
        unique_shlokas = ShlokaReadStatus.objects.filter(user=user).values('shloka').distinct().count()
        reading_xp = unique_shlokas * StatsService.XP_PER_SHLOKA
        
        # Bonus XP from streak
        streak = StatsService.calculate_streak(user)
        streak_xp = streak * StatsService.XP_PER_STREAK_DAY
        
        return reading_xp + streak_xp
    
    @staticmethod
    def calculate_streak(user: User) -> int:
        """Calculate current reading streak in days based on marked-as-read shlokas."""
        today = timezone.now().date()
        streak = 0
        current_date = today
        
        # Check if user marked a shloka as read today
        has_read_today = ShlokaReadStatus.objects.filter(
            user=user,
            marked_read_at__date=current_date
        ).exists()
        
        if not has_read_today:
            # If no reading today, check yesterday
            current_date = today - timedelta(days=1)
            has_read = ShlokaReadStatus.objects.filter(
                user=user,
                marked_read_at__date=current_date
            ).exists()
            if not has_read:
                return 0  # Streak broken
        
        # Count consecutive days with marked-as-read shlokas
        while True:
            has_read = ShlokaReadStatus.objects.filter(
                user=user,
                marked_read_at__date=current_date
            ).exists()
            
            if has_read:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    @staticmethod
    def calculate_total_books_read(user: User) -> int:
        """Calculate total unique books read by the user."""
        # Get distinct book names from shlokas that user has marked as read
        # Records only exist when marked as read (deleted when unmarked)
        books_read = ShlokaReadStatus.objects.filter(user=user).values('shloka__book_name').distinct().count()
        
        return books_read
    
    @staticmethod
    def get_user_stats(user: User) -> dict:
        """Get comprehensive user statistics."""
        # Total unique shlokas marked as read
        # Records only exist when marked as read (deleted when unmarked)
        total_shlokas_read = ShlokaReadStatus.objects.filter(user=user).values('shloka').distinct().count()
        
        # Total unique books read
        total_books_read = StatsService.calculate_total_books_read(user)
        
        # Current streak (based on marked-as-read)
        current_streak = StatsService.calculate_streak(user)
        
        # Experience and level
        experience = StatsService.calculate_experience(user)
        level = StatsService.calculate_level(experience)
        xp_for_next_level = StatsService.calculate_xp_for_next_level(level)
        xp_in_current_level = experience - sum([
            int(StatsService.BASE_LEVEL_XP * (StatsService.LEVEL_XP_MULTIPLIER ** (l - 1)))
            for l in range(1, level)
        ])
        
        # Total readings (including duplicates) - kept for backward compatibility
        total_readings = ReadingLog.objects.filter(user=user).count()
        
        # Readings this week
        week_ago = timezone.now() - timedelta(days=7)
        readings_this_week = ReadingLog.objects.filter(
            user=user,
            read_at__gte=week_ago
        ).count()
        
        # Readings this month
        month_ago = timezone.now() - timedelta(days=30)
        readings_this_month = ReadingLog.objects.filter(
            user=user,
            read_at__gte=month_ago
        ).count()
        
        return {
            'total_shlokas_read': total_shlokas_read,
            'total_books_read': total_books_read,
            'total_readings': total_readings,
            'current_streak': current_streak,
            'level': level,
            'experience': experience,
            'xp_in_current_level': xp_in_current_level,
            'xp_for_next_level': xp_for_next_level,
            'readings_this_week': readings_this_week,
            'readings_this_month': readings_this_month,
        }

