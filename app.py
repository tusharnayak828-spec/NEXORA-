import os, secrets, sqlite3
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory
from werkzeug.security import check_password_hash
from demo_backend import register_demo_routes

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-before-deploy-' + secrets.token_hex(16))
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','false').lower()=='true', MAX_CONTENT_LENGTH=11 * 1024 * 1024)
DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'nexora.db'))
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'hello@nexoratechnologies.in')


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL, service TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New', created_at TEXT NOT NULL)''')


def csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


def valid_csrf():
    return secrets.compare_digest(session.get('csrf_token',''), request.form.get('csrf_token',''))


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return fn(*args, **kwargs)
    return wrapper


@app.get('/')
def home():
    return render_template('index.html', csrf_token=csrf_token(), contact_email=CONTACT_EMAIL, submitted=request.args.get('sent')=='1')


@app.post('/enquiry')
def submit_enquiry():
    if not valid_csrf(): abort(400, 'Invalid form token. Please refresh and try again.')
    name = request.form.get('name','').strip()[:100]
    email = request.form.get('email','').strip()[:254]
    service = request.form.get('service','').strip()[:100]
    message = request.form.get('message','').strip()[:5000]
    if not name or not email or '@' not in email or not service or not message:
        abort(400, 'Please complete all fields with a valid email address.')
    with db() as con:
        con.execute('INSERT INTO leads(name,email,service,message,created_at) VALUES(?,?,?,?,?)', (name,email,service,message,datetime.now(timezone.utc).isoformat()))
    return redirect(url_for('home', sent='1') + '#contact')


@app.get('/demos/<demo>/')
def serve_demo(demo):
    # Only serve the three reviewed portfolio demo folders.
    if demo not in {'factoryos', 'clientflow', 'documind'}:
        abort(404)
    return send_from_directory(os.path.join(app.root_path, 'demos', demo), 'index.html')


@app.get('/admin/login')
def admin_login():
    return render_template('login.html', csrf_token=csrf_token())


@app.post('/admin/login')
def admin_login_post():
    if not valid_csrf(): abort(400)
    username = os.environ.get('ADMIN_USERNAME')
    password_hash = os.environ.get('ADMIN_PASSWORD_HASH')
    password = request.form.get('password','')
    if username and password_hash and request.form.get('username','') == username and check_password_hash(password_hash, password):
        session.clear(); session['admin_logged_in'] = True
        return redirect(url_for('admin_dashboard'))
    flash('Login failed. Check your credentials and deployment settings.')
    return redirect(url_for('admin_login'))


@app.get('/admin')
@admin_required
def admin_dashboard():
    with db() as con:
        leads = con.execute('SELECT * FROM leads ORDER BY id DESC').fetchall()
    return render_template('admin.html', leads=leads, csrf_token=csrf_token())


@app.post('/admin/lead/<int:lead_id>/status')
@admin_required
def update_status(lead_id):
    if not valid_csrf(): abort(400)
    status = request.form.get('status','New')
    if status not in {'New','Contacted','In progress','Won','Closed'}: abort(400)
    with db() as con:
        con.execute('UPDATE leads SET status=? WHERE id=?', (status,lead_id))
    return redirect(url_for('admin_dashboard'))


@app.post('/admin/logout')
@admin_required
def admin_logout():
    if not valid_csrf(): abort(400)
    session.clear()
    return redirect(url_for('admin_login'))


@app.get('/privacy')
def privacy():
    return render_template('legal.html', page='Privacy', title='Privacy Policy')


@app.get('/terms')
def terms():
    return render_template('legal.html', page='Terms', title='Terms of Use')


init_db()
register_demo_routes(app, DB_PATH)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
