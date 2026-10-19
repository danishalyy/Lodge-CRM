"""Live HTTP acceptance checks. Requires a running local stack and real test credentials."""
import json, os, urllib.error, urllib.request, http.cookiejar

BASE=os.getenv("E2E_BASE_URL","http://localhost:8000")
EMAIL=os.environ["E2E_ADMIN_EMAIL"]
PASSWORD=os.environ["E2E_ADMIN_PASSWORD"]
OTP=os.getenv("E2E_ADMIN_OTP")

jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def req(path,method="GET",body=None,csrf=None):
    data=json.dumps(body).encode() if body is not None else None
    headers={"Content-Type":"application/json"}
    if csrf:headers["X-CSRF-Token"]=csrf
    r=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with opener.open(r,timeout=15) as resp:return resp.status,resp.read(),dict(resp.headers)
    except urllib.error.HTTPError as exc:return exc.code,exc.read(),dict(exc.headers)

status,body,_=req("/health")
assert status==200,(status,body)
status,_,_=req("/api/v1/auth/me")
assert status==401,status
payload={"email":EMAIL,"password":PASSWORD}
if OTP:payload["otp"]=OTP
status,body,_=req("/api/v1/auth/login","POST",payload)
assert status==200,(status,body)
status,body,_=req("/api/v1/auth/me")
assert status==200,(status,body)
me=json.loads(body)
assert "memberships" in me
# Unknown fields must be rejected rather than silently ignored.
status,_,_=req("/api/v1/auth/login","POST",{"email":EMAIL,"password":PASSWORD,"unknown_field":True})
assert status==422,status
print("live smoke checks passed")
