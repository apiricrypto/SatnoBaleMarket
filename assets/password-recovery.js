"use strict";
(async function(){
 const form=document.getElementById('recoveryForm'),btn=document.getElementById('submit'),status=document.getElementById('result');
 const reset=document.body.dataset.recovery==='reset';
 let token='';
 if(reset){
  token=new URLSearchParams(location.hash.slice(1)).get('token')||'';
  history.replaceState(null,'',location.pathname);
  if(!/^[A-Za-z0-9_-]{43}$/.test(token)){status.textContent='پیوند بازیابی نامعتبر یا ناقص است؛ پیوند جدید درخواست کنید.';btn.disabled=true;}
  document.getElementById('toggle').addEventListener('click',function(){
   const show=document.getElementById('new').type==='password';
   for(const id of ['new','confirm'])document.getElementById(id).type=show?'text':'password';
   this.textContent=show?'پنهان‌کردن رمز':'نمایش رمز';this.setAttribute('aria-pressed',String(show));
  });
 }else{
  btn.disabled=true;
  try{const r=await fetch('/api/auth/recovery-status',{cache:'no-store'});const data=await r.json();
   btn.disabled=!r.ok||!data.enabled;
   if(btn.disabled)status.textContent='سرویس ارسال ایمیل بازیابی هنوز تنظیم نشده است؛ با مدیر سامانه تماس بگیرید.';
  }catch(e){status.textContent='ارتباط با سرور برقرار نشد؛ صفحه را دوباره بارگذاری کنید.';}
 }
 form.addEventListener('submit',async function(event){
  event.preventDefault();if(btn.disabled)return;
  status.textContent='';
  let payload={email:document.getElementById('email')?.value.trim()};
  if(reset){
   const password=document.getElementById('new').value,confirm=document.getElementById('confirm').value;
   if(password!==confirm){status.textContent='رمز جدید و تکرار آن یکسان نیستند.';return;}
   payload={token:token,new_password:password,confirm_password:confirm};
  }
  const old=btn.textContent;btn.disabled=true;form.setAttribute('aria-busy','true');btn.textContent='در حال ثبت…';
  try{const r=await fetch('/api/auth/'+(reset?'reset-password':'forgot-password'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
   const data=await r.json();status.textContent=r.ok?data.message:(typeof data.detail==='string'?data.detail:'درخواست معتبر نیست.');
   if(r.ok&&reset){token='';form.reset();form.hidden=true;return;}
  }catch(e){status.textContent='ارتباط با سرور برقرار نشد. دوباره تلاش کنید.';}
  finally{btn.disabled=false;btn.textContent=old;form.removeAttribute('aria-busy');}
 });
})();
