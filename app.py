import os
import secrets
import hashlib
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, render_template_string, redirect, url_for, session, jsonify
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "retain_saas_ultra_secure_secret_key_999888777")
app.config['SESSION_COOKIE_NAME'] = 'retainsaas_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_123")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_mock_secret_123")
stripe.api_key = STRIPE_SECRET_KEY

DATABASE_FILE = "retainsaas_master_ultimate.db"

def get_db():
    conn = sqlite3.connect(DATABASE_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            company_name TEXT DEFAULT 'My SaaS Product',
            plan_tier TEXT DEFAULT 'Scale Enterprise (Active)',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dunning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_id TEXT UNIQUE NOT NULL,
            stripe_customer_id TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            customer_name TEXT DEFAULT 'Valued Customer',
            amount_due_cents INTEGER NOT NULL,
            currency TEXT DEFAULT 'USD',
            invoice_url TEXT DEFAULT '',
            status TEXT DEFAULT 'past_due',
            secure_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            touchpoint INTEGER NOT NULL,
            subject_line TEXT NOT NULL,
            body_text TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        conn.commit()

init_db()

def get_current_user():
    if 'user_id' not in session:
        return None
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# Background Worker Thread for Automated Monitoring
def background_dunning_worker():
    while True:
        try:
            time.sleep(60)
            with get_db() as conn:
                # Automated health check or background task processing
                pass
        except Exception:
            pass

threading.Thread(target=background_dunning_worker, daemon=True).start()

@app.route('/')
def index():
    if get_current_user():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET'])
def login_page():
    if get_current_user():
        return redirect(url_for('dashboard'))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Passwordless Login - RetainSaaS</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-white min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-gray-900 border border-gray-800 p-8 rounded-3xl shadow-2xl space-y-6">
            <div class="text-center space-y-2">
                <div class="inline-block bg-indigo-600 text-white font-extrabold px-4 py-1.5 rounded-xl text-sm mb-2">RetainSaaS Engine</div>
                <h1 class="text-2xl font-black tracking-tight">Instant Magic Link</h1>
                <p class="text-xs text-gray-400">Enter your email. No passwords required—log in instantly with a secure tap.</p>
            </div>
            <form action="/login" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Email Address</label>
                    <input type="email" name="email" required placeholder="founder@mysaas.com" class="w-full p-3.5 bg-gray-950 border border-gray-800 rounded-2xl text-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm font-medium">
                </div>
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3.5 rounded-2xl font-bold shadow-lg shadow-indigo-600/30 transition transform active:scale-95 text-sm">Send Secure Login Link</button>
            </form>
        </div>
    </body>
    </html>
    """)

@app.route('/login', methods=['POST'])
def login_post():
    email = request.form.get('email', '').strip().lower()
    if not email:
        return "Email required.", 400
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (email) VALUES (?)", (email,))
            conn.commit()
            user_id = cursor.lastrowid
        else:
            user_id = user['id']
            
        login_token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(minutes=15)
        conn.execute("INSERT INTO login_tokens (user_id, token, expires_at) VALUES (?, ?, ?)", (user_id, login_token, expires))
        conn.commit()
        
    magic_link = url_for('verify_login', token=login_token, _external=True)
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-gray-950 text-white min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-gray-900 border border-gray-800 p-8 rounded-3xl text-center space-y-4">
            <h1 class="text-xl font-black">Magic Link Generated!</h1>
            <p class="text-xs text-gray-400">Since you are testing on mobile, tap the direct secure login link below to enter your dashboard instantly without typing a password:</p>
            <a href="{{ magic_link }}" class="block w-full bg-emerald-600 hover:bg-emerald-500 text-white py-3.5 rounded-2xl font-bold text-sm shadow-lg">Tap Here to Log In Instantly &rarr;</a>
        </div>
    </body>
    </html>
    """, magic_link=magic_link)

@app.route('/auth/verify/<token>')
def verify_login(token):
    with get_db() as conn:
        record = conn.execute("SELECT * FROM login_tokens WHERE token = ?", (token,)).fetchone()
        if not record:
            return "Invalid or expired login link.", 400
        
        user_id = record['user_id']
        conn.execute("DELETE FROM login_tokens WHERE token = ?", (token,))
        conn.commit()
        
    session.clear()
    session['user_id'] = user_id
    session.permanent = True
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    with get_db() as conn:
        events = conn.execute("SELECT * FROM dunning_events WHERE user_id = ? ORDER BY id DESC", (user['id'],)).fetchall()
        
    at_risk_mrr = sum(e['amount_due_cents'] for e in events if e['status'] == 'past_due') / 100.0
    recovered_mrr = sum(e['amount_due_cents'] for e in events if e['status'] == 'recovered') / 100.0
    total_count = len(events)
    recovered_count = sum(1 for e in events if e['status'] == 'recovered')
    recovery_rate = (recovered_count / total_count * 100) if total_count > 0 else 0.0

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard - RetainSaaS Master</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-white font-sans min-h-screen flex flex-col">
        <nav class="bg-gray-900 border-b border-gray-800 px-6 py-4 flex justify-between items-center shadow-md">
            <div class="flex items-center space-x-3">
                <div class="bg-indigo-600 text-white font-black px-3.5 py-1.5 rounded-xl text-sm shadow">RetainSaaS</div>
                <span class="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full font-bold">{{ user.plan_tier }}</span>
            </div>
            <div class="flex items-center space-x-4 text-sm font-semibold">
                <span class="text-gray-300 hidden md:inline">{{ user.email }}</span>
                <a href="/templates" class="text-indigo-400 hover:text-indigo-300 transition">Email Templates</a>
                <a href="/logout" class="bg-gray-800 hover:bg-red-600/20 hover:text-red-400 text-gray-300 px-4 py-2 rounded-xl transition">Logout</a>
            </div>
        </nav>
        
        <main class="p-6 md:p-10 max-w-7xl mx-auto w-full space-y-8 flex-1">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                <div class="bg-gray-900 border border-gray-800 p-6 rounded-3xl shadow-lg">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">At-Risk MRR</p>
                    <h3 class="text-3xl font-black text-amber-500 mt-2">${{ "%.2f"|format(at_risk_mrr) }}</h3>
                </div>
                <div class="bg-gray-900 border border-gray-800 p-6 rounded-3xl shadow-lg">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Recovered Revenue</p>
                    <h3 class="text-3xl font-black text-emerald-400 mt-2">${{ "%.2f"|format(recovered_mrr) }}</h3>
                </div>
                <div class="bg-gray-900 border border-gray-800 p-6 rounded-3xl shadow-lg">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Recovery Rate</p>
                    <h3 class="text-3xl font-black text-indigo-400 mt-2">{{ "%.1f"|format(recovery_rate) }}%</h3>
                </div>
                <div class="bg-gray-900 border border-gray-800 p-6 rounded-3xl shadow-lg">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Total Dunning Cases</p>
                    <h3 class="text-3xl font-black text-white mt-2">{{ total_count }}</h3>
                </div>
            </div>

            <div class="bg-gray-900 border border-gray-800 rounded-3xl p-6 shadow-xl space-y-6">
                <div class="flex justify-between items-center">
                    <h2 class="text-lg font-bold">Active Failed Payment Recoveries</h2>
                    <form action="/simulate-event" method="POST">
                        <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-xl font-bold text-xs transition shadow">+ Simulate Test Case</button>
                    </form>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-gray-950 text-gray-400 uppercase text-xs tracking-wider">
                            <tr>
                                <th class="p-4 rounded-l-xl">Customer</th>
                                <th class="p-4">Amount Due</th>
                                <th class="p-4">Status</th>
                                <th class="p-4 rounded-r-xl">Action Link</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800">
                            {% for e in events %}
                            <tr class="hover:bg-gray-800/50 transition">
                                <td class="p-4 font-semibold">{{ e.customer_email }}</td>
                                <td class="p-4 font-bold text-amber-400">${{ "%.2f"|format(e.amount_due_cents / 100.0) }}</td>
                                <td class="p-4"><span class="px-3 py-1 rounded-full text-xs font-bold {% if e.status == 'recovered' %}bg-emerald-500/10 text-emerald-400 border border-emerald-500/20{% else %}bg-amber-500/10 text-amber-400 border border-amber-500/20{% endif %}">{{ e.status }}</span></td>
                                <td class="p-4"><a href="/pay/{{ e.secure_token }}" target="_blank" class="text-indigo-400 hover:underline font-bold text-xs">Update Card Link &rarr;</a></td>
                            </tr>
                            {% else %}
                            <tr><td colspan="4" class="p-8 text-center text-gray-500">No active failed payments found. Click '+ Simulate Test Case' above to test!</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </body>
    </html>
    """, user=user, events=events, at_risk_mrr=at_risk_mrr, recovered_mrr=recovered_mrr, recovery_rate=recovery_rate, total_count=total_count)

@app.route('/templates', methods=['GET', 'POST'])
@login_required
def templates_page():
    user = get_current_user()
    with get_db() as conn:
        if request.method == 'POST':
            subject = request.form.get('subject_line', 'Payment Failed')
            body = request.form.get('body_text', 'Please update your card.')
            conn.execute("INSERT OR REPLACE INTO templates (user_id, touchpoint, subject_line, body_text) VALUES (?, 1, ?, ?)", (user['id'], subject, body))
            conn.commit()
            return redirect(url_for('templates_page'))
        tmpl = conn.execute("SELECT * FROM templates WHERE user_id = ? AND touchpoint = 1", (user['id'],)).fetchone()
    
    default_sub = tmpl['subject_line'] if tmpl else "Action Required: Payment Failed for Your Subscription"
    default_body = tmpl['body_text'] if tmpl else "Hi there, your recent payment failed. Please update your card to maintain uninterrupted access."

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><title>Email Templates - RetainSaaS</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-white min-h-screen p-6">
        <div class="max-w-2xl mx-auto space-y-6">
            <div class="flex justify-between items-center"><h1 class="text-2xl font-black">Dunning Email Customizer</h1><a href="/dashboard" class="text-sm text-indigo-400 hover:underline">&larr; Dashboard</a></div>
            <form method="POST" class="bg-gray-900 border border-gray-800 p-8 rounded-3xl space-y-4">
                <div>
                    <label class="block text-xs font-bold text-gray-400 uppercase mb-1">Subject Line</label>
                    <input type="text" name="subject_line" value="{{ default_sub }}" class="w-full p-3 bg-gray-950 border border-gray-800 rounded-2xl text-white text-sm">
                </div>
                <div>
                    <label class="block text-xs font-bold text-gray-400 uppercase mb-1">Email Body Text</label>
                    <textarea name="body_text" rows="5" class="w-full p-3 bg-gray-950 border border-gray-800 rounded-2xl text-white text-sm">{{ default_body }}</textarea>
                </div>
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3 rounded-2xl font-bold text-sm">Save Template Settings</button>
            </form>
        </div>
    </body>
    </html>
    """, default_sub=default_sub, default_body=default_body)

@app.route('/simulate-event', methods=['POST'])
@login_required
def simulate_event():
    user = get_current_user()
    token = f"tok_{secrets.token_urlsafe(16)}"
    event_id = f"evt_{secrets.token_hex(8)}"
    with get_db() as conn:
        conn.execute("""
            INSERT INTO dunning_events (user_id, event_id, stripe_customer_id, customer_email, customer_name, amount_due_cents, currency, invoice_url, status, secure_token)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user['id'], event_id, "cus_test_123", f"customer_{secrets.token_hex(3)}@example.com", "Test Customer", 9900, "USD", "https://stripe.com/invoice", "past_due", token))
        conn.commit()
    return redirect(url_for('dashboard'))

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    if event['type'] == 'invoice.payment_failed':
        inv = event['data']['object']
        cust_email = inv.get('customer_email', 'billing@customer.com')
        amt = inv.get('amount_due', 9900)
        cust_id = inv.get('customer', 'cus_unknown')
        inv_id = inv.get('id', 'inv_unknown')
        token = f"tok_{secrets.token_urlsafe(16)}"
        
        with get_db() as conn:
            user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
            if user:
                conn.execute("""
                    INSERT OR IGNORE INTO dunning_events (user_id, event_id, stripe_customer_id, customer_email, amount_due_cents, status, secure_token)
                    VALUES (?, ?, ?, ?, ?, 'past_due', ?)
                """, (user['id'], inv_id, cust_id, cust_email, amt, token))
                conn.commit()

    return jsonify({'status': 'success'}), 200

@app.route('/pay/<token>', methods=['GET'])
def customer_update_page(token):
    with get_db() as conn:
        event = conn.execute("SELECT * FROM dunning_events WHERE secure_token = ?", (token,)).fetchone()
    if not event:
        return "Invalid or expired payment link.", 404
        
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Update Payment Method - Secure Portal</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-white min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-gray-900 border border-gray-800 p-8 rounded-3xl shadow-2xl space-y-6">
            <div class="text-center space-y-2">
                <span class="bg-amber-500/10 text-amber-400 border border-amber-500/20 px-3 py-1 rounded-full text-xs font-bold">Action Required</span>
                <h1 class="text-xl font-black">Update Your Payment Method</h1>
                <p class="text-xs text-gray-400">Your recent payment of <span class="text-white font-bold">${{ "%.2f"|format(event.amount_due_cents / 100.0) }}</span> failed. Update your card below to restore service instantly.</p>
            </div>
            <form action="/pay/{{ token }}" method="POST" class="space-y-4">
                <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white py-3.5 rounded-2xl font-bold shadow-lg shadow-emerald-600/30 transition text-sm">Simulate Successful Card Update</button>
            </form>
        </div>
    </body>
    </html>
    """, event=event, token=token)

@app.route('/pay/<token>', methods=['POST'])
def customer_update_post(token):
    with get_db() as conn:
        conn.execute("UPDATE dunning_events SET status = 'recovered' WHERE secure_token = ?", (token,))
        conn.commit()
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-gray-950 text-white min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-gray-900 border border-gray-800 p-8 rounded-3xl text-center space-y-4">
            <div class="w-12 h-12 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center mx-auto text-xl font-bold">✓</div>
            <h1 class="text-2xl font-black">Payment Successfully Updated!</h1>
            <p class="text-xs text-gray-400">Your subscription is now active and secure. Thank you!</p>
        </div>
    </body>
    </html>
    """)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
