SATNO_UI_CSS = r"""
@font-face{font-family:Vazirmatn;src:url("/assets/Vazirmatn-Regular.woff2") format("woff2");font-display:swap}
:root{
  --satno-bg:#f4f7fb;--satno-surface:#fff;--satno-text:#172033;--satno-muted:#667085;
  --satno-line:#e4eaf1;--satno-primary:#0b7285;--satno-primary-2:#0e8fa3;--satno-primary-soft:#eaf8fb;
  --satno-success:#087a55;--satno-success-soft:#eaf8f1;--satno-warning:#a85d00;--satno-warning-soft:#fff6e8;
  --satno-danger:#b42318;--satno-danger-soft:#fff0ee;--satno-shadow:0 10px 28px rgba(20,35,55,.07);
  --satno-radius:16px;--satno-radius-sm:11px;
}
*{box-sizing:border-box}
html{background:var(--satno-bg)}
body{font-family:Vazirmatn,IRANSansX,Segoe UI,Tahoma,Arial,sans-serif!important;background:
  radial-gradient(circle at 92% 0%,rgba(14,143,163,.08),transparent 26rem),
  var(--satno-bg)!important;color:var(--satno-text)!important}
a{color:var(--satno-primary)!important;text-decoration:none}
a:hover{color:#075968!important}
.wrap{max-width:1280px!important;padding:24px!important}
h1,h2,h3{letter-spacing:-.35px;color:var(--satno-text)}
h1{font-size:28px!important} h2{font-size:23px!important} h3{font-size:17px!important}
.sub,.muted,.meta,.hint{color:var(--satno-muted)!important}
.card,.stats,.surface,.box,.searchpanel{
  background:rgba(255,255,255,.96)!important;border:1px solid var(--satno-line)!important;
  border-radius:var(--satno-radius)!important;box-shadow:var(--satno-shadow)!important
}
.card{transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease}
.card:hover{border-color:#d3e6eb!important;box-shadow:0 14px 34px rgba(20,35,55,.09)!important}
input,select,textarea{
  border:1px solid #ced8e3!important;border-radius:var(--satno-radius-sm)!important;background:#fff!important;
  color:var(--satno-text)!important;outline:none!important;transition:border-color .15s,box-shadow .15s
}
input:focus,select:focus,textarea:focus{border-color:var(--satno-primary-2)!important;box-shadow:0 0 0 3px rgba(14,143,163,.12)!important}
button,.btn{
  border-radius:var(--satno-radius-sm)!important;border:1px solid #cfdae4!important;background:#fff!important;
  color:#29475d!important;font-weight:650;transition:transform .12s,box-shadow .12s,background .12s
}
button:hover,.btn:hover{background:#f8fbfc!important;box-shadow:0 4px 14px rgba(18,48,65,.08);transform:translateY(-1px)}
button.primary,.primary,.btn-primary{background:linear-gradient(135deg,var(--satno-primary),var(--satno-primary-2))!important;color:#fff!important;border-color:transparent!important}
button.danger,.danger{color:var(--satno-danger)!important;border-color:#f0c7c3!important;background:#fff!important}
button.danger:hover,.danger:hover{background:var(--satno-danger-soft)!important}
.nav{display:flex!important;flex-wrap:wrap;gap:8px!important;margin:16px 0 18px!important}
.nav a,.nav button{
  padding:10px 13px!important;border:1px solid var(--satno-line)!important;border-radius:12px!important;background:#fff!important;
  box-shadow:0 3px 10px rgba(28,43,60,.035);font-weight:650
}
.nav a:hover{background:var(--satno-primary-soft)!important;border-color:#c7e6eb!important}
.tag,.badge,.pill{
  display:inline-flex!important;align-items:center;gap:4px;background:#eef4f7!important;color:#35566a!important;
  border:1px solid #e0e9ee;border-radius:999px!important;padding:4px 9px!important;font-size:12px!important;font-weight:650
}
.metric-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:14px 0}
.metric{background:#fff;border:1px solid var(--satno-line);border-radius:15px;padding:14px 15px;box-shadow:0 6px 20px rgba(20,35,55,.045)}
.metric .label{font-size:12px;color:var(--satno-muted);margin-bottom:5px}.metric .value{font-size:22px;font-weight:800;letter-spacing:-.4px}
.metric .foot{font-size:11px;color:#8a96a6;margin-top:4px}
.section-head{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin:4px 0 12px}
.searchpanel{padding:16px!important}
.result-card{position:relative;padding:16px 17px!important}
.result-card .message{font-size:14px;line-height:1.95;margin:10px 0 12px;white-space:pre-wrap}
.result-card .actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.result-card .leadBtn{display:inline-flex;padding:8px 11px;border-radius:10px;background:var(--satno-primary-soft);font-weight:700}
.cat-supplier_seller{border-right:4px solid #0b7285!important}.cat-stock_availability{border-right:4px solid #087a55!important}
.cat-buyer_demand{border-right:4px solid #7c5cff!important}.cat-inquiry_project{border-right:4px solid #d97706!important}
.empty-state{padding:34px;text-align:center;border:1px dashed #cdd8e3;border-radius:16px;background:#fbfdfe;color:var(--satno-muted)}
.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.toolbar>*{min-width:0}
.status.ok,.ok{color:var(--satno-success)!important}.status.err,.err,.error{color:var(--satno-danger)!important}
.source{background:#fff;border:1px solid var(--satno-line)!important;border-radius:14px;padding:12px!important;margin:9px 0;box-shadow:0 4px 16px rgba(20,35,55,.035)}
.source:hover{border-color:#cfe5ea!important}.candidate{background:#fbfdfe!important;border-radius:14px!important}
.scorebox input{font-weight:800;color:var(--satno-primary)!important}
table{border-collapse:separate!important;border-spacing:0!important;overflow:hidden;border:1px solid var(--satno-line);border-radius:14px}
thead th{background:#f8fafc!important;color:#536476;font-size:12px!important}
th,td{border-bottom:1px solid #edf1f5!important}
tbody tr:hover td{background:#fbfdfe}
.toast{position:fixed;left:22px;bottom:22px;background:#172033;color:#fff;padding:11px 15px;border-radius:12px;box-shadow:var(--satno-shadow);z-index:9999;opacity:0;transform:translateY(8px);transition:.2s}
.toast.show{opacity:1;transform:none}
.kpi-good{color:var(--satno-success)}.kpi-warn{color:var(--satno-warning)}.kpi-bad{color:var(--satno-danger)}
@media(max-width:1000px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.bar{grid-template-columns:1fr 1fr!important}}
@media(max-width:680px){.wrap{padding:14px!important}.metric-grid{grid-template-columns:1fr}.bar{grid-template-columns:1fr!important}.nav a,.nav button{flex:1 1 auto;text-align:center}.source{grid-template-columns:1fr!important}}

/* Issue #1 — Canva-inspired RTL staff experience; presentation only. */
:root{
  --satno-bg:#F5F7FC;--satno-text:#142B4A;--satno-muted:#617189;
  --satno-line:#DCE5F1;--satno-primary:#2563EB;--satno-primary-2:#1D4ED8;
  --satno-primary-soft:#EAF1FF;--satno-shadow:0 8px 28px rgba(20,43,74,.055);
}
html{scroll-behavior:smooth}
body{background:radial-gradient(circle at 100% 0,rgba(37,99,235,.055),transparent 36rem),var(--satno-bg)!important;line-height:1.75}
.wrap{max-width:1440px!important;margin-inline:auto}
.nav{display:flex!important;flex-wrap:wrap;align-items:center;gap:8px!important;
  padding:10px!important;border:1px solid var(--satno-line);border-radius:16px;
  background:#fff;box-shadow:0 3px 16px rgba(20,43,74,.035)}
.nav a,.nav button{min-height:42px;display:inline-flex;align-items:center;justify-content:center;
 padding:9px 13px!important;border-radius:11px!important;font-size:13px;font-weight:650;
 white-space:nowrap;transition:background .17s,border-color .17s,box-shadow .17s}
.nav a:hover{background:var(--satno-primary-soft)!important;color:#1D4ED8!important}
.nav a[aria-current="page"]{color:#1D4ED8!important;background:var(--satno-primary-soft)!important;
 border:1px solid #BED3FF!important}
input:focus-visible,select:focus-visible,textarea:focus-visible,button:focus-visible,a:focus-visible,
[tabindex]:focus-visible{outline:3px solid #93B4FF!important;outline-offset:2px!important}
button{min-height:42px;cursor:pointer}
button:disabled{opacity:.55;cursor:not-allowed}
.metric-grid{gap:14px!important}
.metric{background:linear-gradient(160deg,#fff,#FBFCFF)!important;border:1px solid var(--satno-line)!important;
 border-radius:16px!important;padding:18px!important}
.metric .label{color:var(--satno-muted)!important}
.metric .value{color:var(--satno-text)!important;font-variant-numeric:tabular-nums}
.card,.searchpanel,.surface,.box{border-radius:16px!important}
.section-head{gap:14px;flex-wrap:wrap}
.bar input,.bar select,.searchbox input{min-width:0}
.pill{line-height:1.6!important}
.nav,.metric-grid,.card,.source,.candidate{min-width:0}
.source,.candidate{overflow-wrap:anywhere}
a[href],button{touch-action:manipulation}
@media(min-width:1200px){
 body.staff-shell .wrap{padding-right:276px!important;max-width:1560px!important}
 body.staff-shell .nav{position:fixed;z-index:30;right:16px;top:16px;bottom:16px;
   width:232px;display:flex!important;flex-direction:column;justify-content:flex-start;
   flex-wrap:nowrap;align-items:stretch;padding:19px 12px!important;overflow:auto;
   box-shadow:0 8px 30px rgba(20,43,74,.06)}
 body.staff-shell .nav:before{content:"SATNO  /  بله مارکت";display:block;
   font-weight:800;color:var(--satno-text);padding:13px 9px 20px;
   margin-bottom:6px;border-bottom:1px solid var(--satno-line);text-align:center}
 body.staff-shell .nav a,body.staff-shell .nav button{justify-content:flex-start;text-align:right}
}
@media(max-width:767px){
 .wrap{padding:12px!important}
 .nav{gap:6px!important;padding:8px!important}
 .nav a,.nav button{flex:1 1 calc(50% - 6px);min-height:46px;font-size:12px!important}
 h1{font-size:23px!important}h2{font-size:20px!important}
 .card,.searchpanel{padding:14px!important}
 .section-head{align-items:flex-start}
 .toolbar{flex-wrap:wrap}
 .actions{flex-wrap:wrap}
 .metric-grid{grid-template-columns:1fr!important}
 input,select,textarea{max-width:100%}
 table{display:block;max-width:100%;overflow-x:auto;white-space:nowrap}
}
@media(min-width:768px) and (max-width:1199px){
 .metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
}
@media(prefers-reduced-motion:reduce){
 *,*:before,*:after{scroll-behavior:auto!important;transition-duration:.01ms!important;animation-duration:.01ms!important}
}


/* Issue #1 second pass: enforce dashboard sidebar & readable lead cards. */
@media(min-width:1200px){
 body.staff-shell{padding-right:248px!important}
 body.staff-shell .wrap{padding:24px 26px!important;width:100%!important;max-width:1650px!important;margin:0 auto!important}
 body.staff-shell .nav{position:fixed!important;top:14px!important;right:14px!important;bottom:14px!important;left:auto!important;
 width:224px!important;max-width:224px!important;display:flex!important;flex-direction:column!important;
 flex-wrap:nowrap!important;align-items:stretch!important;justify-content:flex-start!important;
 margin:0!important;padding:16px 10px!important;border-radius:20px!important;background:#fff!important;
 box-shadow:0 12px 38px rgba(20,43,74,.08)!important;overflow-y:auto!important;z-index:99!important}
 body.staff-shell .nav>a,body.staff-shell .nav>button{width:100%!important;flex:0 0 auto!important;justify-content:flex-start!important;
 text-align:right!important;padding:10px 12px!important;min-height:46px!important}
}
body.staff-shell .wrap>h1,body.staff-shell .section-head h2{font-size:clamp(23px,2vw,29px)!important}
body.staff-shell .metric-grid{display:grid!important;grid-template-columns:repeat(5,minmax(0,1fr))!important;margin:16px 0!important}
body.staff-shell .metric{min-width:0!important}
body.staff-shell .metric .value{font-size:clamp(21px,2vw,30px)!important;line-height:1.35!important;overflow-wrap:anywhere}
body.staff-shell .searchpanel{padding:19px!important;margin:16px 0!important}
body.staff-shell .searchpanel:before{content:"جست‌وجو و فیلترهای بازار";display:block;font-size:16px;font-weight:800;color:#142B4A;margin-bottom:14px}
body.staff-shell .searchpanel .bar{display:grid!important;grid-template-columns:minmax(240px,2fr) minmax(170px,1fr) minmax(160px,1fr) minmax(135px,1fr) minmax(135px,1fr)!important;gap:10px!important;align-items:stretch!important}
body.staff-shell .searchpanel .bar input,body.staff-shell .searchpanel .bar select{width:100%!important;min-height:44px!important}
body.staff-shell .searchpanel .bar>button{min-width:100px!important;min-height:44px!important}
body.staff-shell .searchpanel .hint{font-size:12px!important;margin-top:12px}
body.market-board #list{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;align-items:start}
body.market-board #list>.empty-state,body.market-board #list>.stats{grid-column:1/-1}
body.market-board #list .result-card{min-width:0!important;min-height:0!important;height:auto!important;
 padding:18px!important;margin:0!important;box-shadow:0 4px 20px rgba(20,43,74,.04)!important;overflow:hidden}
body.market-board #list .result-card .meta{font-size:12px!important;color:#64748B!important;line-height:1.8!important;overflow-wrap:anywhere}
body.market-board #list .result-card .message{font-size:14px!important;line-height:1.95!important;max-height:12em;overflow:auto;
 white-space:pre-wrap!important;overflow-wrap:anywhere;padding:13px!important;border-radius:12px;background:#F8FAFD;
 border:1px solid #EDF1F7;margin:12px 0!important}
body.market-board #list .result-card .tag{display:inline-block;padding:3px 8px!important;margin:3px 2px!important;border-radius:9px!important;font-size:12px!important}
body.market-board #list .result-card .actions{padding-top:10px!important;border-top:1px solid #EFF2F8!important}
body.market-board #list .result-card.cat-supplier_seller{border-right:4px solid #16A34A!important}
body.market-board #list .result-card.cat-buyer_demand{border-right:4px solid #2563EB!important}
body.market-board #list .result-card.cat-stock_availability{border-right:4px solid #7C3AED!important}
body.market-board #list .result-card.cat-inquiry_project{border-right:4px solid #D97706!important}
body.market-board #list .result-card.cat-other{border-right:4px solid #94A3B8!important}
body.market-board #list .result-card .leadBtn{background:#EAF1FF!important;color:#1D4ED8!important}
@media(max-width:1199px){
 body.staff-shell .metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
 body.staff-shell .searchpanel .bar{grid-template-columns:repeat(2,minmax(0,1fr))!important}
 body.market-board #list{grid-template-columns:1fr!important}
}
@media(max-width:600px){
 body.staff-shell .metric-grid{grid-template-columns:1fr!important}
 body.staff-shell .searchpanel .bar{grid-template-columns:1fr!important}
 body.staff-shell .nav{display:flex!important}
 body.market-board #list .result-card{padding:13px!important}
}


/* SATNO_FOUR_COLUMN_BOARD_V1 — stable GitHub version of the verified live board */
body.market-board #list{
 display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;
 gap:13px!important;align-items:start!important;margin-top:18px!important;
}
body.market-board #list>.empty-state,body.market-board #list>.stats{grid-column:1/-1}
body.market-board #list .result-card{
 --board-accent:#64748b;--board-soft:#f1f5f9;
 display:flex!important;flex-direction:column!important;min-width:0!important;
 min-height:290px!important;height:auto!important;position:relative;
 padding:0!important;margin:0!important;overflow:hidden!important;
 background:#fff!important;border:1px solid #dfe6f0!important;
 border-radius:15px!important;box-shadow:0 4px 16px rgba(20,43,74,.06)!important;
 transition:box-shadow .18s ease,transform .18s ease;
}
body.market-board #list .result-card:hover{
 transform:translateY(-2px);box-shadow:0 9px 25px rgba(20,43,74,.12)!important;
}
body.market-board #list .cat-supplier_seller{--board-accent:#059669;--board-soft:#ecfdf5}
body.market-board #list .cat-stock_availability{--board-accent:#0891b2;--board-soft:#ecfeff}
body.market-board #list .cat-buyer_demand{--board-accent:#2563eb;--board-soft:#eff6ff}
body.market-board #list .cat-inquiry_project{--board-accent:#d97706;--board-soft:#fffbeb}
body.market-board #list .cat-other{--board-accent:#7c3aed;--board-soft:#f5f3ff}
body.market-board #list .result-card::before{
 content:"\633 \627 \6cc \631 \20 \67e \6cc \627 \645 \200c \647 \627 ";display:block;flex:0 0 auto;
 padding:9px 13px;text-align:right;background:var(--board-accent);color:#fff;
 font-size:12px;font-weight:800;line-height:1.6;
}
body.market-board #list .cat-supplier_seller::before{content:"\641 \631 \648 \634 \646 \62f \647 \20 \2f \20 \62a \623 \645 \6cc \646 \200c \6a9 \646 \646 \62f \647 "}
body.market-board #list .cat-stock_availability::before{content:"\645 \648 \62c \648 \62f \6cc \20 \2f \20 \641 \631 \648 \634 "}
body.market-board #list .cat-buyer_demand::before{content:"\62e \631 \6cc \62f \627 \631 \20 \2f \20 \62a \642 \627 \636 \627 "}
body.market-board #list .cat-inquiry_project::before{content:"\627 \633 \62a \639 \644 \627 \645 \20 \2f \20 \67e \631 \648 \698 \647 "}
body.market-board #list .result-card .meta{
 display:block;flex:0 0 auto;padding:10px 13px!important;margin:0!important;
 background:var(--board-soft)!important;color:#334155!important;
 border-bottom:1px solid #e5eaf2;font-size:11px!important;
 line-height:1.9!important;overflow-wrap:anywhere;
}
body.market-board #list .result-card .message{
 flex:1 1 auto;display:block;min-height:100px;max-height:175px!important;
 margin:11px 11px 7px!important;padding:10px 11px!important;
 background:#f8fafc!important;border:1px solid #edf1f7!important;
 border-radius:10px!important;color:#1e293b!important;font-size:12px!important;
 line-height:1.85!important;white-space:pre-wrap!important;
 overflow:auto!important;overflow-wrap:anywhere;
}
body.market-board #list .result-card>div:not(.meta):not(.message):not(.actions){
 padding:7px 11px!important;display:flex;flex-wrap:wrap;gap:4px;
}
body.market-board #list .result-card .tag{
 padding:3px 7px!important;margin:0!important;font-size:10px!important;
 border-radius:8px!important;background:#f1f5f9!important;
 border:1px solid #e2e8f0!important;color:#475569!important;
}
body.market-board #list .result-card .actions{
 display:flex!important;align-items:center;justify-content:flex-end;
 margin-top:auto!important;padding:10px 12px!important;
 border-top:1px solid #eef2f7!important;
}
body.market-board #list .result-card .leadBtn{
 padding:7px 12px!important;color:#1d4ed8!important;background:#eff6ff!important;
 border-radius:9px!important;font-size:12px!important;font-weight:750!important;
}
@media(min-width:1200px) and (max-width:1449px){
 body.market-board #list{grid-template-columns:repeat(3,minmax(0,1fr))!important}
}
@media(min-width:700px) and (max-width:1199px){
 body.market-board #list{grid-template-columns:repeat(2,minmax(0,1fr))!important}
}
@media(max-width:699px){
 body.market-board #list{grid-template-columns:1fr!important}
 body.market-board #list .result-card .message{font-size:13px!important}
}
@media(prefers-reduced-motion:reduce){
 body.market-board #list .result-card{transition:none!important}
}


/* SATNO_FOUR_COLUMN_BOARD_V2 — consistent board card proportions */
@media(min-width:1200px){
 body.market-board #list{align-items:stretch!important;grid-auto-rows:minmax(355px,auto)}
 body.market-board #list .result-card{height:100%!important;min-height:355px!important}
}
body.market-board #list .result-card{border-right:1px solid #dfe6f0!important}
body.market-board #list .result-card::before{
 min-height:39px;display:flex;align-items:center;justify-content:flex-start;
 padding:9px 12px!important;font-size:12px!important
}
body.market-board #list .result-card .meta{
 min-height:64px;padding:10px 12px!important;font-size:12px!important;
 line-height:1.8!important;overflow-wrap:anywhere;
}
body.market-board #list .result-card .message{
 flex:1 1 auto!important;min-height:116px!important;max-height:170px!important;
 font-size:13px!important;line-height:1.9!important
}
body.market-board #list .result-card .actions{
 margin-top:auto!important;min-height:52px!important;background:#fff
}
body.market-board #list .result-card .leadBtn{
 min-height:34px;align-items:center;justify-content:center;
 text-align:center!important
}
body.market-board #list .result-card .tag{font-size:11px!important;line-height:1.5}
body.market-board #list .result-card .meta a{overflow-wrap:anywhere}
@media(max-width:699px){
 body.market-board #list .result-card{height:auto!important;min-height:0!important}
 body.market-board #list .result-card .meta{min-height:0}
}

input[type=checkbox]{width:20px!important;height:20px!important;min-height:0!important;vertical-align:middle;accent-color:var(--satno-primary)}
.bulk-toolbar{padding:12px 0;border-bottom:1px solid var(--satno-line);margin-bottom:12px}
/* Final pack: shared role-aware shell and stable four-column market board. */
.staff-brand{font-size:28px;font-weight:850;letter-spacing:2px;color:var(--satno-primary);padding:12px;text-align:center;border-bottom:1px solid var(--satno-line);margin-bottom:12px}
.staff-brand small{display:block;font-size:12px;letter-spacing:0;color:var(--satno-muted)}
.staff-account{padding:12px;color:var(--satno-muted);font-size:13px;overflow-wrap:anywhere;margin-top:auto}
.nav-icon{width:22px;display:inline-flex;justify-content:center;margin-left:9px;font-size:20px;color:#087c91}
body.staff-shell .nav:before{content:none!important}
body.staff-shell .nav{align-content:start}
body.staff-shell{margin:0}
.password-card{width:min(100%,540px);margin:5vh auto!important;padding:28px!important}
.password-card input{font:inherit;min-height:48px;direction:ltr;text-align:right}
.password-card .hint{opacity:1;color:var(--satno-muted)}
.metric{border-top:3px solid #2563eb!important}
.metric:nth-child(4n+2){border-top-color:#0891b2!important}
.metric:nth-child(4n+3){border-top-color:#059669!important}
.metric:nth-child(4n+4){border-top-color:#eab308!important}
@media(min-width:1200px){body.market-board #list{grid-template-columns:repeat(4,minmax(0,1fr))!important}}
@media(max-width:1199px){.staff-brand{width:100%;margin:0;padding:4px;font-size:22px}.staff-brand small{display:inline;margin-right:12px}.staff-account{width:100%;padding:4px;margin:0}.password-card{margin:20px auto!important}}
@media(max-width:699px){.password-card{padding:20px!important}body.staff-shell .metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.metric .value{font-size:21px!important}}

"""


import re
from html import escape


NAV_ICON_PATHS = {'▦': 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z', '◇': 'M9 11l2 2 4-4 M5 3h14v18H5z', '▤': 'M4 5h16v14H4z M4 10h16 M9 5v14', '↻': 'M20 7v5h-5 M4 17v-5h5 M6 6a8 8 0 0 1 14 6 M18 18a8 8 0 0 1-14-6', '⇄': 'M3 7h18l-5-4 M21 17H3l5 4', '♙': 'M8 8a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M4 21v-3a8 8 0 0 1 16 0v3z', '⚿': 'M14 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10 M9 12H2 M5 12v4'}

def staff_document(document, user, current_path):
    """Shared navigation is presentation only; endpoint RBAC remains authoritative."""
    role = user['role']
    links = [('/', 'جست‌وجوی بازار', '▦')]
    if role in {'admin', 'sales'}:
        links.append(('/review', 'بررسی سرنخ‌ها', '◇'))
    if role == 'admin':
        links.append(('/sources/manage', 'مدیریت منابع', '▤'))
    links.append(('/status', 'وضعیت همگام‌سازی', '↻'))
    if role in {'admin', 'sales'}:
        links.append(('/crm/outbox', 'صف CRM', '⇄'))
    if role == 'admin':
        links.append(('/admin/users', 'کاربران', '♙'))
    links.append(('/profile/password', 'تغییر رمز', '⚿'))
    nav = '<nav class="nav" aria-label="ناوبری اصلی"><div class="staff-brand">SATNO<small>هوش بازار بله</small></div>'
    for href, label, icon in links:
        active = ' aria-current="page"' if href == current_path else ''
        graphic = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="' + NAV_ICON_PATHS[icon] + '"/></svg>'
        nav += f'<a href="{href}"{active}><span class="nav-icon" aria-hidden="true">{graphic}</span>{label}</a>'
    nav += '<button id="logoutBtn" data-staff-logout type="button">خروج از حساب</button>'
    nav += '<div class="staff-account">' + escape(user.get('display_name') or user['username']) + '</div></nav>'
    if 'class="nav"' in document:
        document = re.sub(r'<div class="nav"[^>]*>.*?</div>', lambda _: nav, document, count=1, flags=re.S)
    else:
        document = document.replace('<body>', '<body class="staff-shell">' + nav, 1)
    # Dashboard already had a logout listener; centralize it for all pages.
    document = document.replace("document.getElementById('logoutBtn').addEventListener('click',async()=>{await fetch('/api/auth/logout',{method:'POST'});location.href='/login';});", '')
    script = """<script>document.querySelector('[data-staff-logout]').addEventListener('click',async function(){
this.disabled=true;try{const r=await fetch('/api/auth/logout',{method:'POST'});if(!r.ok)throw Error();location.replace('/login');}
catch(e){this.disabled=false;this.textContent='خطای ارتباط؛ تلاش مجدد';}});</script>"""
    document = document.replace('</head>', '<link rel="icon" href="data:,"></head>')
    return document.replace('</body>', script + '</body>')
