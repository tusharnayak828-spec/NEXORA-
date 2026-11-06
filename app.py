import os, re, secrets, sqlite3
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory, make_response
from werkzeug.security import check_password_hash
from demo_backend import register_demo_routes

app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")
if not secret_key and os.environ.get("RENDER"):
    raise RuntimeError("SECRET_KEY must be configured in the production environment.")
app.secret_key = secret_key or secrets.token_urlsafe(48)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
    MAX_CONTENT_LENGTH=11 * 1024 * 1024,
)
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "nexora.db"))
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "NSVERTEXTECHNOLOGIES@GMAIL.COM")
CONTACT_PHONE = os.environ.get("CONTACT_PHONE", "7600308992")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def db():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL,
            service TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New',
            created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS admin_login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT NOT NULL, attempted_at TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0)""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_admin_login_attempts_ip_time ON admin_login_attempts(ip, attempted_at)")


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def valid_csrf():
    return secrets.compare_digest(session.get("csrf_token", ""), request.form.get("csrf_token", ""))


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' mailto:")
    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.get("/")
def home():
    return render_template("index.html", csrf_token=csrf_token(), contact_email=CONTACT_EMAIL, contact_phone=CONTACT_PHONE, submitted=request.args.get("sent") == "1")


@app.post("/enquiry")
def submit_enquiry():
    if not valid_csrf():
        abort(400, "Invalid form token. Please refresh and try again.")
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    service = request.form.get("service", "").strip()
    message = request.form.get("message", "").strip()
    allowed_services = {
        "Custom software development", "Web application development", "AI integration",
        "Business process automation", "Maintenance and support", "Not sure yet",
    }
    if not name or len(name) > 100 or not EMAIL_RE.fullmatch(email) or len(email) > 254:
        abort(400, "Please enter your name and a valid email address.")
    if service not in allowed_services or not message or len(message) > 5000:
        abort(400, "Please choose a service and provide a project message.")
    with db() as con:
        con.execute(
            "INSERT INTO leads(name,email,service,message,created_at) VALUES(?,?,?,?,?)",
            (name, email, service, message, datetime.now(timezone.utc).isoformat()),
        )
    return redirect(url_for("home", sent="1") + "#contact")


@app.get("/demos/<demo>/")
def serve_demo(demo):
    if demo not in {"factoryos", "clientflow", "documind"}:
        abort(404)
    return send_from_directory(os.path.join(app.root_path, "demos", demo), "index.html")


@app.get("/admin/login")
def admin_login():
    return render_template("login.html", csrf_token=csrf_token())


@app.post("/admin/login")
def admin_login_post():
    if not valid_csrf():
        abort(400)
    ip = request.remote_addr or "unknown"
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=15)).isoformat()
    with db() as con:
        con.execute("DELETE FROM admin_login_attempts WHERE attempted_at < ?", ((now - timedelta(days=2)).isoformat(),))
        attempts = con.execute(
            "SELECT COUNT(*) FROM admin_login_attempts WHERE ip=? AND attempted_at>=? AND success=0",
            (ip, cutoff.isoformat()),
        ).fetchone()[0]
        if attempts >= 5:
            abort(429, "Too many sign-in attempts. Please wait 15 minutes and try again.")
    username = os.environ.get("ADMIN_USERNAME")
    password_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    password = request.form.get("password", "")
    success = bool(username and password_hash and request.form.get("username", "") == username and check_password_hash(password_hash, password))
    with db() as con:
        con.execute(
            "INSERT INTO admin_login_attempts(ip,attempted_at,success) VALUES(?,?,?)",
            (ip, now.isoformat(), 1 if success else 0),
        )
    if success:
        session.clear()
        session["admin_logged_in"] = True
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("admin_dashboard"))
    flash("Login failed. Check your credentials and deployment settings.")
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    with db() as con:
        leads = con.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    return render_template("admin.html", leads=leads, csrf_token=csrf_token())


@app.post("/admin/lead/<int:lead_id>/status")
@admin_required
def update_status(lead_id):
    if not valid_csrf():
        abort(400)
    status = request.form.get("status", "New")
    if status not in {"New", "Contacted", "In progress", "Won", "Closed"}:
        abort(400)
    with db() as con:
        con.execute("UPDATE leads SET status=? WHERE id=?", (status, lead_id))
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/logout")
@admin_required
def admin_logout():
    if not valid_csrf():
        abort(400)
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/privacy")
def privacy():
    return render_template("legal.html", page="Privacy", title="Privacy Policy")


@app.get("/terms")
def terms():
    return render_template("legal.html", page="Terms", title="Terms of Use")


init_db()
register_demo_routes(app, DB_PATH)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
