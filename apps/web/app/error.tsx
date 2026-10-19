'use client';
import {useEffect} from 'react';
export default function ErrorBoundary({error,reset}:{error:Error & {digest?:string};reset:()=>void}){
 useEffect(()=>{console.error('Lodge CRM client error',error)},[error]);
 return <main className="fatalErrorPage"><section className="panel statePanel"><span className="stateIcon danger">!</span><span className="eyebrow">APPLICATION ERROR</span><h1>Something went wrong</h1><p>The interface hit an unexpected error. Your persisted lodge data has not been deleted.</p><button className="button primary" onClick={reset}>Try again</button>{error?.digest&&<small>Error reference: {error.digest}</small>}</section></main>
}
