"""SMTP tests never contact a real email provider."""
import ssl
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from app import email_service as mail

@pytest.mark.parametrize('implicit',[False,True])
def test_gmail_uses_verified_transport_and_multipart(monkeypatch,implicit):
    for key,value in {'smtp_host':'smtp.gmail.com','smtp_port':465 if implicit else 587,'smtp_username':'sender@gmail.com','smtp_password':'test-only','smtp_from_email':'sender@gmail.com','smtp_use_tls':not implicit,'smtp_use_ssl':implicit}.items():
        monkeypatch.setattr(mail.settings,key,value)
    constructor=MagicMock();session=constructor.return_value.__enter__.return_value
    monkeypatch.setattr(mail.smtplib,'SMTP_SSL' if implicit else 'SMTP',constructor)
    mail.send_email('owner@business.example','Welcome','Your private invitation',mail.render_email('Welcome <owner>','Safe & private'))
    if implicit:context=constructor.call_args.kwargs['context']
    else:context=session.starttls.call_args.kwargs['context']
    assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname
    session.login.assert_called_once_with('sender@gmail.com','test-only')
    message=session.send_message.call_args.args[0]
    assert message.get_content_type()=='multipart/alternative'
    assert '&lt;owner&gt;' in message.get_payload()[1].get_content()
    assert '<owner>' not in message.get_payload()[1].get_content()


def test_gmail_rejects_unencrypted_delivery(monkeypatch):
    for key,value in {'smtp_host':'smtp.gmail.com','smtp_from_email':'sender@gmail.com','smtp_use_tls':False,'smtp_use_ssl':False}.items():monkeypatch.setattr(mail.settings,key,value)
    with pytest.raises(HTTPException) as exc:mail.validate_email_configuration()
    assert exc.value.status_code==503
