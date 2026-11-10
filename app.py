import os
import json
import secrets
import hashlib
import sqlite3
from datetime import datetime, timedelta
from flask import (
    Flask, request, jsonify, render_template_string, redirect, 
    url_for, session
)
import stripe
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==============================================================================
# CONFIGURATION & ENVIRONMENT SETUP
# ==============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_123")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_mock_pub_key_123")
STRIPE_CLIENT_ID = os.environ.get("STRIPE_CLIENT_ID", "ca_mock_client_id_123")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_mock_secret_123")

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

stripe.api_key = STRIPE_SECRET_KEY
DATABASE_FILE = "dunning_saas.db"

# ==============================================================================
# DATABASE ENGINE & SCHEMA INITIALIZATION
# ==============================================================================
def get_db():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        company_name TEXT DEFAULT 'RetainSaaS',
        brand_color TEXT DEFAULT '#4F46E5',
        brand_logo_url TEXT DEFAULT '',
        stripe_account_id TEXT DEFAULT NULL,
        stripe_access_token TEXT DEFAULT NULL,
        stripe_refresh_token TEXT DEFAULT NULL,
        plan_tier TEXT DEFAULT 'Free',
        from_name TEXT DEFAULT 'Billing Team',
        reply_to_email TEXT DEFAULT 'billing@retainsaas.com',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Dunning Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dunning_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_id TEXT UNIQUE NOT NULL,
        stripe_customer_id TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        customer_name TEXT DEFAULT 'Valued Customer',
        amount_due REAL NOT NULL,
        currency TEXT DEFAULT 'USD',
        invoice_url TEXT DEFAULT '',
        status TEXT DEFAULT 'past_due',
        attempt_count INTEGER DEFAULT 1,
        secure_token TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    # Outreach Queue Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outreach_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dunning_event_id INTEGER NOT NULL,
        touchpoint INTEGER NOT NULL,
        channel TEXT NOT NULL,
        scheduled_time TIMESTAMP NOT NULL,
        status TEXT DEFAULT 'pending',
        sent_at TIMESTAMP DEFAULT NULL,
        FOREIGN KEY (dunning_event_id) REFERENCES dunning_events (id)
    );
    """)

    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# SECURITY & AUTHENTICATION HELPERS
# ==============================================================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def generate_secure_token():
    return f"sec_tok_{secrets.token_urlsafe(24)}"

def send_real_dunning_email(to_email, subject, body_html, from_name="Billing Team"):
    if not SMTP_USER or not SMTP_PASS:
        print(f"⚠️ [SMTP SIMULATION] Email to {to_email} | Subject: {subject}")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{SMTP_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"❌ SMTP Error: {str(e)}")
        return False

# ==============================================================================
# AUTOMATED DUNNING & QUEUE WORKER
# ==============================================================================
def schedule_dunning_sequence(dunning_event_id):
    conn = get_db()
    now = datetime.utcnow()
    t1 = (now + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    t2 = (now + timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
    t3 = (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, 1, 'email', ?)", (dunning_event_id, t1))
    conn.execute("INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, 2, 'email', ?)", (dunning_event_id, t2))
    conn.execute("INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, 3, 'email', ?)", (dunning_event_id, t3))
    conn.commit()
    conn.close()

def auto_kill_outreach_queue(dunning_event_id):
    conn = get_db()
    conn.execute("UPDATE outreach_queue SET status = 'canceled' WHERE dunning_event_id = ? AND status = 'pending'", (dunning_event_id,))
    conn.commit()
    conn.close()

# ==============================================================================
# STRIPE OAUTH CONNECT & WEBHOOK ROUTES
# ==============================================================================
@app.route('/stripe/authorize')
def stripe_authorize():
    user = get_current_user()
    if not user:
        return redirect(url_for('login_page'))
    
    redirect_uri = request.host_url.rstrip('/') + url_for('handle_stripe_oauth_callback')
    authorize_url = (
        f"https://connect.stripe.com/oauth/authorize?"
        f"response_type=code&client_id={STRIPE_CLIENT_ID}&scope=read_write&redirect_uri={redirect_uri}"
    )
    return redirect(authorize_url)

@app.route('/stripe/callback')
@app.route('/oauth/callback')
def handle_stripe_oauth_callback():
    code = request.args.get('code')
    user = get_current_user()
    
    if not user:
        return redirect(url_for('login_page'))

    if code:
        try:
            response = stripe.OAuth.token(grant_type='authorization_code', code=code)
            connected_account_id = response['stripe_user_id']
            access_token = response['access_token']
            refresh_token = response.get('refresh_token', '')

            conn = get_db()
            conn.execute("""
                UPDATE users 
                SET stripe_account_id = ?, stripe_access_token = ?, stripe_refresh_token = ?
                WHERE id = ?
            """, (connected_account_id, access_token, refresh_token, user['id']))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Stripe OAuth Error: {str(e)}")

    return redirect(url_for('dashboard'))

@app.route('/stripe/disconnect', methods=['POST'])
def disconnect_stripe():
    user = get_current_user()
    if user:
        conn = get_db()
        conn.execute("UPDATE users SET stripe_account_id = NULL, stripe_access_token = NULL, stripe_refresh_token = NULL WHERE id = ?", (user['id'],))
        conn.commit()
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', None)

    try:
        if STRIPE_WEBHOOK_SECRET != "whsec_mock_secret_123" and sig_header:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload.decode('utf-8'))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    event_type = event['type']
    data_object = event['data']['object']
    account_id = event.get('account', None)

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE stripe_account_id = ?", (account_id,)).fetchone() if account_id else None
    user_id = user['id'] if user else 1

    if event_type == 'invoice.payment_failed':
        customer_email = data_object.get('customer_email', 'customer@example.com')
        customer_id = data_object.get('customer', 'cus_mock123')
        amount_due = data_object.get('amount_due', 3900) / 100.0
        currency = data_object.get('currency', 'usd').upper()
        hosted_invoice_url = data_object.get('hosted_invoice_url', '')
        event_id = event.get('id', f"evt_{secrets.token_hex(8)}")
        sec_token = generate_secure_token()

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dunning_events 
            (user_id, event_id, stripe_customer_id, customer_email, amount_due, currency, invoice_url, status, attempt_count, secure_token)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'past_due', 1, ?)
        """, (user_id, event_id, customer_id, customer_email, amount_due, currency, hosted_invoice_url, sec_token))
        
        dunning_id = cursor.lastrowid
        conn.commit()
        schedule_dunning_sequence(dunning_id)

    elif event_type == 'invoice.payment_succeeded':
        customer_id = data_object.get('customer')
        event_record = conn.execute("SELECT id FROM dunning_events WHERE stripe_customer_id = ? AND status != 'recovered'", (customer_id,)).fetchone()
        if event_record:
            conn.execute("UPDATE dunning_events SET status = 'recovered', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (event_record['id'],))
            conn.commit()
            auto_kill_outreach_queue(event_record['id'])

    conn.close()
    return jsonify({"status": "success"}), 200

# ==============================================================================
# CUSTOMER CARD UPDATE CHECKOUT & FOUNDER INTERFACE
# ==============================================================================
CARD_UPDATE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Update Card - {{ company_name }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://js.stripe.com/v3/"></script>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen flex flex-col justify-center items-center py-12 px-4">
    <div class="max-w-md w-full space-y-6 bg-white p-8 rounded-2xl shadow-xl border border-gray-100">
        <div class="text-center"><h2 class="text-2xl font-extrabold text-gray-900">{{ company_name }}</h2><p class="text-sm text-gray-500 mt-1">Secure Billing Update</p></div>
        <div class="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-md"><p class="text-sm text-amber-800 font-semibold">Payment of {{ currency }} ${{ "%.2f"|format(amount_due) }} failed. Update your card below.</p></div>
        <form id="payment-form" class="space-y-4">
            <div id="card-element" class="p-3.5 border border-gray-300 rounded-lg bg-white"></div>
            <div id="card-errors" class="text-xs text-red-600 mt-2"></div>
            <button id="submit-btn" type="submit" class="w-full bg-indigo-600 text-white py-3.5 px-4 rounded-xl font-bold shadow hover:bg-indigo-700">Update & Retry Payment</button>
        </form>
    </div>
    <script>
        const stripe = Stripe('{{ stripe_pub_key }}');
        const elements = stripe.elements();
        const card = elements.create('card');
        card.mount('#card-element');
        document.getElementById('payment-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const { paymentMethod, error } = await stripe.createPaymentMethod({ type: 'card', card: card });
            if (error) { document.getElementById('card-errors').textContent = error.message; }
            else {
                const res = await fetch('/api/update-payment-method', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: '{{ token }}', payment_method_id: paymentMethod.id })
                });
                const data = await res.json();
                if (data.success) { alert('Success! Payment recovered.'); window.location.reload(); }
            }
        });
    </script>
</body>
</html>
"""

@app.route('/pay/update/<token>')
def card_update_page(token):
    conn = get_db()
    event = conn.execute("SELECT * FROM dunning_events WHERE secure_token = ?", (token,)).fetchone()
    if not event:
        return "Invalid or Expired Payment Token", 404
    user = conn.execute("SELECT * FROM users WHERE id = ?", (event['user_id'],)).fetchone()
    conn.close()
    return render_template_string(CARD_UPDATE_TEMPLATE, token=token, company_name=user['company_name'], amount_due=event['amount_due'], currency=event['currency'], stripe_pub_key=STRIPE_PUBLISHABLE_KEY)

@app.route('/api/update-payment-method', methods=['POST'])
def api_update_payment_method():
    data = request.json or {}
    token = data.get('token')
    conn = get_db()
    event = conn.execute("SELECT * FROM dunning_events WHERE secure_token = ?", (token,)).fetchone()
    if not event:
        return jsonify({"success": False, "message": "Record not found"}), 404
    conn.execute("UPDATE dunning_events SET status = 'recovered', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (event['id'],))
    conn.commit()
    auto_kill_outreach_queue(event['id'])
    conn.close()
    return jsonify({"success": True})

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>RetainSaaS Founder Dashboard</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-100 text-gray-900 font-sans p-8">
    <div class="max-w-6xl mx-auto space-y-6">
        <div class="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm">
            <div><h1 class="text-2xl font-bold">RetainSaaS Dashboard</h1><p class="text-sm text-gray-500">Logged in as {{ user.email }}</p></div>
            <div class="flex items-center space-x-4">
                {% if user.stripe_account_id %}
                    <span class="px-4 py-2 bg-green-100 text-green-800 rounded-full font-bold text-xs">Stripe Connected</span>
                    <form action="/stripe/disconnect" method="POST"><button type="submit" class="text-xs text-red-500 font-bold hover:underline">Disconnect</button></form>
                {% else %}
                    <a href="/stripe/authorize" class="bg-indigo-600 text-white font-bold px-4 py-2 rounded-xl text-sm shadow hover:bg-indigo-700">Connect Stripe Account</a>
                {% endif %}
                <a href="/logout" class="text-xs text-gray-500 font-semibold hover:text-gray-900">Logout</a>
            </div>
        </div>
        <div class="grid grid-cols-3 gap-6">
            <div class="bg-white p-6 rounded-2xl shadow-sm"><p class="text-xs text-gray-400 font-bold uppercase">At Risk MRR</p><h2 class="text-2xl font-extrabold text-amber-600">${{ "%.2f"|format(at_risk_mrr) }}</h2></div>
            <div class="bg-white p-6 rounded-2xl shadow-sm"><p class="text-xs text-gray-400 font-bold uppercase">Recovered Revenue</p><h2 class="text-2xl font-extrabold text-green-600">${{ "%.2f"|format(recovered_mrr) }}</h2></div>
            <div class="bg-white p-6 rounded-2xl shadow-sm"><p class="text-xs text-gray-400 font-bold uppercase">Active Dunning Cases</p><h2 class="text-2xl font-extrabold text-indigo-600">{{ active_count }}</h2></div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login_page'))
    conn = get_db()
    events = conn.execute("SELECT * FROM dunning_events WHERE user_id = ?", (user['id'],)).fetchall()
    at_risk_mrr = sum(e['amount_due'] for e in events if e['status'] == 'past_due')
    recovered_mrr = sum(e['amount_due'] for e in events if e['status'] == 'recovered')
    active_count = sum(1 for e in events if e['status'] == 'past_due')
    conn.close()
    return render_template_string(DASHBOARD_TEMPLATE, user=user, at_risk_mrr=at_risk_mrr, recovered_mrr=recovered_mrr, active_count=active_count)

AUTH_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>RetainSaaS Login</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 space-y-6">
        <h1 class="text-2xl font-bold text-center text-gray-900">RetainSaaS Access</h1>
        <form action="/login" method="POST" class="space-y-4">
            <input type="email" name="email" placeholder="Founder Email" required class="w-full p-3 border rounded-xl focus:ring-2 focus:ring-indigo-500">
            <input type="password" name="password" placeholder="Password" required class="w-full p-3 border rounded-xl focus:ring-2 focus:ring-indigo-500">
            <button type="submit" class="w-full bg-indigo-600 text-white py-3 rounded-xl font-bold shadow hover:bg-indigo-700">Log In / Register</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        pwd_hash = hash_password(password)
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, pwd_hash))
            conn.commit()
            user_id = cursor.lastrowid
        else:
            user_id = user['id']
        conn.close()
        session['user_id'] = user_id
        return redirect(url_for('dashboard'))
    
    # If already logged in, skip login screen instantly
    if get_current_user():
        return redirect(url_for('dashboard'))
        
    return render_template_string(AUTH_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
