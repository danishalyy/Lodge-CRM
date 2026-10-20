'use client';
import {useState} from 'react';
import {authApi} from '@/lib/api';

export default function SignOutButton(){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function signOut(){
    setBusy(true);setError('');
    try{await authApi.logout();window.location.replace('/login')}
    catch(e){setError(e instanceof Error?e.message:'Unable to sign out');setBusy(false)}
  }
  return <span><button className="button secondary" disabled={busy} onClick={signOut}>{busy?'Signing out…':'Sign out'}</button>{error&&<span role="alert">{error}</span>}</span>;
}
