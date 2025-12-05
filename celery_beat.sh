#!/bin/bash

export DJANGO_SETTINGS_MODULE=core.settings
source venv/bin/activate
celery -A core beat --loglevel=info
