import getpass
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .security import hash_password

def main():
    email=input("Super Admin email: ").strip().lower()
    name=input("Full name: ").strip()
    p1=getpass.getpass("Password (minimum 12 chars): ")
    p2=getpass.getpass("Confirm password: ")
    if len(p1)<12: raise SystemExit("Password too short")
    if p1!=p2: raise SystemExit("Passwords do not match")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email==email)): raise SystemExit("User already exists")
        db.add(User(email=email,full_name=name,password_hash=hash_password(p1),is_active=True,is_super_admin=True))
        db.commit()
    print("Super Admin created.")
if __name__ == "__main__": main()
