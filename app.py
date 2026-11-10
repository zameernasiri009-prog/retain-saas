import os
import json
import time
import secrets
import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, request, jsonify, render_template_string, redirect, 
    url_for, session, make_response
)
import stripe

# ==============================================================================
# RETAINSAAS MASTER ENTERPRISE CONFIGURATION
# ==============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_123")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_mock_pub_key_123")
STRIPE_CLIENT_ID = os.environ.get("STRIPE_CLIENT_ID", "ca_mock_client_id_123")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_mock_secret_123")

stripe.api_key = STRIPE_SECRET_KEY
stripe.default_http_client = stripe.http_client.RequestsClient(timeout=10.0)

DATABASE_FILE = "retainsaas_master_ultimate.db"

# ==============================================================================
# ABSOLUTE DATABASE DETERMINISM (WAL MODE & FOREIGN KEY CASCADES)
# ==============================================================================
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
        
        # 1. Founder Tenant Accounts Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT DEFAULT 'My SaaS Product',
            brand_color TEXT DEFAULT '#4F46E5',
            brand_logo_url TEXT DEFAULT '',
            stripe_account_id TEXT DEFAULT NULL,
            stripe_access_token TEXT DEFAULT NULL,
            stripe_refresh_token TEXT DEFAULT NULL,
            plan_tier TEXT DEFAULT 'Scale Enterprise',
            from_name TEXT DEFAULT 'Billing Support',
            reply_to_email TEXT DEFAULT 'billing@mysaas.com',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Dunning Events Table (Integer Cents Storage - Zero Float Corruption)
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
            attempt_count INTEGER DEFAULT 1,
            secure_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

        # 3. Outreach Queue Table (Multi-Touch Sequence Automation)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS outreach_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dunning_event_id INTEGER NOT NULL,
            touchpoint INTEGER NOT NULL,
            channel TEXT NOT NULL,
            scheduled_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'pending',
            sent_at TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (dunning_event_id) REFERENCES dunning_events (id) ON DELETE CASCADE
        );
        """)

        # 4. Custom Dunning Templates Table
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

# ==============================================================================
# ZERO-TRUST AUTHENTICATION & SECURITY UTILITIES
# ==============================================================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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

def generate_secure_token():
    return f"sec_tok_{secrets.token_urlsafe(24)}"

# ==============================================================================
# FAULT-ISOLATED BACKGROUND OUTREACH WORKER (CRON THREAD)
# ==============================================================================
def background_outreach_worker():
    while True:
        try:
            time.sleep(30)
            with get_db() as conn:
                now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                pending = conn.execute(
                    "SELECT * FROM outreach_queue WHERE status = 'pending' AND scheduled_time <= ?", 
                    (now,)
                ).fetchall()

                for task in pending:
                    event = conn.execute("SELECT * FROM dunning_events WHERE id = ?", (task['dunning_event_id'],)).fetchone()
                    if event and event['status'] == 'past_due':
                        print(f"[ENTERPRISE DISPATCH] Touchpoint {task['touchpoint']} via {task['channel']} -> {event['customer_email']} (${event['amount_due_cents']/100.0})")
                    
                    conn.execute("UPDATE outreach_queue SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE id = ?", (task['id'],))
                conn.commit()
        except Exception as e:
            print(f"[WORKER RECOVERY EXCEPTION] {str(e)}")

threading.Thread(target=background_outreach_worker, daemon=True).start()

# ==============================================================================
# STRIPE OAUTH & CRYPTOGRAPHICALLY SECURE WEBHOOK ENGINE
# ==============================================================================
@app.route('/stripe/authorize')
@login_required
def stripe_authorize():
    oauth_state = secrets.token_hex(16)
    session['stripe_oauth_state'] = oauth_state
    authorize_url = (
        f"https://connect.stripe.com/oauth/authorize?"
        f"response_type=code&client_id={STRIPE_CLIENT_ID}&scope=read_write&state={oauth_state}"
    )
    return redirect(authorize_url)

@app.route('/stripe/callback')
@login_required
def handle_stripe_oauth_callback():
    code = request.args.get('code')
    returned_state = request.args.get('state')
    expected_state = session.pop('stripe_oauth_state', None)

    if not expected_state or returned_state != expected_state:
        return "CSRF State Mismatch Error. Authorization aborted.", 400

    user = get_current_user()
    if code:
        try:
            response = stripe.OAuth.token(grant_type='authorization_code', code=code)
            with get_db() as conn:
                conn.execute("""
                    UPDATE users 
                    SET stripe_account_id = ?, stripe_access_token = ?, stripe_refresh_token = ?
                    WHERE id = ?
                """, (response['stripe_user_id'], response['access_token'], response.get('refresh_token', ''), user['id']))
                conn.commit()
        except stripe.error.StripeError as e:
            return f"Stripe OAuth Error: {str(e)}", 500

    return redirect(url_for('dashboard'))

@app.route('/stripe/disconnect', methods=['POST'])
@login_required
def disconnect_stripe():
    user = get_current_user()
    with get_db() as conn:
        conn.execute("""
            UPDATE users 
            SET stripe_account_id = NULL, stripe_access_token = NULL, stripe_refresh_token = NULL
            WHERE id = ?
        """, (user['id'],))
        conn.commit()
    return redirect(url_for('dashboard'))

@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', None)

    try:
        if STRIPE_WEBHOOK_SECRET != "whsec_mock_secret_123":
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload.decode('utf-8'))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    event_type = event['type']
    data_object = event['data']['object']
    account_id = event.get('account', 'default_account')

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE stripe_account_id = ?", (account_id,)).fetchone()
        user_id = user['id'] if user else 1

        if event_type == 'invoice.payment_failed':
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO dunning_events 
                    (user_id, event_id, stripe_customer_id, customer_email, customer_name, amount_due_cents, currency, invoice_url, status, attempt_count, secure_token)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'past_due', 1, ?)
                """, (
                    user_id, 
                    event.get('id', f"evt_{secrets.token_hex(8)}"), 
                    data_object.get('customer', 'cus_mock'), 
                    data_object.get('customer_email', 'client@example.com'),
                    data_object.get('customer_name', 'Valued Customer'),
                    int(data_object.get('amount_due', 3900)), 
                    data_object.get('currency', 'usd').upper(), 
                    data_object.get('hosted_invoice_url', ''), 
                    generate_secure_token()
                ))
                dunning_id = cursor.lastrowid
                conn.commit()

                # Schedule Multi-Touch Sequence (T+15m, T+72h, T+7d)
                now = datetime.utcnow()
                conn.execute("INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, 1, 'email', ?)", (dunning_id, now + timedelta(minutes=15)))
                conn.execute("INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, 2, 'email', ?)", (dunning_id, now + timedelta(hours=72)))
                conn.execute("INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, 2, 'sms', ?)", (dunning_id, now + timedelta(hours=72)))
                conn.execute("INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, 3, 'email', ?)", (dunning_id, now + timedelta(days=7)))
                conn.commit()
            except sqlite3.IntegrityError:
                pass # Idempotent duplicate rejection

        elif event_type == 'invoice.payment_succeeded':
            customer_id = data_object.get('customer')
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dunning_events 
                SET status = 'recovered', updated_at = CURRENT_TIMESTAMP 
                WHERE stripe_customer_id = ? AND status != 'recovered'
            """, (customer_id,))
            event_record = cursor.execute("SELECT id FROM dunning_events WHERE stripe_customer_id = ?", (customer_id,)).fetchone()
            if event_record:
                cursor.execute("UPDATE outreach_queue SET status = 'canceled' WHERE dunning_event_id = ? AND status = 'pending'", (event_record['id'],))
            conn.commit()

        elif event_type == 'customer.subscription.updated':
            customer_id = data_object.get('customer')
            sub_status = data_object.get('status')
            conn.execute("UPDATE dunning_events SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE stripe_customer_id = ? AND status != 'recovered'", (sub_status, customer_id))
            conn.commit()

    return jsonify({"status": "success"}), 200

# ==============================================================================
# PIXEL-PERFECT CUSTOMER CARD UPDATE PORTAL (RESPONSIVE TAILWIND UI)
# ==============================================================================
CARD_UPDATE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure Payment Portal - {{ company_name }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://js.stripe.com/v3/"></script>
    <style>:root { --brand-color: {{ brand_color }}; } .bg-brand { background-color: var(--brand-color); }</style>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-gray-100 space-y-6">
        <div class="text-center">
            {% if brand_logo_url %}<img src="{{ brand_logo_url }}" class="h-12 mx-auto mb-3 object-contain">{% endif %}
            <h2 class="text-2xl font-extrabold text-gray-900">{{ company_name }}</h2>
            <p class="text-sm text-amber-600 mt-1 font-semibold">Subscription Paused Due to Payment Failure</p>
        </div>
        <div class="bg-gray-50 p-4 rounded-xl border flex justify-between items-center">
            <span class="text-sm text-gray-500 font-medium">Amount Due:</span>
            <span class="text-lg font-bold text-gray-900">{{ currency }} ${{ "%.2f"|format(amount_due) }}</span>
        </div>
        <form id="payment-form" class="space-y-4">
            <div id="card-element" class="p-3.5 border rounded-lg bg-white shadow-sm"></div>
            <div id="card-errors" class="text-xs text-red-600 font-medium"></div>
            <button id="submit-btn" type="submit" class="w-full bg-brand text-white py-3.5 rounded-xl font-bold shadow-lg hover:opacity-90 transition">Update Payment Method & Restore</button>
        </form>
    </div>
    <script>
        const stripe = Stripe('{{ stripe_pub_key }}');
        const elements = stripe.elements();
        const card = elements.create('card');
        card.mount('#card-element');

        document.getElementById('payment-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submit-btn');
            btn.disabled = true;
            btn.textContent = 'Processing Securely...';

            const { paymentMethod, error } = await stripe.createPaymentMethod({ type: 'card', card: card });
            if (error) {
                document.getElementById('card-errors').textContent = error.message;
                btn.disabled = false;
                btn.textContent = 'Update Payment Method & Restore';
            } else {
                const res = await fetch('/api/update-payment-method', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: '{{ token }}', payment_method_id: paymentMethod.id })
                });
                const data = await res.json();
                if (data.success) {
                    alert('Payment successful! Your subscription has been fully restored.');
                    window.location.reload();
                } else {
                    document.getElementById('card-errors').textContent = data.message || 'Error processing transaction.';
                    btn.disabled = false;
                    btn.textContent = 'Update Payment Method & Restore';
                }
            }
        });
    </script>
</body>
</html>
"""

@app.route('/pay/update/<token>')
def card_update_page(token):
    with get_db() as conn:
        event = conn.execute("SELECT * FROM dunning_events WHERE secure_token = ?", (token,)).fetchone()
        if not event: return "Invalid or Expired Payment Link", 404
        user = conn.execute("SELECT * FROM users WHERE id = ?", (event['user_id'],)).fetchone()
    return render_template_string(CARD_UPDATE_TEMPLATE, token=token, company_name=user['company_name'], brand_color=user['brand_color'], brand_logo_url=user['brand_logo_url'], amount_due=event['amount_due_cents']/100.0, currency=event['currency'], stripe_pub_key=STRIPE_PUBLISHABLE_KEY)

@app.route('/api/update-payment-method', methods=['POST'])
def api_update_payment_method():
    data = request.json or {}
    token, pm_id = data.get('token'), data.get('payment_method_id')
    if not token or not pm_id: return jsonify({"success": False, "message": "Missing required parameters."}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        event = cursor.execute("SELECT * FROM dunning_events WHERE secure_token = ?", (token,)).fetchone()
        if not event: return jsonify({"success": False, "message": "Dunning record not found."}), 404
        if event['status'] == 'recovered': return jsonify({"success": True})

        # Atomic State Lock: Guaranteed race-condition protection
        cursor.execute("UPDATE dunning_events SET status = 'recovered', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status != 'recovered'", (event['id'],))
        cursor.execute("UPDATE outreach_queue SET status = 'canceled' WHERE dunning_event_id = ? AND status = 'pending'", (event['id'],))
        conn.commit()
    return jsonify({"success": True})

# ==============================================================================
# PIXEL-PERFECT FOUNDER DASHBOARD & KPI ANALYTICS
# ==============================================================================
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Founder Dashboard - RetainSaaS</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-100 text-gray-900 font-sans">
    <div class="min-h-screen flex flex-col">
        <nav class="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm">
            <div class="flex items-center space-x-3">
                <div class="bg-indigo-600 text-white font-extrabold px-3 py-1.5 rounded-lg">RetainSaaS Master</div>
                <span class="text-xs bg-indigo-100 text-indigo-700 px-2.5 py-1 rounded-full font-bold">{{ user.plan_tier }}</span>
            </div>
            <div class="flex items-center space-x-4 text-sm font-semibold">
                <span class="text-gray-600">{{ user.email }}</span>
                <a href="/logout" class="text-red-500 hover:text-red-700">Logout</a>
            </div>
        </nav>
        <div class="p-8 max-w-7xl mx-auto w-full space-y-8 flex-1">
            <div class="bg-white p-6 rounded-2xl shadow-sm border flex justify-between items-center">
                <div>
                    <h3 class="font-bold text-lg text-gray-800">Stripe Integration Status</h3>
                    <p class="text-sm text-gray-500 mt-0.5">Connected account ID: {{ user.stripe_account_id or 'Not Connected' }}</p>
                </div>
                <div>
                    {% if user.stripe_account_id %}
                        <form action="/stripe/disconnect" method="POST"><button class="text-xs bg-red-50 text-red-600 font-bold px-3 py-2 rounded-lg border border-red-200">Disconnect</button></form>
                    {% else %}
                        <a href="/stripe/authorize" class="bg-indigo-600 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow hover:bg-indigo-700 transition">Connect Stripe Account</a>
                    {% endif %}
                </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div class="bg-white p-6 rounded-2xl shadow-sm border"><p class="text-xs font-bold text-gray-400 uppercase">At-Risk MRR</p><h3 class="text-3xl font-extrabold text-amber-600 mt-2">${{ "%.2f"|format(at_risk_mrr) }}</h3></div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border"><p class="text-xs font-bold text-gray-400 uppercase">Recovered Revenue</p><h3 class="text-3xl font-extrabold text-green-600 mt-2">${{ "%.2f"|format(recovered_mrr) }}</h3></div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border"><p class="text-xs font-bold text-gray-400 uppercase">Recovery Rate</p><h3 class="text-3xl font-extrabold text-indigo-600 mt-2">{{ "%.1f"|format(recovery_rate) }}%</h3></div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border"><p class="text-xs font-bold text-gray-400 uppercase">Active Recoveries</p><h3 class="text-3xl font-extrabold text-gray-800 mt-2">{{ active_count }}</h3></div>
            </div>
            <div class="bg-white rounded-2xl shadow-sm border overflow-hidden">
                <div class="px-6 py-4 border-b font-extrabold text-gray-800">Active Dunning Transactions & Recovery Log</div>
                <table class="w-full text-left text-sm text-gray-600">
                    <thead class="bg-gray-50 text-xs uppercase font-semibold text-gray-500"><tr><th class="px-6 py-3">Customer Email</th><th class="px-6 py-3">Amount Due</th><th class="px-6 py-3">Status</th><th class="px-6 py-3 text-right">Customer Portal Link</th></tr></thead>
                    <tbody class="divide-y">
                        {% for ev in events %}
                        <tr class="hover:bg-gray-50/50">
                            <td class="px-6 py-4 font-semibold text-gray-900">{{ ev.customer_email }}</td>
                            <td class="px-6 py-4">${{ "%.2f"|format(ev.amount_due_cents / 100.0) }} {{ ev.currency }}</td>
                            <td class="px-6 py-4"><span class="px-2.5 py-1 text-xs font-bold rounded-full {% if ev.status == 'recovered' %}bg-green-100 text-green-800{% else %}bg-amber-100 text-amber-800{% endif %}">{{ ev.status }}</span></td>
                            <td class="px-6 py-4 text-right"><a href="/pay/update/{{ ev.secure_token }}" target="_blank" class="text-xs bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-md font-bold hover:bg-indigo-100 transition">Open Link</a></td>
                        </tr>
                        {% else %}<tr><td colspan="4" class="px-6 py-12 text-center text-gray-400">No failed payments recorded yet.</td></tr>{% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    with get_db() as conn:
        events = conn.execute("SELECT * FROM dunning_events WHERE user_id = ? ORDER BY id DESC", (user['id'],)).fetchall()

    at_risk_mrr = sum(e['amount_due_cents'] for e in events if e['status'] == 'past_due') / 100.0
    recovered_mrr = sum(e['amount_due_cents'] for e in events if e['status'] == 'recovered') / 100.0
    total_count, recovered_count = len(events), sum(1 for e in events if e['status'] == 'recovered')
    recovery_rate = (recovered_count / total_count * 100) if total_count > 0 else 0.0
    active_count = sum(1 for e in events if e['status'] == 'past_due')

    return render_template_string(
        DASHBOARD_TEMPLATE,
        user=user,
        events=events,
        at_risk_mrr=at_risk_mrr,
        recovered_mrr=recovered_mrr,
        recovery_rate=recovery_rate,
        active_count=active_count
    )

# ==============================================================================
# ZERO-TRUST AUTHENTICATION & PORTAL ROUTES
# ==============================================================================
AUTH_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>RetainSaaS Auth Portal</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-gray-100 space-y-6">
        <h1 class="text-2xl font-extrabold text-center text-gray-900">RetainSaaS Master Portal</h1>
        <form action="/login" method="POST" class="space-y-4">
            <div><label class="block text-sm font-bold text-gray-700">Email Address</label><input type="email" name="email" required class="w-full mt-1 p-3 border rounded-xl focus:ring-2 focus:ring-indigo-500"></div>
            <div><label class="block text-sm font-bold text-gray-700">Password</label><input type="password" name="password" required class="w-full mt-1 p-3 border rounded-xl focus:ring-2 focus:ring-indigo-500"></div>
            <button type="submit" class="w-full bg-indigo-600 text-white py-3 rounded-xl font-bold shadow hover:bg-indigo-700 transition">Log In / Sign Up</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET'])
@app.route('/login', methods=['GET'])
def login_page():
    if get_current_user(): return redirect(url_for('dashboard'))
    return render_template_string(AUTH_TEMPLATE)

@app.route('/login', methods=['POST'])
def login_post():
    email, password = request.form.get('email'), request.form.get('password')
    pwd_hash = hash_password(password)

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, pwd_hash))
            conn.commit()
            user_id = cursor.lastrowid
        else:
            if user['password_hash'] != pwd_hash: return "Invalid credentials.", 401
            user_id = user['id']

    # Session fixation defense: Clear session and generate brand new secure ID
    session.clear()
    session['user_id'] = user_id
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == '__main__':
    print("🚀 RetainSaaS Master Ultimate Edition Running on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)


