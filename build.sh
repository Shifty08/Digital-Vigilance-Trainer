set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

python manage.py loaddata saved_scenarios.json

export DJANGO_SUPERUSER_USERNAME=admin
export DJANGO_SUPERUSER_PASSWORD=capstoneadmin123!
export DJANGO_SUPERUSER_EMAIL=admin@example.com
python manage.py createsuperuser --noinput || true