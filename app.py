import os
import json
import time
import secrets
import hashlib
import sqlite3
import threading
import re
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, request, jsonify, render_template_string, redirect, 
    url_for, session, make_response
)
import stripe

# ==============================================================================
# CONFIGURATION & ENTERPRISE ENGINE SETUP
# ==============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_123")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_mock_pub_key_123")
STRIPE_CLIENT_ID = os.environ.get("STRIPE_CLIENT_ID", "ca_mock_client_id_123")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_mock_secret_123")

stripe.api_key = STRIPE_SECRET_KEY
stripe.default_http_client = stripe.http_client.RequestsClient(timeout=10.0)

DATABASE_FILE = "retain_saas_pro.db"

# ==============================================================================
# DATABASE DETERMINISM & WAL MODE
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT DEFAULT 'RetainSaaS',
            brand_color TEXT DEFAULT '#4F46E5',
            stripe_account_id TEXT DEFAULT NULL,
            stripe_access_token TEXT DEFAULT NULL,
            stripe_refresh_token TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dunning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_id TEXT UNIQUE NOT NULL,
            stripe_customer_id TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            amount_due_cents INTEGER NOT NULL,
            currency TEXT DEFAULT 'USD',
            invoice_url TEXT DEFAULT '',
            status TEXT DEFAULT 'past_due',
            secure_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        conn.commit()

init_db()

# ==============================================================================
# SECURITY & VALIDATION HELPERS
# ==============================================================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None

def get_current_user():
    if 'user_id' not in session:
        return None
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for('auth_page'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# 1. ANIMATED SPLASH & WELCOME LANDING PAGE (ROOT)
# ==============================================================================
SPLASH_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to RetainSaaS</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @keyframes float { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-10px); } }
        .animate-float { animation: float 4s ease-in-out infinite; }
    </style>
</head>
<body class="h-full bg-slate-950 text-white font-sans flex flex-col justify-between overflow-x-hidden selection:bg-indigo-500 selection:text-white">
    <div class="absolute inset-0 bg-[linear-gradient(to_right,#1e293b15_1px,transparent_1px),linear-gradient(to_bottom,#1e293b15_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none"></div>

    <header class="w-full max-w-7xl mx-auto px-6 py-6 flex justify-between items-center relative z-10">
        <div class="flex items-center space-x-3">
            <div class="h-10 w-10 rounded-xl bg-indigo-600 flex items-center justify-center font-extrabold text-xl shadow-lg shadow-indigo-500/30">R</div>
            <span class="font-extrabold text-xl tracking-tight bg-gradient-to-r from-white via-slate-200 to-indigo-400 bg-clip-text text-transparent">RetainSaaS</span>
        </div>
        <a href="/auth" class="text-sm font-semibold bg-slate-900 hover:bg-slate-800 text-slate-200 px-5 py-2.5 rounded-xl border border-slate-800 transition shadow-sm">Log In / Sign Up</a>
    </header>

    <main class="max-w-4xl mx-auto px-6 text-center relative z-10 my-auto space-y-8 py-12">
        <div class="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold tracking-wide uppercase">
            <span class="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
            <span>Next-Gen Subscription Revenue Recovery</span>
        </div>

        <h1 class="text-5xl sm:text-7xl font-black tracking-tight text-white leading-tight">
            Welcome to <span class="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">RetainSaaS</span>.
        </h1>

        <p class="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto font-normal">
            Save your money and recover failed customer credit card payments automatically. Built for high-speed modern web applications.
        </p>

        <div class="pt-4 flex flex-col sm:flex-row justify-center items-center gap-4">
            <a href="/auth" class="w-full sm:w-auto px-8 py-4 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-2xl shadow-xl shadow-indigo-600/25 transition transform hover:-translate-y-0.5 text-base flex items-center justify-center space-x-3">
                <span>Get Started Now</span>
                <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"></path></svg>
            </a>
        </div>
    </main>

    <footer class="w-full text-center py-6 text-slate-600 text-xs relative z-10 border-t border-slate-900">
        &copy; 2026 RetainSaaS Engine. All rights reserved.
    </footer>
</body>
</html>
"""

@app.route('/')
def splash_page():
    if get_current_user():
        return redirect(url_for('dashboard'))
    return render_template_string(SPLASH_TEMPLATE)

# ==============================================================================
# 2. AUTHENTICATION & REGISTRATION PORTAL (/auth)
# ==============================================================================
AUTH_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Account Portal - RetainSaaS</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="h-full bg-slate-950 text-white flex items-center justify-center p-4 selection:bg-indigo-500 selection:text-white">
    <div class="max-w-md w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
        <div class="text-center space-y-2">
            <div class="h-12 w-12 rounded-2xl bg-indigo-600 text-white flex items-center justify-center font-black text-2xl mx-auto shadow-lg shadow-indigo-500/30">R</div>
            <h2 class="text-2xl font-black tracking-tight text-white">Welcome Back</h2>
            <p class="text-xs text-slate-400">Enter your credentials to access your dunning control center.</p>
        </div>

        {% if error %}
            <div class="bg-red-500/10 border border-red-500/20 p-3 rounded-xl text-xs text-red-400 font-semibold text-center">
                {{ error }}
            </div>
        {% endif %}

        <form action="/auth" method="POST" class="space-y-4">
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Email Address</label>
                <input type="email" name="email" required placeholder="founder@mysaas.com" class="w-full p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-600 text-sm focus:outline-none focus:border-indigo-500 transition">
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Password</label>
                <input type="password" name="password" required placeholder="••••••••" class="w-full p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-600 text-sm focus:outline-none focus:border-indigo-500 transition">
            </div>
            <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/25 transition text-sm">
                Log In / Create Account
            </button>
        </form>
        <div class="text-center">
            <a href="/" class="text-xs text-slate-500 hover:text-slate-400 transition">&larr; Back to Welcome Screen</a>
        </div>
    </div>
</body>
</html>
"""

@app.route('/auth', methods=['GET', 'POST'])
def auth_page():
    if get_current_user():
        return redirect(url_for('dashboard'))
    
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not validate_email(email):
            error = "Please enter a valid email address (e.g., name@domain.com)."
        elif len(password) < 4:
            error = "Password must be at least 4 characters long."
        else:
            pwd_hash = hash_password(password)
            with get_db() as conn:
                user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if not user:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, pwd_hash))
                    conn.commit()
                    user_id = cursor.lastrowid
                else:
                    if user['password_hash'] != pwd_hash:
                        error = "Incorrect password for this email."
                        return render_template_string(AUTH_TEMPLATE, error=error)
                    user_id = user['id']

            session.clear()
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))

    return render_template_string(AUTH_TEMPLATE, error=error)

# ==============================================================================
# 3. SECURE FOUNDER DASHBOARD (/dashboard)
# ==============================================================================
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - RetainSaaS</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="h-full bg-slate-950 text-white font-sans flex flex-col">
    <nav class="border-b border-slate-900 bg-slate-900/50 backdrop-blur px-6 py-4 flex justify-between items-center">
        <div class="flex items-center space-x-3">
            <div class="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-sm">R</div>
            <span class="font-bold text-base tracking-tight text-white">RetainSaaS Control Center</span>
        </div>
        <div class="flex items-center space-x-4">
            <span class="text-xs text-slate-400 hidden sm:inline">{{ user.email }}</span>
            <a href="/logout" class="text-xs bg-red-500/10 text-red-400 font-semibold px-3.5 py-2 rounded-xl border border-red-500/20 hover:bg-red-500/20 transition">Logout</a>
        </div>
    </nav>

    <div class="p-6 sm:p-8 max-w-7xl mx-auto w-full space-y-6 flex-1">
        <div class="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
                <h3 class="font-bold text-lg text-white">Stripe Account Integration</h3>
                <p class="text-xs text-slate-400 mt-1">Status: <span class="text-indigo-400 font-semibold">{{ user.stripe_account_id or 'Not Connected (Test Sandbox)' }}</span></p>
            </div>
            <div>
                {% if user.stripe_account_id %}
                    <form action="/stripe/disconnect" method="POST"><button class="text-xs bg-red-500/10 text-red-400 font-bold px-4 py-2.5 rounded-xl border border-red-500/20 hover:bg-red-500/20 transition">Disconnect</button></form>
                {% else %}
                    <a href="/stripe/authorize" class="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-5 py-3 rounded-xl shadow-lg shadow-indigo-600/25 transition inline-block">Connect Stripe Account</a>
                {% endif %}
            </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <div class="px-6 py-4 border-b border-slate-800 font-bold text-sm text-slate-200">Active Dunning Transactions</div>
            <div class="p-12 text-center text-slate-500 text-sm">
                No failed payments recorded yet. Your system is live and listening for webhooks.
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
    return render_template_string(DASHBOARD_TEMPLATE, user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('splash_page'))

@app.route('/stripe/authorize')
@login_required
def stripe_authorize():
    return redirect("https://connect.stripe.com/oauth/authorize?response_type=code&client_id=" + STRIPE_CLIENT_ID + "&scope=read_write")

@app.route('/stripe/disconnect', methods=['POST'])
@login_required
def disconnect_stripe():
    user = get_current_user()
    with get_db() as conn:
        conn.execute("UPDATE users SET stripe_account_id = NULL, stripe_access_token = NULL WHERE id = ?", (user['id'],))
        conn.commit()
    return redirect(url_for('dashboard'))

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == '__main__':
    print("🚀 RetainSaaS Pro Engine Running on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
