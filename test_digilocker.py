"""
Standalone throwaway test app for DigiLocker / MeriPehchaan OAuth2 (PKCE flow).
NOT part of VerifyX - purely for testing your API Setu credentials.

Now saves every completed login to a Postgres (Supabase) database so you can
see results from multiple people who test the /login link, not just whoever
is looking at their own browser screen.

Run with:  uvicorn test_digilocker:app --port 9000
Then visit http://localhost:9000/login in your browser.
"""

import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

# ── Fill these in with your real values ────────────────────────────────────
CLIENT_ID     = "ZN3F721F14"
CLIENT_SECRET = "4a55f36f5cacfe1f3de0"
REDIRECT_URI  = "https://digilocker-oauth-test.onrender.com/digilocker/callback"

# Paste your fresh Supabase project's connection string here (Project Settings -> Database)
# Fill in YOUR-PASSWORD below before pushing - don't paste your real password into chat/AI tools.
DATABASE_URL  = "postgresql://postgres.sartmvpbhgdqsphgzdmi:Nangia%4012358@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres"

AUTHORIZE_URL = "https://digilocker.meripehchaan.gov.in/public/oauth2/1/authorize"
TOKEN_URL     = "https://digilocker.meripehchaan.gov.in/public/oauth2/2/token"

# ── Database setup ───────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class DigilockerResult(Base):
    __tablename__ = "digilocker_results"

    id            = Column(Integer, primary_key=True, index=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    access_token  = Column(Text)
    id_token      = Column(Text)
    scope         = Column(Text)
    expires_in    = Column(Integer)
    id_token_claims = Column(Text)   # decoded JWT payload, stored as JSON string
    raw_response  = Column(Text)     # full raw token response, stored as JSON string


Base.metadata.create_all(bind=engine)

app = FastAPI()

_pending = {}


def _generate_pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _decode_id_token_claims(id_token: str) -> dict:
    """
    Decode (NOT verify) the JWT payload just to peek at identity claims.
    Never treat this as a security check - it's for display purposes only.
    """
    try:
        payload_b64 = id_token.split(".")[1]
        padding = "=" * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64 + padding)
        return json.loads(decoded)
    except Exception as e:
        return {"decode_error": str(e)}


@app.get("/login")
def login():
    verifier, challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(16)
    _pending[state] = verifier

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": "openid",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"{AUTHORIZE_URL}?{query}")


@app.get("/digilocker/callback")
async def callback(request: Request):
    params = dict(request.query_params)
    print("\n📥 CALLBACK RECEIVED:", params)

    code = params.get("code")
    state = params.get("state")

    if not code or not state or state not in _pending:
        return JSONResponse({"error": "missing/invalid code or state", "raw": params}, status_code=400)

    verifier = _pending.pop(state)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    print("\n🔑 TOKEN RESPONSE STATUS:", resp.status_code)
    print("🔑 TOKEN RESPONSE BODY:", resp.text)

    if resp.status_code != 200:
        return JSONResponse({"status_code": resp.status_code, "body": resp.text}, status_code=resp.status_code)

    body = resp.json()
    claims = _decode_id_token_claims(body.get("id_token", "")) if body.get("id_token") else {}

    # ── Save to database ────────────────────────────────────────────────
    db = SessionLocal()
    try:
        row = DigilockerResult(
            access_token=body.get("access_token"),
            id_token=body.get("id_token"),
            scope=body.get("scope"),
            expires_in=body.get("expires_in"),
            id_token_claims=json.dumps(claims),
            raw_response=json.dumps(body),
        )
        db.add(row)
        db.commit()
        print(f"💾 Saved result to database, row id={row.id}")
    except Exception as e:
        print(f"⚠️  Failed to save to database: {e}")
        db.rollback()
    finally:
        db.close()

    return JSONResponse({
        "status_code": resp.status_code,
        "body": body,
        "decoded_claims": claims,
        "saved": True,
    })


@app.get("/results", response_class=HTMLResponse)
def results():
    db = SessionLocal()
    try:
        rows = db.query(DigilockerResult).order_by(DigilockerResult.created_at.desc()).all()
    finally:
        db.close()

    html = ["<h1>DigiLocker test results</h1>"]
    if not rows:
        html.append("<p>No submissions yet.</p>")
    for r in rows:
        claims = json.loads(r.id_token_claims or "{}")
        html.append(f"""
        <div style="border:1px solid #ccc; padding:12px; margin-bottom:12px; font-family:monospace;">
            <strong>#{r.id}</strong> — {r.created_at}<br>
            Scope: {r.scope}<br>
            Claims: <pre>{json.dumps(claims, indent=2)}</pre>
        </div>
        """)
    return "".join(html)


@app.get("/")
def home():
    return {"message": "Go to /login to start the DigiLocker OAuth test flow, or /results to view saved submissions"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9000))
    uvicorn.run(app, host="0.0.0.0", port=port)