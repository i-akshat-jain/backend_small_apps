# Streaks, Achievements & User Journey Design

## 📊 Implementation Status

**Last Updated:** 2025-01-27

- ✅ **Phase 1: Enhanced Streak System** - **COMPLETED** (Backend: 55/55 tests passing, Frontend: Core features implemented)
- ⏳ **Phase 2: Achievement Categories & Rarity** - PENDING
- ⏳ **Phase 3: User Journey - Onboarding** - PENDING
- ⏳ **Phase 4: User Journey - Habit Formation** - PENDING
- ⏳ **Phase 5: Re-engagement & Analytics** - PENDING

### Phase 1 Completion Summary ✅

**Backend - What Was Built:**
- ✅ UserStreak model with all required fields
- ✅ Enhanced streak calculation with UserStreak integration
- ✅ Streak freeze system (1 per month)
- ✅ Milestone bonus system (7, 30, 100, 365 days)
- ✅ Streak multipliers (increased XP at milestones)
- ✅ Three API endpoints for streak management
- ✅ Comprehensive test suite (55 tests, all passing)

**Frontend - What Was Built:**
- ✅ Updated API service to fetch new streak fields (`getUserStats()` includes `longest_streak`, `total_streak_days`, `streak_freeze_available`)
- ✅ Added API methods for streak endpoints (`getUserStreak()`, `useStreakFreeze()`, `getStreakHistory()`)
- ✅ Updated HomeScreen to display longest streak, total streak days
- ✅ Added streak freeze UI/button with confirmation dialog
- ⏳ Display streak milestones and achievements (API ready, UI pending)
- ⏳ Optional: Streak history screen (API ready, screen pending)

**Key Features:**
- Automatic streak tracking and longest streak recording
- Monthly streak freeze (prevents accidental breaks)
- Milestone XP bonuses (one-time rewards)
- Streak multipliers (ongoing XP bonuses)
- Full API integration with authentication
- Backward compatible with existing stats system

## 📊 Current State Analysis

### Existing Streak System ✅ **ENHANCED**
- **Daily streak** based on marking shlokas as read
- Calculated from `ShlokaReadStatus` (consecutive days)
- ✅ **Streak freeze system implemented** - 1 freeze per month
- ✅ Streak contributes to XP (5 XP base, multipliers at 7/30/100 days)
- ✅ Enhanced implementation: `StatsService.calculate_streak()` with UserStreak model
- ✅ Milestone bonuses: 7 days (+50 XP), 30 days (+200 XP), 100 days (+500 XP), 365 days (+2000 XP)

### Existing Achievement System
- Multiple condition types: `shlokas_read`, `streak`, `level`, `readings_total`, `readings_week`, `readings_month`
- Auto-unlock when conditions are met
- XP rewards per achievement
- Basic structure in place: `Achievement` and `UserAchievement` models
- Service: `AchievementService.check_and_unlock_achievements()`

---

## 🎯 Streak System Design

### 1. Streak Types & Granularity

#### Primary: Daily Streak (Current)
- Based on marking shlokas as read each day
- Most common and motivating type
- **Implementation:** Keep current system, enhance with recovery

#### Future Considerations:
- **Weekly Streak:** 4+ days per week (less pressure, more flexible)
- **Monthly Streak:** 15+ days per month (long-term consistency)
- **Reading Streak:** Consecutive shlokas read (not time-based)

**Decision:** Start with enhanced daily streak, add others later if needed.

### 2. Streak Recovery & Grace Periods

#### Recommended: Streak Freeze System
- **One freeze per month** - user can "freeze" their streak once per month
- Freeze prevents streak from breaking on one missed day
- Visual indicator when freeze is available/used
- Encourages habit without being too punishing

#### Alternative Options:
- **Recovery Window:** 24-48 hours to recover (automatic)
- **Streak Saver:** Consumable item (earned through achievements)
- **No Recovery:** Strict (current) - may be too harsh for habit formation

**Decision:** Implement streak freeze system (1 per month).

### 3. Streak Milestones & Rewards

#### Milestone Bonuses:
- **7 days:** "Week Warrior" - Bonus XP + Achievement
- **30 days:** "Monthly Devotee" - Bonus XP + Achievement + Special Badge
- **100 days:** "Centurion" - Major XP bonus + Achievement + Exclusive Badge
- **365 days:** "Year of Wisdom" - Legendary Achievement + Special Recognition

#### Streak Multipliers:
- After 7 days: +1 XP per streak day (6 XP/day instead of 5)
- After 30 days: +2 XP per streak day (7 XP/day)
- After 100 days: +3 XP per streak day (8 XP/day)

**Decision:** Implement milestone bonuses and multipliers.

### 4. Streak Data Tracking

#### New Fields Needed:
- `current_streak`: Current consecutive days (existing)
- `longest_streak`: All-time best streak
- `streak_freeze_used_this_month`: Boolean flag
- `last_streak_date`: Last date streak was maintained
- `total_streak_days`: Lifetime total days with streaks

**Decision:** Add `UserStreak` model or extend `User` model with streak fields.

---

## 🏆 Achievement System Design

### 1. Achievement Categories

#### A. Reading Milestones
- "First Steps" - Read 1 shloka
- "Getting Started" - Read 10 shlokas
- "Dedicated Learner" - Read 50 shlokas
- "Scholar" - Read 100 shlokas
- "Master Scholar" - Read 500 shlokas
- "Sage" - Read 1000 shlokas

#### B. Streak Achievements
- "Day One" - 1 day streak
- "Week Warrior" - 7 day streak
- "Fortnight Focus" - 14 day streak
- "Monthly Devotee" - 30 day streak
- "Centurion" - 100 day streak
- "Year of Wisdom" - 365 day streak

#### C. Book Completion
- "Chapter Complete" - Complete a chapter (varies by book)
- "Book Explorer" - Read from 3 different books
- "Bhagavad Gita Complete" - Read all 700 shlokas
- "Multi-Book Master" - Read from 5 different books

#### D. Engagement Achievements
- "Daily Reader" - Read 5 shlokas in one day
- "Power Reader" - Read 10 shlokas in one day
- "Marathon Reader" - Read 20 shlokas in one day
- "Weekend Warrior" - Read every day this week
- "Perfect Week" - Read 7 days in a row

#### E. Special Achievements
- "Night Owl" - Read at midnight (00:00-02:00)
- "Early Bird" - Read at dawn (05:00-07:00)
- "Reflection Master" - Re-read favorite shloka 5 times
- "Theme Explorer" - Read 10 shlokas with same theme
- "Bookmark Collector" - Favorite 10 shlokas

#### F. Mastery Achievements
- "Deep Dive" - Read same shloka 10 times
- "Theme Master" - Read all shlokas in a theme category
- "Context Seeker" - Read 50 shlokas with context explanations

**Decision:** Implement all categories, start with A, B, C (most important).

### 2. Achievement Progression & Tiers

#### Tiered Achievements:
- **Bronze/Silver/Gold** for major milestones
  - Example: "Week Warrior" (Bronze) → "Monthly Devotee" (Silver) → "Centurion" (Gold)

#### Progressive Achievements:
- Series of achievements that build on each other
- Example: "Read 10" → "Read 50" → "Read 100" → "Read 500"

**Decision:** Use progressive achievements (simpler, clearer progression).

### 3. Achievement Rarity & Rewards

#### Rarity Levels:
- **Common** (Green): Easy to achieve, 10-50 XP
- **Rare** (Blue): Moderate difficulty, 50-100 XP
- **Epic** (Purple): Hard to achieve, 100-250 XP
- **Legendary** (Gold): Very difficult, 250-500 XP

#### Reward Structure:
- XP rewards scale with rarity
- Special unlocks for Epic/Legendary (themes, badges, titles)
- Visual distinction in UI

**Decision:** Implement rarity system with scaled XP rewards.

---

## 🗺️ User Journey Design

### Phase 1: Onboarding (Days 1-3)

**Goals:**
- First reading within 24 hours
- Understand the app value
- Unlock first achievement

**Strategies:**
- **Welcome Achievement:** "First Shloka Read" (instant unlock)
- **Guided Tutorial:** Show streak/XP system
- **Quick Wins:** Easy early achievements (Read 1, Read 3, Read 5)
- **Onboarding Quest:** "Read 3 shlokas to complete setup"

**Implementation:**
- Create onboarding achievements
- Add tutorial flow
- Welcome message with first achievement

### Phase 2: Early Engagement (Week 1)

**Goals:**
- Daily habit formation
- Build first streak
- Understand value proposition

**Strategies:**
- **Daily Reminder Notifications:** Push notifications for reading
- **3-Day Streak Milestone:** Early achievement
- **Weekly Summary:** "You read X shlokas this week"
- **Progressive Achievements:** 1, 3, 5, 7 shlokas

**Implementation:**
- Notification system
- Weekly summary endpoint
- Early streak achievements

### Phase 3: Habit Formation (Weeks 2-4)

**Goals:**
- Maintain daily reading
- Build 7+ day streak
- Explore different features

**Strategies:**
- **7-Day Streak Achievement:** Major milestone
- **Weekly Challenges:** "Read 10 shlokas this week"
- **Theme Exploration:** "Read 5 shlokas about Dharma"
- **Social Proof:** "You're in the top 20% of readers"

**Implementation:**
- Weekly challenge system
- Theme-based achievements
- Analytics for social proof

### Phase 4: Long-Term Engagement (Month 2+)

**Goals:**
- Sustained engagement
- Deep learning
- Community connection

**Strategies:**
- **Monthly Milestones:** 30, 60, 90, 365 days
- **Book Completion Achievements:** Complete entire books
- **Mastery Achievements:** Re-reading favorites
- **Seasonal Events:** Special achievements during festivals
- **Reflection Prompts:** Encourage deeper engagement

**Implementation:**
- Long-term milestone tracking
- Book completion detection
- Seasonal event system

### Phase 5: Re-engagement (For Inactive Users)

**Goals:**
- Bring back lapsed users
- Rebuild streaks
- Rekindle interest

**Strategies:**
- **Streak Recovery:** Special offer to restore streak
- **"We Miss You" Notifications:** Personalized messages
- **Comeback Achievements:** "Return after 7 days"
- **Fresh Content:** New shlokas or themes

**Implementation:**
- Streak recovery mechanism
- Re-engagement notifications
- Comeback achievement tracking

---

## 🎨 Key Design Decisions

### 1. Streak Philosophy
**Decision:** **Forgiving with Freeze System**
- 1 freeze per month prevents accidental breaks
- Encourages habit formation without being too harsh
- Still requires consistency

### 2. Achievement Balance
**Decision:** **Mix of Easy Wins + Meaningful Milestones**
- 60% easy/medium achievements (motivation)
- 40% challenging achievements (long-term goals)
- Visible roadmap (users can see what's next)

### 3. User Motivation
**Decision:** **Intrinsic + Extrinsic Balance**
- Focus on learning (intrinsic)
- Gamification supports learning (extrinsic)
- Individual progress (no competitive pressure initially)

### 4. Progression Pacing
**Decision:** **Fast Early, Steady Later**
- Quick level-ups in first week (engagement)
- Steady progression after level 5 (sustainability)
- XP requirements scale: `BASE_LEVEL_XP * (1.5 ^ (level - 1))`

### 5. Data Tracking
**Decision:** **Comprehensive Tracking**
- Track longest streak separately
- Track streak history (when broken, when achieved)
- Track achievement unlock dates for analytics
- Track user journey phase

---

## 📋 Implementation Phases

### Phase 1: Enhanced Streak System ✅ **COMPLETED**
**Priority: High**

1. **Create UserStreak Model** ✅
   - ✅ Track current_streak, longest_streak
   - ✅ Track streak_freeze_used_this_month
   - ✅ Track last_streak_date, total_streak_days
   - ✅ Track streak_freeze_reset_date
   - ✅ Track awarded_milestones (JSON field)

2. **Enhance Streak Calculation** ✅
   - ✅ Update `StatsService.calculate_streak()`
   - ✅ Add streak freeze logic
   - ✅ Track longest streak
   - ✅ Auto-create UserStreak on first use
   - ✅ Monthly freeze reset logic

3. **Streak Milestone System** ✅
   - ✅ Add milestone bonuses (7, 30, 100, 365 days)
   - ✅ Implement streak multipliers (7, 30, 100 day bonuses)
   - ✅ Track awarded milestones to prevent duplicates
   - ✅ Integrate milestone XP into experience calculation

4. **API Endpoints** ✅
   - ✅ GET `/api/user/streak` - Get streak details
   - ✅ POST `/api/user/streak/freeze` - Use streak freeze
   - ✅ GET `/api/user/streak/history` - Streak history and milestones

5. **Backend Testing** ✅
   - ✅ Model tests (UserStreak creation, validation)
   - ✅ Service tests (streak calculation, freeze, milestones)
   - ✅ API endpoint tests (all endpoints, authentication)
   - ✅ Integration tests (with stats and achievements)
   - ✅ All 55 tests passing

6. **Frontend Implementation** ✅ **COMPLETED**
   - ✅ Updated API service (`api.ts`) to include new streak fields
   - ✅ Added `getUserStreak()` method to API service
   - ✅ Added `useStreakFreeze()` method to API service
   - ✅ Added `getStreakHistory()` method to API service
   - ✅ Updated `getUserStats()` to include `longest_streak`, `total_streak_days`, `streak_freeze_available`
   - ✅ Updated HomeScreen to display new streak data (current streak, longest streak, total streak days)
   - ✅ Added streak freeze button/UI with confirmation dialog and loading states
   - ✅ Added streak freeze availability status display
   - ⏳ Display milestone achievements (API ready, UI display pending - can be added later)
   - ⏳ Optional: Create streak history screen (API ready, screen pending - can be added later)

### Phase 2: Achievement Categories & Rarity
**Priority: High**

1. **Extend Achievement Model**
   - Add `rarity` field (Common, Rare, Epic, Legendary)
   - Add `category` field (Reading, Streak, Book, Engagement, Special, Mastery)
   - Add `tier` field for progressive achievements

2. **Create Initial Achievements**
   - Reading Milestones (10 achievements)
   - Streak Achievements (6 achievements)
   - Book Completion (4 achievements)
   - Engagement (5 achievements)

3. **Achievement Service Enhancements**
   - Add category-based checking
   - Add rarity-based XP rewards
   - Add achievement grouping

4. **API Endpoints**
   - GET `/api/achievements` - List all (with filters)
   - GET `/api/achievements/categories` - Group by category
   - GET `/api/achievements/{id}` - Achievement details

### Phase 3: User Journey - Onboarding & Early Engagement
**Priority: Medium**

1. **Onboarding Achievements**
   - "First Shloka Read"
   - "Getting Started" (3 shlokas)
   - "Day One" (1 day streak)

2. **Tutorial System**
   - Welcome screen
   - Streak/XP explanation
   - Achievement showcase

3. **Early Engagement Features**
   - Daily reminder notifications (backend)
   - Weekly summary endpoint
   - Progressive achievements (1, 3, 5, 7 shlokas)

### Phase 4: User Journey - Habit Formation & Long-Term
**Priority: Medium**

1. **Weekly Challenges**
   - Challenge model
   - Challenge tracking
   - Challenge achievements

2. **Theme Exploration**
   - Theme-based achievements
   - Theme tracking

3. **Long-Term Milestones**
   - Monthly milestone tracking
   - Book completion detection
   - Mastery achievements

### Phase 5: Re-engagement & Analytics
**Priority: Low**

1. **Streak Recovery**
   - Recovery mechanism
   - Recovery achievements

2. **Re-engagement System**
   - Inactive user detection
   - Comeback achievements
   - Personalized notifications

3. **Analytics & Insights**
   - User journey phase tracking
   - Engagement metrics
   - Achievement unlock analytics

---

## 🗄️ Database Schema Changes

### New Model: UserStreak ✅ **IMPLEMENTED**
```python
class UserStreak(TimestampedModel):
    user = OneToOneField(User, on_delete=CASCADE, db_index=True)
    current_streak = IntegerField(default=0, validators=[MinValueValidator(0)])
    longest_streak = IntegerField(default=0, validators=[MinValueValidator(0)])
    streak_freeze_used_this_month = BooleanField(default=False)
    last_streak_date = DateField(null=True, blank=True)
    total_streak_days = IntegerField(default=0, validators=[MinValueValidator(0)])
    streak_freeze_reset_date = DateField(null=True, blank=True)
    awarded_milestones = JSONField(default=list, blank=True)  # Tracks [7, 30, 100, 365]
```

### Enhanced Model: Achievement
```python
class Achievement(TimestampedModel):
    # Existing fields...
    rarity = CharField(max_length=20, choices=RarityChoices)  # NEW
    category = CharField(max_length=50)  # NEW
    tier = IntegerField(default=1)  # NEW (for progressive achievements)
    is_hidden = BooleanField(default=False)  # NEW (for surprise achievements)
```

### New Model: StreakMilestone (Optional)
```python
class StreakMilestone(TimestampedModel):
    user = ForeignKey(User, on_delete=CASCADE)
    milestone_days = IntegerField()  # 7, 30, 100, 365
    achieved_at = DateTimeField(auto_now_add=True)
    xp_bonus_awarded = IntegerField()
```

---

## 📊 XP & Leveling System

### Current System:
- **XP per Shloka:** 10 XP
- **XP per Streak Day:** 5 XP
- **Base Level XP:** 100
- **Level Multiplier:** 1.5x

### Enhanced System:
- **XP per Shloka:** 10 XP (unchanged)
- **XP per Streak Day:** 5 XP base
  - After 7 days: 6 XP/day
  - After 30 days: 7 XP/day
  - After 100 days: 8 XP/day
- **Achievement XP:** Based on rarity
  - Common: 10-50 XP
  - Rare: 50-100 XP
  - Epic: 100-250 XP
  - Legendary: 250-500 XP
- **Streak Milestone Bonuses:**
  - 7 days: +50 XP
  - 30 days: +200 XP
  - 100 days: +500 XP
  - 365 days: +2000 XP

---

## 🎯 Success Metrics

### Engagement Metrics:
- Daily Active Users (DAU)
- Streak retention rate
- Average streak length
- Achievement unlock rate

### User Journey Metrics:
- Onboarding completion rate
- Week 1 retention
- Month 1 retention
- Long-term retention (90+ days)

### Achievement Metrics:
- Average achievements per user
- Most unlocked achievements
- Rarest achievements
- Achievement unlock velocity

---

## 🚀 Next Steps

1. **Review & Approve Design** ✅
2. **Phase 1 Implementation:** Enhanced Streak System ✅ **COMPLETED**
3. **Phase 2 Implementation:** Achievement Categories & Rarity ⏳ **NEXT**
4. **Phase 3 Implementation:** User Journey - Onboarding
5. **Phase 4 Implementation:** User Journey - Habit Formation
6. **Phase 5 Implementation:** Re-engagement & Analytics

---

## 📝 Notes

- All implementations should maintain backward compatibility
- Use UUIDs for all primary keys (existing pattern)
- Follow existing code patterns and service architecture
- Add comprehensive tests for new features
- Update API documentation as features are added

