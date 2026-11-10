import os
from flask import Flask, render_template_string, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'enterprise-secure-master-key-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///enterprise_portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- DATABASE MODEL ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- HTML TEMPLATES ---
BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-950">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Enterprise Portal{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>body { font-family: 'Plus Jakarta Sans', sans-serif; }</style>
</head>
<body class="h-full text-slate-100 flex flex-col justify-between selection:bg-indigo-500 selection:text-white">
    <!-- Header Navbar -->
    <header class="border-b border-slate-800/80 bg-slate-900/80 backdrop-blur-xl sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <a href="{{ url_for('index') }}" class="flex items-center gap-3 group">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-violet-600 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/30 group-hover:scale-105 transition-transform duration-300">
                    <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
                </div>
                <span class="text-xl font-extrabold tracking-tight text-white">VORTEX<span class="text-indigo-400">SECURE</span></span>
            </a>
            <div class="flex items-center gap-4">
                {% if current_user.is_authenticated %}
                    <a href="{{ url_for('dashboard') }}" class="text-sm font-medium text-slate-300 hover:text-white transition-colors">Dashboard</a>
                    <a href="{{ url_for('logout') }}" class="px-4 py-2 rounded-xl text-sm font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 transition-all border border-slate-700/60 shadow-sm">Sign Out</a>
                {% else %}
                    <a href="{{ url_for('login') }}" class="text-sm font-medium text-slate-300 hover:text-white transition-colors">Sign In</a>
                    <a href="{{ url_for('register') }}" class="px-5 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30 transition-all">Get Started</a>
                {% endif %}
            </div>
        </div>
    </header>

    <!-- Flash Messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="max-w-xl mx-auto w-full px-6 mt-6">
                {% for category, message in messages %}
                    <div class="p-4 rounded-xl border {% if category == 'error' %}bg-rose-500/10 border-rose-500/30 text-rose-300{% else %}bg-emerald-500/10 border-emerald-500/30 text-emerald-300{% endif %} text-sm font-medium shadow-lg flex items-center justify-between">
                        <span>{{ message }}</span>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    <!-- Main Content -->
    <main class="flex-grow flex flex-col justify-center">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-900 bg-slate-950 py-8 px-6 text-center text-xs text-slate-500">
        <p>&copy; 2026 VortexSecure Enterprise Systems. Multi-device ready & fortified with advanced security protocols.</p>
    </footer>
</body>
</html>
"""

INDEX_TEMPLATE = """
{% extends "base" %}
{% block title %}VortexSecure - Next-Gen Enterprise Portal{% endblock %}
{% block content %}
<div class="relative overflow-hidden py-24 px-6 lg:px-8">
    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-600/15 rounded-full blur-3xl pointer-events-none"></div>
    <div class="max-w-4xl mx-auto text-center relative z-10">
        <div class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-8">
            <span class="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span> Enterprise Security Grade 5.0
        </div>
        <h1 class="text-5xl sm:text-7xl font-extrabold tracking-tight text-white mb-8 leading-tight">
            The Ultimate <span class="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">Enterprise Gateway</span>
        </h1>
        <p class="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto mb-12 font-light">
            Engineered for high-scale organizations with permanent SQLite database storage, bulletproof credential protection, and multi-device fluid readiness.
        </p>
        <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a href="{{ url_for('register') }}" class="w-full sm:w-auto px-8 py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-bold shadow-xl shadow-indigo-600/25 transition-all text-center">
                Create Secure Account
            </a>
            <a href="{{ url_for('login') }}" class="w-full sm:w-auto px-8 py-4 rounded-2xl bg-slate-900 hover:bg-slate-800 text-slate-200 font-semibold border border-slate-800 transition-all text-center">
                Access Portal Login
            </a>
        </div>
    </div>
</div>
{% endblock %}
"""

LOGIN_TEMPLATE = """
{% extends "base" %}
{% block title %}Sign In - VortexSecure{% endblock %}
{% block content %}
<div class="max-w-md mx-auto w-full px-6 py-12">
    <div class="bg-slate-900/80 border border-slate-800/80 p-8 rounded-3xl shadow-2xl backdrop-blur-xl relative overflow-hidden">
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
        <h2 class="text-2xl font-extrabold text-white mb-2">Welcome Back</h2>
        <p class="text-sm text-slate-400 mb-8">Authenticate using your Gmail and master password.</p>
        
        <form method="POST" class="space-y-5">
            <div>
                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Gmail Address</label>
                <input type="email" name="email" required placeholder="name@gmail.com" class="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-all text-sm">
            </div>
            <div>
                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Password</label>
                <input type="password" name="password" required placeholder="••••••••••••" class="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-all text-sm">
            </div>
            <button type="submit" class="w-full py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold shadow-lg shadow-indigo-600/30 transition-all text-sm">
                Authenticate & Enter
            </button>
        </form>
        <p class="text-center text-xs text-slate-500 mt-6">
            New operator? <a href="{{ url_for('register') }}" class="text-indigo-400 font-semibold hover:underline">Register account</a>
        </p>
    </div>
</div>
{% endblock %}
"""

REGISTER_TEMPLATE = """
{% extends "base" %}
{% block title %}Register - VortexSecure{% endblock %}
{% block content %}
<div class="max-w-md mx-auto w-full px-6 py-12">
    <div class="bg-slate-900/80 border border-slate-800/80 p-8 rounded-3xl shadow-2xl backdrop-blur-xl relative overflow-hidden">
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
        <h2 class="text-2xl font-extrabold text-white mb-2">Create Account</h2>
        <p class="text-sm text-slate-400 mb-8">Set up permanent enterprise database access.</p>
        
        <form method="POST" class="space-y-5">
            <div>
                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Gmail Address</label>
                <input type="email" name="email" required placeholder="name@gmail.com" class="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-all text-sm">
            </div>
            <div>
                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Secure Password</label>
                <input type="password" name="password" required placeholder="••••••••••••" class="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-all text-sm">
            </div>
            <button type="submit" class="w-full py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold shadow-lg shadow-indigo-600/30 transition-all text-sm">
                Register & Initialize
            </button>
        </form>
        <p class="text-center text-xs text-slate-500 mt-6">
            Already authorized? <a href="{{ url_for('login') }}" class="text-indigo-400 font-semibold hover:underline">Sign in here</a>
        </p>
    </div>
</div>
{% endblock %}
"""

DASHBOARD_TEMPLATE = """
{% extends "base" %}
{% block title %}Dashboard - VortexSecure{% endblock %}
{% block content %}
<div class="max-w-5xl mx-auto w-full px-6 py-12">
    <div class="bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 border border-indigo-500/20 p-8 rounded-3xl shadow-2xl mb-8 flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
            <div class="inline-block px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold mb-3">● Session Secured</div>
            <h1 class="text-3xl font-extrabold text-white">Welcome, {{ current_user.email }}</h1>
            <p class="text-sm text-slate-400 mt-1">Your multi-device enterprise environment is fully active and encrypted.</p>
        </div>
        <div class="px-4 py-3 rounded-2xl bg-slate-950 border border-slate-800 text-center">
            <span class="block text-xs text-slate-500 uppercase">Database Status</span>
            <span class="text-sm font-bold text-emerald-400">Online & Persistent</span>
        </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="p-6 rounded-3xl bg-slate-900/60 border border-slate-800/80">
            <h3 class="text-lg font-bold text-white mb-2">Advanced User Files</h3>
            <p class="text-sm text-slate-400 mb-6">Manage your encrypted vaults, document repositories, and export logs.</p>
            <div class="p-4 rounded-2xl bg-slate-950 border border-slate-800/60 text-center text-slate-500 text-sm">
                No active files uploaded in vault yet.
            </div>
        </div>
        <div class="p-6 rounded-3xl bg-slate-900/60 border border-slate-800/80">
            <h3 class="text-lg font-bold text-white mb-2">Security Diagnostics</h3>
            <ul class="space-y-3 text-sm text-slate-300">
                <li class="flex items-center justify-between p-3 rounded-xl bg-slate-950/50 border border-slate-800/50">
                    <span>Password Encryption</span>
                    <span class="text-emerald-400 font-semibold">Werkzeug Hashed</span>
                </li>
                <li class="flex items-center justify-between p-3 rounded-xl bg-slate-950/50 border border-slate-800/50">
                    <span>Multi-Device Ready</span>
                    <span class="text-indigo-400 font-semibold">Tailwind Responsive</span>
                </li>
            </ul>
        </div>
    </div>
</div>
{% endblock %}
"""

# --- ROUTING LOGIC ---
@app.route('/')
def index():
    return render_template_string(INDEX_TEMPLATE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Successfully authenticated!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid Gmail or password combination.', 'error')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'error')
            return redirect(url_for('register'))
            
        new_user = User(email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please sign in.', 'success')
        return redirect(url_for('login'))
    return render_template_string(REGISTER_TEMPLATE)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out securely.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
