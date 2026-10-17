// Exercise the actual UI event handlers with controlled asynchronous API replies.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map(),pending=[],downloads=[],released=[];
const html=fs.readFileSync(__dirname+'/static/index.html','utf8'),lookups=new Set();
let focused=null;
class Element{
  constructor(){this.value='';this.hidden=false;this.disabled=false;this.children=[];this.listeners={};this.dataset={};this.attributes={};const classes=new Set();this.classList={add(...xs){xs.forEach(x=>classes.add(x));},remove(...xs){xs.forEach(x=>classes.delete(x));},contains(x){return classes.has(x);},toggle(x,on){on??=!classes.has(x);on?classes.add(x):classes.delete(x);return on;}};this.style={};}
  addEventListener(event,handler){this.listeners[event]=handler;}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  removeAttribute(key){delete this[key];}
  setAttribute(key,value){this.attributes[key]=value;}
  getAttribute(key){return this.attributes[key];}
  focus(){focused=this;}
  getContext(){return{drawImage(){},beginPath(){},lineTo(){},moveTo(){},closePath(){},stroke(){}};}
  click(){if(this.download)downloads.push(this.href);}
}
function el(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);}
for(const tag of html.matchAll(/<([a-z][\w-]*)\b([^>]*)>/gi)){
  const attrs=tag[2],id=attrs.match(/\bid="([^"]+)"/)?.[1];if(!id)continue;
  assert(!elements.has(id),'duplicate HTML id '+id);const node=el(id);
  for(const attr of attrs.matchAll(/([\w-]+)="([^"]*)"/g)){node.attributes[attr[1]]=attr[2];if(attr[1].startsWith('data-'))node.dataset[attr[1].slice(5)]=attr[2];}
  node.hidden=/\bhidden(?:\s|$)/.test(attrs);node.disabled=/\bdisabled(?:\s|$)/.test(attrs);
  node.value=node.attributes.value||'';node.classList.add(...(node.attributes.class||'').split(/\s+/).filter(Boolean));
}
const htmlIds=new Set(elements.keys());
function select(selector){return [...elements.values()].filter(node=>selector==='[data-tab]'?'tab' in node.dataset:selector==='[data-scan]'?'scan' in node.dataset:selector==='.upload-zone'&&node.classList.contains('upload-zone'));}
const blobs=new Map();let urls=0;
const context=vm.createContext({
  document:{getElementById(id){lookups.add(id);assert(htmlIds.has(id),'UI binding missing in HTML: '+id);return el(id);},querySelectorAll:select,createElement:()=>new Element(),createDocumentFragment:()=>new Element()},
  window:{addEventListener(){}},navigator:{},console,Date,Math,AbortController,Blob,File,
  URL:{createObjectURL(blob){const url='blob:'+ ++urls;blobs.set(url,blob);return url;},revokeObjectURL(){}},
  Image:class{constructor(){this.naturalWidth=600;this.naturalHeight=400;}set src(value){this._src=value;this.onload?.();}async decode(){}},
  FormData:class{constructor(){this.values={};}append(k,v){this.values[k]=v;}},
  setTimeout(){return 0;},clearTimeout(){},
  fetch(path,options={}){
    if(path==='/api/health')return Promise.resolve({ok:true,json:async()=>({models:{ocr:true},face_reference_source:'scanned_document_front'})});
    if(options.method==='DELETE'){released.push(path);return Promise.resolve({ok:true,json:async()=>({deleted:true})});}
    return new Promise(resolve=>pending.push({path,options,reply(data,ok=true,status=ok?200:422){resolve({ok,status,json:async()=>data,blob:async()=>new Blob(['photo'],{type:'image/jpeg'})});}}));
  }
});
vm.runInContext(fs.readFileSync(__dirname+'/static/app.js','utf8'),context);
function file(name){return{name,size:100,type:'image/jpeg'};}
function data(id='000000000001',address=''){return{document_token:'token-'+id,document_detection:{side:'front'},fields:{id_number:id,full_name:'NGUYỄN VĂN AN',date_of_birth:'2000-02-01',residence_address:address},lines:[],warnings:[],elapsed_ms:10,image_width:600,image_height:400,normalized_preview:'data:image/jpeg;base64,'+id};}
const run=()=>el('ocr-run').listeners.click();
const choose=f=>el('ocr-file').listeners.change({target:{files:[f]}});
const back=f=>el('back-file').listeners.change({target:{files:[f]}});
function reply(result,ok=true){assert(pending.length);pending.shift().reply(result,ok);}

(async()=>{
  assert(!html.includes('id="reference-file"'));assert(!html.includes('id="reuse-ocr"'));
  const nav=select('[data-tab]');assert.equal(nav.length,3);
  nav[1].listeners.click();assert.equal(el('panel-face').hidden,false);assert.equal(el('panel-ocr').hidden,true);assert.equal(nav[1].getAttribute('aria-selected'),'true');
  nav[1].listeners.keydown({key:'ArrowDown',preventDefault(){}});assert.equal(el('panel-live').hidden,false);assert.equal(focused,nav[2]);
  nav[0].listeners.click();
  el('scan-tab-back').listeners.click();assert.equal(el('scan-back').hidden,false);assert.equal(el('scan-front').hidden,true);
  el('scan-tab-back').listeners.keydown({key:'Home',preventDefault(){}});assert.equal(el('scan-front').hidden,false);assert.equal(focused,el('scan-tab-front'));
  el('face-threshold').value='0.363';
  await choose(file('A.jpg'));const old=run();await choose(file('B.jpg'));const fresh=run();
  pending[1].reply(data('000000000002'));pending.splice(1,1);await fresh;
  reply(data('000000000001'));await old;
  assert.equal(el('field-id').value,'000000000002','old OCR response must not overwrite new front');
  assert.equal(el('front-detected').hidden,false);assert.equal(el('front-detected-id').textContent,'000000000002');assert.equal(el('front-detected-dob').textContent,'01/02/2000');
  el('field-name').value='Tên đã sửa';assert.equal(el('front-detected-name').textContent,'NGUYỄN VĂN AN','editing final fields must preserve original scan result');
  assert(el('ocr-zone').classList.contains('has-file'));assert.equal(el('continue-face').disabled,false);
  el('continue-face').listeners.click();assert.equal(el('panel-face').hidden,false);nav[0].listeners.click();
  assert.equal(el('reference-preview').src,data('000000000002').normalized_preview);assert.equal(el('selfie-file').disabled,false);
  assert(released.includes('/api/documents/token-000000000001'),'stale OCR token must be released');
  await back(file('B-back.jpg'));const b=el('back-run').listeners.click();reply(data('000000000002','Địa chỉ B'));await b;
  assert.equal(el('field-address').value,'Địa chỉ B');
  assert.equal(el('back-detected').hidden,false);assert.equal(el('back-detected-address').textContent,'Địa chỉ B');assert.match(el('back-detected-verify').textContent,/khớp/);assert.equal(el('address-origin').textContent,'Mặt sau cùng thẻ');
  await back(file('wrong-back.jpg'));assert.equal(el('field-address').value,'');
  assert.equal(el('back-detected').hidden,true);
  const mismatch=el('back-run').listeners.click();reply(data('000000000003','Sai thẻ'));await mismatch;
  assert.equal(el('field-address').value,'');assert.match(el('back-message').textContent,/không cùng/);
  assert.equal(el('back-detected').hidden,true,'a mismatching back must not be shown as accepted');
  await back(file('B-back-2.jpg'));const stale=el('back-run').listeners.click();await choose(file('C.jpg'));
  reply(data('000000000002','Địa chỉ cũ'));await stale;
  assert.equal(el('field-address').value,'');assert.equal(el('field-id').value,'');assert.equal(el('back-run').disabled,true);
  assert.equal(el('front-detected').hidden,true);assert.equal(el('back-detected').hidden,true);assert.equal(el('continue-face').disabled,true);
  const c=run();reply(data('000000000004','Địa chỉ mặt trước'));await c;
  await back(file('C-back.jpg'));assert.equal(el('field-address').value,'Địa chỉ mặt trước');
  const cb=el('back-run').listeners.click();reply(data('000000000004','Địa chỉ mặt sau'));await cb;
  el('export-ocr').listeners.click();const exported=JSON.parse(await blobs.get(downloads.at(-1)).text());
  assert.equal(exported.fields.residence_address,'Địa chỉ mặt sau');assert.equal(exported.address_source,'back');assert(!('normalized_preview' in exported.front));
  assert(!('document_token' in exported.front),'reference token must not be exported');
  await choose(file('D.jpg'));const failed=run();reply({detail:'Model unavailable'},false);await failed;
  assert.equal(el('field-id').value,'');assert.equal(el('field-address').value,'');assert.equal(el('export-ocr').disabled,true);
  assert.equal(el('front-detected').hidden,true,'failed scan must clear previous summary');
  await choose(file('back-in-front.jpg'));const wrongFront=run();reply({detail:'Ảnh này là mặt sau, nhưng bạn đang quét mặt trước.',code:'wrong_document_side'},false);await wrongFront;
  assert.match(el('ocr-message').textContent,/mặt sau/);assert.equal(el('field-id').value,'');assert.equal(el('export-ocr').disabled,true);
  await choose(file('front.jpg'));const correctFront=run();reply(data('000000000005'));await correctFront;
  await back(file('front-in-back.jpg'));const wrongBack=el('back-run').listeners.click();reply({detail:'Ảnh này là mặt trước, nhưng bạn đang quét mặt sau.',code:'wrong_document_side'},false);await wrongBack;
  assert.match(el('back-message').textContent,/mặt trước/);assert.equal(el('field-address').value,'');assert.equal(el('field-id').value,'000000000005');
  const deviceSelfie=file('selfie.jpg');el('selfie-file').listeners.change({target:{files:[deviceSelfie]}});
  assert.equal(el('face-run').disabled,false);assert.match(el('selfie-source').textContent,/thiết bị/);
  const match=el('face-run').listeners.click();assert.equal(pending[0].path,'/api/face-match');assert.equal(pending[0].options.body.values.document_token,'token-000000000005');assert(!('reference' in pending[0].options.body.values));
  const matched={score:.62,threshold:.363,matched:true,elapsed_ms:10,reference_crop:'front-crop',selfie_crop:'selfie-crop',note:'Locked reference'};
  reply(matched);await match;assert.equal(el('face-result').hidden,false);
  assert.match(el('match-title').textContent,/khớp/i);assert.equal(el('match-verdict').className,'match-verdict');assert.equal(el('match-symbol').textContent,'✓');
  const noMatch=el('face-run').listeners.click();reply({...matched,matched:false,score:.1});await noMatch;assert.match(el('match-verdict').className,/bad/);
  const late=el('face-run').listeners.click();await choose(file('another-front.jpg'));
  assert.equal(el('reference-preview').hidden,true);assert.equal(el('selfie-preview').hidden,true);assert.equal(el('face-run').disabled,true);assert.equal(el('selfie-file').disabled,true);
  reply(matched);await late;assert.equal(el('face-result').hidden,true,'old match must not survive changing CCCD');
  const newScan=run();reply(data('000000000006'));await newScan;
  vm.runInContext("liveToken='approved-camera';renderLive({actions:[{key:'blink',label:'Nhắm mắt'}],completed:['blink'],current_index:1,calibrated:true,challenge_completed:true,prototype_passed:true,pad_score:.9,pad_threshold:.7,pad_samples:5,prompt:'Đã đạt',failed_reason:''})",context);
  assert.equal(el('use-live-selfie').disabled,false);
  const camera=el('use-live-selfie').listeners.click();assert.equal(pending[0].path,'/api/liveness/approved-camera/selfie');reply({});await camera;
  assert.equal(el('face-run').disabled,false);assert.match(el('selfie-source').textContent,/camera đã đạt/);assert.equal(el('reference-preview').src,data('000000000006').normalized_preview);
  vm.runInContext("liveToken='old-camera'",context);const staleCamera=el('use-live-selfie').listeners.click();await choose(file('last-front.jpg'));reply({});await staleCamera;
  assert.equal(el('selfie-preview').hidden,true);assert.equal(el('face-run').disabled,true);
  const lastScan=run();reply(data('000000000007'));await lastScan;
  el('selfie-file').listeners.change({target:{files:[deviceSelfie]}});const expired=el('face-run').listeners.click();pending.shift().reply({detail:'Hãy đọc lại mặt trước.'},false,410);await expired;
  assert.equal(el('reference-preview').hidden,true);assert.equal(el('face-run').disabled,true);assert.equal(el('selfie-file').disabled,true);assert.match(el('face-message').textContent,/đọc lại/);
  console.log('PASS: Actual HTML bindings; navigation/keyboard; per-scan summaries/reset; locked reference; token-only matching; device/camera selfie; match verdicts; stale results and expiry.');
})().catch(error=>{console.error(error);process.exitCode=1;});
