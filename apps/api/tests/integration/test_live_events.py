"""Real PostgreSQL outbox, scope filtering and authenticated SSE checkpoints."""
from uuid import uuid4
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from app import live_events as live
from app.models import Task, LiveEvent, Lodge, Membership, Role, LodgeEntitlementOverride, Notification, NotificationRecipient
from app.db import set_rls_context


def snapshot(a):
    token=a['client'].cookies['lodge_session']
    with a['application']() as db:
        ctx,permissions,features,fp=live.authorize(db,token,a['user'].id,a['lodge'].id)
        position=live.head(db,a['lodge'].id)
    return token,fp,position


def create_task(a, **kw):
    with a['owner']() as db:
        task=Task(lodge_id=a['lodge'].id,title='Private guest detail never streamed',created_by_user_id=a['user'].id,**kw)
        db.add(task);db.commit()
        return task.id


def page(a, snap):
    token,fp,pos=snap
    return live.read_page(a['application'],token,a['user'].id,a['lodge'].id,pos,fp)


def test_atomic_outbox_and_safe_payload(account):
    a=account;s=snapshot(a);tid=create_task(a)
    pos,changes,changed=page(a,s)
    assert pos>s[2] and not changed
    assert any(c['id']==str(tid) and c['type']=='task.created' for c in changes)
    assert all(set(c)=={'type','id','version'} for c in changes)
    assert 'Private guest' not in json.dumps(changes)
    with a['owner']() as db:
        db.add(Task(lodge_id=a['lodge'].id,title='Rolled back',created_by_user_id=a['user'].id));db.flush();db.rollback()
        assert live.head(db,a['lodge'].id)==pos


def test_application_rls_and_append_only(account):
    a=account;create_task(a)
    with a['owner']() as db:
        foreign=Lodge(name='Other');db.add(foreign);db.flush()
        db.add(Task(lodge_id=foreign.id,title='Other secret',created_by_user_id=a['user'].id));db.commit();fid=foreign.id
    with a['application']() as db:
        set_rls_context(db,str(a['lodge'].id),False,str(a['user'].id))
        assert not db.scalars(select(LiveEvent).where(LiveEvent.lodge_id==fid)).all()
        with pytest.raises(DBAPIError):db.execute(text('DELETE FROM live_events'))
        db.rollback()


def test_resume_tokens_are_bound_and_opaque(account):
    a=account;token,fp,pos=snapshot(a)
    cursor=live.encode_cursor(token,a['lodge'].id,a['user'].id,fp,pos)
    assert str(a['lodge'].id) not in cursor
    assert live.decode_cursor(cursor,token,a['lodge'].id,a['user'].id,fp)==pos
    assert live.decode_cursor(cursor,token,a['lodge'].id,a['user'].id,'changed') is None
    for t,l,u in [(token,uuid4(),a['user'].id),(token,a['lodge'].id,uuid4()),('other',a['lodge'].id,a['user'].id)]:
        with pytest.raises(HTTPException):live.decode_cursor(cursor,t,l,u,fp)
    with pytest.raises(HTTPException):live.decode_cursor(cursor[:20]+'x'+cursor[21:],token,a['lodge'].id,a['user'].id,fp)


def test_feature_override_filters_records(account):
    a=account
    with a['owner']() as db:
        db.add(LodgeEntitlementOverride(lodge_id=a['lodge'].id,feature_key='tasks',enabled=False));db.commit()
    s=snapshot(a);create_task(a)
    assert page(a,s)[1]==[]


def test_role_change_restricts_before_delivery(account):
    a=account;s=snapshot(a);create_task(a)
    with a['owner']() as db:
        m=db.scalar(select(Membership).where(Membership.user_id==a['user'].id,Membership.lodge_id==a['lodge'].id))
        m.role_id=db.scalar(select(Role.id).where(Role.key=='housekeeping'));db.commit()
    assert page(a,s)[1:]==([],True)


def test_owned_scope_excludes_unassigned_work(account):
    a=account
    with a['owner']() as db:
        m=db.scalar(select(Membership).where(Membership.user_id==a['user'].id,Membership.lodge_id==a['lodge'].id))
        m.role_id=db.scalar(select(Role.id).where(Role.key=='housekeeping'));db.commit()
    s=snapshot(a);create_task(a)
    assert page(a,s)[1]==[]


def test_notification_delivery_is_recipient_private(account):
    a=account;s=snapshot(a)
    with a['owner']() as db:
        mine=Notification(lodge_id=a['lodge'].id,title='Private',body='Do not stream',notification_type='task.updated')
        other=Notification(lodge_id=a['lodge'].id,title='Other',body='Other secret',notification_type='task.updated')
        db.add_all([mine,other]);db.flush()
        db.add(NotificationRecipient(lodge_id=a['lodge'].id,notification_id=mine.id,user_id=a['user'].id));db.commit()
    ids={c['id'] for c in page(a,s)[1]}
    assert str(mine.id) in ids and str(other.id) not in ids


def test_http_stream_heartbeat_resume_and_cross_tenant(account,monkeypatch):
    a=account;monkeypatch.setattr(live,'MAX_STREAM_SECONDS',.025);monkeypatch.setattr(live,'POLL_SECONDS',.005);monkeypatch.setattr(live,'HEARTBEAT_SECONDS',.005)
    url=f"/api/v1/lodges/{a['lodge'].id}/events"
    r=a['client'].get(url)
    assert r.status_code==200,r.text
    assert r.headers['x-accel-buffering']=='no' and 'no-store' in r.headers['cache-control']
    assert 'event: ready' in r.text and 'event: heartbeat' in r.text
    cursor=next(line[4:] for line in r.text.splitlines() if line.startswith('id: '))
    tid=create_task(a)
    resumed=a['client'].get(url,headers={'Last-Event-ID':cursor})
    assert 'task.created' in resumed.text and str(tid) in resumed.text and 'event: checkpoint' in resumed.text
    assert a['client'].get(url,headers={'Last-Event-ID':'invalid'}).status_code==400
    assert a['client'].get(f'/api/v1/lodges/{uuid4()}/events').status_code==403


def test_revoked_membership_cannot_continue(account):
    a=account;s=snapshot(a)
    with a['owner']() as db:
        m=db.scalar(select(Membership).where(Membership.user_id==a['user'].id,Membership.lodge_id==a['lodge'].id));db.delete(m);db.commit()
    with pytest.raises(HTTPException):page(a,s)


def test_department_and_staff_scope_are_checked_on_each_delivery(account):
    from app.models import Department, StaffProfile
    a=account
    with a['owner']() as db:
        one=Department(lodge_id=a['lodge'].id,name='One');two=Department(lodge_id=a['lodge'].id,name='Two');db.add_all([one,two]);db.flush()
        staff=StaffProfile(lodge_id=a['lodge'].id,user_id=a['user'].id,full_name='Assigned user',department_id=one.id);db.add(staff);db.flush()
        m=db.scalar(select(Membership).where(Membership.user_id==a['user'].id,Membership.lodge_id==a['lodge'].id));m.role_id=db.scalar(select(Role.id).where(Role.key=='department_manager'));m.department_id=one.id;db.commit()
    s=snapshot(a);mine=create_task(a,department_id=one.id,assigned_staff_id=staff.id);other=create_task(a,department_id=two.id)
    ids={c['id'] for c in page(a,s)[1]};assert str(mine) in ids and str(other) not in ids
    with a['owner']() as db:
        m=db.scalar(select(Membership).where(Membership.user_id==a['user'].id,Membership.lodge_id==a['lodge'].id));m.role_id=db.scalar(select(Role.id).where(Role.key=='housekeeping'));db.commit()
    s=snapshot(a)
    with a['owner']() as db:
        task=db.get(Task,mine);task.title='Changed assigned work';db.get(Task,other).title='Changed unassigned work';db.commit()
    ids={c['id'] for c in page(a,s)[1]};assert str(mine) in ids and str(other) not in ids


def test_suspension_stops_delivery(account):
    from app.models import Subscription
    a=account;s=snapshot(a)
    with a['owner']() as db:
        sub=db.get(Subscription,a['lodge'].id);sub.suspended=True;db.commit()
    # Actual subscription authority, not client-supplied metadata.
    with pytest.raises(HTTPException):page(a,s)


def test_revoked_session_is_rechecked_on_active_stream(account):
    from datetime import datetime, timezone
    from app.models import AuthSession
    from app.security import token_hash
    a=account;s=snapshot(a)
    with a['owner']() as db:
        session=db.scalar(select(AuthSession).where(AuthSession.token_hash==token_hash(s[0])))
        session.revoked_at=datetime.now(timezone.utc);db.commit()
    with pytest.raises(HTTPException) as error:page(a,s)
    assert error.value.status_code==401


def test_resume_does_not_skip_a_transaction_that_commits_late(account):
    a=account
    with a['owner']() as first:
        late=Task(lodge_id=a['lodge'].id,title='First write, late commit',created_by_user_id=a['user'].id)
        first.add(late);first.flush()
        early=create_task(a)
        s=snapshot(a)
        assert all(c['id']!=str(early) for c in page(a,s)[1])
        first.commit()
    assert any(c['id']==str(late.id) for c in page(a,s)[1])


def test_staff_department_change_invalidates_even_with_membership_department(account):
    from app.models import Department, StaffProfile
    a=account
    with a['owner']() as db:
        first=Department(lodge_id=a['lodge'].id,name='Membership department');other=Department(lodge_id=a['lodge'].id,name='New staff department');db.add_all([first,other]);db.flush()
        staff=StaffProfile(lodge_id=a['lodge'].id,user_id=a['user'].id,full_name='Scope test',department_id=first.id);db.add(staff)
        member=db.scalar(select(Membership).where(Membership.user_id==a['user'].id,Membership.lodge_id==a['lodge'].id));member.department_id=first.id;db.commit()
    s=snapshot(a)
    with a['owner']() as db:
        db.get(StaffProfile,staff.id).department_id=other.id;db.commit()
    assert page(a,s)[1:]==([],True)
