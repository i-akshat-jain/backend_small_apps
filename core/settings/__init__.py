"""
Django settings module.

This module loads the appropriate settings based on the DJANGO_SETTINGS_MODULE
environment variable or defaults to base settings.

Usage:
    - Development: DJANGO_SETTINGS_MODULE=core.settings.base (or just core.settings)
    - Production: DJANGO_SETTINGS_MODULE=core.settings.prod
"""

import os

# Determine which settings to use
settings_env = os.getenv('DJANGO_SETTINGS_MODULE', '')
django_env = os.getenv('DJANGO_ENV', '')

# If explicitly set to prod, or DJANGO_ENV is production, use prod settings
if 'prod' in settings_env.lower() or django_env.lower() == 'production':
    from .prod import *
else:
    # Default to base settings for development
    from .base import *

