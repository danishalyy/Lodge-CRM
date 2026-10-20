import base64
from datetime import datetime,timezone
from io import BytesIO
from uuid import uuid4

import pytest
import pyotp
from PIL import Image,PngImagePlugin
from fastapi.testclient import TestClient
from sqlalchemy import select


def png_logo():
    image=Image.new('RGB',(32,32),(76,83,74));out=BytesIO()
    metadata=PngImagePlugin.PngInfo();metadata.add_text('private-source','discard this metadata')
    image.save(out,format='PNG',pnginfo=metadata)
    return base64.b64encode(out.getvalue()).decode()


@pytest.fixture
def platform(account):
    from app.main import app
    from app.models import User
    from app.security import encrypt_mfa_secret
    secret=pyotp.random_base32()
    with account['owner']() as db:
        admin=User(email=uuid4().hex+'@example.com',full_name='Platform Operator',password_hash=account['user'].password_hash,is_super_admin=True,mfa_enabled_at=datetime.now(timezone.utc),mfa_secret_encrypted=encrypt_mfa_secret(secret))
        db.add(admin);db.commit()
    client=TestClient(app)
    result=client.post('/api/v1/auth/login',json={'email':admin.email,'password':account['password'],'otp':pyotp.TOTP(secret).now()})
    assert result.status_code==200,result.text
    try:yield client,{'X-CSRF-Token':client.cookies['lodge_csrf']}
    finally:client.close()


def test_platform_can_set_branding_and_own_lodge_can_read_normalized_logo(account,platform):
    from app.models import AuditLog
    client,csrf=platform;lid=account['lodge'].id
    response=client.patch(f'/api/v1/platform/lodges/{lid}/branding',headers=csrf,json={'display_name':'Acacia River Lodge','logo_base64':png_logo()})
    assert response.status_code==200,response.text
    brand=account['client'].get(f'/api/v1/lodges/{lid}/branding').json()
    assert brand['display_name']=='Acacia River Lodge'
    assert brand['platform_name']=='SafariOS'
    asset=account['client'].get(brand['logo_url'])
    assert asset.status_code==200
    assert asset.headers['content-type']=='image/png'
    with Image.open(BytesIO(asset.content)) as image:
        assert image.size==(32,32)
        assert 'private-source' not in image.info
    me=account['client'].get('/api/v1/auth/me').json()
    assert me['memberships'][0]['branding']['display_name']=='Acacia River Lodge'
    dashboard=account['client'].get(f'/api/v1/lodges/{lid}/dashboard')
    assert dashboard.status_code==200,dashboard.text
    assert dashboard.json()['lodge']['branding']['display_name']=='Acacia River Lodge'
    with account['owner']() as db:
        assert db.scalar(select(AuditLog).where(AuditLog.lodge_id==lid,AuditLog.action=='lodge.branding_updated')) is not None


def test_lodge_admin_cannot_change_its_own_branding(account):
    result=account['client'].patch(f"/api/v1/platform/lodges/{account['lodge'].id}/branding",headers=account['csrf'],json={'display_name':'Unauthorized'})
    assert result.status_code==403


@pytest.mark.parametrize('suffix',['branding','branding/logo'])
def test_foreign_branding_is_not_accessible(account,suffix):
    from app.models import Lodge
    with account['owner']() as db:
        foreign=Lodge(name='Private brand '+uuid4().hex);db.add(foreign);db.commit()
    assert account['client'].get(f'/api/v1/lodges/{foreign.id}/{suffix}').status_code==403


@pytest.mark.parametrize('logo',['not-base64',base64.b64encode(b'<svg onload="alert(1)"></svg>').decode(),base64.b64encode(b'x'*(256*1024+1)).decode()])
def test_invalid_logo_is_rejected_without_changing_branding(account,platform,logo):
    from app.models import Lodge
    result=platform[0].patch(f"/api/v1/platform/lodges/{account['lodge'].id}/branding",headers=platform[1],json={'display_name':'Must not persist','logo_base64':logo})
    assert result.status_code==422
    with account['owner']() as db:assert db.get(Lodge,account['lodge'].id).brand_name==''


def test_logo_removal_and_name_only_update(account,platform):
    path=f"/api/v1/platform/lodges/{account['lodge'].id}/branding";client,csrf=platform
    assert client.patch(path,headers=csrf,json={'display_name':'First','logo_base64':png_logo()}).status_code==200
    assert client.patch(path,headers=csrf,json={'display_name':'Renamed'}).json()['logo_url'] is not None
    result=client.patch(path,headers=csrf,json={'display_name':'Renamed','remove_logo':True})
    assert result.status_code==200 and result.json()['logo_url'] is None
    assert account['client'].get(f"/api/v1/lodges/{account['lodge'].id}/branding/logo").status_code==404


def test_existing_lodge_uses_original_name_until_customized(account):
    result=account['client'].get(f"/api/v1/lodges/{account['lodge'].id}/branding")
    assert result.status_code==200
    assert result.json()['display_name']==account['lodge'].name
    assert result.json()['logo_url'] is None


def test_normalized_logo_discards_exif_metadata(account,platform):
    image=Image.new('RGB',(24,24));exif=Image.Exif();exif[0x010E]='Private original description'
    raw=BytesIO();image.save(raw,format='JPEG',exif=exif)
    lid=account['lodge'].id
    response=platform[0].patch(f'/api/v1/platform/lodges/{lid}/branding',headers=platform[1],json={'display_name':'Private lodge','logo_base64':base64.b64encode(raw.getvalue()).decode()})
    assert response.status_code==200,response.text
    asset=account['client'].get(response.json()['logo_url'])
    with Image.open(BytesIO(asset.content)) as sanitized:assert not sanitized.getexif()
