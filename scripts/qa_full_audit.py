#!/usr/bin/env python3
from pathlib import Path
import ast,re,sys
root=Path(__file__).resolve().parents[1]
main=(root/'apps/api/app/main.py').read_text()
web=root/'apps/web'
issues=[]
# Route-level guard audit
routes=[]
for source in [main,(root/'apps/api/app/account_routes.py').read_text(), (root/'apps/api/app/group_routes.py').read_text(), (root/'apps/api/app/ai/routes.py').read_text(), (root/'apps/api/app/ai/knowledge_routes.py').read_text()]:
    for n in ast.parse(source).body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            src=ast.get_source_segment(source,n) or ''
            for d in n.decorator_list:
                if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and isinstance(d.func.value,ast.Name) and d.func.value.id in {'app','router'} and d.func.attr in {'get','post','patch','put','delete'}:
                    path=ast.literal_eval(d.args[0]); dec=ast.get_source_segment(source,d) or ''; method=d.func.attr.upper();routes.append((method,path,n.name,dec,src))
for method,path,name,dec,src in routes:
    if path.startswith('/api/v1/lodges/{lodge_id}'):
        if 'Depends(require_permission' not in src and 'Depends(require_lodge_access' not in src:issues.append(f'{method} {path}: missing lodge authorization')
        if method in {'POST','PATCH','PUT','DELETE'} and 'write=True' not in src and 'ensure_subscription_write_allowed' not in src:issues.append(f'{method} {path}: missing subscription write guard')
    if path.startswith('/api/v1/platform/') and 'Depends(require_super_admin)' not in src:issues.append(f'{method} {path}: missing super-admin guard')
    if method in {'POST','PATCH','PUT','DELETE'} and path not in {'/api/v1/auth/invitations/preview','/api/v1/auth/login','/api/v1/auth/activate','/api/v1/auth/password-reset/request','/api/v1/auth/password-reset/confirm'} and 'require_csrf' not in dec:issues.append(f'{method} {path}: missing CSRF')
print(f'API routes audited: {len(routes)}')
print(f'Guard issues: {len(issues)}')
for i in issues: print(' -',i)
# UI page coverage
mods=(web/'lib/modules.ts').read_text(); keys=re.findall(r"\['([^']+)','",mods)
missing=[k for k in keys if not (web/'app'/'(app)'/k/'page.tsx').exists()]
print(f'Visible modules audited: {len(keys)}; missing pages: {len(missing)}')
for k in missing:print(' - missing page',k)
if issues or missing:sys.exit(1)
print('FULL STATIC QA AUDIT: PASS')
