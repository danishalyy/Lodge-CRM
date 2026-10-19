'use client';

import {FormEvent, Suspense, useState} from 'react';
import {useRouter, useSearchParams} from 'next/navigation';
import {authApi} from '@/lib/api';

function ResetPasswordForm(){
  const router = useRouter();
  const q = useSearchParams();
  const token = q.get('token') || '';
  const [pw,setPw] = useState('');
  const [pw2,setPw2] = useState('');
  const [err,setErr] = useState('');
  const [busy,setBusy] = useState(false);

  async function submit(e:FormEvent){
    e.preventDefault();
    setErr('');
    if(pw!==pw2){
      setErr('Passwords do not match');
      return;
    }
    setBusy(true);
    try{
      await authApi.confirmPasswordReset(token,pw);
      router.replace('/login');
    }catch(e:any){
      setErr(e.message);
    }finally{
      setBusy(false);
    }
  }

  return <main style={{minHeight:'100vh',display:'grid',placeItems:'center',padding:24}}>
    <form className="panel" onSubmit={submit} style={{width:'min(430px,100%)'}}>
      <span className="eyebrow">SECURE PASSWORD RESET</span>
      <h1>Choose a new password</h1>
      <p>After updating your password, sign in again with your authenticator if MFA is enabled.</p>
      {!token&&<p className="dangerText">Reset token is missing.</p>}
      <label className="fieldLabel">New password</label>
      <input className="field" type="password" required minLength={12} value={pw} onChange={e=>setPw(e.target.value)} autoComplete="new-password"/>
      <label className="fieldLabel">Confirm password</label>
      <input className="field" type="password" required minLength={12} value={pw2} onChange={e=>setPw2(e.target.value)} autoComplete="new-password"/>
      {err&&<p className="dangerText">{err}</p>}
      <button className="button primary full" disabled={busy||!token}>{busy?'Updating…':'Update password'}</button>
    </form>
  </main>;
}

export default function ResetPassword(){
  return <Suspense fallback={<main style={{minHeight:'100vh',display:'grid',placeItems:'center',padding:24}}><div className="panel">Loading secure reset form…</div></main>}>
    <ResetPasswordForm/>
  </Suspense>;
}
