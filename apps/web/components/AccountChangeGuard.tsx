'use client';
import {useEffect} from 'react';
export default function AccountChangeGuard(){
  useEffect(()=>{
    const changed=(event:StorageEvent)=>{
      if(event.key===null||event.key==='active_user_id'||event.key==='active_lodge_id')window.location.reload();
    };
    const lodgeChanged=()=>window.location.reload();
    window.addEventListener('safarios-lodge-changed',lodgeChanged);
    window.addEventListener('storage',changed);
    return ()=>{window.removeEventListener('storage',changed);window.removeEventListener('safarios-lodge-changed',lodgeChanged)};
  },[]);
  return null;
}
