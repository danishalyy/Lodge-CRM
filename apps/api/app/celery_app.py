from celery import Celery
from .config import settings

celery_app=Celery("lodge_crm",broker=settings.redis_url,backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",accept_content=["json"],result_serializer="json",timezone="UTC",enable_utc=True,
    task_acks_late=True,worker_prefetch_multiplier=1,task_reject_on_worker_lost=True,
    beat_schedule={
        "process-account-email-outbox":{"task":"app.worker.process_account_email_outbox","schedule":15.0},
        "process-notification-outbox":{"task":"app.worker.process_notification_outbox","schedule":60.0},
        "generate-operational-alerts":{"task":"app.worker.generate_operational_alerts","schedule":300.0},
        "generate-subscription-reminders":{"task":"app.worker.generate_subscription_reminders","schedule":21600.0},
        "sync-staff-leave-status":{"task":"app.worker.sync_staff_leave_status","schedule":3600.0},
        "generate-hr-expiry-alerts":{"task":"app.worker.generate_hr_expiry_alerts","schedule":21600.0},
    },
)
celery_app.autodiscover_tasks(["app"])
