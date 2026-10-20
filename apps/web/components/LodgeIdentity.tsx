'use client';
import {useEffect,useState} from 'react';
import {API_URL,lodgeBrandingApi} from '@/lib/api';
export default function LodgeIdentity({lodgeId,name}:{lodgeId:string;name:string}){
 const [brand,setBrand]=useState<{display_name:string;logo_url:string|null}|null>(null);
 const [imageFailed,setImageFailed]=useState(false);
 useEffect(()=>{let active=true;setBrand(null);setImageFailed(false);lodgeBrandingApi.get(lodgeId).then(b=>{if(active)setBrand(b)}).catch(()=>{});return()=>{active=false}},[lodgeId]);
 const title=brand?.display_name||name||'Lodge workspace';
 return <div className="lodgeIdentity"><div className="lodgeLogo">{brand?.logo_url&&!imageFailed?<img src={`${API_URL}${brand.logo_url}`} alt={`${title} logo`} onError={()=>setImageFailed(true)}/>:<span>{title.split(' ').map(w=>w[0]).join('').slice(0,2)}</span>}</div><strong>{title}</strong><small>Powered by SafariOS</small></div>;
}
