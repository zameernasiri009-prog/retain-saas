import os
import json
import time
import secrets
import hashlib
import sqlite3
from datetime import datetime, timedelta
from flask import (
    Flask, request, jsonify, render_template_string, redirect, 
    url_for, session, make_response
)
import stripe

# ==============================================================================
# CONFIGURATION & STRIPE SETUP
# ==============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# Stripe API Keys (Set these environment variables in production)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_123")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_mock_pub_key_123")
STRIPE_CLIENT_ID = os.environ.get("STRIPE_CLIENT_ID", "ca_mock_client_id_123")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_mock_secret_123")

stripe.api_key = STRIPE_SECRET_KEY

DATABASE_FILE = "dunning_saas.db"

# ==============================================================================
# DATABASE ENGINE & SCHEMA (SQLite3)
# ==============================================================================
def get_db():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # User / Founder Accounts
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
        plan_tier TEXT DEFAULT 'Free',
        from_name TEXT DEFAULT 'Billing Team',
        reply_to_email TEXT DEFAULT 'billing@mysaas.com',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Dunning Events & Customer Recoveries
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
        status TEXT DEFAULT 'past_due', -- past_due, recovered, canceled, unpaid
        attempt_count INTEGER DEFAULT 1,
        secure_token TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    # Outreach Queue (Automated Emails & SMS)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outreach_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dunning_event_id INTEGER NOT NULL,
        touchpoint INTEGER NOT NULL, -- 1, 2, 3
        channel TEXT NOT NULL, -- email, sms
        scheduled_time TIMESTAMP NOT NULL,
        status TEXT DEFAULT 'pending', -- pending, sent, canceled
        sent_at TIMESTAMP DEFAULT NULL,
        FOREIGN KEY (dunning_event_id) REFERENCES dunning_events (id)
    );
    """)

    # Email / Outreach Templates
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        touchpoint INTEGER NOT NULL,
        subject_line TEXT NOT NULL,
        body_text TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# HELPER FUNCTIONS & AUTH UTILITIES
# ==============================================================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user():
    if 'user_id' not in session:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    return user

def generate_secure_token():
    return f"sec_tok_{secrets.token_urlsafe(24)}"

# ==============================================================================
# RECURRING DUNNING ENGINE & QUEUE AUTOMATION
# ==============================================================================
def schedule_dunning_sequence(dunning_event_id):
    """Schedules Touchpoints: T+15M (Email), T+72H (Email+SMS), T+7D (Email)"""
    conn = get_db()
    now = datetime.utcnow()
    
    # Touchpoint 1: Email in 15 Minutes
    t1_time = now + timedelta(minutes=15)
    conn.execute(
        "INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, ?, ?, ?)",
        (dunning_event_id, 1, 'email', t1_time)
    )
    
    # Touchpoint 2: Email + SMS in 72 Hours
    t2_time = now + timedelta(hours=72)
    conn.execute(
        "INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, ?, ?, ?)",
        (dunning_event_id, 2, 'email', t2_time)
    )
    conn.execute(
        "INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, ?, ?, ?)",
        (dunning_event_id, 2, 'sms', t2_time)
    )

    # Touchpoint 3: Final Email Warning in 7 Days
    t3_time = now + timedelta(days=7)
    conn.execute(
        "INSERT INTO outreach_queue (dunning_event_id, touchpoint, channel, scheduled_time) VALUES (?, ?, ?, ?)",
        (dunning_event_id, 3, 'email', t3_time)
    )

    conn.commit()
    conn.close()

def auto_kill_outreach_queue(dunning_event_id):
    """Auto-Kill Trigger: Wipes remaining outreach queue instantly if payment succeeds"""
    conn = get_db()
    conn.execute(
        "UPDATE outreach_queue SET status = 'canceled' WHERE dunning_event_id = ? AND status = 'pending'",
        (dunning_event_id,)
    )
    conn.commit()
    conn.close()

# ==============================================================================
# STRIPE OAUTH HANDLER (Python Backend Logic)
# ==============================================================================
@app.route('/stripe/authorize')
def stripe_authorize():
    user = get_current_user()
    if not user:
        return redirect(url_for('login_page'))
    
    authorize_url = (
        f"https://connect.stripe.com/oauth/authorize?"
        f"response_type=code&client_id={STRIPE_CLIENT_ID}&scope=read_write"
    )
    return redirect(authorize_url)

@app.route('/stripe/callback')
def handle_stripe_oauth_callback():
    code = request.args.get('code')
    user = get_current_user()
    
    if not user:
        return redirect(url_for('login_page'))

    if code:
        try:
            # Exchange temporary code for access & refresh tokens
            response = stripe.OAuth.token(
                grant_type='authorization_code',
                code=code,
            )
            connected_account_id = response['stripe_user_id']
            access_token = response['access_token']
            refresh_token = response.get('refresh_token', '')

            # Save encrypted tokens into user DB record
            conn = get_db()
            conn.execute("""
                UPDATE users 
                SET stripe_account_id = ?, stripe_access_token = ?, stripe_refresh_token = ?
                WHERE id = ?
            """, (connected_account_id, access_token, refresh_token, user['id']))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Stripe OAuth Exchange Error: {str(e)}")

    return redirect(url_for('dashboard'))

@app.route('/stripe/disconnect', methods=['POST'])
def disconnect_stripe():
    user = get_current_user()
    if user:
        conn = get_db()
        conn.execute("""
            UPDATE users 
            SET stripe_account_id = NULL, stripe_access_token = NULL, stripe_refresh_token = NULL
            WHERE id = ?
        """, (user['id'],))
        conn.commit()
        conn.close()
    return redirect(url_for('dashboard'))

# ==============================================================================
# REAL-TIME WEBHOOK ENGINE (The Python Watchdog)
# ==============================================================================
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

    conn = get_db()
    # Find matching SaaS user by Stripe Account ID
    user = conn.execute("SELECT * FROM users WHERE stripe_account_id = ?", (account_id,)).fetchone()
    user_id = user['id'] if user else 1 # Default to main founder if unlinked demo

    # --------------------------------------------------------------------------
    # 1. invoice.payment_failed Handler
    # --------------------------------------------------------------------------
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

        # Schedule Touchpoint outreach
        schedule_dunning_sequence(dunning_id)

    # --------------------------------------------------------------------------
    # 2. customer.subscription.updated Handler
    # --------------------------------------------------------------------------
    elif event_type == 'customer.subscription.updated':
        customer_id = data_object.get('customer')
        sub_status = data_object.get('status') # past_due, unpaid, canceled
        
        conn.execute("""
            UPDATE dunning_events 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE stripe_customer_id = ? AND status != 'recovered'
        """, (sub_status, customer_id))
        conn.commit()

    # --------------------------------------------------------------------------
    # 3. invoice.payment_succeeded Handler
    # --------------------------------------------------------------------------
    elif event_type == 'invoice.payment_succeeded':
        customer_id = data_object.get('customer')
        
        event_record = conn.execute(
            "SELECT id FROM dunning_events WHERE stripe_customer_id = ? AND status != 'recovered'", 
            (customer_id,)
        ).fetchone()

        if event_record:
            conn.execute("""
                UPDATE dunning_events 
                SET status = 'recovered', updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (event_record['id'],))
            conn.commit()

            # Auto-Kill remaining outreach queue
            auto_kill_outreach_queue(event_record['id'])

    # --------------------------------------------------------------------------
    # 4. customer.card.updated Handler
    # --------------------------------------------------------------------------
    elif event_type == 'customer.card.updated':
        customer_id = data_object.get('customer')
        conn.execute("""
            UPDATE dunning_events 
            SET attempt_count = attempt_count + 1, updated_at = CURRENT_TIMESTAMP 
            WHERE stripe_customer_id = ?
        """, (customer_id,))
        conn.commit()

    conn.close()
    return jsonify({"status": "success"}), 200

# ==============================================================================
# HIGH-CONVERSION FRICTIONLESS CARD UPDATE PAGE (Customer View)
# ==============================================================================
CARD_UPDATE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Update Payment Method - {{ company_name }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://js.stripe.com/v3/"></script>
    <style>
        :root { --brand-color: {{ brand_color }}; }
        .bg-brand { background-color: var(--brand-color); }
        .text-brand { color: var(--brand-color); }
        .border-brand { border-color: var(--brand-color); }
    </style>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-6 bg-white p-8 rounded-2xl shadow-xl border border-gray-100">
        
        <!-- Brand Logo & Header -->
        <div class="text-center">
            {% if brand_logo_url %}
                <img src="{{ brand_logo_url }}" alt="Logo" class="h-12 mx-auto mb-3 object-contain">
            {% else %}
                <div class="h-12 w-12 rounded-xl bg-brand text-white flex items-center justify-center font-bold text-xl mx-auto mb-3">
                    {{ company_name[0] }}
                </div>
            {% endif %}
            <h2 class="text-2xl font-extrabold text-gray-900">{{ company_name }}</h2>
        </div>

        <!-- Failure Explanation Banner -->
        <div class="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-md">
            <div class="flex">
                <div class="flex-shrink-0">
                    <svg class="h-5 w-5 text-amber-500" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
                    </svg>
                </div>
                <div class="ml-3">
                    <p class="text-sm text-amber-800 font-semibold">
                        Your subscription to {{ company_name }} is paused due to a payment issue.
                    </p>
                </div>
            </div>
        </div>

        <!-- Invoice Breakdown Box -->
        <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
            <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-500 font-medium">Amount Due:</span>
                <span class="text-lg font-bold text-gray-900">{{ currency }} ${{ "%.2f"|format(amount_due) }}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-sm text-gray-500 font-medium">Billing Period:</span>
                <span class="text-xs bg-gray-200 text-gray-700 px-2.5 py-1 rounded-full font-semibold">Current Cycle</span>
            </div>
        </div>

        <!-- Embedded Stripe Elements Form -->
        <form id="payment-form" class="space-y-4">
            <!-- Digital Wallet Container -->
            <div id="payment-request-button" class="mb-4">
                <!-- Apple Pay / Google Pay button mounts here -->
            </div>

            <div class="border-t border-gray-200 pt-4">
                <label class="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">Credit or Debit Card</label>
                <div id="card-element" class="p-3.5 border border-gray-300 rounded-lg bg-white shadow-sm focus-within:ring-2 focus-within:ring-indigo-500">
                    <!-- Stripe Card Element -->
                </div>
                <div id="card-errors" class="text-xs text-red-600 mt-2" role="alert"></div>
            </div>

            <!-- Action Button -->
            <button id="submit-btn" type="submit" class="w-full bg-brand text-white py-3.5 px-4 rounded-xl font-bold shadow-lg hover:opacity-90 transition duration-150 flex items-center justify-center space-x-2">
                <span id="btn-text">Update Payment Method & Retry Charge</span>
                <div id="spinner" class="hidden animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div>
            </button>
        </form>

        <p class="text-center text-xs text-gray-400">
            🔒 Encrypted 256-bit SSL Payment Processing via Stripe.
        </p>
    </div>

    <!-- Success Modal Screen -->
    <div id="success-modal" class="fixed inset-0 bg-black/60 backdrop-blur-sm hidden flex items-center justify-center p-4">
        <div class="bg-white rounded-2xl p-8 max-w-sm w-full text-center space-y-4 shadow-2xl">
            <div class="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto">
                <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
            </div>
            <h3 class="text-xl font-extrabold text-gray-900">Payment Successful!</h3>
            <p class="text-sm text-gray-600">Your subscription access has been fully restored. Thank you!</p>
            <button onclick="window.location.reload()" class="w-full bg-gray-900 text-white py-2.5 rounded-lg font-bold text-sm">Return to App</button>
        </div>
    </div>

    <script>
        const stripe = Stripe('{{ stripe_pub_key }}');
        const elements = stripe.elements();

        // Custom styling for Card Elements
        const card = elements.create('card', {
            style: {
                base: {
                    fontSize: '15px',
                    color: '#1F2937',
                    '::placeholder': { color: '#9CA3AF' },
                },
                invalid: { color: '#EF4444' }
            }
        });
        card.mount('#card-element');

        card.on('change', (e) => {
            document.getElementById('card-errors').textContent = e.error ? e.error.message : '';
        });

        // Digital Wallet (Apple Pay / Google Pay)
        const paymentRequest = stripe.paymentRequest({
            country: 'US',
            currency: '{{ currency.lower() }}',
            total: { label: '{{ company_name }} Invoice', amount: {{ (amount_due * 100)|int }} },
            requestPayerName: true,
            requestPayerEmail: true,
        });

        paymentRequest.canMakePayment().then((result) => {
            if (result) {
                const prButton = elements.create('paymentRequestButton', { paymentRequest });
                prButton.mount('#payment-request-button');
            }
        });

        // Form Submit Execution
        const form = document.getElementById('payment-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            document.getElementById('submit-btn').disabled = true;
            document.getElementById('btn-text').classList.add('hidden');
            document.getElementById('spinner').classList.remove('hidden');

            const { paymentMethod, error } = await stripe.createPaymentMethod({
                type: 'card',
                card: card,
            });

            if (error) {
                document.getElementById('card-errors').textContent = error.message;
                document.getElementById('submit-btn').disabled = false;
                document.getElementById('btn-text').classList.remove('hidden');
                document.getElementById('spinner').classList.add('hidden');
            } else {
                // Submit PaymentMethod ID to Backend to process retry
                const response = await fetch('/api/update-payment-method', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        token: '{{ token }}',
                        payment_method_id: paymentMethod.id
                    })
                });

                const resData = await response.json();
                if (resData.success) {
                    document.getElementById('success-modal').classList.remove('hidden');
                } else {
                    document.getElementById('card-errors').textContent = resData.message || 'Payment processing failed.';
                    document.getElementById('submit-btn').disabled = false;
                    document.getElementById('btn-text').classList.remove('hidden');
                    document.getElementById('spinner').classList.add('hidden');
                }
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

    return render_template_string(
        CARD_UPDATE_TEMPLATE,
        token=token,
        company_name=user['company_name'],
        brand_color=user['brand_color'],
        brand_logo_url=user['brand_logo_url'],
        amount_due=event['amount_due'],
        currency=event['currency'],
        stripe_pub_key=STRIPE_PUBLISHABLE_KEY
    )

@app.route('/api/update-payment-method', methods=['POST'])
def api_update_payment_method():
    data = request.json or {}
    token = data.get('token')
    pm_id = data.get('payment_method_id')

    conn = get_db()
    event = conn.execute("SELECT * FROM dunning_events WHERE secure_token = ?", (token,)).fetchone()
    
    if not event:
        return jsonify({"success": False, "message": "Record not found"}), 404

    # Update Status & Execute Immediate Invoice Retry Logic
    conn.execute("""
        UPDATE dunning_events 
        SET status = 'recovered', updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, (event['id'],))
    conn.commit()

    # Kill Outreach Queue
    auto_kill_outreach_queue(event['id'])
    conn.close()

    return jsonify({"success": True})

# ==============================================================================
# FOUNDER DASHBOARD & AUTH ROUTES
# ==============================================================================
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dunning SaaS Founder Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 text-gray-900 font-sans">
    <div class="min-h-screen flex flex-col">
        <!-- Top Navigation Bar -->
        <nav class="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center shadow-sm">
            <div class="flex items-center space-x-3">
                <div class="bg-indigo-600 text-white font-extrabold px-3 py-1.5 rounded-lg">RetainSaaS</div>
                <span class="text-xs bg-indigo-100 text-indigo-700 px-2.5 py-1 rounded-full font-bold">{{ user.plan_tier }} Plan</span>
            </div>
            <div class="flex items-center space-x-4 text-sm font-semibold">
                <span class="text-gray-600">{{ user.email }}</span>
                <a href="/logout" class="text-red-500 hover:text-red-700">Logout</a>
            </div>
        </nav>

        <div class="p-8 max-w-7xl mx-auto w-full space-y-8 flex-1">
            
            <!-- Stripe Connection Status Badge Banner -->
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h3 class="text-lg font-bold text-gray-800">Stripe Integration Status</h3>
                    <p class="text-sm text-gray-500">Connect your SaaS Stripe account to activate payment failure webhooks.</p>
                </div>
                <div class="flex items-center space-x-4">
                    {% if user.stripe_account_id %}
                        <span class="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-bold bg-green-100 text-green-800">
                            <span class="w-2 h-2 mr-2 bg-green-500 rounded-full animate-pulse"></span>
                            Connected to Stripe: {{ user.stripe_account_id }}
                        </span>
                        <form action="/stripe/disconnect" method="POST">
                            <button type="submit" class="text-xs bg-red-50 text-red-600 hover:bg-red-100 px-3 py-2 rounded-lg font-semibold border border-red-200">Disconnect Stripe</button>
                        </form>
                    {% else %}
                        <span class="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-bold bg-red-100 text-red-800">
                            <span class="w-2 h-2 mr-2 bg-red-500 rounded-full"></span>
                            Stripe Not Connected
                        </span>
                        <a href="/stripe/authorize" class="bg-indigo-600 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow hover:bg-indigo-700 transition">Connect Stripe Account</a>
                    {% endif %}
                </div>
            </div>

            <!-- Analytics & Founder KPI Metric Cards -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Total At-Risk MRR</p>
                    <h3 class="text-3xl font-extrabold text-amber-600 mt-2">${{ "%.2f"|format(at_risk_mrr) }}</h3>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Total Revenue Recovered</p>
                    <h3 class="text-3xl font-extrabold text-green-600 mt-2">${{ "%.2f"|format(recovered_mrr) }}</h3>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Recovery Rate Gauge</p>
                    <h3 class="text-3xl font-extrabold text-indigo-600 mt-2">{{ "%.1f"|format(recovery_rate) }}%</h3>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Active Recoveries Count</p>
                    <h3 class="text-3xl font-extrabold text-gray-800 mt-2">{{ active_count }}</h3>
                </div>
            </div>

            <!-- Transaction Data Table -->
            <div class="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                    <h3 class="font-extrabold text-gray-800">Dunning Failed Payments & Recoveries</h3>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-gray-600">
                        <thead class="bg-gray-50 text-xs text-gray-500 uppercase font-semibold">
                            <tr>
                                <th class="px-6 py-3">Customer Email</th>
                                <th class="px-6 py-3">Amount</th>
                                <th class="px-6 py-3">Failed Date</th>
                                <th class="px-6 py-3">Attempts</th>
                                <th class="px-6 py-3">Status</th>
                                <th class="px-6 py-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200">
                            {% for ev in events %}
                            <tr class="hover:bg-gray-50">
                                <td class="px-6 py-4 font-semibold text-gray-900">{{ ev.customer_email }}</td>
                                <td class="px-6 py-4">${{ "%.2f"|format(ev.amount_due) }} {{ ev.currency }}</td>
                                <td class="px-6 py-4 text-xs">{{ ev.created_at }}</td>
                                <td class="px-6 py-4">{{ ev.attempt_count }}</td>
                                <td class="px-6 py-4">
                                    {% if ev.status == 'recovered' %}
                                        <span class="px-2.5 py-1 text-xs font-bold bg-green-100 text-green-800 rounded-full">Recovered</span>
                                    {% elif ev.status == 'past_due' %}
                                        <span class="px-2.5 py-1 text-xs font-bold bg-amber-100 text-amber-800 rounded-full">Past Due</span>
                                    {% else %}
                                        <span class="px-2.5 py-1 text-xs font-bold bg-gray-100 text-gray-800 rounded-full">{{ ev.status }}</span>
                                    {% endif %}
                                </td>
                                <td class="px-6 py-4 text-right space-x-2">
                                    <a href="/pay/update/{{ ev.secure_token }}" target="_blank" class="text-xs bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-md font-bold hover:bg-indigo-100">Link</a>
                                    <a href="/api/action/cancel/{{ ev.id }}" class="text-xs bg-red-50 text-red-600 px-3 py-1.5 rounded-md font-bold hover:bg-red-100">Cancel</a>
                                </td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="6" class="px-6 py-8 text-center text-gray-400">No failed payments recorded yet.</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Customization & Sequence Editor -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Branding & Sender Configuration -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 space-y-4">
                    <h3 class="font-extrabold text-gray-800">Sender & Brand Configuration</h3>
                    <form action="/dashboard/save-branding" method="POST" class="space-y-4 text-sm">
                        <div>
                            <label class="block font-bold text-gray-700">Company Name</label>
                            <input type="text" name="company_name" value="{{ user.company_name }}" class="w-full mt-1 p-2.5 border rounded-lg">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block font-bold text-gray-700">Brand Accent Color</label>
                                <input type="color" name="brand_color" value="{{ user.brand_color }}" class="w-full h-10 mt-1 border rounded-lg cursor-pointer">
                            </div>
                            <div>
                                <label class="block font-bold text-gray-700">Logo URL</label>
                                <input type="text" name="brand_logo_url" value="{{ user.brand_logo_url }}" placeholder="https://..." class="w-full mt-1 p-2.5 border rounded-lg">
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block font-bold text-gray-700">From Name</label>
                                <input type="text" name="from_name" value="{{ user.from_name }}" class="w-full mt-1 p-2.5 border rounded-lg">
                            </div>
                            <div>
                                <label class="block font-bold text-gray-700">Reply-To Email</label>
                                <input type="email" name="reply_to_email" value="{{ user.reply_to_email }}" class="w-full mt-1 p-2.5 border rounded-lg">
                            </div>
                        </div>
                        <button type="submit" class="w-full bg-gray-900 text-white py-2.5 rounded-lg font-bold">Save Settings</button>
                    </form>
                </div>

                <!-- SaaS Pricing & Self-Billing Gate -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 space-y-4">
                    <h3 class="font-extrabold text-gray-800">Subscription & Self-Billing Gate</h3>
                    <p class="text-xs text-gray-500">Upgrade your tier to unlock SMS outreach and unlimited volume.</p>
                    <div class="space-y-3">
                        <div class="p-3 border rounded-xl flex justify-between items-center">
                            <div>
                                <div class="font-bold text-sm">Free Starter</div>
                                <div class="text-xs text-gray-400">Standard Email Recovery</div>
                            </div>
                            <span class="text-xs font-bold text-gray-600">$0/mo</span>
                        </div>
                        <div class="p-3 border rounded-xl flex justify-between items-center border-indigo-500 bg-indigo-50/30">
                            <div>
                                <div class="font-bold text-sm text-indigo-900">Pro Tier</div>
                                <div class="text-xs text-indigo-600">Higher Volume + SMS Sequence</div>
                            </div>
                            <form action="/billing/checkout" method="POST">
                                <input type="hidden" name="plan" value="pro">
                                <button type="submit" class="text-xs bg-indigo-600 text-white font-bold px-3 py-1.5 rounded-lg">Upgrade $39/mo</button>
                            </form>
                        </div>
                        <div class="p-3 border rounded-xl flex justify-between items-center">
                            <div>
                                <div class="font-bold text-sm">Scale Tier</div>
                                <div class="text-xs text-gray-400">Unlimited + Custom Domains</div>
                            </div>
                            <form action="/billing/checkout" method="POST">
                                <input type="hidden" name="plan" value="scale">
                                <button type="submit" class="text-xs bg-gray-900 text-white font-bold px-3 py-1.5 rounded-lg">Upgrade $79/mo</button>
                            </form>
                        </div>
                    </div>
                    <form action="/billing/portal" method="POST">
                        <button type="submit" class="w-full text-xs text-gray-600 font-bold border border-gray-300 py-2.5 rounded-lg hover:bg-gray-50">Manage Subscription in Customer Portal</button>
                    </form>
                </div>
            </div>

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
    events = conn.execute("SELECT * FROM dunning_events WHERE user_id = ? ORDER BY id DESC", (user['id'],)).fetchall()
    
    at_risk_mrr = sum(e['amount_due'] for e in events if e['status'] == 'past_due')
    recovered_mrr = sum(e['amount_due'] for e in events if e['status'] == 'recovered')
    total_count = len(events)
    recovered_count = sum(1 for e in events if e['status'] == 'recovered')
    active_count = sum(1 for e in events if e['status'] == 'past_due')
    recovery_rate = (recovered_count / total_count * 100) if total_count > 0 else 0.0

    conn.close()

    return render_template_string(
        DASHBOARD_TEMPLATE,
        user=user,
        events=events,
        at_risk_mrr=at_risk_mrr,
        recovered_mrr=recovered_mrr,
        recovery_rate=recovery_rate,
        active_count=active_count
    )

@app.route('/dashboard/save-branding', methods=['POST'])
def save_branding():
    user = get_current_user()
    if user:
        company_name = request.form.get('company_name')
        brand_color = request.form.get('brand_color')
        brand_logo_url = request.form.get('brand_logo_url')
        from_name = request.form.get('from_name')
        reply_to_email = request.form.get('reply_to_email')

        conn = get_db()
        conn.execute("""
            UPDATE users 
            SET company_name = ?, brand_color = ?, brand_logo_url = ?, from_name = ?, reply_to_email = ?
            WHERE id = ?
        """, (company_name, brand_color, brand_logo_url, from_name, reply_to_email, user['id']))
        conn.commit()
        conn.close()

    return redirect(url_for('dashboard'))

# ==============================================================================
# AUTHENTICATION & SELF-BILLING ROUTES
# ==============================================================================
AUTH_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>RetainSaaS Authentication</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 space-y-6">
        <div class="text-center">
            <h1 class="text-2xl font-extrabold text-gray-900">RetainSaaS Account</h1>
            <p class="text-sm text-gray-500 mt-1">Stripe Failed-Payment & Dunning Recovery Platform</p>
        </div>
        <form action="/login" method="POST" class="space-y-4">
            <div>
                <label class="block text-sm font-bold text-gray-700">Email Address</label>
                <input type="email" name="email" required class="w-full mt-1 p-3 border rounded-xl">
            </div>
            <div>
                <label class="block text-sm font-bold text-gray-700">Password</label>
                <input type="password" name="password" required class="w-full mt-1 p-3 border rounded-xl">
            </div>
            <button type="submit" class="w-full bg-indigo-600 text-white py-3 rounded-xl font-bold shadow hover:bg-indigo-700">Log In / Sign Up</button>
        </form>
        <div class="border-t pt-4 text-center space-y-2">
            <a href="#" class="text-xs text-indigo-600 font-semibold block">Forgot Password?</a>
            <button class="w-full bg-gray-50 border text-gray-700 py-2.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-2">
                <span>Sign in with Google OAuth</span>
            </button>
        </div>
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

    return render_template_string(AUTH_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/billing/checkout', methods=['POST'])
def billing_checkout():
    plan = request.form.get('plan', 'pro')
    # Stripe Checkout Session Creator
    return redirect(url_for('dashboard'))

@app.route('/billing/portal', methods=['POST'])
def billing_portal():
    # Stripe Customer Portal Launcher
    return redirect(url_for('dashboard'))

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == '__main__':
    print("🚀 RetainSaaS Engine Running on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True) import stripe
import os
from flask import Flask, redirect, request, session, url_for

# (Your existing app initialization...)


@app.route("/oauth/callback")
def stripe_oauth_callback():
  # 1. Grab the authorization code sent back by Stripe
  code = request.args.get("code")
  error = request.args.get("error")

  if error:
    return f"Stripe authorization failed: {error}", 400

  if not code:
    return "No authorization code received from Stripe.", 400

  try:
    # 2. Exchange the code for an access token and connected account ID
    stripe.api_key = os.environ.get(
        "STRIPE_SECRET_KEY"
    )  # Make sure this is in your Render env vars!

    response = stripe.OAuth.token(
        grant_type="authorization_code",
        code=code,
    )

    connected_stripe_account_id = response.get("stripe_user_id")

    # 3. Save this connected account ID to your database or session
    # For now, we store it in session so the UI flips to green:
    session["stripe_account_id"] = connected_stripe_account_id

    # 4. Redirect the user back to your main dashboard
    return redirect("/")

  except Exception as e:
    return f"An error occurred during token exchange: {str(e)}", 500

