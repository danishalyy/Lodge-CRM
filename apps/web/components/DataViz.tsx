'use client';

export type BarDatum={label:string;value:number;hint?:string};

export function BarChart({data,max:providedMax}:{data:BarDatum[];max?:number}){
 const max=Math.max(providedMax||0,...data.map(d=>Number(d.value)||0),1);
 return <div className="premiumChart" role="img" aria-label="Operational bar chart">
  <div className="chartPlot">{data.map((d,i)=>{
   const h=Math.max(3,Math.round((Number(d.value)||0)/max*100));
   return <div className="chartColumn" key={`${d.label}-${i}`} title={`${d.label}: ${d.value}`}>
    <div className="chartValue">{d.value}</div><div className="chartTrack"><div className="chartBar" style={{height:`${h}%`}}/></div><div className="chartLabel">{d.label}</div>
   </div>
  })}</div>
 </div>
}

export function RingChart({value,total,label}:{value:number;total:number;label:string}){
 const safeTotal=Math.max(total,1),pct=Math.max(0,Math.min(100,Math.round((value/safeTotal)*100)));
 const r=40,c=2*Math.PI*r,dash=c*pct/100;
 return <div className="ringChart" role="img" aria-label={`${label}: ${pct}%`}>
  <svg viewBox="0 0 100 100" aria-hidden="true"><circle className="ringTrack" cx="50" cy="50" r={r}/><circle className="ringValue" cx="50" cy="50" r={r} strokeDasharray={`${dash} ${c-dash}`} transform="rotate(-90 50 50)"/></svg>
  <div className="ringCenter"><strong>{pct}%</strong><span>{label}</span></div>
 </div>
}

export type CalendarEvent={date:string;label:string;kind?:'arrival'|'departure'|'activity'|'transfer'|'other'};
const key=(d:Date)=>{const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');return `${y}-${m}-${day}`};
export function OperationsCalendar({events=[],monthDate=new Date()}:{events?:CalendarEvent[];monthDate?:Date}){
 const y=monthDate.getFullYear(),m=monthDate.getMonth();
 const first=new Date(y,m,1),last=new Date(y,m+1,0),start=(first.getDay()+6)%7;
 const cells:(Date|null)[]=Array(start).fill(null);
 for(let d=1;d<=last.getDate();d++)cells.push(new Date(y,m,d));
 while(cells.length%7)cells.push(null);
 const today=key(new Date());
 const grouped=events.reduce<Record<string,CalendarEvent[]>>((a,e)=>{(a[e.date]??=[]).push(e);return a},{});
 return <div className="opsCalendar">
  <div className="calendarWeek">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d=><span key={d}>{d}</span>)}</div>
  <div className="calendarGrid">{cells.map((d,i)=>{
   if(!d)return <div className="calendarCell muted" key={`x-${i}`}/>;
   const k=key(d),items=grouped[k]||[];
   return <div className={`calendarCell ${k===today?'today':''}`} key={k}><div className="calendarDate"><span>{d.getDate()}</span>{items.length>0&&<em>{items.length}</em>}</div><div className="calendarEvents">{items.slice(0,2).map((e,j)=><div key={j} className={`calendarEvent ${e.kind||'other'}`} title={e.label}><i/>{e.label}</div>)}{items.length>2&&<small>+{items.length-2} more</small>}</div></div>
  })}</div>
 </div>
}
