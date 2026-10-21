import os, secrets, string, io, csv
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "replace-this-secret")
db_url = os.environ.get("DATABASE_URL", "sqlite:///ancient_event.db")
if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql://", 1)
if db_url.startswith("postgresql://") and "sslmode=" not in db_url:
    db_url += ("&" if "?" in db_url else "?") + "sslmode=require"
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

BASE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#111"><title>{{ title or 'Ancient Event' }}</title><style>
:root{--bg:#0b0c0e;--panel:#15171a;--line:#2a2d31;--gold:#d9b46b;--text:#f5f1e8;--muted:#a3a6ad}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#242019 0,#0b0c0e 45%);color:var(--text);font-family:Arial,sans-serif;min-height:100vh}.top{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:18px max(18px,calc((100vw - 1080px)/2));border-bottom:1px solid #28251f;background:#0b0c0eee;position:sticky;top:0;z-index:4}.brand{color:var(--text);font-weight:bold;letter-spacing:2px;text-decoration:none;font-size:14px}nav{display:flex;gap:12px;flex-wrap:wrap}nav a,.sectionhead a{color:var(--gold);font-size:12px;text-decoration:none}.wrap{max-width:1080px;margin:auto;padding:26px 16px 55px}.hero{display:flex;justify-content:space-between;align-items:center;gap:20px;margin:12px 0 28px}.eyebrow{color:var(--gold);font-size:10px;letter-spacing:2px;font-weight:bold}h1{font-size:clamp(32px,6vw,46px);margin:8px 0}h2{font-size:18px}.muted{color:var(--muted);line-height:1.6}.panel{background:linear-gradient(145deg,#191b1e,#121315);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 15px 35px #0002}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:30px}.stat{background:#17191c;border:1px solid var(--line);border-radius:14px;padding:18px}.stat span{display:block;color:var(--muted);font-size:12px}.stat strong{display:block;font-size:30px;margin-top:9px;color:var(--gold)}table{border-collapse:collapse;width:100%;font-size:13px;min-width:400px}th,td{text-align:left;padding:13px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:11px;text-transform:uppercase}.tablewrap{overflow:auto;padding:0;margin:15px 0}.code{font-family:monospace;color:var(--gold)}.pill{font-size:11px;border-radius:99px;padding:5px 9px}.unused{background:#26392e;color:#9ee0b5}.used{background:#3c3020;color:#f0ca83}.primary,.secondary,.buttonlink{border:0;border-radius:9px;padding:12px 15px;font-weight:bold;font-size:13px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center}.primary{background:var(--gold);color:#17130c}.secondary{background:#24272b;border:1px solid #3b3e42;color:var(--text)}.full{width:100%;margin-top:14px}.buttonlink{white-space:nowrap}label{display:block;color:#d8d3c8;font-size:12px;margin:15px 0 7px}input,select{width:100%;background:#0e0f11;border:1px solid #37393d;color:var(--text);border-radius:9px;padding:13px;font:inherit;font-size:14px}.login{max-width:420px;margin:5vh auto}.tiny{font-size:11px;color:var(--muted);line-height:1.6}.flash{padding:12px;border-radius:10px;margin-bottom:15px;font-size:13px}.success{background:#183121;color:#a8f0bf}.error{background:#321b1c;color:#ffb2b4}.result{max-width:520px;margin:20px auto;text-align:center;border:1px solid;border-radius:16px;padding:22px}.accepted{background:#10291c;border-color:#267448;color:#a8f0bf}.rejected{background:#301719;border-color:#9c3e42;color:#ffb2b4}@media(max-width:620px){.top{align-items:flex-start;flex-direction:column;padding:14px}nav{gap:10px}.hero{align-items:flex-start;flex-direction:column}.hero .buttonlink{width:100%}.panel{padding:16px}}
</style></head><body><header class="top"><a class="brand" href="{{ url_for('dashboard') }}">ANCIENT <span style="color:var(--gold)">EVENT</span></a>{% if session.get('staff_id') %}<nav><a href="{{ url_for('dashboard') }}">Home</a><a href="{{ url_for('verify') }}">Verify</a><a href="{{ url_for('tickets') }}">Tickets</a><a href="{{ url_for('guest_list') }}">Guests</a>{% if session.get('role')=='admin' %}<a href="{{ url_for('staff') }}">Staff</a>{% endif %}<a href="{{ url_for('logout') }}">Logout</a></nav>{% endif %}</header><main class="wrap">{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="flash {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}{{ body|safe }}</main><footer style="text-align:center;color:#777;font-size:10px;letter-spacing:2px;padding:20px;border-top:1px solid #222">ANCIENT EVENT · TICKET CONTROL</footer></body></html>"""
def page(body, title="Ancient Event"):
    return render_template_string(BASE, body=body, title=title)

class Staff(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(80),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)
    role=db.Column(db.String(20),nullable=False,default="staff")
class Ticket(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    ticket_code=db.Column(db.String(40),unique=True,nullable=False,index=True)
    guest_name=db.Column(db.String(160),nullable=False,default="Guest")
    created_at=db.Column(db.DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
    used_at=db.Column(db.DateTime(timezone=True))
    used_by=db.Column(db.String(80))
def login_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not session.get("staff_id"): return redirect(url_for("login"))
        return fn(*a,**kw)
    return w
def admin_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if session.get("role")!="admin":
            flash("Admin access required.","error"); return redirect(url_for("dashboard"))
        return fn(*a,**kw)
    return w
def make_code():
    alphabet=string.ascii_uppercase+string.digits
    while True:
        code="AVE-"+"".join(secrets.choice(alphabet) for _ in range(10))
        if not Ticket.query.filter_by(ticket_code=code).first(): return code

@app.route("/")
def home(): return redirect(url_for("dashboard") if session.get("staff_id") else url_for("login"))
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form.get("username","").strip(); p=request.form.get("password","")
        s=Staff.query.filter_by(username=u).first()
        if s and check_password_hash(s.password_hash,p):
            session.clear();session.update(staff_id=s.id,username=s.username,role=s.role);return redirect(url_for("dashboard"))
        flash("Incorrect username or password.","error")
    body="""<section class="login panel"><div class="eyebrow">EVENT ACCESS CONTROL</div><h1>Welcome back.</h1><p class="muted">Sign in to manage guests and verify tickets.</p><form method="post"><label>Username</label><input name="username" autocomplete="username" required><label>Password</label><input name="password" type="password" autocomplete="current-password" required><button class="primary full">Sign in</button></form><p class="tiny">Authorized event staff only.</p></section>"""
    return page(body,"Sign in · Ancient Event")
@app.route("/logout")
def logout(): session.clear();return redirect(url_for("login"))
@app.route("/dashboard")
@login_required
def dashboard():
    total=Ticket.query.count();used=Ticket.query.filter(Ticket.used_at.isnot(None)).count()
    recent=Ticket.query.order_by(Ticket.id.desc()).limit(8).all()
    rows="".join(f"<tr><td class='code'>{t.ticket_code}</td><td>{t.guest_name}</td><td><span class='pill {'used' if t.used_at else 'unused'}'>{'Used' if t.used_at else 'Unused'}</span></td></tr>" for t in recent) or "<tr><td colspan='3'>No tickets yet.</td></tr>"
    admin=f"""<div style="display:flex;gap:10px;flex-wrap:wrap"><a class="secondary buttonlink" href="{url_for('tickets')}">＋ Generate tickets</a><a class="secondary buttonlink" href="{url_for('export_csv')}">↓ Export CSV</a></div>""" if session.get("role")=="admin" else ""
    body=f"""<div class="hero"><div><div class="eyebrow">CONTROL CENTER</div><h1>Ancient Event</h1><p class="muted">Welcome, {session['username']}. Verify every entry.</p></div><a class="primary buttonlink" href="{url_for('verify')}">Verify a ticket ↗</a></div><div class="stats"><div class="stat"><span>Total tickets</span><strong>{total}</strong></div><div class="stat"><span>Unused</span><strong>{total-used}</strong></div><div class="stat"><span>Used / entered</span><strong>{used}</strong></div></div><h2>Recent tickets</h2><div class="panel tablewrap"><table><tr><th>Ticket ID</th><th>Guest</th><th>Status</th></tr>{rows}</table></div>{admin}"""
    return page(body,"Dashboard · Ancient Event")
@app.route("/tickets",methods=["GET","POST"])
@login_required
def tickets():
    if request.method=="POST":
        if session.get("role")!="admin": flash("Only admins can generate tickets.","error");return redirect(url_for("tickets"))
        name=request.form.get("guest_name","").strip() or "Guest"
        try: count=max(1,min(100,int(request.form.get("count","1"))))
        except ValueError: count=1
        for _ in range(count): db.session.add(Ticket(ticket_code=make_code(),guest_name=name))
        db.session.commit();flash(f"Generated {count} ticket(s).","success");return redirect(url_for("tickets"))
    q=request.args.get("q","").strip()
    query=Ticket.query
    if q: query=query.filter(db.or_(Ticket.ticket_code.ilike(f"%{q}%"),Ticket.guest_name.ilike(f"%{q}%")))
    ts=query.order_by(Ticket.id.desc()).limit(300).all()
    rows="".join(f"<tr><td class='code'>{t.ticket_code}</td><td>{t.guest_name}</td><td><span class='pill {'used' if t.used_at else 'unused'}'>{'Used' if t.used_at else 'Unused'}</span><br><a href='{url_for('ticket_qr',code=t.ticket_code)}' target='_blank'>Open QR</a></td></tr>" for t in ts) or "<tr><td colspan='3'>No matching tickets.</td></tr>"
    form="""<form method="post" class="panel"><h2>Generate tickets</h2><label>Guest name</label><input name="guest_name" placeholder="Guest or group name"><label>Number (1–100)</label><input type="number" name="count" min="1" max="100" value="1"><button class="primary">Generate tickets</button></form>""" if session.get("role")=="admin" else ""
    body=f"""<div class="hero"><div><div class="eyebrow">TICKET REGISTER</div><h1>Tickets</h1><p class="muted">Generate unique IDs and QR codes.</p></div></div>{form}<form class="hero" method="get"><input name="q" value="{q}" placeholder="Search ID or guest name"><button class="secondary">Search</button></form><div class="panel tablewrap"><table><tr><th>Ticket ID</th><th>Guest</th><th>Status / QR</th></tr>{rows}</table></div>"""
    return page(body,"Tickets · Ancient Event")
@app.route("/ticket/<code>/qr.png")
@login_required
def ticket_qr(code):
    t=Ticket.query.filter_by(ticket_code=code).first_or_404()
    img=qrcode.make(t.ticket_code);b=io.BytesIO();img.save(b,format="PNG");b.seek(0)
    return send_file(b,mimetype="image/png",download_name=code+".png")
@app.route("/verify",methods=["GET","POST"])
@login_required
def verify():
    result=""
    if request.method=="POST":
        code=request.form.get("ticket_code","").strip().upper()
        updated=Ticket.query.filter_by(ticket_code=code,used_at=None).update({Ticket.used_at:datetime.now(timezone.utc),Ticket.used_by:session.get("username")},synchronize_session=False)
        db.session.commit()
        if updated: status="accepted";message="VALID TICKET — ENTRY ACCEPTED"
        elif Ticket.query.filter_by(ticket_code=code).first(): status="rejected";message="ALREADY USED — ENTRY REJECTED"
        else: status="rejected";message="INVALID TICKET — ENTRY REJECTED"
        result=f"""<section class="result {status}"><h2>{message}</h2><p class="code">{code}</p></section>"""
    body=f"""<div class="hero"><div><div class="eyebrow">ENTRANCE CHECK-IN</div><h1>Verify ticket</h1><p class="muted">Scan a QR code or enter the ID. Successful check-in happens once.</p></div></div><section class="panel" style="max-width:520px;margin:auto"><div id="reader"></div><p id="note" class="tiny">Allow camera permission to scan QR codes.</p><button id="start" class="secondary full" type="button">Start camera scanner</button><form id="vf" method="post"><label>Ticket ID</label><input id="ticket_code" name="ticket_code" placeholder="AVE-XXXXXXXXXX" autocapitalize="characters" required><button class="primary full">Verify and check in</button></form></section>{result}<script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script><script>let scanner,busy=false;document.getElementById('start').onclick=async()=>{{let note=document.getElementById('note');if(!window.Html5Qrcode){{note.textContent='Scanner unavailable; type the ID instead.';return}}try{{scanner=new Html5Qrcode('reader');await scanner.start({{facingMode:'environment'}},{{fps:10,qrbox:230}},async text=>{{if(busy)return;busy=true;document.getElementById('ticket_code').value=text.trim();try{{await scanner.stop()}}catch(e){{}}document.getElementById('vf').requestSubmit()}});note.textContent='Point the camera at the QR code.'}}catch(e){{note.textContent='Allow camera permission and use HTTPS, or type the ticket ID.'}}}}</script>"""
    return page(body,"Verify · Ancient Event")
@app.route("/api/verify",methods=["POST"])
@login_required
def api_verify():
    data=request.get_json(silent=True) or {};code=str(data.get("ticket_code","")).strip().upper()
    updated=Ticket.query.filter_by(ticket_code=code,used_at=None).update({Ticket.used_at:datetime.now(timezone.utc),Ticket.used_by:session.get("username")},synchronize_session=False)
    db.session.commit()
    if updated:return jsonify(status="accepted",message="VALID TICKET — ENTRY ACCEPTED",ticket_code=code)
    if Ticket.query.filter_by(ticket_code=code).first():return jsonify(status="used",message="ALREADY USED — ENTRY REJECTED",ticket_code=code),409
    return jsonify(status="invalid",message="INVALID TICKET — ENTRY REJECTED",ticket_code=code),404
@app.route("/guest-list")
@login_required
def guest_list():
    ts=Ticket.query.order_by(Ticket.guest_name.asc()).all()
    rows="".join(f"<tr><td>{t.guest_name}</td><td class='code'>{t.ticket_code}</td><td>{'Checked in' if t.used_at else 'Not entered'}</td></tr>" for t in ts) or "<tr><td colspan='3'>No guests yet.</td></tr>"
    return page(f"<h1>Guest list</h1><div class='panel tablewrap'><table><tr><th>Guest</th><th>Ticket ID</th><th>Status</th></tr>{rows}</table></div>","Guest list")
@app.route("/staff",methods=["GET","POST"])
@login_required
@admin_required
def staff():
    if request.method=="POST":
        u=request.form.get("username","").strip();p=request.form.get("password","");role=request.form.get("role","staff")
        if not u or len(p)<10:flash("Use a username and password of at least 10 characters.","error")
        elif role not in ("staff","admin"):flash("Invalid role.","error")
        elif Staff.query.filter_by(username=u).first():flash("Username already exists.","error")
        else:db.session.add(Staff(username=u,password_hash=generate_password_hash(p),role=role));db.session.commit();flash("Staff account created.","success");return redirect(url_for("staff"))
    ss=Staff.query.order_by(Staff.username.asc()).all()
    rows="".join(f"<tr><td>{s.username}</td><td>{s.role}</td></tr>" for s in ss)
    body=f"""<h1>Staff accounts</h1><form method="post" class="panel"><h2>Create staff login</h2><label>Username</label><input name="username" required><label>Password (10+ characters)</label><input type="password" name="password" minlength="10" required><label>Role</label><select name="role"><option value="staff">Staff</option><option value="admin">Admin</option></select><button class="primary">Create account</button></form><div class="panel tablewrap"><table><tr><th>Username</th><th>Role</th></tr>{rows}</table></div>"""
    return page(body,"Staff · Ancient Event")
@app.route("/export.csv")
@login_required
@admin_required
def export_csv():
    out=io.StringIO();w=csv.writer(out);w.writerow(["Ticket ID","Guest Name","Status","Used At UTC","Used By"])
    for t in Ticket.query.order_by(Ticket.id.asc()).all():w.writerow([t.ticket_code,t.guest_name,"Used" if t.used_at else "Unused",t.used_at or "",t.used_by or ""])
    b=io.BytesIO(out.getvalue().encode("utf-8-sig"));b.seek(0);return send_file(b,mimetype="text/csv",as_attachment=True,download_name="ancient-event-tickets.csv")
with app.app_context():
    db.create_all()
    if Staff.query.count()==0:
        db.session.add(Staff(username=os.environ.get("ADMIN_USERNAME","admin"),password_hash=generate_password_hash(os.environ.get("ADMIN_PASSWORD","ChangeMe12345!")),role="admin"));db.session.commit()
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")))
