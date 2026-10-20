export type QueueScope = {userId:string;lodgeId:string};
export type QueuedSighting = {id:string;payload:any;photo?:Blob;photoName?:string;photoType?:string;createdAt:string};
type StoredSighting = QueuedSighting & QueueScope;
const DB='lodge-crm-offline',STORE='wildlife-queue-v2';

function validate(scope:QueueScope){
  if(!scope.userId||!scope.lodgeId)throw new Error('Sign in and select a lodge before accessing offline records');
}
function openDb(){
  return new Promise<IDBDatabase>((resolve,reject)=>{
    const r=indexedDB.open(DB,2);
    r.onupgradeneeded=()=>{
      // Legacy unscoped records remain untouched; never assign them to a new user.
      if(!r.result.objectStoreNames.contains(STORE)){
        const store=r.result.createObjectStore(STORE,{keyPath:['userId','lodgeId','id']});
        store.createIndex('owner',['userId','lodgeId']);
      }
    };
    r.onsuccess=()=>resolve(r.result);
    r.onerror=()=>reject(r.error);
    r.onblocked=()=>reject(new Error('Close older Lodge CRM tabs to update offline storage'));
  });
}
export async function queueSighting(scope:QueueScope,item:QueuedSighting){
  validate(scope);const db=await openDb();
  return new Promise<void>((resolve,reject)=>{
    const tx=db.transaction(STORE,'readwrite');
    tx.objectStore(STORE).put({...item,...scope} as StoredSighting);
    tx.oncomplete=()=>{db.close();resolve()};
    tx.onerror=tx.onabort=()=>{db.close();reject(tx.error)};
  });
}
export async function queuedSightings(scope:QueueScope){
  validate(scope);const db=await openDb();
  return new Promise<QueuedSighting[]>((resolve,reject)=>{
    const tx=db.transaction(STORE);
    const r=tx.objectStore(STORE).index('owner').getAll([scope.userId,scope.lodgeId]);
    tx.oncomplete=()=>{db.close();resolve(r.result)};
    tx.onerror=tx.onabort=()=>{db.close();reject(tx.error)};
  });
}
export async function removeQueuedSighting(scope:QueueScope,id:string){
  validate(scope);const db=await openDb();
  return new Promise<void>((resolve,reject)=>{
    const tx=db.transaction(STORE,'readwrite');
    tx.objectStore(STORE).delete([scope.userId,scope.lodgeId,id]);
    tx.oncomplete=()=>{db.close();resolve()};
    tx.onerror=tx.onabort=()=>{db.close();reject(tx.error)};
  });
}
