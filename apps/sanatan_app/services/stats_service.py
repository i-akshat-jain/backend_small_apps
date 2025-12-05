"""
Statistics service for calculating user stats from reading logs.
"""
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Count, Q
from django.db import transaction
from ..models import ReadingLog, User, ShlokaReadStatus, UserStreak


class StatsService:
    """Service for calculating user statistics."""
    
    # XP calculation constants
    XP_PER_SHLOKA = 10
    XP_PER_STREAK_DAY = 5  # Base XP per streak day
    BASE_LEVEL_XP = 100
    LEVEL_XP_MULTIPLIER = 1.5
    
    # Streak milestone multipliers (additional XP per day after milestone)
    STREAK_MULTIPLIER_7_DAYS = 1  # +1 XP/day after 7 days (6 total)
    STREAK_MULTIPLIER_30_DAYS = 2  # +2 XP/day after 30 days (7 total)
    STREAK_MULTIPLIER_100_DAYS = 3  # +3 XP/day after 100 days (8 total)
    
    # Streak milestone bonuses (one-time XP rewards)
    STREAK_BONUS_7_DAYS = 50
    STREAK_BONUS_30_DAYS = 200
    STREAK_BONUS_100_DAYS = 500
    STREAK_BONUS_365_DAYS = 2000
    
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
    def get_or_create_user_streak(user: User) -> UserStreak:
        """Get or create UserStreak instance for a user."""
        streak_data, created = UserStreak.objects.get_or_create(user=user)
        if created:
            # Initialize with current streak if user has reading history
            streak_data.current_streak = StatsService._calculate_streak_from_reading_history(user)
            streak_data.longest_streak = streak_data.current_streak
            streak_data.total_streak_days = streak_data.current_streak
            if streak_data.current_streak > 0:
                streak_data.last_streak_date = timezone.now().date()
            streak_data.save()
        return streak_data
    
    @staticmethod
    def _calculate_streak_from_reading_history(user: User) -> int:
        """Calculate streak from reading history (used for initialization)."""
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
    def _get_streak_multiplier(streak_days: int) -> int:
        """Get XP multiplier based on streak milestone."""
        if streak_days >= 100:
            return StatsService.STREAK_MULTIPLIER_100_DAYS
        elif streak_days >= 30:
            return StatsService.STREAK_MULTIPLIER_30_DAYS
        elif streak_days >= 7:
            return StatsService.STREAK_MULTIPLIER_7_DAYS
        return 0
    
    @staticmethod
    def calculate_experience(user: User) -> int:
        """Calculate total experience points for a user."""
        # Base XP from marking shlokas as read
        # Records only exist when marked as read (deleted when unmarked)
        unique_shlokas = ShlokaReadStatus.objects.filter(user=user).values('shloka').distinct().count()
        reading_xp = unique_shlokas * StatsService.XP_PER_SHLOKA
        
        # Bonus XP from streak (with multipliers)
        streak_data = StatsService.get_or_create_user_streak(user)
        streak = streak_data.current_streak
        base_streak_xp = streak * StatsService.XP_PER_STREAK_DAY
        
        # Add multiplier bonus
        multiplier = StatsService._get_streak_multiplier(streak)
        multiplier_xp = streak * multiplier
        
        streak_xp = base_streak_xp + multiplier_xp
        
        # Add milestone bonuses (one-time XP rewards)
        milestone_xp = StatsService._calculate_milestone_bonuses(streak_data)
        
        return reading_xp + streak_xp + milestone_xp
    
    @staticmethod
    def _calculate_milestone_bonuses(streak_data: UserStreak) -> int:
        """Calculate total XP from awarded milestone bonuses."""
        milestone_map = {
            7: StatsService.STREAK_BONUS_7_DAYS,
            30: StatsService.STREAK_BONUS_30_DAYS,
            100: StatsService.STREAK_BONUS_100_DAYS,
            365: StatsService.STREAK_BONUS_365_DAYS,
        }
        
        awarded = streak_data.awarded_milestones or []
        total_bonus = 0
        
        for milestone_days in awarded:
            if milestone_days in milestone_map:
                total_bonus += milestone_map[milestone_days]
        
        return total_bonus
    
    @staticmethod
    def _reset_streak_freeze_if_needed(streak_data: UserStreak):
        """Reset streak freeze if we're in a new month."""
        today = timezone.now().date()
        if streak_data.streak_freeze_reset_date:
            if today >= streak_data.streak_freeze_reset_date:
                streak_data.streak_freeze_used_this_month = False
                # Set reset date to first day of next month
                if today.month == 12:
                    streak_data.streak_freeze_reset_date = date(today.year + 1, 1, 1)
                else:
                    streak_data.streak_freeze_reset_date = date(today.year, today.month + 1, 1)
                streak_data.save(update_fields=['streak_freeze_used_this_month', 'streak_freeze_reset_date'])
        else:
            # Initialize reset date to first day of next month
            if today.month == 12:
                streak_data.streak_freeze_reset_date = date(today.year + 1, 1, 1)
            else:
                streak_data.streak_freeze_reset_date = date(today.year, today.month + 1, 1)
            streak_data.save(update_fields=['streak_freeze_reset_date'])
    
    @staticmethod
    def calculate_streak(user: User, update_streak_data: bool = True) -> int:
        """
        Calculate current reading streak in days based on marked-as-read shlokas.
        Updates UserStreak model if update_streak_data is True.
        """
        streak_data = StatsService.get_or_create_user_streak(user)
        
        # Reset freeze if needed (new month)
        StatsService._reset_streak_freeze_if_needed(streak_data)
        
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
                # Check if streak freeze can be used
                if streak_data.streak_freeze_used_this_month:
                    # Streak is broken
                    if update_streak_data:
                        with transaction.atomic():
                            streak_data.current_streak = 0
                            streak_data.save(update_fields=['current_streak', 'updated_at'])
                    return 0
                else:
                    # Streak can be frozen (but don't auto-freeze, user must explicitly use it)
                    # For now, return 0 but don't break the streak in DB yet
                    # The streak will be maintained if user uses freeze before next reading
                    if update_streak_data and streak_data.current_streak > 0:
                        # Only break if it's been more than 1 day since last streak
                        if streak_data.last_streak_date:
                            days_since_last = (today - streak_data.last_streak_date).days
                            if days_since_last > 1:
                                with transaction.atomic():
                                    streak_data.current_streak = 0
                                    streak_data.save(update_fields=['current_streak', 'updated_at'])
                                return 0
                    # Return current streak if freeze is available
                    return streak_data.current_streak
        
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
        
        # Update streak data if needed
        if update_streak_data:
            with transaction.atomic():
                streak_data.current_streak = streak
                streak_data.last_streak_date = today
                
                # Update longest streak if current is higher
                if streak > streak_data.longest_streak:
                    streak_data.longest_streak = streak
                
                # Update total streak days (only count if this is a new day)
                if streak_data.last_streak_date != today or streak_data.total_streak_days == 0:
                    streak_data.total_streak_days += 1
                
                streak_data.save(update_fields=[
                    'current_streak', 'longest_streak', 'last_streak_date', 
                    'total_streak_days', 'updated_at'
                ])
        
        return streak
    
    @staticmethod
    def use_streak_freeze(user: User) -> dict:
        """
        Use streak freeze to prevent streak from breaking.
        Returns dict with success status and message.
        """
        streak_data = StatsService.get_or_create_user_streak(user)
        
        # Reset freeze if needed (new month)
        StatsService._reset_streak_freeze_if_needed(streak_data)
        
        if streak_data.streak_freeze_used_this_month:
            return {
                'success': False,
                'message': 'Streak freeze already used this month',
                'freeze_available': False
            }
        
        # Check if streak is actually at risk (no reading today or yesterday)
        today = timezone.now().date()
        has_read_today = ShlokaReadStatus.objects.filter(
            user=user,
            marked_read_at__date=today
        ).exists()
        
        yesterday = today - timedelta(days=1)
        has_read_yesterday = ShlokaReadStatus.objects.filter(
            user=user,
            marked_read_at__date=yesterday
        ).exists()
        
        if has_read_today:
            return {
                'success': False,
                'message': 'No need to use freeze - you have already read today',
                'freeze_available': True
            }
        
        # Use the freeze
        with transaction.atomic():
            streak_data.streak_freeze_used_this_month = True
            # Maintain current streak (don't break it)
            if streak_data.current_streak > 0:
                streak_data.last_streak_date = yesterday if has_read_yesterday else today
            streak_data.save(update_fields=['streak_freeze_used_this_month', 'last_streak_date', 'updated_at'])
        
        return {
            'success': True,
            'message': 'Streak freeze activated! Your streak is protected.',
            'freeze_available': False,
            'current_streak': streak_data.current_streak
        }
    
    @staticmethod
    def check_streak_milestones(user: User) -> list:
        """
        Check if user has reached any streak milestones, award bonuses, and return list of milestones reached.
        This should be called after streak is updated.
        Awards milestone bonuses only once per milestone.
        """
        streak_data = StatsService.get_or_create_user_streak(user)
        milestones_reached = []
        
        # Ensure awarded_milestones is a list
        if streak_data.awarded_milestones is None:
            streak_data.awarded_milestones = []
        
        awarded = streak_data.awarded_milestones.copy() if isinstance(streak_data.awarded_milestones, list) else []
        
        # Check milestone thresholds
        milestones = [
            (7, StatsService.STREAK_BONUS_7_DAYS, 'Week Warrior'),
            (30, StatsService.STREAK_BONUS_30_DAYS, 'Monthly Devotee'),
            (100, StatsService.STREAK_BONUS_100_DAYS, 'Centurion'),
            (365, StatsService.STREAK_BONUS_365_DAYS, 'Year of Wisdom'),
        ]
        
        newly_awarded = False
        for days, bonus_xp, name in milestones:
            # Check if milestone is reached and not yet awarded
            if streak_data.current_streak >= days and days not in awarded:
                milestones_reached.append({
                    'days': days,
                    'bonus_xp': bonus_xp,
                    'name': name,
                    'message': f'Congratulations! {days}-day streak milestone reached!'
                })
                awarded.append(days)
                newly_awarded = True
        
        # Update awarded milestones if any new ones were reached
        if newly_awarded:
            with transaction.atomic():
                streak_data.awarded_milestones = awarded
                streak_data.save(update_fields=['awarded_milestones', 'updated_at'])
        
        return milestones_reached
    
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
        
        # Current streak (based on marked-as-read) - update streak data
        current_streak = StatsService.calculate_streak(user, update_streak_data=True)
        
        # Get streak data for additional info
        streak_data = StatsService.get_or_create_user_streak(user)
        
        # Check for milestone achievements (this will award bonuses if milestones are reached)
        StatsService.check_streak_milestones(user)
        
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
            'longest_streak': streak_data.longest_streak,
            'total_streak_days': streak_data.total_streak_days,
            'streak_freeze_available': not streak_data.streak_freeze_used_this_month,
            'level': level,
            'experience': experience,
            'xp_in_current_level': xp_in_current_level,
            'xp_for_next_level': xp_for_next_level,
            'readings_this_week': readings_this_week,
            'readings_this_month': readings_this_month,
        }

