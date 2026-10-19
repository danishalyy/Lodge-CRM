from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
import smtplib
import redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .celery_app import celery_app
from .config import settings
from .db import SessionLocal,set_rls_context
from .models import (
    Lodge, MaintenanceTicket, Membership, Notification, NotificationDelivery, NotificationPreference,
    StaffProfile, StaffLeave, StaffCredential, MaintenanceAsset, Subscription, Task, User, Vehicle, Stay, Unit
)
from .notification_service import create_notification, staff_user_id, user_ids_with_permission

redis_client=redis.Redis.from_url(settings.redis_url,decode_responses=True)

def _lock(name,ttl):
    return redis_client.set(f"job-lock:{name}",str(datetime.now(timezone.utc).timestamp()),nx=True,ex=ttl)

def _send_email(destination,title,body):
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP delivery is not configured")
    msg=EmailMessage();msg["Subject"]=title;msg["From"]=settings.smtp_from_email;msg["To"]=destination;msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=20) as smtp:
        if settings.smtp_use_tls:smtp.starttls()
        if settings.smtp_username:smtp.login(settings.smtp_username,settings.smtp_password)
        smtp.send_message(msg)

@celery_app.task(name="app.worker.process_notification_outbox")
def process_notification_outbox():
    if not _lock("notification-outbox",55):return {"skipped":"locked"}
    now=datetime.now(timezone.utc);processed=0
    with SessionLocal() as db:
        set_rls_context(db,None,True)
        rows=db.scalars(select(NotificationDelivery).where(NotificationDelivery.status.in_(["pending","failed"]),NotificationDelivery.next_attempt_at<=now).order_by(NotificationDelivery.next_attempt_at).limit(100)).all()
        for delivery in rows:
            set_rls_context(db,str(delivery.lodge_id),True)
            notification=db.get(Notification,delivery.notification_id)
            if not notification:
                delivery.status="dead";delivery.last_error="Notification no longer exists";continue
            delivery.status="sending";delivery.attempts+=1;db.commit()
            try:
                _send_email(delivery.destination,notification.title,notification.body or notification.title)
                set_rls_context(db,str(delivery.lodge_id),True)
                delivery.status="sent";delivery.sent_at=datetime.now(timezone.utc);delivery.last_error=""
            except Exception as exc:
                set_rls_context(db,str(delivery.lodge_id),True)
                delivery.last_error=str(exc)[:2000]
                if delivery.attempts>=8:delivery.status="dead"
                else:
                    delivery.status="failed"
                    delay=min(3600,60*(2**max(0,delivery.attempts-1)))
                    delivery.next_attempt_at=datetime.now(timezone.utc)+timedelta(seconds=delay)
            db.commit();processed+=1
    return {"processed":processed}

@celery_app.task(name="app.worker.generate_operational_alerts")
def generate_operational_alerts():
    if not _lock("operational-alerts",280):return {"skipped":"locked"}
    created=0;now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        set_rls_context(db,None,True)
        lodges=db.scalars(select(Lodge).where(Lodge.status=="active")).all()
        for lodge in lodges:
            set_rls_context(db,str(lodge.id),True)
            sub=db.get(Subscription,lodge.id);today=date.today()
            if not sub or sub.suspended or today<sub.start_date or today>sub.expiry_date:continue
            managers=user_ids_with_permission(db,lodge.id,"notifications.view")
            overdue=db.scalars(select(Task).where(Task.lodge_id==lodge.id,Task.status.not_in(["completed","cancelled"]),Task.due_at.is_not(None),Task.due_at<now)).all()
            for task in overdue:
                assignee=staff_user_id(db,lodge.id,task.assigned_staff_id)
                recipients=list(dict.fromkeys(([assignee] if assignee else [])+managers))
                n=create_notification(db,lodge_id=lodge.id,notification_type="task.overdue",severity="high" if task.priority!="critical" else "critical",title=f"Overdue task: {task.title}",body=f"Task was due {task.due_at.isoformat()} and is still {task.status}.",resource_type="task",resource_id=task.id,dedupe_key=f"task-overdue:{task.id}:{task.due_at.isoformat()}",recipient_user_ids=recipients)
                if n:created+=1
            critical=db.scalars(select(MaintenanceTicket).where(MaintenanceTicket.lodge_id==lodge.id,MaintenanceTicket.priority=="critical",MaintenanceTicket.status.not_in(["completed","cancelled"]))).all()
            for ticket in critical:
                assignee=staff_user_id(db,lodge.id,ticket.assigned_staff_id)
                recipients=list(dict.fromkeys(([assignee] if assignee else [])+managers))
                n=create_notification(db,lodge_id=lodge.id,notification_type="maintenance.critical",severity="critical",title=f"Critical maintenance: {ticket.title}",body=ticket.description,resource_type="maintenance",resource_id=ticket.id,dedupe_key=f"maintenance-critical:{ticket.id}:{ticket.updated_at.isoformat()}",recipient_user_ids=recipients)
                if n:created+=1
            assigned=db.scalars(select(Task).where(Task.lodge_id==lodge.id,Task.assigned_staff_id.is_not(None),Task.status.in_(["assigned","accepted","started"]))).all()
            for task in assigned:
                uid=staff_user_id(db,lodge.id,task.assigned_staff_id)
                if uid:
                    n=create_notification(db,lodge_id=lodge.id,notification_type="task.assigned",severity="normal",title=f"Task assigned: {task.title}",body=task.description,resource_type="task",resource_id=task.id,dedupe_key=f"task-assigned:{task.id}:{task.assigned_staff_id}",recipient_user_ids=[uid])
                    if n:created+=1
            service_due=db.scalars(select(Vehicle).where(Vehicle.lodge_id==lodge.id,Vehicle.service_due_odometer_km.is_not(None),Vehicle.odometer_km>=Vehicle.service_due_odometer_km,Vehicle.status!="out_of_service")).all()
            for vehicle in service_due:
                n=create_notification(db,lodge_id=lodge.id,notification_type="vehicle.service_due",severity="high",title=f"Vehicle service due: {vehicle.registration}",body=f"Current odometer {vehicle.odometer_km} km; service due at {vehicle.service_due_odometer_km} km.",resource_type="vehicle",resource_id=vehicle.id,dedupe_key=f"vehicle-service:{vehicle.id}:{vehicle.service_due_odometer_km}",recipient_user_ids=managers)
                if n:created+=1
            arrivals=db.scalars(select(Stay).where(Stay.lodge_id==lodge.id,Stay.arrival_date==today,Stay.status.in_(["upcoming","arriving"]))).all()
            for stay in arrivals:
                unit=db.get(Unit,stay.unit_id)
                if unit and unit.status not in {"ready","available"}:
                    n=create_notification(db,lodge_id=lodge.id,notification_type="room.arrival_not_ready",severity="high",title=f"Room not ready: {unit.name}",body=f"Today's arrival is assigned to {unit.name}, currently {unit.status.replace('_',' ')}.",resource_type="stay",resource_id=stay.id,dedupe_key=f"arrival-room-not-ready:{stay.id}:{today.isoformat()}",recipient_user_ids=managers)
                    if n:created+=1
            asset_due=db.scalars(select(MaintenanceAsset).where(MaintenanceAsset.lodge_id==lodge.id,MaintenanceAsset.status=="active",MaintenanceAsset.next_service_date.is_not(None),MaintenanceAsset.next_service_date<=date.today()+timedelta(days=7))).all()
            for asset in asset_due:
                n=create_notification(db,lodge_id=lodge.id,notification_type="maintenance.asset_service_due",severity="high",title=f"Asset service due: {asset.name}",body=f"Asset {asset.asset_code} service date: {asset.next_service_date.isoformat()}.",resource_type="maintenance_asset",resource_id=asset.id,dedupe_key=f"asset-service:{asset.id}:{asset.next_service_date.isoformat()}",recipient_user_ids=managers)
                if n:created+=1
            db.commit()
    return {"created":created}

@celery_app.task(name="app.worker.generate_subscription_reminders")
def generate_subscription_reminders():
    if not _lock("subscription-reminders",21000):return {"skipped":"locked"}
    created=0;today=date.today();thresholds=[30,14,7,3,0]
    with SessionLocal() as db:
        set_rls_context(db,None,True)
        superadmins=list(db.scalars(select(User.id).where(User.is_super_admin.is_(True),User.is_active.is_(True))).all())
        for sub in db.scalars(select(Subscription).where(Subscription.suspended.is_(False))).all():
            days=(sub.expiry_date-today).days
            if days<0:continue
            lodge=db.get(Lodge,sub.lodge_id)
            if not lodge:continue
            eligible=[t for t in thresholds if days<=t]
            for threshold in sorted(eligible,reverse=True):
                key=f"subscription-expiry:{lodge.id}:{sub.expiry_date.isoformat()}:{threshold}"
                if db.scalar(select(Notification.id).where(Notification.lodge_id==lodge.id,Notification.dedupe_key==key)):continue
                title=f"Subscription {'expires today' if days==0 else f'expires in {days} days'}: {lodge.name}"
                n=create_notification(db,lodge_id=lodge.id,notification_type="subscription.expiry",severity="critical" if days<=3 else "high",title=title,body=f"{sub.package} subscription expiry date: {sub.expiry_date.isoformat()}.",resource_type="subscription",resource_id=lodge.id,dedupe_key=key,recipient_user_ids=superadmins)
                if n:created+=1
                break
        db.commit()
    return {"created":created}



@celery_app.task(name="app.worker.sync_staff_leave_status")
def sync_staff_leave_status():
    if not _lock("staff-leave-status",3300):return {"skipped":"locked"}
    today=date.today();changed=0
    with SessionLocal() as db:
        set_rls_context(db,None,True)
        for lodge in db.scalars(select(Lodge).where(Lodge.status=="active")).all():
            set_rls_context(db,str(lodge.id),True)
            active_ids=set(db.scalars(select(StaffLeave.staff_id).where(StaffLeave.lodge_id==lodge.id,StaffLeave.status=="approved",StaffLeave.start_date<=today,StaffLeave.end_date>=today)).all())
            for staff in db.scalars(select(StaffProfile).where(StaffProfile.lodge_id==lodge.id,StaffProfile.employment_status=="active")).all():
                desired="leave" if staff.id in active_ids else ("available" if staff.operational_status=="leave" else staff.operational_status)
                if staff.operational_status!=desired:staff.operational_status=desired;changed+=1
            db.commit()
    return {"changed":changed}

@celery_app.task(name="app.worker.generate_hr_expiry_alerts")
def generate_hr_expiry_alerts():
    if not _lock("hr-expiry-alerts",21000):return {"skipped":"locked"}
    today=date.today();created=0
    with SessionLocal() as db:
        set_rls_context(db,None,True)
        for lodge in db.scalars(select(Lodge).where(Lodge.status=="active")).all():
            set_rls_context(db,str(lodge.id),True);recipients=user_ids_with_permission(db,lodge.id,"staff.hr.manage")
            rows=db.scalars(select(StaffCredential).where(StaffCredential.lodge_id==lodge.id,StaffCredential.expiry_date.is_not(None),StaffCredential.expiry_date>=today,StaffCredential.expiry_date<=today+timedelta(days=30))).all()
            for cred in rows:
                staff=db.get(StaffProfile,cred.staff_id);days=(cred.expiry_date-today).days
                n=create_notification(db,lodge_id=lodge.id,notification_type="staff.credential_expiry",severity="critical" if days<=7 else "high",title=f"Credential expiry: {staff.full_name if staff else 'Staff'} — {cred.name}",body=f"Expires {cred.expiry_date.isoformat()} ({days} days).",resource_type="staff_credential",resource_id=cred.id,dedupe_key=f"credential-expiry:{cred.id}:{cred.expiry_date.isoformat()}:{days}",recipient_user_ids=recipients)
                if n:created+=1
            db.commit()
    return {"created":created}
