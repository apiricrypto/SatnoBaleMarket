SATNO_UI_CSS = r"""
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
"""
