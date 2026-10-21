from pydantic import TypeAdapter, EmailStr
from sqlalchemy import select
from .db import SessionLocal, set_rls_context
from .models import User
from .security import hash_password, new_token
from .email_service import issue_invitation
from .config import settings

def main():
    email=str(TypeAdapter(EmailStr).validate_python(input("Super Admin email: ").strip())).lower()
    name=input("Full name: ").strip()
    if len(name)<2:raise SystemExit("Enter a full name")
    with SessionLocal() as db:
        set_rls_context(db,None,True)
        if db.scalar(select(User).where(User.email==email)):raise SystemExit("User already exists; use the platform resend invitation action or password recovery")
        user=User(email=email,full_name=name,password_hash=hash_password(new_token()+new_token()),is_active=False,is_super_admin=True)
        db.add(user);db.flush()
        result=issue_invitation(db,user)
        db.commit()
    if result.get("activation_token"):
        print("Development only: open this private link to set your password:")
        print(settings.public_web_url.rstrip('/')+"/activate#token="+result["activation_token"])
    else:print("Super Admin invitation queued. Start the worker and scheduler; the account owner sets their own password from the email.")
if __name__=="__main__":main()
