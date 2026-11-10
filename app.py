import os
import time
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

import stripe
from fastapi import (
    FastAPI, Request, Depends, HTTPException, status, Form, Header, BackgroundTasks
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from jose import jwt, JWTError

# ------------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ------------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-retain-saas-production-key-908234")
ALGORITHM = "HS256"
MAGIC_LINK_EXPIRE_MINUTES = 15
SESSION_EXPIRE_HOURS = 24
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./retain_saas.db")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_mock_key")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_mock_key")

stripe.api_key = STRIPE_SECRET_KEY

# ------------------------------------------------------------------------------
# DATABASE SETUP
# ------------------------------------------------------------------------------
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    subscription_plan = Column(String, default="Scale Enterprise (Active)")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class MagicToken(Base):
    __tablename__ = "magic_tokens"
    token = Column(String, primary_key=True)
    email = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

class PaymentRecovery(Base):
    __tablename__ = "payment_recoveries"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    customer_email = Column(String, nullable=False)
    amount_due = Column(Float, nullable=False)
    status = Column(String, default="ACTION REQUIRED")  # ACTION REQUIRED, RECOVERED, FAILED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------------------------------------------------------------------
# SECURITY & AUTHENTICATION HELPERS
# ------------------------------------------------------------------------------
def create_session_jwt(email: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRE_HOURS)
    payload = {"sub": email, "exp": expires}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = request.cookies.get("session_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return db.query(User).filter(User.email == email).first()
    except JWTError:
        return None

# Simple double-submission in-memory tracking
PROCESSED_REQUEST_IDS = set()

# ------------------------------------------------------------------------------
# FASTAPI APPLICATION CREATION
# ------------------------------------------------------------------------------
app = FastAPI(title="Retain SaaS Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# FRONTEND TEMPLATES & HTML DASHBOARD
# ------------------------------------------------------------------------------
LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RetainSaaS Engine - Instant Magic Link</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0b0f19] text-white flex items-center justify-center min-h-screen p-4 font-sans">
    <div id="login-card" class="bg-[#111827] border border-gray-800 rounded-2xl p-8 max-w-md w-full text-center shadow-2xl">
        <span class="bg-indigo-900/60 text-indigo-400 text-xs px-3 py-1 rounded-full font-semibold inline-block mb-4">RetainSaaS Engine</span>
        <h1 class="text-2xl font-bold mb-2">Instant Magic Link</h1>
        <p class="text-gray-400 text-sm mb-6">Enter your email. No passwords required—log in instantly with a secure tap.</p>
        
        <form id="magic-form" onsubmit="handleMagicSubmit(event)">
            <div class="text-left mb-4">
                <label class="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Email Address</label>
                <input type="email" id="email" required placeholder="founder@mysaas.com" 
                    class="w-full bg-[#1f2937] border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition">
            </div>
            <button type="submit" id="submit-btn" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 rounded-lg transition duration-200">
                Send Secure Login Link
            </button>
        </form>
    </div>

    <div id="success-card" class="hidden bg-[#111827] border border-gray-800 rounded-2xl p-8 max-w-md w-full text-center shadow-2xl">
        <h2 class="text-xl font-bold text-emerald-400 mb-2">Magic Link Generated!</h2>
        <p class="text-gray-400 text-xs mb-6">Since you are testing on mobile, tap the direct secure login link below to enter your dashboard instantly without typing a password:</p>
        <a id="instant-link" href="#" class="inline-block w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg transition">
            Tap Here to Log In Instantly &rarr;
        </a>
    </div>

    <script>
        async function handleMagicSubmit(e) {
            e.preventDefault();
            const btn = document.getElementById('submit-btn');
            btn.disabled = true;
            btn.innerText = "Generating Link...";

            const email = document.getElementById('email').value;
            const res = await fetch('/api/auth/magic-link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ email })
            });

            const data = await res.json();
            if (res.ok) {
                document.getElementById('login-card').classList.add('hidden');
                document.getElementById('success-card').classList.remove('hidden');
                document.getElementById('instant-link').href = data.magic_url;
            } else {
                alert(data.detail || "Authentication error");
                btn.disabled = false;
                btn.innerText = "Send Secure Login Link";
            }
        }
    </script>
</body>
</html>
"""

DASHBOARD_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RetainSaaS Engine - Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0b0f19] text-white min-h-screen p-6 font-sans">
    <header class="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
        <div class="flex items-center gap-3">
            <div class="bg-indigo-600 text-white font-bold px-3 py-1 rounded text-sm">RetainSaaS</div>
            <span class="text-xs text-gray-400 border border-gray-700 px-2 py-0.5 rounded">{{ user.subscription_plan }}</span>
        </div>
        <div class="flex items-center gap-4 text-xs text-gray-400">
            <span>{{ user.email }}</span>
            <a href="/auth/logout" class="hover:text-white transition">Logout</a>
        </div>
    </header>

    <main class="max-w-6xl mx-auto">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="bg-[#111827] p-6 rounded-xl border border-gray-800">
                <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">AT-RISK MRR</p>
                <p class="text-3xl font-extrabold text-white">${{ "%.2f"|format(at_risk_mrr) }}</p>
            </div>
            <div class="bg-[#111827] p-6 rounded-xl border border-gray-800">
                <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">RECOVERED REVENUE</p>
                <p class="text-3xl font-extrabold text-emerald-400">${{ "%.2f"|format(recovered_mrr) }}</p>
            </div>
            <div class="bg-[#111827] p-6 rounded-xl border border-gray-800">
                <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">RECOVERY RATE</p>
                <p class="text-3xl font-extrabold text-indigo-400">{{ "%.1f"|format(recovery_rate) }}%</p>
            </div>
        </div>

        <div class="bg-[#111827] rounded-xl border border-gray-800 p-6">
            <div class="flex justify-between items-center mb-6">
                <h2 class="font-bold text-lg">Active Failed Payment Recoveries</h2>
                <form action="/api/simulate-test-case" method="POST">
                    <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-xs font-bold px-4 py-2 rounded transition">
                        + Simulate Test Case
                    </button>
                </form>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm text-gray-300">
                    <thead class="text-xs text-gray-500 uppercase border-b border-gray-800">
                        <tr>
                            <th class="py-3 px-4">Customer</th>
                            <th class="py-3 px-4">Amount Due</th>
                            <th class="py-3 px-4">Status</th>
                            <th class="py-3 px-4 text-right">Action Link</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if recoveries %}
                            {% for item in recoveries %}
                            <tr class="border-b border-gray-800/50">
                                <td class="py-3 px-4">{{ item.customer_email }}</td>
                                <td class="py-3 px-4">${{ "%.2f"|format(item.amount_due) }}</td>
                                <td class="py-3 px-4">
                                    {% if item.status == 'RECOVERED' %}
                                        <span class="bg-emerald-900/40 text-emerald-400 text-xs px-2 py-1 rounded">RECOVERED</span>
                                    {% else %}
                                        <span class="bg-amber-900/40 text-amber-400 text-xs px-2 py-1 rounded">ACTION REQUIRED</span>
                                    {% endif %}
                                </td>
                                <td class="py-3 px-4 text-right">
                                    {% if item.status != 'RECOVERED' %}
                                    <form action="/api/recover/{{ item.id }}" method="POST" class="inline">
                                        <button type="submit" class="text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-3 py-1 rounded transition">
                                            Mark Recovered
                                        </button>
                                    </form>
                                    {% else %}
                                        <span class="text-xs text-gray-600">Complete</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="4" class="py-8 text-center text-gray-500">
                                    No active failed payments found. Click "+ Simulate Test Case" above to test!
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </main>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# ROUTE HANDLERS: FRONTEND & AUTHENTICATION
# ------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return HTMLResponse(content=LOGIN_PAGE_HTML)

@app.post("/api/auth/magic-link")
def request_magic_link(
    email: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    # Double-submit guard check
    client_ip = request.client.host if request else "unknown"
    req_key = f"{client_ip}_{email}_{int(time.time() / 5)}"
    if req_key in PROCESSED_REQUEST_IDS:
        raise HTTPException(status_code=429, detail="Too many rapid requests. Please wait a second.")
    PROCESSED_REQUEST_IDS.add(req_key)

    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES)
    
    magic_record = MagicToken(token=token, email=email, expires_at=expires)
    db.add(magic_record)
    db.commit()

    magic_url = f"/auth/verify?token={token}"
    return JSONResponse(content={"status": "success", "magic_url": magic_url})

@app.get("/auth/verify")
def verify_magic_link(token: str, db: Session = Depends(get_db)):
    record = db.query(MagicToken).filter(MagicToken.token == token).first()
    
    if not record or record.used or record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Magic link is invalid or expired.")

    record.used = True
    
    user = db.query(User).filter(User.email == record.email).first()
    if not user:
        user = User(email=record.email)
        db.add(user)
    
    db.commit()

    jwt_token = create_session_jwt(user.email)
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=jwt_token, httponly=True, max_age=86400, samesite="lax")
    return response

@app.get("/auth/logout")
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def render_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    recoveries = db.query(PaymentRecovery).filter(PaymentRecovery.user_id == user.id).all()
    
    at_risk = sum(r.amount_due for r in recoveries if r.status == "ACTION REQUIRED")
    recovered = sum(r.amount_due for r in recoveries if r.status == "RECOVERED")
    total = sum(r.amount_due for r in recoveries)
    rate = (recovered / total * 100) if total > 0 else 0.0

    from jinja2 import Template
    template = Template(DASHBOARD_PAGE_HTML)
    rendered = template.render(
        user=user,
        recoveries=recoveries,
        at_risk_mrr=at_risk,
        recovered_mrr=recovered,
        recovery_rate=rate
    )
    return HTMLResponse(content=rendered)

# ------------------------------------------------------------------------------
# ROUTE HANDLERS: SIMULATION & RECOVERY API
# ------------------------------------------------------------------------------
@app.post("/api/simulate-test-case")
def simulate_failed_payment(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    test_case = PaymentRecovery(
        user_id=user.id,
        customer_email=f"client_{secrets.token_hex(3)}@example.com",
        amount_due=49.00,
        status="ACTION REQUIRED"
    )
    db.add(test_case)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/api/recover/{recovery_id}")
def mark_recovered(recovery_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    rec = db.query(PaymentRecovery).filter(
        PaymentRecovery.id == recovery_id, 
        PaymentRecovery.user_id == user.id
    ).first()
    
    if rec:
        rec.status = "RECOVERED"
        db.commit()

    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

# ------------------------------------------------------------------------------
# PRODUCTION STRIPE WEBHOOK HANDLER
# ------------------------------------------------------------------------------
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    if event["type"] == "invoice.payment_failed":
        session_obj = event["data"]["object"]
        customer_email = session_obj.get("customer_email")
        amount_due = session_obj.get("amount_due", 0) / 100.0

        # Assign to demo user for integration testing
        admin_user = db.query(User).first()
        if admin_user and customer_email:
            recovery_entry = PaymentRecovery(
                user_id=admin_user.id,
                customer_email=customer_email,
                amount_due=amount_due,
                status="ACTION REQUIRED"
            )
            db.add(recovery_entry)
            db.commit()

    return JSONResponse(content={"status": "success"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
