import os
from celery import Celery
from kombu import Exchange, Queue



os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FaceGuard.settings')

app = Celery('FaceGuard')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

CELERY_DEFAULT_QUEUE = 'default'
CELERY_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
)

CELERY_TASK_RESULT_EXPIRES = 3600

