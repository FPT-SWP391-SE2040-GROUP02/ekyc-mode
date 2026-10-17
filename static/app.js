'use strict';
const $ = id => document.getElementById(id);
const files = {ocr:null,back:null,selfie:null,pad:null};
let frontVersion=0,backVersion=0,backResult=null,addressSource=null,frontAbort=null,backAbort=null,documentToken=null,faceVersion=0,faceAbort=null,selfieSource=null;
const previews = {};
let ocrResult = null, ocrImage = null, stream = null, liveToken = null, liveRunning = false, liveVersion = 0, liveDeadline = 0, cameraVersion = 0;
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,4500);}
function status(id,text,kind=''){$(id).textContent=text;$(id).className=`status ${kind}`;}
function notice(id,text,kind=''){$(id).textContent=text;$(id).className=`notice ${kind}`;}
function tab(key){if(key!=='live'&&stream)stopCamera();document.querySelectorAll('[data-tab]').forEach(el=>{const active=el.dataset.tab===key;el.classList.toggle('active',active);el.setAttribute('aria-selected',String(active));el.tabIndex=active?0:-1;$(`panel-${el.dataset.tab}`).hidden=!active;});$('section-label').textContent={ocr:'Căn cước',face:'Khuôn mặt',live:'Camera'}[key];}
function bindTabKeyboard(selector,activate,keys){const buttons=[...document.querySelectorAll(selector)];buttons.forEach((button,index)=>button.addEventListener('keydown',event=>{if(![...keys,'Home','End'].includes(event.key))return;event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key===keys[1]?1:-1)+buttons.length)%buttons.length;activate(buttons[next]);buttons[next].focus();}));}
document.querySelectorAll('[data-tab]').forEach(el=>el.addEventListener('click',()=>tab(el.dataset.tab)));
bindTabKeyboard('[data-tab]',button=>tab(button.dataset.tab),['ArrowUp','ArrowDown']);
function scanTab(key){document.querySelectorAll('[data-scan]').forEach(button=>{const active=button.dataset.scan===key;button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;});$('scan-front').hidden=key!=='front';$('scan-back').hidden=key!=='back';}
document.querySelectorAll('[data-scan]').forEach(button=>button.addEventListener('click',()=>scanTab(button.dataset.scan)));
bindTabKeyboard('[data-scan]',button=>scanTab(button.dataset.scan),['ArrowLeft','ArrowRight']);
async function api(path,options={}){const res=await fetch(path,options);let body;try{body=await res.json();}catch{throw new Error('Không nhận được kết quả. Kiểm tra chương trình đang chạy.');}if(!res.ok){const error=new Error(typeof body.detail==='string'?body.detail:'Dữ liệu đầu vào chưa hợp lệ.');error.status=res.status;throw error;}return body;}
function validFile(file){if(!file)return false;if(file.size>8*1024*1024){toast('Ảnh phải nhỏ hơn 8 MB.');return false;}if(!['image/jpeg','image/png','image/webp'].includes(file.type)){toast('Hãy chọn ảnh JPG, PNG hoặc WebP.');return false;}return true;}
function setPreview(key,file,id){if(previews[key])URL.revokeObjectURL(previews[key]);previews[key]=URL.createObjectURL(file);$(id).src=previews[key];$(id).hidden=false;}
function faceButtons(){
  $('face-run').disabled=!(documentToken&&files.selfie);
  $('selfie-file').disabled=!documentToken;$('selfie-camera').disabled=!documentToken;
  $('continue-face').disabled=!documentToken;
}
function clearDetected(side){$(`${side}-detected`).hidden=true;for(const key of side==='front'?['id','name','dob','address']:['id','address'])$(`${side}-detected-${key}`).textContent='—';$(`${side}-detected-meta`).textContent='';if(side==='back')$('back-detected-verify').textContent='';}
function updateAddressOrigin(){$('address-origin').textContent=addressSource==='back'?'Mặt sau cùng thẻ':addressSource==='front'?'Mặt trước căn cước':'Chưa có địa chỉ';}
function renderDetected(side,result,verify=''){
  const f=result.fields,prefix=`${side}-detected-`;$(`${side}-detected`).hidden=false;
  $(prefix+'id').textContent=f.id_number||'Chưa đọc được';$(prefix+'address').textContent=f.residence_address||(side==='front'?'Chưa có; thêm mặt sau nếu dùng thẻ mới.':'Chưa đọc được');
  if(side==='front'){$(prefix+'name').textContent=f.full_name||'Chưa đọc được';$(prefix+'dob').textContent=/^\d{4}-\d{2}-\d{2}$/.test(f.date_of_birth)?f.date_of_birth.split('-').reverse().join('/'):(f.date_of_birth||'Chưa đọc được');}
  else $('back-detected-verify').textContent=verify;
  $(prefix+'meta').textContent=`Lần quét ${new Date().toLocaleTimeString('vi-VN')} · ${(result.elapsed_ms/1000).toFixed(1)} giây`;
}
function clearFaceResult(){
  faceVersion++;faceAbort?.abort();$('face-result').hidden=true;$('face-empty').hidden=false;
  $('ref-crop').removeAttribute('src');$('selfie-crop').removeAttribute('src');$('face-score').textContent='—';$('face-meter').style.width='0%';
  status('face-status','Chưa chạy');
  $('match-title').textContent='Kết quả so khớp';$('match-caption').textContent='';$('match-verdict').className='match-verdict';
}
function releaseReference(token){if(token)api(`/api/documents/${token}`,{method:'DELETE'}).catch(()=>{});}
function invalidateReference(){
  const oldToken=documentToken;documentToken=null;releaseReference(oldToken);clearFaceResult();
  $('reference-preview').hidden=true;$('reference-preview').removeAttribute('src');$('reference-placeholder').hidden=false;
  $('reference-meta').textContent='Đọc mặt trước ở mục Đọc CCCD để bắt đầu.';
  files.selfie=null;selfieSource=null;$('selfie-file').value='';$('selfie-preview').hidden=true;$('selfie-preview').removeAttribute('src');
  $('selfie-zone').classList.remove('has-file');
  if(previews.selfie){URL.revokeObjectURL(previews.selfie);delete previews.selfie;}
  $('selfie-source').textContent='Chưa có selfie.';notice('face-message','Hãy đọc mặt trước CCCD trước khi so khớp.');
  $('use-live-selfie').disabled=true;if(liveToken)void stopLive();faceButtons();
}
function bindReference(result){
  documentToken=result.document_token||null;
  if(documentToken){$('reference-preview').src=result.normalized_preview;$('reference-preview').hidden=false;$('reference-placeholder').hidden=true;$('reference-meta').textContent='Đã khóa mặt trước từ mục Đọc CCCD.';notice('face-message','Mặt trước đã sẵn sàng. Chọn selfie từ thiết bị hoặc kiểm tra camera.');}
  else{$('reference-meta').textContent='Chưa lấy được khuôn mặt trên mặt trước. Hãy chọn ảnh thẻ rõ hơn và đọc lại.';notice('face-message','Chưa có ảnh CCCD hợp lệ để so khớp.','busy');}
  faceButtons();
}
function chooseSelfie(file,source='device'){
  if(!documentToken){toast('Hãy đọc mặt trước CCCD trước khi chọn selfie.');return;}
  if(!validFile(file))return;clearFaceResult();files.selfie=file;selfieSource=source;setPreview('selfie',file,'selfie-preview');
  $('selfie-zone').classList.add('has-file');
  $('selfie-source').textContent=source==='camera'?'Selfie từ phiên camera đã đạt thử thách.':'Selfie được chọn từ thiết bị.';
  notice('face-message','Ảnh CCCD đã khóa. Bấm So khớp để đối chiếu selfie.');faceButtons();
}
function rawLines(id,countId,result){
  const fragment=document.createDocumentFragment();
  for(const line of result.lines){const div=document.createElement('div');div.className='raw-line';const span=document.createElement('span');span.textContent=line.text;const score=document.createElement('small');score.textContent=`điểm ${line.score.toFixed(3)}`;div.append(span,score);fragment.append(div);}
  $(id).replaceChildren(fragment);$(countId).textContent=`(${result.lines.length} dòng)`;
}
function backButtons(){$('back-run').disabled=!(files.back&&ocrResult?.fields.id_number);}
function resetBack(){
  backVersion++;backAbort?.abort();backResult=null;files.back=null;$('back-file').value='';
  clearDetected('back');$('back-zone').classList.remove('has-file');
  if(previews.back){URL.revokeObjectURL(previews.back);delete previews.back;}
  $('back-preview').hidden=true;$('back-preview').removeAttribute('src');$('back-lines').replaceChildren();$('back-line-count').textContent='';
  $('back-run').disabled=true;$('back-file-meta').textContent='Đọc mặt trước trước khi thêm mặt sau.';notice('back-message','Chưa chọn mặt sau.');
}
async function chooseOCR(file){
  frontVersion++;frontAbort?.abort();resetBack();files.ocr=null;ocrResult=null;ocrImage=null;addressSource=null;
  clearDetected('front');updateAddressOrigin();$('ocr-zone').classList.remove('has-file');scanTab('front');
  $('export-ocr').disabled=true;$('ocr-lines').replaceChildren();$('line-count').textContent='';
  ['id','name','dob','address'].forEach(k=>$(`field-${k}`).value='');
  $('ocr-image-stage').hidden=true;$('ocr-run').disabled=true;invalidateReference();
  status('ocr-status','Chưa chạy');notice('ocr-message','Chọn ảnh mặt trước để đọc thông tin.');
  if(!validFile(file))return;
  files.ocr=file;$('ocr-file-meta').textContent=`${file.name} · ${(file.size/1024).toFixed(0)} KB`;$('ocr-run').disabled=false;
  $('ocr-zone').classList.add('has-file');
  if(previews.ocr)URL.revokeObjectURL(previews.ocr);previews.ocr=URL.createObjectURL(file);
  const image=new Image();ocrImage=image;image.onload=()=>{if(files.ocr!==file)return;const canvas=$('ocr-canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;canvas.getContext('2d').drawImage(image,0,0);$('ocr-image-stage').hidden=false;};image.src=previews.ocr;
}
function chooseBack(file){
  backVersion++;backAbort?.abort();backResult=null;files.back=null;
  clearDetected('back');$('back-zone').classList.remove('has-file');
  if(addressSource==='back'){$('field-address').value=ocrResult?.fields.residence_address||'';addressSource=$('field-address').value?'front':null;}
  $('back-lines').replaceChildren();$('back-line-count').textContent='';$('back-preview').hidden=true;
  updateAddressOrigin();
  if(validFile(file)){files.back=file;setPreview('back',file,'back-preview');$('back-zone').classList.add('has-file');$('back-file-meta').textContent=file.name;notice('back-message',ocrResult?.fields.id_number?'Bấm Đọc nơi cư trú từ mặt sau.':'Hãy đọc mặt trước trước.');}
  backButtons();
}
$('back-file').addEventListener('change',e=>chooseBack(e.target.files[0]));
$('ocr-file').addEventListener('change',e=>chooseOCR(e.target.files[0]));
$('selfie-file').addEventListener('change',e=>chooseSelfie(e.target.files[0]));
$('selfie-camera').addEventListener('click',()=>{if(documentToken){tab('live');toast('Mở camera, làm thử thách rồi bấm Dùng selfie đã đạt thử thách.');}});
$('change-document').addEventListener('click',()=>tab('ocr'));
$('continue-face').addEventListener('click',()=>{if(documentToken)tab('face');});
$('pad-file').addEventListener('change',e=>{const file=e.target.files[0];if(validFile(file)){files.pad=file;$('pad-run').disabled=false;}});
for(const zone of document.querySelectorAll('.upload-zone')){zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('drag');});zone.addEventListener('dragleave',()=>zone.classList.remove('drag'));zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('drag');const file=e.dataTransfer.files[0];const id=zone.getAttribute('for');if(id==='ocr-file')chooseOCR(file);else if(id==='back-file')chooseBack(file);else if(id==='selfie-file')chooseSelfie(file);});}
$('sample-btn').addEventListener('click',async()=>{try{const response=await fetch('/api/sample-document');if(!response.ok)throw new Error('Không tải được ảnh mẫu.');await chooseOCR(new File([await response.blob()],'mau-chu-OCR.png',{type:'image/png'}));toast('Đây là ảnh chữ giả lập, chưa phải bài kiểm tra CCCD thực tế.');}catch(e){toast(e.message);}});
$('ocr-run').addEventListener('click',async()=>{
  const selected=files.ocr;if(!selected)return;
  const version=++frontVersion;frontAbort?.abort();frontAbort=new AbortController();
  resetBack();invalidateReference();ocrResult=null;addressSource=null;['id','name','dob','address'].forEach(k=>$(`field-${k}`).value='');$('export-ocr').disabled=true;
  clearDetected('front');updateAddressOrigin();
  $('ocr-run').disabled=true;status('ocr-status','Đang đọc…','busy');notice('ocr-message','Model đang đọc ảnh bằng CPU. Lần đầu cần nạp model…','busy');
  let pendingToken=null;
  try{
    const form=new FormData();form.append('file',selected);form.append('side','front');
    const result=await api('/api/ocr',{method:'POST',body:form,signal:frontAbort.signal});
    pendingToken=result.document_token;
    if(version!==frontVersion||files.ocr!==selected){releaseReference(result.document_token);return;}
    const image=new Image();image.src=result.normalized_preview;await image.decode();
    if(version!==frontVersion||files.ocr!==selected){releaseReference(result.document_token);return;}
    ocrResult=result;bindReference(result);$('field-id').value=result.fields.id_number;$('field-name').value=result.fields.full_name;$('field-dob').value=result.fields.date_of_birth;$('field-address').value=result.fields.residence_address||'';addressSource=$('field-address').value?'front':null;
    renderDetected('front',result);updateAddressOrigin();
    rawLines('ocr-lines','line-count',result);
    const canvas=$('ocr-canvas');canvas.width=result.image_width;canvas.height=result.image_height;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0,canvas.width,canvas.height);ctx.strokeStyle='#169c77';ctx.lineWidth=Math.max(2,canvas.width/550);
    for(const line of result.lines){if(!line.box)continue;ctx.beginPath();line.box.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.stroke();}
    const message=[...result.warnings];if(!result.fields.residence_address)message.push('Nếu dùng thẻ Căn cước mới, thêm mặt sau để đọc nơi cư trú.');
    status('ocr-status',`Mặt trước · ${(result.elapsed_ms/1000).toFixed(1)} giây`,result.fields.id_number?'good':'bad');notice('ocr-message','Đã nhận diện mặt trước. '+(message.join(' ')||'Đã đọc thông tin. Hãy đối chiếu ảnh gốc.'),'good');$('export-ocr').disabled=false;backButtons();
    pendingToken=null;
  }catch(e){releaseReference(pendingToken);if(version!==frontVersion)return;if(pendingToken&&documentToken===pendingToken)invalidateReference();status('ocr-status','Chưa đọc được','bad');notice('ocr-message',e.message,'bad');}
  finally{if(version===frontVersion)$('ocr-run').disabled=!files.ocr;}
});
$('back-run').addEventListener('click',async()=>{
  const selected=files.back,front=ocrResult,fv=frontVersion,version=++backVersion;if(!selected||!front?.fields.id_number)return;
  backAbort?.abort();backAbort=new AbortController();$('back-run').disabled=true;backResult=null;
  clearDetected('back');
  if(addressSource==='back'){$('field-address').value=front.fields.residence_address||'';addressSource=$('field-address').value?'front':null;}
  updateAddressOrigin();
  notice('back-message','Đang đọc nơi cư trú từ mặt sau…','busy');
  try{
    const form=new FormData();form.append('file',selected);form.append('side','back');
    const result=await api('/api/ocr',{method:'POST',body:form,signal:backAbort.signal});
    if(version!==backVersion||fv!==frontVersion||ocrResult!==front||files.back!==selected)return;
    rawLines('back-lines','back-line-count',result);$('back-preview').src=result.normalized_preview;
    if(result.fields.id_number&&result.fields.id_number!==front.fields.id_number)throw new Error('Mặt sau không cùng số căn cước với mặt trước. Hãy chọn lại đúng thẻ.');
    if(!result.fields.residence_address)throw new Error('Chưa lấy được nơi cư trú. Xem các dòng model đọc được và đối chiếu ảnh.');
    backResult=result;$('field-address').value=result.fields.residence_address;addressSource='back';
    const verify=result.fields.id_number?'Số căn cước ở hai mặt khớp nhau.':'Chưa đọc được số để đối chiếu hai mặt; hãy kiểm tra chúng thuộc cùng thẻ.';
    renderDetected('back',result,verify);updateAddressOrigin();
    notice('back-message',`Đã nhận diện mặt sau và đọc nơi cư trú. ${verify} ${result.warnings.join(' ')}`,'good');
  }catch(e){if(version===backVersion&&fv===frontVersion)notice('back-message',e.message,'bad');}
  finally{if(version===backVersion&&fv===frontVersion)backButtons();}
});
$('export-ocr').addEventListener('click',()=>{
  if(!ocrResult)return;
  const {normalized_preview:_,document_token:_token,...front}=ocrResult;
  const back=backResult?(({normalized_preview:_,...result})=>result)(backResult):null;
  const data={fields:{id_number:$('field-id').value,full_name:$('field-name').value,date_of_birth:$('field-dob').value,residence_address:$('field-address').value},front,back,address_source:addressSource,user_edited:true};
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='ket-qua-can-cuoc.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$('face-run').addEventListener('click',async()=>{
  const token=documentToken,selfie=files.selfie;if(!token||!selfie)return;
  const version=++faceVersion;faceAbort?.abort();faceAbort=new AbortController();$('face-run').disabled=true;
  $('face-result').hidden=true;$('face-empty').hidden=false;status('face-status','Đang so khớp…','busy');notice('face-message','Đang so selfie với khuôn mặt trên CCCD đã đọc…','busy');
  try{
    const form=new FormData();form.append('document_token',token);form.append('selfie',selfie);form.append('threshold',$('face-threshold').value);
    const result=await api('/api/face-match',{method:'POST',body:form,signal:faceAbort.signal});
    if(version!==faceVersion||documentToken!==token||files.selfie!==selfie)return;
    $('face-empty').hidden=true;$('face-result').hidden=false;$('face-score').textContent=result.score.toFixed(3);$('face-threshold-result').textContent=result.threshold.toFixed(3);
    $('face-meter').style.width=`${Math.max(0,Math.min(100,result.score*100))}%`;$('face-meter').style.background=result.matched?'var(--accent)':'var(--orange)';
    $('ref-crop').src=result.reference_crop;$('selfie-crop').src=result.selfie_crop;status('face-status',result.matched?'Đạt ngưỡng thử':'Dưới ngưỡng',result.matched?'good':'bad');
    $('match-verdict').className=`match-verdict${result.matched?'':' bad'}`;$('match-symbol').textContent=result.matched?'✓':'!';$('match-title').textContent=result.matched?'Đạt ngưỡng so khớp':'Chưa đạt ngưỡng';$('match-caption').textContent=result.matched?'Selfie phù hợp với khuôn mặt trên căn cước đã đọc.':'Hãy đối chiếu ảnh, ánh sáng và căn cước trước khi thử lại.';
    notice('face-message',`${result.matched?'Selfie đạt ngưỡng so khớp với CCCD đã đọc.':'Selfie chưa đạt ngưỡng so khớp với CCCD đã đọc.'} ${(result.elapsed_ms/1000).toFixed(1)} giây. ${result.note}`,result.matched?'good':'busy');
  }catch(e){if(version!==faceVersion||documentToken!==token)return;if(e.status===410)invalidateReference();status('face-status','Chưa so được','bad');notice('face-message',e.message,'bad');}
  finally{if(version===faceVersion)faceButtons();}
});
async function stopLive(deleteSession=true){liveRunning=false;liveVersion++;$('live-start').disabled=!stream;if(deleteSession&&liveToken){const token=liveToken;liveToken=null;$('use-live-selfie').disabled=true;try{await api(`/api/liveness/${token}`,{method:'DELETE'});}catch{}}}
async function stopCamera(){cameraVersion++;if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}await stopLive();$('camera-video').srcObject=null;$('camera-video').hidden=true;$('camera-placeholder').hidden=false;$('face-guide').hidden=true;$('camera-tag').hidden=true;$('camera-open').disabled=false;$('camera-stop').disabled=true;$('live-start').disabled=true;status('camera-status','Đang tắt');}
$('camera-open').addEventListener('click',async()=>{if(!navigator.mediaDevices?.getUserMedia){toast('Trình duyệt chưa hỗ trợ camera. Mở địa chỉ localhost bằng Chrome hoặc Edge.');return;}$('camera-open').disabled=true;const version=++cameraVersion;try{const opened=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},facingMode:'user'},audio:false});if(version!==cameraVersion||$('panel-live').hidden){opened.getTracks().forEach(track=>track.stop());$('camera-open').disabled=false;return;}stream=opened;$('camera-video').srcObject=stream;await $('camera-video').play();$('camera-video').hidden=false;$('camera-placeholder').hidden=true;$('face-guide').hidden=false;$('camera-tag').hidden=false;$('camera-stop').disabled=false;$('live-start').disabled=false;status('camera-status','Đang mở','good');}catch(e){$('camera-open').disabled=false;const messages={NotAllowedError:'Bạn chưa cấp quyền camera. Hãy cho phép camera rồi thử lại.',NotFoundError:'Không tìm thấy camera trên máy.',NotReadableError:'Camera đang được ứng dụng khác sử dụng.'};toast(messages[e.name]||`Chưa mở được camera: ${e.message}`);}});
$('camera-stop').addEventListener('click',()=>stopCamera());
function renderLive(result){$('live-prompt').textContent=result.frame_hint||result.prompt;$('challenge-list').replaceChildren(...result.actions.map((action,i)=>{const li=document.createElement('li');li.textContent=action.label;if(result.completed.includes(action.key))li.className='done';else if(i===result.current_index&&result.calibrated)li.className='current';return li;}));$('gesture-result').textContent=result.challenge_completed?'Đã hoàn thành':`${result.completed.length}/${result.actions.length} động tác`;$('gesture-result').className=result.challenge_completed?'good':'';$('pad-score').textContent=result.pad_score===null?'—':`${result.pad_score.toFixed(3)} / ngưỡng ${result.pad_threshold}`;$('pad-samples').textContent=result.pad_samples;$('live-time').textContent=`${Math.max(0,Math.ceil((liveDeadline-Date.now())/1000))} giây`;if(result.failed_reason){status('live-status','Cần thử lại','bad');notice('live-message',result.failed_reason,'bad');}else if(result.challenge_completed){status('live-status',result.prototype_passed?'Đạt bài thử':'Động tác hoàn tất',result.prototype_passed?'good':'busy');notice('live-message',result.prototype_passed?'Đã đạt cả động tác và ngưỡng chống giả mạo của prototype. Kết quả chưa bảo đảm chống deepfake hoặc xác thực CCCD.':'Đã hoàn thành động tác nhưng chưa đạt chống giả mạo. Kiểm tra ánh sáng/camera và thử lại; không tự kết luận người dùng gian lận.',result.prototype_passed?'good':'busy');$('use-live-selfie').disabled=!(result.prototype_passed&&documentToken);}else{status('live-status','Đang kiểm tra…','busy');notice('live-message','Làm theo hướng dẫn. Nhắm mắt đủ lâu để bản CPU nhận được khung hình.','');}}
const captureCanvas=document.createElement('canvas');
async function capture(){const video=$('camera-video');if(!video.videoWidth)throw new Error('Camera chưa sẵn sàng.');captureCanvas.width=640;captureCanvas.height=Math.round(video.videoHeight/video.videoWidth*640);captureCanvas.getContext('2d').drawImage(video,0,0,captureCanvas.width,captureCanvas.height);return new Promise((resolve,reject)=>captureCanvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Không lấy được ảnh camera.')),'image/jpeg',0.86));}
$('live-start').addEventListener('click',async()=>{await stopLive();if(!stream)return;$('live-start').disabled=true;$('use-live-selfie').disabled=true;status('live-status','Đang nạp model…','busy');try{const initial=await api('/api/liveness/start',{method:'POST'});liveToken=initial.session_id;liveDeadline=Date.now()+initial.expires_in*1000;liveRunning=true;const version=++liveVersion;renderLive(initial);while(liveRunning&&version===liveVersion){if(Date.now()>liveDeadline){throw new Error('Phiên hết hạn. Bấm Bắt đầu thử thách để tạo phiên mới.');}const form=new FormData();form.append('session_id',liveToken);form.append('frame',await capture(),'camera.jpg');const result=await api('/api/liveness/frame',{method:'POST',body:form});if(version!==liveVersion)break;renderLive(result);if(result.challenge_completed||result.failed_reason){liveRunning=false;break;}await new Promise(resolve=>setTimeout(resolve,130));}}catch(e){status('live-status','Cần thử lại','bad');notice('live-message',e.message,'bad');}finally{liveRunning=false;$('live-start').disabled=!stream;}});
$('use-live-selfie').addEventListener('click',async()=>{
  const token=documentToken,version=frontVersion,session=liveToken;if(!token||!session){toast('Hãy đọc mặt trước CCCD trước khi lấy selfie.');return;}
  try{
    const res=await fetch(`/api/liveness/${session}/selfie`);if(!res.ok){const body=await res.json();throw new Error(body.detail||'Chưa lấy được selfie.');}
    const blob=await res.blob();if(token!==documentToken||version!==frontVersion||session!==liveToken)return;
    chooseSelfie(new File([blob],'selfie-tu-phien-camera.jpg',{type:'image/jpeg'}),'camera');await stopCamera();tab('face');toast('Đã chuyển selfie của phiên camera sang So khớp mặt.');
  }catch(e){if(token===documentToken&&version===frontVersion)toast(e.message);}
});
$('pad-run').addEventListener('click',async()=>{const selected=files.pad;const button=$('pad-run');button.disabled=true;notice('pad-message','Đang nạp model và đánh giá ảnh…','busy');try{const form=new FormData();form.append('file',selected);const result=await api('/api/anti-spoof',{method:'POST',body:form});if(files.pad!==selected)return;notice('pad-message',`Điểm live: ${result.live_score.toFixed(3)} · Ngưỡng thử: ${result.threshold} · ${result.passed?'Đạt ngưỡng':'Chưa đạt ngưỡng'} · ${(result.elapsed_ms/1000).toFixed(1)} giây. ${result.note}`,result.passed?'good':'busy');}catch(e){if(files.pad!==selected)return;notice('pad-message',e.message,'bad');}finally{button.disabled=!files.pad;}});
window.addEventListener('pagehide',()=>{liveRunning=false;if(documentToken)fetch(`/api/documents/${documentToken}`,{method:'DELETE',keepalive:true}).catch(()=>{});if(stream)stream.getTracks().forEach(track=>track.stop());if(liveToken)fetch(`/api/liveness/${liveToken}`,{method:'DELETE',keepalive:true}).catch(()=>{});});
api('/api/health').then(data=>{if(data.face_reference_source!=='scanned_document_front'){$('health-dot').className='dot bad';$('health-label').textContent='Cần khởi động lại bản mới';toast('Máy chủ đang chạy bản cũ. Dừng rồi mở lại START.cmd.');return;}const ready=Object.values(data.models).every(Boolean);$('health-dot').className=`dot ${ready?'ready':'bad'}`;$('health-label').textContent=ready?'CPU · Model đã tải':'Một số model chưa tải';if(!ready)toast('Thiếu model. Chạy setup.ps1 trước khi thử.');}).catch(()=>{$('health-dot').className='dot bad';$('health-label').textContent='Chưa kết nối máy chủ';});
