cat > /mnt/user-data/outputs/app.py << 'PYEOF'
from flask import (Flask, render_template, render_template_string,
                   request, redirect, url_for, session, abort, jsonify)
import requests, requests.adapters, ssl, time, json, threading, urllib3, traceback
from functools import wraps
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NoVerifyHTTPSAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        ctx.set_ciphers("DEFAULT")
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)

def make_session():
    s = requests.Session()
    s.mount("https://", NoVerifyHTTPSAdapter())
    s.verify = False
    return s

_rs = make_session()
def _get(u,**k):    k.setdefault("timeout",10);k.setdefault("verify",False);return _rs.get(u,**k)
def _post(u,**k):   k.setdefault("timeout",10);k.setdefault("verify",False);return _rs.post(u,**k)
def _put(u,**k):    k.setdefault("timeout",10);k.setdefault("verify",False);return _rs.put(u,**k)
def _delete(u,**k): k.setdefault("timeout",10);k.setdefault("verify",False);return _rs.delete(u,**k)

app = Flask(__name__)
app.secret_key = 'VOID_SECRET_KEY_2026'
app.permanent_session_lifetime = timedelta(hours=2)

LOGS_FILE   = "system_history.json"
STAFF_FILE  = "staff_registry.json"
BOT_API_KEY = "VOID_BOT_SECRET_2026"

BOT_TOKEN            = "MTQ4NzQ2ODI1OTcwMjczOTEzNQ.GoPwyd.F9MyLJT-d3TRXneER5SwqfEVnVK0ElwjWTj9ck"
GUILD_ID             = "1341845115949420584"
JOB_LOG_CHANNEL      = "1491731945015476254"
INV_ACCEPTED_CHANNEL = "1342423579223920686"
CLIENT_ID            = "1487468259702739135"
CLIENT_SECRET        = "1n64oAOmAzEhN9haKrx8k88_k-UogatB"
ROLE_ADMIN           = "1474517059143729234"
ROLE_PROBATION       = "1474517059143729235"
BOT_BRIDGE_URL       = "http://127.0.0.1:6000/post-review"

OAUTH_REDIRECT_URI   = "https://voids-craft-studio.vercel.app/"
OAUTH_SCOPES         = "identify gdm.join guilds messages.read rpc.video.read rpc activities.write rpc.voice.read guilds.channels.read guilds.join connections"

DEPT_TO_ROLE = {
    "investigation":"1342014734156959804",
    "sales":        "1342020629901213807",
    "marketing":    "1342015527538921573",
    "support":      "1342015383108063304",
    "development":  "1342014965426688010",
    "moderation":   "1453125788898431058",
    "qa":           "1342015104484376576",
}

MANAGER_ROLE_MAP = {
    "1341860517224120462":{"dept":"sales_manager",      "folder":"sales_manager",      "title":"Sales Manager",           "base_dept":"sales",        "color":"#f59e0b","emoji":"S"},
    "1341860279050305656":{"dept":"marketing_manager",  "folder":"marketing_manager",  "title":"Marketing Manager",       "base_dept":"marketing",    "color":"#ec4899","emoji":"M"},
    "1341859942805798965":{"dept":"support_manager",    "folder":"support_manager",    "title":"Support Manager",         "base_dept":"support",      "color":"#06b6d4","emoji":"CS"},
    "1364580443927609445":{"dept":"development_manager","folder":"development_manager","title":"Development Manager",     "base_dept":"development",  "color":"#6366f1","emoji":"DV"},
    "1341860888939991151":{"dept":"qa_manager",         "folder":"qa_manager",         "title":"QA Manager",              "base_dept":"qa",           "color":"#22d3a0","emoji":"QA"},
    "1341859477120483489":{"dept":"ia_manager",         "folder":"ia_manager",         "title":"Internal Affairs Manager","base_dept":"investigation","color":"#e11d48","emoji":"IA"},
}

TEAM_CONFIG = {
    "CEO":{"user_ids":["1341845440835883099","1063338723883896892","685391998152081412"],"title":"Chief Executive Officer"},
    "Secretary":{"user_ids":["1234023191135916084"],"title":"Secretary"},
    "OM":{"role_id":"1474517059143729234","title":"Operations Manager"},
    "Sales Manager":{"user_ids":["1039160061689352294"],"title":"Sales Manager"},
    "Marketing Manager":{"user_ids":["1165571218414510090"],"title":"Marketing Manager"},
    "Development Management":{"special":"Overseen by Management","title":"Development Management"},
    "Customer Support Manager":{"user_ids":["1338789690068701204"],"title":"Customer Support Manager"},
    "QA Manager":{"vacant":True,"title":"QA Manager"},
    "Internal Affairs Manager":{"vacant":True,"title":"Internal Affairs Manager"},
}

ALL_DEPTS = [
    ("investigation","Investigation","#e11d48"),
    ("sales","Sales","#f59e0b"),
    ("marketing","Marketing","#ec4899"),
    ("support","Support","#06b6d4"),
    ("development","Development","#6366f1"),
    ("moderation","Moderation","#8b5cf6"),
    ("qa","QA","#22d3a0"),
]

# Maps each manager folder to the page that hosts the job form.
# Only folders that actually have ops.html should be in OPS_FOLDERS.
OPS_FOLDERS = ('marketing_manager', 'support_manager', 'qa_manager', 'ia_manager')

# Per-folder overrides: folder -> page name (without .html).
# If a folder is not listed here, the default logic below applies.
_JOB_PAGE_MAP = {
    'development_manager': 'broadcasts',
    'sales_manager':       'job-creator',
}
_ANN_PAGE_MAP = {
    'sales_manager': 'broadcasts',
}

def get_manager_job_page(folder):
    if folder in _JOB_PAGE_MAP:
        return _JOB_PAGE_MAP[folder]
    if folder in OPS_FOLDERS:
        return 'ops'
    return 'job-creator'

def get_manager_ann_page(folder):
    if folder in _ANN_PAGE_MAP:
        return _ANN_PAGE_MAP[folder]
    if folder in OPS_FOLDERS:
        return 'ops'
    return 'broadcasts'

# ─────────────────────────────────────────────────────────────────────────────
# FIX 1: SECURITY JS — removed RAF blackout loop that caused black/white flash.
# Kept: right-click block, keyboard shortcuts, tab-blur shield, devtools heuristic,
# canvas poisoning, drag/select prevention, watermark text.
# ─────────────────────────────────────────────────────────────────────────────
SECURITY_JS = """
<style id="void-sec">
* {
  -webkit-user-select: none !important;
  -moz-user-select:    none !important;
  user-select:         none !important;
}
img, video, canvas, svg {
  pointer-events: none;
  -webkit-user-drag: none;
}
body::after {
  content: "VOIDCRAFT · CONFIDENTIAL · VOIDCRAFT · CONFIDENTIAL · VOIDCRAFT · CONFIDENTIAL";
  position: fixed;
  top: 50%; left: 50%;
  transform: translate(-50%,-50%) rotate(-28deg);
  font-size: 48px;
  font-weight: 900;
  letter-spacing: .14em;
  color: rgba(255,255,255,0.028);
  white-space: nowrap;
  pointer-events: none;
  z-index: 2147483644;
  font-family: monospace;
}
#void-blur-shield {
  display: none;
  position: fixed;
  inset: 0;
  background: #000000;
  z-index: 2147483647;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 16px;
}
#void-blur-shield.active { display: flex; }
#void-blur-shield svg { width:52px;height:52px;color:#6366f1; }
#void-blur-shield p {
  color:#edf0fa;
  font-size:14px;
  font-family:monospace;
  letter-spacing:.1em;
  text-transform:uppercase;
}
</style>

<div id="void-blur-shield">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
    <path d="M7 11V7a5 5 0 0110 0v4"/>
  </svg>
  <p>Content hidden — return to tab to continue</p>
</div>

<script>
(function(){
  'use strict';

  var shield = document.getElementById('void-blur-shield');

  /* ── 1. Tab blur / visibility shield ───────────────────────────────── */
  function showShield() {
    if (shield) shield.classList.add('active');
  }
  function hideShield() {
    if (shield) shield.classList.remove('active');
  }

  document.addEventListener('visibilitychange', function() {
    if (document.hidden) showShield(); else hideShield();
  });
  window.addEventListener('blur',  showShield);
  window.addEventListener('focus', hideShield);

  /* ── 2. Keyboard shortcuts ─────────────────────────────────────────── */
  document.addEventListener('keydown', function(e) {
    var k = e.key, ct = e.ctrlKey, sh = e.shiftKey, mt = e.metaKey, alt = e.altKey;
    if (k === 'PrintScreen' || k === 'Print Screen') {
      e.preventDefault(); e.stopPropagation();
      showShield(); setTimeout(hideShield, 3000);
      return;
    }
    if (k === 'F12') { e.preventDefault(); return; }
    if (ct && sh && ['i','I','j','J','c','C','k','K'].indexOf(k) > -1) { e.preventDefault(); return; }
    if (ct && !sh && ['u','U','s','S','p','P','a','A'].indexOf(k) > -1) { e.preventDefault(); return; }
    if (mt && sh && ['3','4','5'].indexOf(k) > -1) { e.preventDefault(); return; }
    if (mt && ['s','S'].indexOf(k) > -1) { e.preventDefault(); return; }
    if (alt && (k === 'PrintScreen' || k === 'Print Screen')) {
      e.preventDefault(); showShield(); setTimeout(hideShield, 3000); return;
    }
  }, true);

  /* ── 3. Right-click / drag / selection prevention ──────────────────── */
  document.addEventListener('contextmenu', function(e) { e.preventDefault(); return false; });
  document.addEventListener('dragstart',   function(e) { e.preventDefault(); });
  document.addEventListener('selectstart', function(e) { e.preventDefault(); });

  /* ── 4. DevTools size heuristic ────────────────────────────────────── */
  var _devOpen = false;
  setInterval(function() {
    var wD = window.outerWidth  - window.innerWidth;
    var hD = window.outerHeight - window.innerHeight;
    var open = wD > 160 || hD > 160;
    if (open  && !_devOpen) { _devOpen = true;  showShield(); }
    if (!open &&  _devOpen) { _devOpen = false; hideShield(); }
  }, 700);

  /* ── 5. Canvas fingerprint poisoning ───────────────────────────────── */
  try {
    var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {
      if (this.width > 16 || this.height > 16) {
        var c = document.createElement('canvas');
        c.width = this.width; c.height = this.height;
        return origToDataURL.call(c, type);
      }
      return origToDataURL.apply(this, arguments);
    };
    var origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(x,y,w,h) {
      var data = origGetImageData.call(this,x,y,w,h);
      for (var i=0; i<data.data.length; i+=4) {
        data.data[i]   = 0;
        data.data[i+1] = 0;
        data.data[i+2] = 0;
      }
      return data;
    };
  } catch(e) {}

})();
</script>"""

# ─────────────────────────────────────────────────────────────────────────────
# CHOOSER HTML (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
CHOOSER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>VoidCraft — Select Portal</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,700;12..96,800&display=swap" rel="stylesheet"/>
{{ security_js | safe }}
<style>
:root {
  --bg:     #060711;
  --bg2:    #0a0c18;
  --card:   #0d0f1d;
  --card2:  #11142a;
  --border: #1a1d35;
  --border2:#222645;
  --text:   #e8ecff;
  --text2:  #7b82aa;
  --text3:  #3d4268;
  --accent: #5b5ef4;
  --accent2:#7c7ef7;
  --font:   'Space Grotesk', sans-serif;
  --display:'Bricolage Grotesque', sans-serif;
  --mono:   'JetBrains Mono', monospace;
  --r:      10px;
  --r2:     14px;
  --r3:     18px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body {
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}
.bg-grid {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(91,94,244,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(91,94,244,.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 80% 80% at 50% 0%, black 0%, transparent 70%);
}
.bg-glow {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 70% 50% at 50% -10%, rgba(91,94,244,.22) 0%, transparent 60%),
    radial-gradient(ellipse 40% 30% at 10% 90%,  rgba(91,94,244,.07) 0%, transparent 55%),
    radial-gradient(ellipse 30% 25% at 90% 80%,  rgba(236,72,153,.05) 0%, transparent 55%);
}
.bg-noise {
  position: fixed; inset: 0; z-index: 0; pointer-events: none; opacity: .18;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.1'/%3E%3C/svg%3E");
}
.page { position: relative; z-index: 1; width: 100%; max-width: 1040px; margin: 0 auto; padding: 52px 28px 72px; }
.header { text-align: center; margin-bottom: 60px; }
.logo-wrap {
  display: inline-flex; align-items: center; justify-content: center;
  width: 68px; height: 68px; border-radius: 18px; margin-bottom: 24px;
  background: linear-gradient(145deg, rgba(91,94,244,.25), rgba(91,94,244,.08));
  border: 1px solid rgba(91,94,244,.35);
  box-shadow: 0 0 0 4px rgba(91,94,244,.06), 0 0 40px rgba(91,94,244,.2), 0 12px 40px rgba(0,0,0,.5);
  position: relative;
}
.logo-wrap::after {
  content: '';
  position: absolute; inset: -1px; border-radius: 19px;
  background: linear-gradient(145deg, rgba(91,94,244,.5), transparent 60%);
  z-index: -1;
}
.logo-wrap svg { width: 28px; height: 28px; color: #818cf8; }
.eyebrow {
  display: inline-flex; align-items: center; gap: 10px; margin-bottom: 16px;
  font-family: var(--mono); font-size: 10px; letter-spacing: .22em; text-transform: uppercase;
  color: rgba(129,140,248,.65);
}
.eyebrow::before, .eyebrow::after {
  content: ''; display: block; width: 20px; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(91,94,244,.5));
}
.eyebrow::after { background: linear-gradient(90deg, rgba(91,94,244,.5), transparent); }
h1 {
  font-family: var(--display);
  font-size: clamp(32px, 5vw, 48px);
  font-weight: 800;
  letter-spacing: -.04em;
  line-height: 1;
  margin-bottom: 14px;
  color: var(--text);
}
h1 em {
  font-style: normal;
  background: linear-gradient(135deg, #818cf8 0%, #5b5ef4 50%, #a78bfa 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.sub {
  font-size: 14px; color: var(--text2); max-width: 340px; margin: 0 auto 28px;
  line-height: 1.65;
}
.user-chip {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 5px 16px 5px 6px; border-radius: 100px;
  background: rgba(91,94,244,.06);
  border: 1px solid rgba(91,94,244,.2);
  backdrop-filter: blur(10px);
}
.chip-av {
  width: 30px; height: 30px; border-radius: 50%; overflow: hidden; flex-shrink: 0;
  border: 1.5px solid rgba(91,94,244,.4);
  box-shadow: 0 0 10px rgba(91,94,244,.25);
}
.chip-av img   { width: 100%; height: 100%; object-fit: cover; }
.chip-av-ph    {
  width: 100%; height: 100%;
  background: rgba(91,94,244,.2);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 12px; font-weight: 600; color: #818cf8;
}
.chip-name     { font-size: 13px; font-weight: 600; color: var(--text); }
.chip-status   {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--mono); font-size: 9px; letter-spacing: .12em; color: #34d399;
  padding: 2px 8px; border-radius: 20px;
  background: rgba(52,211,153,.08); border: 1px solid rgba(52,211,153,.2);
}
.chip-status::before {
  content: ''; width: 5px; height: 5px; border-radius: 50%;
  background: #34d399; box-shadow: 0 0 5px #34d399;
  animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: .4; } }
.section-row {
  display: flex; align-items: center; gap: 14px;
  margin: 48px 0 20px;
}
.section-label {
  font-family: var(--mono); font-size: 9px; text-transform: uppercase;
  letter-spacing: .22em; color: var(--text3); white-space: nowrap;
}
.section-line { flex: 1; height: 1px; background: linear-gradient(90deg, var(--border2), transparent); }
.section-pill {
  font-family: var(--mono); font-size: 9px; padding: 2px 9px; border-radius: 20px;
  background: var(--card2); border: 1px solid var(--border2); color: var(--text3);
}
.portal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }
.pcard {
  position: relative; display: flex; flex-direction: column;
  padding: 22px 20px 20px; background: var(--card);
  border: 1px solid var(--border); border-radius: var(--r3);
  text-decoration: none; color: var(--text); overflow: hidden;
  transition: border-color .2s, transform .18s, box-shadow .2s;
  cursor: pointer;
  animation: fadeUp .4s ease both;
}
.pcard::before {
  content: ''; position: absolute; top: -40px; right: -40px;
  width: 130px; height: 130px; border-radius: 50%;
  background: var(--c, #5b5ef4);
  filter: blur(50px); opacity: 0; transition: opacity .35s;
  pointer-events: none;
}
.pcard:hover { transform: translateY(-4px); }
.pcard:hover::before { opacity: .2; }
.pcard.t-admin:hover  { border-color: rgba(240,180,41,.4);  box-shadow: 0 8px 36px rgba(240,180,41,.08); }
.pcard.t-mgr:hover    { box-shadow: 0 8px 36px rgba(0,0,0,.45); }
.pcard.t-staff:hover  { box-shadow: 0 8px 36px rgba(0,0,0,.45); }
.pcard-line {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--c, #5b5ef4), transparent 80%);
  border-radius: var(--r3) var(--r3) 0 0;
}
.pcard-icon {
  width: 44px; height: 44px; border-radius: 11px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 11px; font-weight: 600; letter-spacing: .03em;
  margin-bottom: 15px; flex-shrink: 0; position: relative; z-index: 1;
  background: color-mix(in srgb, var(--c, #5b5ef4) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--c, #5b5ef4) 28%, transparent);
  color: var(--c, #5b5ef4);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
}
.pcard-name {
  font-family: var(--display); font-size: 14.5px; font-weight: 700;
  color: var(--text); line-height: 1.2; margin-bottom: 6px;
  position: relative; z-index: 1;
}
.pcard-desc {
  font-size: 11.5px; color: var(--text2); line-height: 1.45;
  margin-bottom: 14px; position: relative; z-index: 1;
}
.pcard-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: 20px;
  font-family: var(--mono); font-size: 8.5px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .1em;
  position: relative; z-index: 1; align-self: flex-start; margin-top: auto;
  background: color-mix(in srgb, var(--c, #5b5ef4) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--c, #5b5ef4) 22%, transparent);
  color: var(--c, #5b5ef4);
}
.pcard-badge::before {
  content: ''; width: 5px; height: 5px; border-radius: 50%;
  background: var(--c, #5b5ef4);
  box-shadow: 0 0 5px var(--c, #5b5ef4);
}
.pcard-arrow {
  position: absolute; top: 18px; right: 18px;
  width: 18px; height: 18px; color: var(--text3);
  opacity: 0; transform: translateX(-6px);
  transition: opacity .2s, transform .2s;
}
.pcard:hover .pcard-arrow { opacity: .7; transform: translateX(0); }
.footer {
  text-align: center; margin-top: 56px;
  display: flex; flex-direction: column; align-items: center; gap: 16px;
}
.footer-meta {
  font-family: var(--mono); font-size: 10px; color: var(--text3);
  display: flex; align-items: center; gap: 10px;
}
.footer-meta span { color: var(--text2); }
.footer-dot { width: 3px; height: 3px; border-radius: 50%; background: var(--text3); }
.logout-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 22px; border-radius: var(--r2);
  background: rgba(239,68,68,.06); border: 1px solid rgba(239,68,68,.18);
  color: #f87171; font-size: 12.5px; font-family: var(--font); font-weight: 500;
  text-decoration: none; letter-spacing: .01em;
  transition: background .15s, border-color .15s, transform .15s;
}
.logout-btn:hover {
  background: rgba(239,68,68,.13); border-color: rgba(239,68,68,.38);
  transform: translateY(-1px);
}
.logout-btn svg { width: 13px; height: 13px; }
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}
{% for i in range(40) %}.pcard:nth-child({{ i+1 }}) { animation-delay: {{ '%.2f'|format(i*0.045) }}s; }{% endfor %}
@media (max-width: 600px) {
  .page { padding: 32px 16px 48px; }
  h1 { font-size: 30px; }
  .portal-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 400px) {
  .portal-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="bg-grid"></div>
<div class="bg-glow"></div>
<div class="bg-noise"></div>

<div class="page">

  <div class="header">
    <div class="logo-wrap">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
      </svg>
    </div>
    <div class="eyebrow">VoidCraft Staff Portal</div>
    <h1>Select <em>Portal</em></h1>
    <p class="sub">You have access to multiple areas. Choose which dashboard to open.</p>
    <div class="user-chip">
      <div class="chip-av">
        {% if pfp %}
          <img src="{{ pfp }}" alt=""
               onerror="this.parentElement.innerHTML='<div class=chip-av-ph>{{ (username or 'U')[0]|upper }}</div>'">
        {% else %}
          <div class="chip-av-ph">{{ (username or 'U')[0]|upper }}</div>
        {% endif %}
      </div>
      <span class="chip-name">{{ username }}</span>
      <span class="chip-status">Online</span>
    </div>
  </div>

  {% if is_admin %}
  <div class="section-row">
    <span class="section-label">Administrator</span>
    <div class="section-line"></div>
    <span class="section-pill">{{ 1 + all_manager_portals|length + all_depts|length }} portals</span>
  </div>
  <div class="portal-grid">
    <a href="/portal/admin/dashboard" class="pcard t-admin" style="--c:#f0b429">
      <div class="pcard-line"></div>
      <div class="pcard-icon">ADM</div>
      <div class="pcard-name">Admin Panel</div>
      <div class="pcard-desc">Full system control, staff management &amp; audit logs.</div>
      <div class="pcard-badge">Administrator</div>
      <svg class="pcard-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
      </svg>
    </a>
    {% for folder, title, base, color in all_manager_portals %}
    <a href="/manager/{{ folder }}/dashboard" class="pcard t-admin" style="--c:{{ color }}">
      <div class="pcard-line"></div>
      <div class="pcard-icon">MGR</div>
      <div class="pcard-name">{{ title }}</div>
      <div class="pcard-desc">{{ base|capitalize }} manager dashboard.</div>
      <div class="pcard-badge">Mgr View</div>
      <svg class="pcard-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
      </svg>
    </a>
    {% endfor %}
    {% for dept_key, dept_label, color in all_depts %}
    <a href="/portal/{{ dept_key }}/dashboard" class="pcard t-admin" style="--c:{{ color }}">
      <div class="pcard-line"></div>
      <div class="pcard-icon">{{ dept_key[:3]|upper }}</div>
      <div class="pcard-name">{{ dept_label }}</div>
      <div class="pcard-desc">{{ dept_key|capitalize }} staff dashboard.</div>
      <div class="pcard-badge">Staff View</div>
      <svg class="pcard-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
      </svg>
    </a>
    {% endfor %}
  </div>
  {% endif %}

  {% if manager_portals %}
  <div class="section-row">
    <span class="section-label">Your Manager Portals</span>
    <div class="section-line"></div>
    <span class="section-pill">{{ manager_portals|length }}</span>
  </div>
  <div class="portal-grid">
    {% for p in manager_portals %}
    <a href="/manager/{{ p.folder }}/dashboard" class="pcard t-mgr" style="--c:{{ p.color }}">
      <div class="pcard-line"></div>
      <div class="pcard-icon">{{ p.emoji }}</div>
      <div class="pcard-name">{{ p.title }}</div>
      <div class="pcard-desc">{{ p.base_dept|capitalize }} department manager dashboard.</div>
      <div class="pcard-badge">Manager</div>
      <svg class="pcard-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
      </svg>
    </a>
    {% endfor %}
  </div>
  {% endif %}

  {% if staff_depts %}
  <div class="section-row">
    <span class="section-label">Your Staff Portals</span>
    <div class="section-line"></div>
    <span class="section-pill">{{ staff_depts|length }}</span>
  </div>
  <div class="portal-grid">
    {% for sd in staff_depts %}
    <a href="/portal/{{ sd.dept }}/dashboard" class="pcard t-staff" style="--c:{{ sd.color }}">
      <div class="pcard-line"></div>
      <div class="pcard-icon">{{ sd.dept[:3]|upper }}</div>
      <div class="pcard-name">{{ sd.dept|capitalize }}</div>
      <div class="pcard-desc">
        {{ sd.dept|capitalize }} department portal.
        {% if sd.probation %}&nbsp;<span style="color:#fbbf24">· Probation</span>{% endif %}
      </div>
      <div class="pcard-badge">Staff</div>
      <svg class="pcard-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
      </svg>
    </a>
    {% endfor %}
  </div>
  {% endif %}

  <div class="footer">
    <div class="footer-meta">
      Logged in as <span>{{ username }}</span>
      <span class="footer-dot"></span>
      VoidCraft Staff Portal
    </div>
    <a href="/logout" class="logout-btn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>
        <polyline points="16 17 21 12 16 7"/>
        <line x1="21" y1="12" x2="9" y2="12"/>
      </svg>
      Sign Out
    </a>
  </div>

</div>
</body>
</html>"""

# ─── Data layer ───────────────────────────────────────────────────────────────
def load_history():
    try:
        with open(LOGS_FILE,'r') as f:
            d=json.load(f)
            for k in ("accepted_logs","pending_logs","denied_logs","directives","broadcasts"):
                d.setdefault(k,[])
            return d
    except Exception:
        return {"accepted_logs":[],"pending_logs":[],"denied_logs":[],"directives":[],"broadcasts":[]}

history       = load_history()
accepted_logs = history["accepted_logs"]
pending_logs  = history["pending_logs"]
denied_logs   = history["denied_logs"]
directives    = history["directives"]
broadcasts    = history["broadcasts"]

def save_history():
    with open(LOGS_FILE,'w') as f:
        json.dump({"accepted_logs":accepted_logs,"pending_logs":pending_logs,
                   "denied_logs":denied_logs,"directives":directives,"broadcasts":broadcasts},f,indent=4)

def load_staff():
    try:
        with open(STAFF_FILE,'r') as f: return json.load(f)
    except Exception: return {}

def save_staff(s):
    with open(STAFF_FILE,'w') as f: json.dump(s,f,indent=4)

def register_staff_login(uid,username,pfp,dept,role):
    s=load_staff()
    if s.get(uid,{}).get("terminated"): return False
    s[uid]={"uid":uid,"username":username,"pfp":pfp,"dept":dept,"role":role,
            "last_login":datetime.now().strftime("%Y-%m-%d %H:%M"),"active":True,"terminated":False}
    save_staff(s); return True

def kick_staff_member(uid):
    s=load_staff()
    if uid in s: s[uid]["active"]=False; save_staff(s)

def terminate_staff_member(uid):
    s=load_staff()
    if uid in s: s[uid]["active"]=False; s[uid]["terminated"]=True; save_staff(s)
    _put(f"https://discord.com/api/guilds/{GUILD_ID}/bans/{uid}",
         headers={"Authorization":f"Bot {BOT_TOKEN}","Content-Type":"application/json"},
         json={"delete_message_days":0,"reason":"Terminated via Staff Manager"})

def revoke_termination(uid):
    s=load_staff()
    if uid in s: s[uid]["active"]=True; s[uid]["terminated"]=False; save_staff(s)
    _delete(f"https://discord.com/api/guilds/{GUILD_ID}/bans/{uid}",
            headers={"Authorization":f"Bot {BOT_TOKEN}"})

# ─── Helpers ──────────────────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    from flask import session as _s
    return {"now":datetime.now,"session":_s}

def format_dept(k):
    return "ALL DEPARTMENTS" if k=="all" else k.upper()

def normalize_log_type(t):
    if not t: return "Unknown"
    lt=t.lower()
    if lt in("sale","sales"): return "Sales"
    if lt=="outreach":        return "Outreach"
    if lt=="giveaway":        return "Giveaway"
    if lt=="investigation":   return "Investigation"
    return t

def filter_by_dept(items, view_dept, is_admin):
    """Return items visible to view_dept.
    view_dept must be a base dept key e.g. 'sales', 'marketing'.
    Items with dept_key='all' are shown to everyone.
    Items with a specific dept_key are ONLY shown to that exact dept.
    """
    if is_admin:
        return items
    return [i for i in items
            if i.get("dept_key") == "all" or i.get("dept_key") == view_dept]

def build_template_vars(uid,user_dept,is_admin,manager_base_dept=None):
    def bt(logs,t): return [l for l in logs if normalize_log_type(l.get('type'))==t]
    def uf(logs):
        if is_admin: return logs
        if manager_base_dept: return [l for l in logs if l.get('dept')==manager_base_dept]
        return [l for l in logs if str(l.get('user_id',''))==str(uid)]
    all_logs=accepted_logs+pending_logs+denied_logs

    # Resolve filter_dept to a base dept key (e.g. 'sales', 'marketing').
    # manager_base_dept is already correct when provided.
    # user_dept for staff portals = URL dept = correct base key.
    # user_dept for manager sessions = 'sales_manager' etc — strip suffix.
    if manager_base_dept:
        filter_dept = manager_base_dept
    elif user_dept and user_dept.endswith('_manager'):
        filter_dept = user_dept.replace('_manager', '')
    else:
        filter_dept = user_dept

    return {
        "uid":uid,"is_admin":is_admin,"user_dept":user_dept,"manager_base_dept":manager_base_dept,
        "staff_list":list(load_staff().values()),
        "sales_logs":             uf(bt(all_logs,"Sales")),
        "outreach_logs":          uf(bt(all_logs,"Outreach")),
        "giveaway_logs":          uf(bt(all_logs,"Giveaway")),
        "investigation_logs":     uf(bt(all_logs,"Investigation")),
        "marketing_logs":         uf([l for l in all_logs if l.get('dept')=='marketing']),
        "accepted_logs":          uf(accepted_logs),
        "accepted_sales":         uf(bt(accepted_logs,"Sales")),
        "accepted_outreach":      uf(bt(accepted_logs,"Outreach")),
        "accepted_giveaway":      uf(bt(accepted_logs,"Giveaway")),
        "accepted_investigation": uf(bt(accepted_logs,"Investigation")),
        "accepted_marketing":     uf([l for l in accepted_logs if l.get('dept')=='marketing']),
        "pending_logs":           uf(pending_logs),
        "denied_logs":            uf(denied_logs),
        "directives":             filter_by_dept(directives, filter_dept, is_admin),
        "broadcasts":             filter_by_dept(broadcasts, filter_dept, is_admin),
    }

# ─── Session helpers ──────────────────────────────────────────────────────────
def get_all_manager_portals_list():
    return [(cfg["folder"],cfg["title"],cfg["base_dept"],cfg.get("color","#6366f1"))
            for cfg in MANAGER_ROLE_MAP.values()]

def get_allowed_manager_folders():
    if session.get('role')=='admin':
        return [cfg["folder"] for cfg in MANAGER_ROLE_MAP.values()]
    return [p['folder'] for p in session.get('manager_portals',[])]

def get_allowed_staff_depts():
    if session.get('role')=='admin':
        return [d for d,_,_ in ALL_DEPTS]
    depts=list({sd['dept'] for sd in session.get('staff_depts',[])})
    for p in session.get('manager_portals',[]):
        if p['base_dept'] not in depts: depts.append(p['base_dept'])
    return depts

def get_manager_base_dept_for_folder(folder):
    if session.get('role')=='admin':
        for cfg in MANAGER_ROLE_MAP.values():
            if cfg['folder']==folder: return cfg['base_dept']
        return ''
    for p in session.get('manager_portals',[]):
        if p['folder']==folder: return p['base_dept']
    return ''

# ─── Decorators ───────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if 'username' not in session: return redirect(url_for('index'))
        return f(*a,**k)
    return w

def manager_required(f):
    @wraps(f)
    def w(*a,**k):
        if 'username' not in session: return redirect(url_for('index'))
        if session.get('role') not in ('manager','admin'): abort(403)
        return f(*a,**k)
    return w

def bot_auth_required(f):
    @wraps(f)
    def w(*a,**k):
        key=request.headers.get("X-Bot-Key") or (request.json or {}).get("bot_key")
        if key!=BOT_API_KEY: return jsonify({"status":"error","message":"Unauthorized"}),401
        return f(*a,**k)
    return w

# ─── Discord helpers ──────────────────────────────────────────────────────────
def send_dm(uid,msg):
    h={"Authorization":f"Bot {BOT_TOKEN}"}
    ch=_post("https://discord.com/api/users/@me/channels",headers=h,json={"recipient_id":uid})
    if ch.status_code==200:
        cid=ch.json().get("id")
        _post(f"https://discord.com/api/channels/{cid}/messages",headers=h,json={"content":msg})

def send_log_embed(embed,channel_id=None):
    ch=channel_id or JOB_LOG_CHANNEL
    _post(f"https://discord.com/api/channels/{ch}/messages",
          headers={"Authorization":f"Bot {BOT_TOKEN}","Content-Type":"application/json"},
          json={"embeds":[embed]})

def notify_department(dept_key,message):
    h={"Authorization":f"Bot {BOT_TOKEN}"}
    res=_get(f"https://discord.com/api/guilds/{GUILD_ID}/members?limit=1000",headers=h)
    if res.status_code!=200: return
    for m in res.json():
        if dept_key=="all": send_dm(m["user"]["id"],message)
        else:
            rid=DEPT_TO_ROLE.get(dept_key)
            if rid and rid in m.get("roles",[]): send_dm(m["user"]["id"],message)

def notify_bot_post_review(log):
    def _send():
        d=log.get("details",{}) if isinstance(log.get("details"),dict) else {}
        body={"log_id":log["id"],"user_id":log.get("user_id"),"payload":{
            "type":"Investigation",
            "investigator":  d.get("investigator",log.get("username","---")),
            "reported_user": d.get("reported_user","---"),
            "reporting_user":d.get("reporting_user","---"),
            "date":d.get("date","---"),"outcome":d.get("outcome","---"),
            "reason":d.get("reason","---"),
            "case_number":d.get("case_number",log.get("id","---")),
            "proof":log.get("proof",""),
        }}
        for attempt in range(1,4):
            try:
                r=_post(BOT_BRIDGE_URL,json=body,headers={"X-Bot-Key":BOT_API_KEY,"Content-Type":"application/json"})
                if r.status_code==200: return
            except Exception as e:
                if attempt<3: time.sleep(2)
    threading.Thread(target=_send,daemon=True).start()

def send_inv_accepted_embed(log):
    d=log.get("details",{}) if isinstance(log.get("details"),dict) else {}
    send_log_embed({"title":"Case Log Accepted","color":2277736,"fields":[
        {"name":"Log ID",        "value":str(log.get("id","---")),             "inline":True},
        {"name":"Investigator",  "value":log.get("username","---"),            "inline":True},
        {"name":"Case #",        "value":d.get("case_number","---") or "---",  "inline":True},
        {"name":"Reported User", "value":d.get("reported_user","---") or "---","inline":True},
        {"name":"Reporting User","value":d.get("reporting_user","---") or "---","inline":True},
        {"name":"Date of Case",  "value":d.get("date","---") or "---",         "inline":True},
        {"name":"Outcome",       "value":d.get("outcome","---") or "---",      "inline":True},
        {"name":"Reason",        "value":d.get("reason","---") or "---",       "inline":False},
        {"name":"Google Doc",    "value":log.get("proof","None") or "None",    "inline":False},
        {"name":"Reviewed By",   "value":log.get("reviewed_by","---"),         "inline":True},
        {"name":"Reviewed At",   "value":log.get("reviewed_at","---"),         "inline":True},
    ],"timestamp":datetime.utcnow().isoformat()},channel_id=INV_ACCEPTED_CHANNEL)

def get_team_members():
    h={"Authorization":f"Bot {BOT_TOKEN}"}
    try:
        res=_get(f"https://discord.com/api/guilds/{GUILD_ID}/members?limit=1000",headers=h)
        if res.status_code!=200: return get_placeholder_members()
        all_m=res.json(); out={}
        for pos,cfg in TEAM_CONFIG.items():
            if cfg.get("vacant"):  out[pos]={"username":"Vacant","pfp":"","uid":""}; continue
            if cfg.get("special"): out[pos]={"username":cfg["special"],"pfp":"","uid":"","special":True}; continue
            found=False
            if "user_ids" in cfg:
                matched=[]
                for m in all_m:
                    u=m.get("user",{})
                    if u.get("id") in cfg["user_ids"]:
                        matched.append({"username":u.get("username","Unknown"),"uid":u["id"],
                            "pfp":f"https://cdn.discordapp.com/avatars/{u['id']}/{u.get('avatar')}.png" if u.get('avatar') else ""})
                if matched:
                    out[pos]=matched[0]
                    if pos=="CEO" and len(matched)>1:
                        out[pos]["username"]=" & ".join(x["username"] for x in matched); out[pos]["all_ceos"]=matched
                    found=True
            elif "role_id" in cfg:
                for m in all_m:
                    if cfg["role_id"] in m.get("roles",[]):
                        u=m["user"]; out[pos]={"username":u.get("username","Unknown"),"uid":u["id"],
                            "pfp":f"https://cdn.discordapp.com/avatars/{u['id']}/{u.get('avatar')}.png" if u.get('avatar') else ""}
                        found=True; break
            if not found and pos not in out: out[pos]={"username":"Vacant","pfp":"","uid":""}
        return out
    except Exception as e:
        print(f"[ERROR] get_team_members: {e}"); return get_placeholder_members()

def get_placeholder_members():
    out={}
    for pos,cfg in TEAM_CONFIG.items():
        if cfg.get("special"): out[pos]={"username":cfg["special"],"pfp":"","uid":"","special":True}
        else:                  out[pos]={"username":"Vacant","pfp":"","uid":""}
    return out

def get_dept_members_from_discord(dept_key):
    role_id=DEPT_TO_ROLE.get(dept_key)
    if not role_id: return []
    h={"Authorization":f"Bot {BOT_TOKEN}"}
    try:
        res=_get(f"https://discord.com/api/guilds/{GUILD_ID}/members?limit=1000",headers=h)
        if res.status_code!=200: return []
        staff_db=load_staff(); result=[]; now=datetime.now()
        for member in res.json():
            if role_id not in member.get("roles",[]): continue
            user=member.get("user",{}); uid=user.get("id",""); uname=user.get("username","Unknown")
            avatar=user.get("avatar")
            pfp=f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png" if avatar else ""
            db=staff_db.get(uid,{}); last=db.get("last_login",""); is_online=False
            try:
                ll=datetime.strptime(last,"%Y-%m-%d %H:%M"); is_online=(now-ll).total_seconds()<1800
            except Exception: pass
            result.append({"uid":uid,"username":uname,"nick":member.get("nick") or uname,"pfp":pfp,
                "online":is_online,"last_login":last,"probation":ROLE_PROBATION in member.get("roles",[]),
                "role":db.get("role","member"),"active":db.get("active",True)})
        result.sort(key=lambda x:(not x["online"],x["username"].lower()))
        return result
    except Exception as e:
        print(f"[ERROR] get_dept_members_from_discord: {e}"); return []

# ─── Public routes ────────────────────────────────────────────────────────────
@app.route('/api/health')
def health():
    return jsonify({"status":"online","accepted":len(accepted_logs),"pending":len(pending_logs),
                    "denied":len(denied_logs),"directives":len(directives),"broadcasts":len(broadcasts)})

@app.route('/')
def index(): return render_template('index.html')

@app.route('/team')
def team(): return render_template('team.html',members=get_team_members())

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

@app.route('/api/dept-members/<dept_key>')
@login_required
def api_dept_members(dept_key):
    is_admin=session.get('role')=='admin'
    if session.get('role') not in ('admin','manager'): abort(403)
    if not is_admin:
        allowed_bases=[p['base_dept'] for p in session.get('manager_portals',[])]
        if dept_key not in allowed_bases: abort(403)
    return jsonify({"status":"ok","members":get_dept_members_from_discord(dept_key),"dept":dept_key})

# ─── Portal chooser ───────────────────────────────────────────────────────────
@app.route('/choose-portal')
@login_required
def choose_portal():
    is_admin       =session.get('role')=='admin'
    manager_portals=session.get('manager_portals',[])
    staff_depts    =session.get('staff_depts',[])
    if not is_admin:
        total=len(manager_portals)+len(staff_depts)
        if total==1:
            if manager_portals: return redirect(f"/manager/{manager_portals[0]['folder']}/dashboard")
            return redirect(f"/portal/{staff_depts[0]['dept']}/dashboard")
    return render_template_string(CHOOSER_HTML,
        username=session.get('username',''), pfp=session.get('pfp',''),
        is_admin=is_admin, manager_portals=manager_portals, staff_depts=staff_depts,
        all_depts=ALL_DEPTS, all_manager_portals=get_all_manager_portals_list(),
        security_js=SECURITY_JS)

# ─── OAuth callback ───────────────────────────────────────────────────────────
@app.route('/callback')
def callback():
    code=request.args.get('code')
    if not code: return redirect('/')
    try:
        td=_post("https://discord.com/api/oauth2/token",data={
            "client_id":CLIENT_ID,"client_secret":CLIENT_SECRET,"grant_type":"authorization_code",
            "code":code,"redirect_uri":OAUTH_REDIRECT_URI,"scope":OAUTH_SCOPES
        }).json()
    except Exception as e: return f"OAuth token error: {e}",500
    at=td.get("access_token")
    if not at: return "OAuth failed -- no access token"
    try: ur=_get("https://discord.com/api/users/@me",headers={"Authorization":f"Bearer {at}"}).json()
    except Exception as e: return f"Failed to fetch user info: {e}",500
    user_id=ur.get("id"); username=ur.get("username"); avatar=ur.get("avatar")
    if not user_id: return "No user data"
    try:
        mr=_get(f"https://discord.com/api/users/@me/guilds/{GUILD_ID}/member",headers={"Authorization":f"Bearer {at}"})
        roles=mr.json().get("roles",[]) if mr.status_code==200 else []
    except Exception: roles=[]
    pfp=f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png" if avatar else ""
    staff=load_staff()
    if staff.get(user_id,{}).get("terminated"):
        return render_template('access_denied.html',reason="You have been terminated from the staff portal.")
    if staff.get(user_id,{}).get("active") is False:
        return render_template('access_denied.html',reason="You have been removed from the staff portal.")
    session['username']=username; session['uid']=user_id; session['pfp']=pfp; session.permanent=True
    if ROLE_ADMIN in roles:
        session['role']='admin'; session['dept']='admin'
        register_staff_login(user_id,username,pfp,'admin','admin')
        session['manager_portals']=[]; session['staff_depts']=[]
        return redirect('/choose-portal')
    manager_portals=[]
    for role_id,cfg in MANAGER_ROLE_MAP.items():
        if role_id in roles:
            manager_portals.append({"folder":cfg["folder"],"title":cfg["title"],
                "base_dept":cfg["base_dept"],"emoji":cfg.get("emoji","MGR"),
                "color":cfg.get("color","#6366f1"),"dept":cfg["dept"]})
    staff_depts=[]
    for dept,rid in DEPT_TO_ROLE.items():
        if rid in roles:
            color=next((c for d,_,c in ALL_DEPTS if d==dept),"#6366f1")
            staff_depts.append({"dept":dept,"probation":(ROLE_PROBATION in roles),"color":color})
    if not manager_portals and not staff_depts:
        return render_template('access_denied.html',reason="You do not have a recognized role.")
    if manager_portals:
        primary=manager_portals[0]
        session['role']='manager'; session['dept']=primary['dept']
        session['manager_folder']=primary['folder']; session['manager_title']=primary['title']
        session['manager_base_dept']=primary['base_dept']
        register_staff_login(user_id,username,pfp,primary['dept'],'manager')
    else:
        sd=staff_depts[0]; role_label='probation_member' if ROLE_PROBATION in roles else 'member'
        session['role']=role_label; session['dept']=sd['dept']; session['probation']=(ROLE_PROBATION in roles)
        register_staff_login(user_id,username,pfp,sd['dept'],role_label)
    session['manager_portals']=manager_portals; session['staff_depts']=staff_depts
    total=len(manager_portals)+len(staff_depts)
    if total==1:
        if manager_portals: return redirect(f"/manager/{manager_portals[0]['folder']}/dashboard")
        return redirect(f"/portal/{staff_depts[0]['dept']}/dashboard")
    return redirect('/choose-portal')

# ─── Manager portal ───────────────────────────────────────────────────────────
@app.route('/manager/<folder>/<page>')
@manager_required
def serve_manager_portal(folder, page):
    clean = page.replace(".html", "")
    uid = session.get('uid')
    is_admin = session.get('role') == 'admin'

    if folder not in get_allowed_manager_folders():
        abort(403)

    manager_base_dept = get_manager_base_dept_for_folder(folder)

    if not is_admin:
        for p in session.get('manager_portals', []):
            if p['folder'] == folder:
                session['manager_folder'] = folder
                session['manager_title']  = p['title']
                session['manager_base_dept'] = p['base_dept']
                session['dept'] = p['dept']
                break

    vd = build_template_vars(uid, session.get('dept'), is_admin, manager_base_dept)
    vd.update({
        "username":       session.get('username'),
        "pfp":            session.get('pfp'),
        "pfp_url":        session.get('pfp'),
        "role":           session.get('role'),
        "dept":           session.get('dept'),
        "page":           clean,
        "manager_title":  session.get('manager_title', ''),
        "manager_folder": folder,
        "manager_portals":session.get('manager_portals', []),
        "staff_depts":    session.get('staff_depts', []),
        "normalize_log_type": normalize_log_type,
    })

    try:
        return render_template(f"{folder}/{clean}.html", **vd)
    except Exception:
        err = traceback.format_exc()
        print(f"[TEMPLATE ERROR] {folder}/{clean}.html\n{err}")
        return (
            f"<pre style='background:#1a1a2e;color:#f05a5a;padding:24px;"
            f"font-family:monospace;font-size:13px;white-space:pre-wrap'>"
            f"TEMPLATE ERROR: {folder}/{clean}.html\n\n{err}</pre>"
        ), 500

# ─── Create job ───────────────────────────────────────────────────────────────
@app.route('/api/create-job',methods=['POST'])
@login_required
def create_job():
    if session.get('role') not in ('admin','manager'): abort(403)
    dk=request.form.get('department_id','').strip()
    # Normalize: managers may only post to their own base dept or 'all'.
    # If the form sends a manager-folder name, convert to base dept.
    if session.get('role') == 'manager':
        base = session.get('manager_base_dept','')
        if dk not in ('all',) and dk not in [d for d,_,_ in ALL_DEPTS]:
            dk = base  # fall back to their base dept
    dn=format_dept(dk)
    job={"id":int(time.time()),"title":request.form.get('title','').strip(),
         "content":request.form.get('content','').strip(),"deadline":request.form.get('deadline','').strip(),
         "priority":request.form.get('priority','Normal').strip(),
         "dept_key":dk,"dept_name":dn,"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M")}
    directives.insert(0,job); save_history()
    notify_department(dk,f"New Job -- {dn}\n{job['title']}\n{job['content']}\nPriority: {job['priority']}\nDeadline: {job['deadline']}")
    send_log_embed({"title":"Job Directive Issued","description":job['content'],"color":3447003,
        "fields":[{"name":"Title","value":job['title'],"inline":False},
                  {"name":"Department","value":dn,"inline":True},
                  {"name":"Priority","value":job['priority'],"inline":True},
                  {"name":"Deadline","value":job['deadline'],"inline":False}],
        "timestamp":datetime.utcnow().isoformat()})
    if session.get('role') == 'admin':
        return redirect('/portal/admin/job-creator')
    # Get folder from form (hidden field) or fall back to session.
    # Validate it belongs to this manager before using.
    folder = request.form.get('manager_folder','').strip()
    allowed = get_allowed_manager_folders()
    if not folder or folder not in allowed:
        folder = session.get('manager_folder','')
    if folder and folder not in allowed:
        folder = allowed[0] if allowed else ''
    if folder:
        session['manager_folder'] = folder
        # also keep manager_base_dept in sync
        for cfg in MANAGER_ROLE_MAP.values():
            if cfg['folder'] == folder:
                session['manager_base_dept'] = cfg['base_dept']
                break
    page = get_manager_job_page(folder)
    return redirect(f'/manager/{folder}/{page}?sent=1')

# ─── Create announcement ──────────────────────────────────────────────────────
@app.route('/api/create-announcement',methods=['POST'])
@login_required
def create_announcement():
    if session.get('role') not in ('admin','manager'): abort(403)
    dk=request.form.get('department_id','').strip()
    # Normalize: managers may only post to their own base dept or 'all'.
    # If the form sends a manager-folder name, convert to base dept.
    if session.get('role') == 'manager':
        base = session.get('manager_base_dept','')
        if dk not in ('all',) and dk not in [d for d,_,_ in ALL_DEPTS]:
            dk = base  # fall back to their base dept
    dn=format_dept(dk)
    ann={"id":int(time.time()),"title":request.form.get('title','').strip(),
         "content":request.form.get('content','').strip(),"dept_key":dk,"dept_name":dn,
         "author":session.get('username'),"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M")}
    broadcasts.insert(0,ann); save_history()
    notify_department(dk,f"Announcement -- {dn}\n{ann['title']}\n\n{ann['content']}\n-- {ann['author']}")
    send_log_embed({"title":"Announcement Broadcast","description":ann['content'],"color":15844367,
        "fields":[{"name":"Title","value":ann['title'],"inline":False},
                  {"name":"Department","value":dn,"inline":True},
                  {"name":"Author","value":ann['author'],"inline":True}],
        "timestamp":datetime.utcnow().isoformat()})
    if session.get('role') == 'admin':
        return redirect('/portal/admin/broadcasts')
    # Get folder from form (hidden field) or fall back to session.
    # Validate it belongs to this manager before using.
    folder = request.form.get('manager_folder','').strip()
    allowed = get_allowed_manager_folders()
    if not folder or folder not in allowed:
        folder = session.get('manager_folder','')
    if folder and folder not in allowed:
        folder = allowed[0] if allowed else ''
    if folder:
        session['manager_folder'] = folder
        for cfg in MANAGER_ROLE_MAP.values():
            if cfg['folder'] == folder:
                session['manager_base_dept'] = cfg['base_dept']
                break
    page = get_manager_ann_page(folder)
    ref  = request.referrer or ''
    if 'reviews' in ref:     return redirect(f'/manager/{folder}/reviews?sent=1')
    if 'commissions' in ref: return redirect(f'/manager/{folder}/commissions?sent=1')
    return redirect(f'/manager/{folder}/{page}?sent=1')

# ─── Delete broadcast/job ─────────────────────────────────────────────────────
@app.route('/portal/admin/delete-broadcast/<int:bid>')
@login_required
def delete_broadcast(bid):
    if session.get('role')!='admin': abort(403)
    broadcasts[:]=[b for b in broadcasts if b.get('id')!=bid]; save_history()
    return redirect('/portal/admin/broadcasts')

@app.route('/manager/<folder>/delete-broadcast/<int:bid>')
@manager_required
def manager_delete_broadcast(folder,bid):
    if folder not in get_allowed_manager_folders(): abort(403)
    broadcasts[:]=[b for b in broadcasts if b.get('id')!=bid]; save_history()
    ref=request.referrer or ''
    page = get_manager_ann_page(folder)
    if 'reviews' in ref:     return redirect(f'/manager/{folder}/reviews')
    if 'commissions' in ref: return redirect(f'/manager/{folder}/commissions')
    return redirect(f'/manager/{folder}/{page}')

@app.route('/portal/admin/delete-job/<int:jid>')
@login_required
def delete_job(jid):
    if session.get('role')!='admin': abort(403)
    directives[:]=[d for d in directives if d.get('id')!=jid]; save_history()
    return redirect('/portal/admin/job-creator')

@app.route('/manager/<folder>/delete-job/<int:jid>')
@manager_required
def manager_delete_job(folder,jid):
    if folder not in get_allowed_manager_folders(): abort(403)
    directives[:]=[d for d in directives if d.get('id')!=jid]; save_history()
    page = get_manager_job_page(folder)
    return redirect(f'/manager/{folder}/{page}')

# ─── Staff management ─────────────────────────────────────────────────────────
@app.route('/portal/admin/kick-staff/<uid>',methods=['POST'])
@login_required
def kick_staff(uid):
    if session.get('role')!='admin': abort(403)
    kick_staff_member(uid); return redirect('/portal/admin/staff-manager')

@app.route('/portal/admin/terminate-staff/<uid>',methods=['POST'])
@login_required
def terminate_staff(uid):
    if session.get('role')!='admin': abort(403)
    terminate_staff_member(uid); return redirect('/portal/admin/staff-manager')

@app.route('/portal/admin/revoke-staff/<uid>',methods=['POST'])
@login_required
def revoke_staff(uid):
    if session.get('role')!='admin': abort(403)
    revoke_termination(uid); return redirect('/portal/admin/staff-manager')

# ─── Investigation case log ───────────────────────────────────────────────────
@app.route('/api/submit-case-log',methods=['POST'])
@login_required
def submit_case_log():
    uid=session.get('uid'); username=session.get('username'); is_admin=session.get('role')=='admin'
    manager_bases=[p['base_dept'] for p in session.get('manager_portals',[])]
    staff_dept_list=[sd['dept'] for sd in session.get('staff_depts',[])]
    allowed=(is_admin or 'investigation' in staff_dept_list or 'investigation' in manager_bases
             or session.get('dept') in ('investigation','ia_manager'))
    if not allowed: abort(403)
    log_id=str(int(time.time()))
    nl={"id":log_id,"user_id":uid,"username":username,"type":"Investigation",
        "proof":request.form.get('doc_link','').strip(),
        "details":{"reported_user":request.form.get('reported_user','').strip(),
                   "reporting_user":request.form.get('reporting_user','').strip(),
                   "investigator":request.form.get('investigator','').strip(),
                   "date":request.form.get('date','').strip(),
                   "outcome":request.form.get('outcome','').strip(),
                   "reason":request.form.get('reason','').strip(),"case_number":log_id},
        "amount":"","dept":"investigation","status":"Pending",
        "reviewed_by":"","reviewed_at":"","deny_reason":"",
        "timestamp":datetime.now().strftime("%Y-%m-%d %H:%M")}
    pending_logs.insert(0,nl); save_history(); notify_bot_post_review(nl)
    folder=session.get('manager_folder','')
    if folder=='ia_manager': return redirect(f'/manager/{folder}/logs?submitted=1')
    if session.get('role') in ('manager','admin') and folder:
        return redirect(f'/manager/{folder}/logs?submitted=1')
    return redirect('/portal/investigation/dashboard?submitted=1')

# ─── Bot API ──────────────────────────────────────────────────────────────────
@app.route('/api/submit-log',methods=['POST'])
def submit_log():
    data=request.json or {}
    key=request.headers.get("X-Bot-Key") or data.get("bot_key"); trusted=(key==BOT_API_KEY)
    log_id=str(data.get('id',str(int(time.time()))))
    all_ids=[str(l.get('id')) for l in pending_logs+accepted_logs+denied_logs]
    if log_id in all_ids: return jsonify({"status":"exists","log_id":log_id})
    status=data.get('status','Pending') if trusted else 'Pending'
    raw=data.get('details',{})
    if not isinstance(raw,dict): raw={}
    for f in('reported_user','reporting_user','investigator','date','outcome','reason','case_number'):
        if f not in raw and f in data: raw[f]=data[f]
    nl={"id":log_id,"user_id":data.get('user_id'),"username":data.get('username'),
        "type":normalize_log_type(data.get('type')),"proof":data.get('proof',''),
        "details":raw,"amount":data.get('amount',''),"dept":data.get('dept',''),
        "status":status,"reviewed_by":data.get('reviewed_by',''),"reviewed_at":data.get('reviewed_at',''),
        "deny_reason":data.get('deny_reason',''),"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M")}
    if status=='Accepted':   accepted_logs.insert(0,nl)
    elif status=='Denied':   denied_logs.insert(0,nl)
    else:                    pending_logs.insert(0,nl)
    save_history(); return jsonify({"status":"success","log_id":log_id})

@app.route('/api/accept-log/<log_id>',methods=['POST'])
@bot_auth_required
def accept_log(log_id):
    log_id=str(log_id)
    log=next((l for l in pending_logs if str(l.get('id'))==log_id),None)
    if not log:
        if next((l for l in accepted_logs if str(l.get('id'))==log_id),None):
            return jsonify({"status":"already_accepted","log_id":log_id})
        return jsonify({"status":"error","message":f"Log {log_id} not found"}),404
    data=request.json or {}
    log['status']='Accepted'; log['reviewed_by']=data.get('reviewed_by','Admin')
    log['reviewed_at']=datetime.now().strftime("%Y-%m-%d %H:%M")
    pending_logs.remove(log); accepted_logs.insert(0,log); save_history()
    if normalize_log_type(log.get('type'))=='Investigation': send_inv_accepted_embed(log)
    return jsonify({"status":"success","log_id":log_id})

@app.route('/api/deny-log/<log_id>',methods=['POST'])
@bot_auth_required
def deny_log(log_id):
    log_id=str(log_id)
    log=next((l for l in pending_logs if str(l.get('id'))==log_id),None)
    if not log:
        if next((l for l in denied_logs if str(l.get('id'))==log_id),None):
            return jsonify({"status":"already_denied","log_id":log_id})
        return jsonify({"status":"error","message":f"Log {log_id} not found"}),404
    data=request.json or {}
    log['status']='Denied'; log['deny_reason']=data.get('reason','No reason provided')
    log['reviewed_by']=data.get('reviewed_by','Admin'); log['reviewed_at']=datetime.now().strftime("%Y-%m-%d %H:%M")
    pending_logs.remove(log); denied_logs.insert(0,log); save_history()
    return jsonify({"status":"success","log_id":log_id})

# ─── Admin explicit route ─────────────────────────────────────────────────────
@app.route('/portal/admin/inv')
@login_required
def admin_inv():
    if session.get('role')!='admin': abort(403)
    uid=session.get('uid'); vd=build_template_vars(uid,'admin',is_admin=True)
    vd.update({"username":session.get('username'),"pfp":session.get('pfp'),
               "role":'admin',"dept":'admin',"page":'inv',
               "normalize_log_type":normalize_log_type})
    return render_template('admin/inv.html',**vd)

# ─── Generic staff portal — MUST BE LAST ─────────────────────────────────────
@app.route('/portal/<dept>/<page>')
@login_required
def serve_portal(dept,page):
    clean=page.replace(".html",""); uid=session.get('uid'); is_admin=session.get('role')=='admin'
    if not is_admin:
        if dept not in get_allowed_staff_depts(): abort(403)
    vd=build_template_vars(uid,dept,is_admin)
    vd.update({"username":session.get('username'),"pfp":session.get('pfp'),"pfp_url":session.get('pfp'),
               "role":session.get('role'),"probation":session.get('probation',False),"dept":dept,"page":clean,
               "manager_portals":session.get('manager_portals',[]),"staff_depts":session.get('staff_depts',[]),
               "normalize_log_type":normalize_log_type})
    try:
        return render_template(f"{dept}/{clean}.html",**vd)
    except Exception:
        err = traceback.format_exc()
        print(f"[TEMPLATE ERROR] {dept}/{clean}.html\n{err}")
        return (
            f"<pre style='background:#1a1a2e;color:#f05a5a;padding:24px;"
            f"font-family:monospace;font-size:13px;white-space:pre-wrap'>"
            f"TEMPLATE ERROR: {dept}/{clean}.html\n\n{err}</pre>"
        ), 500

if __name__=='__main__':
    app.run(debug=False, port=5000)
