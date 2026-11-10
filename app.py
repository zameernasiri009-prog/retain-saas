import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "revivepay-super-secret-key-2026")
app.permanent_session_lifetime = 86400 * 7

DB_PATH = "revivepay.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# Initialize database on app startup
init_db()

@app.route('/')
def landing():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RevivePay - Automated B2B Dunning & Revenue Recovery</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-white min-h-screen flex flex-col justify-between p-6">
        <header class="max-w-5xl mx-auto w-full flex justify-between items-center py-4">
            <div class="flex items-center space-x-2">
                <div class="w-9 h-9 bg-indigo-600 rounded-2xl flex items-center justify-center font-black text-lg shadow-lg shadow-indigo-600/30">R</div>
                <span class="font-black text-xl tracking-tight">RevivePay</span>
            </div>
            <div class="space-x-4">
                <a href="/login" class="text-sm font-bold text-gray-400 hover:text-white transition">Sign In</a>
                <a href="/register" class="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-xl font-bold text-sm shadow-lg shadow-indigo-600/30 transition">Get Started</a>
            </div>
        </header>
        <main class="max-w-4xl mx-auto text-center space-y-6 my-auto py-12">
            <span class="bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-4 py-1.5 rounded-full text-xs font-black uppercase tracking-widest">Enterprise Revenue Recovery</span>
            <h1 class="text-5xl md:text-6xl font-black tracking-tight leading-tight">Stop Chasing Failed Payments. <span class="text-indigo-500">Recover SaaS Revenue Automatically.</span></h1>
            <p class="text-gray-400 text-base md:text-lg max-w-xl mx-auto font-medium">RevivePay automates Stripe dunning, secure card updates, and customer outreach so you never lose a subscriber to expired cards again.</p>
            <div class="pt-4 flex justify-center space-x-4">
                <a href="/register" class="bg-indigo-600 hover:bg-indigo-500 text-white px-8 py-4 rounded-2xl font-bold shadow-xl shadow-indigo-600/30 transition transform active:scale-95 text-base">Launch Recovery Engine</a>
            </div>
        </main>
        <footer class="text-center text-xs text-gray-400 py-4">&copy; 2026 RevivePay. All rights reserved.</footer>
    </body>
    </html>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password. Please check your credentials or register."
            
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sign In - RevivePay</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-white min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-gray-900 border border-gray-800 p-8 rounded-3xl shadow-2xl space-y-6">
            <div class="text-center space-y-2">
                <a href="/" class="inline-block w-10 h-10 bg-indigo-600 rounded-2xl leading-10 font-black text-xl mb-2 shadow-lg shadow-indigo-600/30">R</a>
                <h1 class="text-2xl font-black tracking-tight">Welcome Back</h1>
                <p class="text-xs text-gray-400">Sign in to manage your dunning recovery workflows.</p>
            </div>
            {% if error %}
            <div class="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-2xl text-xs font-bold text-center">{{ error }}</div>
            {% endif %}
            <form action="/login" method="POST" autocomplete="off" class="space-y-4">
                <div>
                    <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Email Address</label>
                    <input type="email" name="email" required placeholder="name@domain.com" class="w-full p-3.5 bg-gray-950 border border-gray-800 rounded-2xl text-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm font-medium">
                </div>
                <div>
                    <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Password</label>
                    <input type="password" name="password" required placeholder="••••••••" class="w-full p-3.5 bg-gray-950 border border-gray-800 rounded-2xl text-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm font-medium">
                </div>
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3.5 rounded-2xl font-bold shadow-lg shadow-indigo-600/30 transition transform active:scale-95 text-sm">Sign In</button>
            </form>
            <p class="text-center text-xs text-gray-400">Don't have an account? <a href="/register" class="text-indigo-400 font-bold hover:underline">Register here</a></p>
        </div>
    </body>
    </html>
    """, error=error)

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not email or not password:
            error = "Email and password are required."
        else:
            pwd_hash = generate_password_hash(password)
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, pwd_hash))
                    conn.commit()
                    user_id = cursor.lastrowid
                
                session.clear()
                session['user_id'] = user_id
                session.permanent = True
                return redirect(url_for('dashboard'))
            except sqlite3.IntegrityError:
                error = "This email is already registered. Please sign in instead."

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Register - RevivePay</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-white min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-gray-900 border border-gray-800 p-8 rounded-3xl shadow-2xl space-y-6">
            <div class="text-center space-y-2">
                <a href="/" class="inline-block w-10 h-10 bg-indigo-600 rounded-2xl leading-10 font-black text-xl mb-2 shadow-lg shadow-indigo-600/30">R</a>
                <h1 class="text-2xl font-black tracking-tight">Create Account</h1>
                <p class="text-xs text-gray-400">Protect your SaaS revenue with enterprise security.</p>
            </div>
            {% if error %}
            <div class="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-2xl text-xs font-bold text-center">{{ error }}</div>
            {% endif %}
            <form action="/register" method="POST" autocomplete="off" class="space-y-4">
                <div>
                    <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Email Address</label>
                    <input type="email" name="email" required placeholder="name@domain.com" class="w-full p-3.5 bg-gray-950 border border-gray-800 rounded-2xl text-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm font-medium">
                </div>
                <div>
                    <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Password</label>
                    <input type="password" name="password" required placeholder="••••••••" class="w-full p-3.5 bg-gray-950 border border-gray-800 rounded-2xl text-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm font-medium">
                </div>
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3.5 rounded-2xl font-bold shadow-lg shadow-indigo-600/30 transition transform active:scale-95 text-sm">Create Secure Account</button>
            </form>
            <p class="text-center text-xs text-gray-400">Already have an account? <a href="/login" class="text-indigo-400 font-bold hover:underline">Sign in</a></p>
        </div>
    </body>
    </html>
    """, error=error)

@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login_page'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        session.clear()
        return redirect(url_for('login_page'))
        
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard - RevivePay</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-white min-h-screen flex flex-col">
        <nav class="border-b border-gray-800 bg-gray-900/50 backdrop-blur px-6 py-4 flex justify-between items-center">
            <div class="flex items-center space-x-3">
                <div class="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center font-black text-sm shadow-md shadow-indigo-600/30">R</div>
                <span class="font-black text-lg tracking-tight">RevivePay</span>
            </div>
            <div class="flex items-center space-x-4">
                <span class="text-xs text-gray-400 font-semibold hidden md:inline">{{ user['email'] }}</span>
                <a href="/logout" class="bg-gray-800 hover:bg-gray-700 text-gray-300 px-3.5 py-2 rounded-xl text-xs font-bold transition">Sign Out</a>
            </div>
        </nav>
        <main class="max-w-6xl mx-auto w-full p-6 space-y-8 my-auto">
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 class="text-3xl font-black tracking-tight">Revenue Recovery Command</h1>
                    <p class="text-xs text-gray-400 mt-1">Live metrics and dunning performance for your Stripe integration.</p>
                </div>
                <div class="bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 px-4 py-2 rounded-2xl text-xs font-bold">System Status: Active ⚡</div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-gray-900 border border-gray-800 p-6 rounded-3xl space-y-2">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Total Recovered</p>
                    <p class="text-3xl font-black text-emerald-400">$12,450</p>
                    <p class="text-[11px] text-gray-400">+18% from last month</p>
                </div>
                <div class="bg-gray-900 border border-gray-800 p-6 rounded-3xl space-y-2">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Failed Charges Caught</p>
                    <p class="text-3xl font-black">42</p>
                    <p class="text-[11px] text-gray-400">Automatic dunning emails sent</p>
                </div>
                <div class="bg-gray-900 border border-gray-800 p-6 rounded-3xl space-y-2">
                    <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Recovery Success Rate</p>
                    <p class="text-3xl font-black text-indigo-400">94.2%</p>
                    <p class="text-[11px] text-gray-400">Industry leading benchmark</p>
                </div>
            </div>
        </main>
    </body>
    </html>
    """, user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
