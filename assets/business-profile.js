"use strict";
(function(){
 const e=v=>String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
 const rolesLabel=roles=>(roles||[]).length===2?'تأمین‌کننده و مشتری بالقوه':(roles||[])[0]==='supplier'?'تأمین‌کنندهٔ بالقوه':(roles||[])[0]==='buyer'?'مشتری بالقوه':'نیازمند تعیین نقش';
 function businessSummaryHtml(profile,reviewed){
  if(!profile||!profile.declared_name)return '';
  return '<div class="business-summary"><strong>نام اعلام‌شده: '+e(profile.declared_name)+'</strong><span>'+e(rolesLabel(profile.roles))+(reviewed?'؛ بازبینی کارشناس':'؛ پیشنهاد از متن آگهی')+'</span></div>';
 }
 function auditHtml(p){
  if(!p.contact_verified_by)return 'بازبینی اطلاعات با تأیید تعلق شماره متفاوت است؛ تأیید به همهٔ تماس‌های آگهی تعمیم داده نمی‌شود.';
  let time='زمان ثبت‌شده';
  try{time=new Intl.DateTimeFormat('fa-IR-u-ca-persian',{timeZone:'Asia/Tehran',dateStyle:'short',timeStyle:'short'}).format(new Date(p.contact_verified_at));}catch(e){}
  return 'تأیید تماس اصلی توسط <bdi>'+e(p.contact_verified_by)+'</bdi> در <bdi dir="ltr">'+e(time)+'</bdi>';
 }
 function businessEditorHtml(r){
  const p=r.business_profile||r.business_suggestion||{};
  const newName=r.business_profile&&!p.declared_name&&r.business_suggestion?.declared_name;
  function option(v,label,current){return '<option value="'+e(v)+'"'+(v===current?' selected':'')+'>'+label+'</option>';}
  return '<fieldset class="business-editor"><legend>طرف تجاری و مسیر CRM</legend>'+
   '<p class="muted">نامِ درج‌شده در آگهی، نام حقوقی تأییدشده نیست. منتشرکننده ممکن است نماینده یا ادمین گروه باشد.</p>'+
   (r.business_profile_error?'<p class="error" role="alert">'+e(r.business_profile_error)+'</p>':'')+
   (newName?'<button type="button" data-apply-name="'+e(newName)+'">استفاده از نام پیشنهادی: '+e(newName)+'</button>':'')+
   '<div class="grid"><label>نام اعلام‌شدهٔ طرف تجاری<input class="party-name" maxlength="200" value="'+e(p.declared_name)+'" autocomplete="off"></label>'+
   '<label>نوع طرف تجاری<select class="party-type" aria-label="نوع طرف تجاری">'+option('unknown','مشخص نشده',p.entity_type||'unknown')+option('company','شرکت / کسب‌وکار',p.entity_type)+option('person','شخص حقیقی',p.entity_type)+'</select></label>'+
   '<label>نقش تجاری<select class="party-roles" aria-label="نقش تجاری">'+option('','مشخص نشده',(p.roles||[]).join(','))+option('supplier','تأمین‌کنندهٔ بالقوه',(p.roles||[]).join(','))+option('buyer','مشتری بالقوه',(p.roles||[]).join(','))+option('supplier,buyer','هر دو نقش',(p.roles||[]).join(','))+'</select></label>'+
   '<label>نام نمایندهٔ شرکت (در صورت مشخص بودن)<input class="party-person" maxlength="200" value="'+e(p.contact_person)+'" autocomplete="off"></label>'+
   '<label>تعلق تماس اصلی به طرف تجاری<select class="party-verification" aria-label="تعلق تماس اصلی به طرف تجاری">'+option('unverified','هنوز بررسی نشده',p.contact_verification||'unverified')+option('confirmed','کارشناس تأیید کرده است',p.contact_verification)+'</select></label>'+
   '<label>توضیح بررسی تعلق تماس<textarea class="party-evidence" maxlength="1000" placeholder="در صورت تأیید، روش و نتیجهٔ بررسی را بنویسید">'+e(p.verification_note)+'</textarea></label></div>'+
   '<p class="party-audit muted">'+auditHtml(p)+'</p></fieldset>';
 }
 function businessBody(card){
  const val=s=>card.querySelector(s).value.trim();
  const roles=val('.party-roles');
  return {declared_name:val('.party-name'),entity_type:val('.party-type'),roles:roles?roles.split(','):[],
   contact_person:val('.party-person'),contact_verification:val('.party-verification'),verification_note:val('.party-evidence')};
 }
 function updateBusinessAudit(card,p){
  if(!p)return;
  card.querySelector('.party-audit').innerHTML=auditHtml(p);
  card.querySelector('.ad-contacts .contact-note')?.replaceChildren(document.createTextNode(p.contact_verification==='confirmed'?'تعلق تماس اصلی توسط کارشناس تأیید شده؛ سایر تماس‌ها صرفاً از متن استخراج شده‌اند.':'اطلاعات تماس از متن آگهی استخراج شده‌اند؛ تعلق تماس اصلی هنوز بررسی نشده است.'));
 }
 function businessValidationError(card,status){
  const p=businessBody(card);
  if(status==='selected'&&(!p.declared_name||p.entity_type==='unknown'||!p.roles.length))return 'برای ورود به صف، نام طرف تجاری، نوع و نقش را مشخص کنید.';
  if(p.contact_verification==='confirmed'&&(!p.declared_name||!p.verification_note||!card.querySelector('.contact').value.trim()))return 'تأیید تعلق تماس نیازمند نام، تماس اصلی معتبر و توضیح بررسی است.';
  return '';
 }
 function initBusinessEditor(card){
  function update(){
   const roles=card.querySelector('.party-roles').value;
   card.querySelector('[data-queue-business]').textContent=roles==='supplier'?'ثبت تأمین‌کننده در صف CRM':roles==='buyer'?'ثبت سرنخ خرید در صف CRM':roles==='supplier,buyer'?'ثبت طرف تجاری با هر دو نقش در صف CRM':'تکمیل اطلاعات و ورود به صف CRM';
   card.querySelector('.party-person').disabled=card.querySelector('.party-type').value==='person';
   if(card.querySelector('.party-person').disabled)card.querySelector('.party-person').value='';
  }
  card.querySelector('.party-roles').addEventListener('change',update);
  card.querySelector('.party-type').addEventListener('change',update);
  for(const selector of ['.contact','.party-name','.party-type'])card.querySelector(selector).addEventListener('input',()=>{
   card.querySelector('.party-verification').value='unverified';
   card.querySelector('.party-evidence').value='';
   card.querySelector('.party-audit').textContent='اطلاعات اصلی تغییر کرده؛ تعلق تماس نیازمند بررسی مجدد است.';
   card.querySelector('.ad-contacts .contact-note')?.replaceChildren(document.createTextNode('اطلاعات اصلی تغییر کرده؛ تعلق تماس نیازمند بررسی مجدد است.'));
  });
  const suggestion=card.querySelector('[data-apply-name]');
  if(suggestion)suggestion.addEventListener('click',()=>{
   card.querySelector('.party-name').value=suggestion.dataset.applyName;
   card.querySelector('.party-type').value='company';
   card.querySelector('.party-name').dispatchEvent(new Event('input',{bubbles:true}));
   suggestion.disabled=true;update();
  });
  update();
 }
 function businessSnapshotHtml(context){
  if(!context||!context.party)return '';
  const p=context.party;
  return '<section class="business-snapshot"><strong>'+e(p.declared_name)+'</strong><span>'+e(rolesLabel(p.roles))+'</span>'+
   '<span>مقصد پیشنهادی: '+e(context.intended_intake==='supplier_intake'?'بانک تأمین‌کنندگان':context.intended_intake==='sales_lead_intake'?'سرنخ‌های فروش':context.intended_intake==='dual_role_intake'?'تأمین‌کننده و مشتری':'بررسی بیشتر')+'</span>'+
   '<span>تعلق تماس اصلی: '+(p.contact_verification==='confirmed'?'تأیید کارشناس؛ '+e(p.contact_verified_by):'هنوز بررسی نشده')+'</span>'+
   '<span>در انتظار هماهنگی قرارداد CRM؛ هنوز رکوردی ایجاد نشده است.</span></section>';
 }
 Object.assign(window,{businessSummaryHtml,businessEditorHtml,businessBody,updateBusinessAudit,businessValidationError,initBusinessEditor,businessSnapshotHtml});
})();
