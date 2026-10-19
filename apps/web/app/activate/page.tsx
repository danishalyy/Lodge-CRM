'use client';
import {FormEvent,useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import {authApi,setActiveLodgeId} from '@/lib/api';
export default function Activate(){
 const router=useRouter();const[token,setToken]=useState('');const[password,setPassword]=useState(''),[confirm,setConfirm]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{setToken(new URLSearchParams(window.location.search).get('token')||'')},[]);
 async function submit(e:FormEvent){e.preventDefault();if(!token)return setError('Activation token is missing.');if(password!==confirm)return setError('Passwords do not match.');setBusy(true);setError('');try{await authApi.activate(token,password);const me=await authApi.me();if(me.memberships?.[0])setActiveLodgeId(me.memberships[0].lodge_id);router.replace('/dashboard')}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 return <main style={{minHeight:'100vh',display:'grid',placeItems:'center',padding:24}}><form className="panel" onSubmit={submit} style={{width:'min(430px,100%)'}}><div className="brand" style={{marginBottom:24}}><div className="brandMark">L</div><div>Lodge <span>CRM</span></div></div><span className="eyebrow">ACCOUNT ACTIVATION</span><h1 style={{margin:'8px 0'}}>Set your password</h1><p style={{color:'var(--tx2)'}}>This one-time link activates your lodge account.</p><label className="fieldLabel">Password</label><input className="field" type="password" minLength={12} required value={password} onChange={e=>setPassword(e.target.value)} autoComplete="new-password"/><label className="fieldLabel">Confirm password</label><input className="field" type="password" minLength={12} required value={confirm} onChange={e=>setConfirm(e.target.value)} autoComplete="new-password"/>{error&&<p className="dangerText">{error}</p>}<button className="button primary full" disabled={busy}>{busy?'Activating…':'Activate account'}</button></form></main>
}
