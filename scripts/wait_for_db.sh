#!/bin/sh

set -e

echo "⏳ Waiting for database..."

until python manage.py shell -c "
import django
django.setup()
from django.db import connection
connection.cursor()
print('✅ Database is ready!')
"; do
    echo "⏳ Database is unavailable - sleeping..."
    sleep 2
done

echo "🚀 Database is up - continuing..."
