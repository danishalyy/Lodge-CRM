'use client';
import {useEffect} from 'react';
export default function AccountChangeGuard(){
  useEffect(()=>{
    const changed=(event:StorageEvent)=>{
      if(event.key===null||event.key==='active_user_id')window.location.reload();
    };
    window.addEventListener('storage',changed);
    return ()=>window.removeEventListener('storage',changed);
  },[]);
  return null;
}
