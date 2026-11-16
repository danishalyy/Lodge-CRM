from datetime import date, datetime, timezone
from types import SimpleNamespace
from cryptography.fernet import Fernet
import pytest
from app.config import Settings
from app.services.clock import lodge_day
from app.services.deployment import production_problems
from app.ops.health import readiness


def production():
    return Settings(app_env='production', cookie_secure=True,
        database_url='postgresql+psycopg://runtime:'+'x'*32+'@postgres/lodge',
        frontend_origins='https://app.example.test', public_web_url='https://app.example.test',
        object_storage_public_endpoint='https://media.example.test',object_storage_secret_key='y'*32,
        mfa_encryption_key=Fernet.generate_key().decode(),smtp_host='smtp.example.test',smtp_from_email='sender@example.test')


def test_production_configuration_rejects_development_secrets_without_echoing_them():
    config=production();assert production_problems(config)==[]
    config.database_url='postgresql://lodge:private-but-short@postgres/lodge'
    config.object_storage_secret_key='replace-me-secret'
    config.mfa_encryption_key='invalid'
    problems='; '.join(production_problems(config))
    assert 'DATABASE_URL' in problems and 'OBJECT_STORAGE_SECRET_KEY' in problems
    assert 'MFA_ENCRYPTION_KEY' in problems
    assert 'private-but-short' not in problems and 'replace-me-secret' not in problems


@pytest.mark.parametrize('field,value', [('cookie_secure',False),('frontend_origins','https://app.example.test,http://unsafe.test'),('public_web_url','http://unsafe.test'),('object_storage_public_endpoint','http://unsafe.test'),('smtp_use_tls',False)])
def test_unsafe_deployment_configuration_fails_closed(field,value):
    config=production();setattr(config,field,value)
    assert production_problems(config)


def test_south_african_business_day_does_not_depend_on_server_timezone():
    instant=datetime(2026,11,15,22,30,tzinfo=timezone.utc)
    assert lodge_day(SimpleNamespace(timezone='Africa/Johannesburg'),instant)==date(2026,11,16)
    assert lodge_day(SimpleNamespace(timezone='America/New_York'),instant)==date(2026,11,15)
    with pytest.raises(ValueError):lodge_day(None,datetime(2026,11,15,22,30))


def test_readiness_checks_worker_scheduler_and_storage_without_exception_details():
    class DB:
        def execute(self, query):pass
    class Broker:
        def ping(self):pass
        def get(self,key):return 'ready'
    class Store:
        def head_bucket(self,**kwargs):pass
    result,code=readiness(DB(),Broker(),Store(),'private-bucket')
    assert code==200 and result['status']=='ready'
    class LostWorker(Broker):
        def get(self,key):return None
    result,code=readiness(DB(),LostWorker(),Store(),'private-bucket')
    assert code==503 and result['checks']['worker_scheduler']=='unavailable'
    class BrokenStore:
        def head_bucket(self,**kwargs):raise RuntimeError('secret connection credentials')
    result,code=readiness(DB(),Broker(),BrokenStore(),'private-bucket')
    assert code==503 and 'secret' not in str(result) and 'private-bucket' not in str(result)

def test_scheduler_does_not_require_unneeded_media_or_email_secrets():
 config=production();config.smtp_host='';config.mfa_encryption_key='';config.object_storage_secret_key=''
 assert production_problems(config,component='beat')==[]
 assert production_problems(config,component='worker')


@pytest.mark.parametrize('privileges', [(True,False),(False,True),(True,True)])
def test_privileged_runtime_database_role_is_rejected(privileges):
 from app.services.deployment import validate_runtime
 class Result:
  def one(self):return privileges
 class Connection:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def execute(self,query):return Result()
 class Engine:
  def connect(self):return Connection()
 with pytest.raises(RuntimeError,match='without BYPASSRLS'):
  validate_runtime(production(),Engine())


def test_database_validation_failure_does_not_expose_connection_secret():
 from app.services.deployment import validate_runtime
 class BrokenEngine:
  def connect(self):raise RuntimeError('password=do-not-echo-this')
 with pytest.raises(RuntimeError) as error:
  validate_runtime(production(),BrokenEngine())
 assert 'security-role validation failed' in str(error.value)
 assert 'do-not-echo-this' not in str(error.value)
