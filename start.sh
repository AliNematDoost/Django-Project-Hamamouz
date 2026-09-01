#!/bin/sh

python manage.py migrate

gunicorn clusterproject.wsgi:application --bind 0.0.0.0:8000 &

celery -A clusterproject worker --loglevel=info &

celery -A clusterproject beat --loglevel=info 