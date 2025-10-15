#!/bin/bash

# Install dependencies
python3.11 -m pip install -r requirements.txt

# Collect static files
python3.11 manage.py collectstatic --noinput

# Apply database migrations
python3.11 manage.py migrate
