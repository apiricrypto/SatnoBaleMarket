"use strict";
(function(){
function contactEscape(v){const d=document.createElement("div");d.textContent=v==null?"":String(v);return d.innerHTML.replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function senderHtml(r){
 const label=contactEscape(r.sender_username||r.sender_name||r.sender_id||'-');
 if(r.sender_link && /^https:\/\/ble\.ir\/[A-Za-z0-9_.-]+\/?$/.test(r.sender_link)){
   return '<a class="sender-contact" href="'+contactEscape(r.sender_link)+'" target="_blank" rel="noopener noreferrer">پروفایل منتشرکننده پیام: '+label+'</a>';
 }
 const id=r.sender_id?' • ID: '+contactEscape(r.sender_id):'';
 return 'منتشرکننده: '+label+id+' <span class="tag">نام کاربری منتشرکننده دریافت نشده</span>';
}
function adContactsHtml(r,options){
 options=options||{};
 const contacts=Array.isArray(r.ad_contacts)?r.ad_contacts:[];
 if(!contacts.length)return '';
 const labels={phone:'تلفن درج‌شده',whatsapp:'واتس‌اپ',bale:'بله',email:'ایمیل',website:'وب‌سایت',whatsapp_group:'گروه واتس‌اپ',username:'شناسه؛ شبکه نامشخص',needs_review:'پیوند نیازمند بررسی'};
 function item(c){
   const content='<span class="contact-kind">'+contactEscape(labels[c.kind]||'اطلاعات تماس')+'</span><bdi class="contact-value" dir="ltr">'+contactEscape(c.value||'')+'</bdi>';
   const href=typeof c.href==='string'?c.href:'';
   if(/^(https:\/\/|tel:\+|mailto:)/.test(href))return '<a class="ad-contact" href="'+contactEscape(href)+'"'+(href.startsWith('https://')?' target="_blank" rel="noopener noreferrer"':'')+'>'+content+'</a>';
   return '<span class="ad-contact contact-review">'+content+'</span>';
 }
 const extra=contacts.length>3?'<details class="more-contacts"><summary>اطلاعات تماس بیشتر ('+(contacts.length-3)+')</summary><div class="ad-contact-grid">'+contacts.slice(3).map(item).join('')+'</div></details>':'';
 return '<section class="ad-contacts" aria-label="اطلاعات تماس داخل آگهی"><strong>'+contactEscape(options.title||'اطلاعات تماس داخل آگهی')+'</strong><p class="contact-note">'+contactEscape(options.note||'از متن پیام؛ هویت مخاطب تأیید نشده است.')+'</p><div class="ad-contact-grid">'+contacts.slice(0,3).map(item).join('')+'</div>'+extra+'</section>';
}

window.senderHtml=senderHtml;window.adContactsHtml=adContactsHtml;
})();
