"""
Standalone throwaway test app for DigiLocker / MeriPehchaan OAuth2 (PKCE flow).
NOT part of VerifyX - purely for testing your API Setu credentials.

Run with:  uvicorn test_digilocker:app --port 9000
Then visit http://localhost:9000/login in your browser.
"""

import base64
import hashlib
import os
import secrets

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse

app = FastAPI()

# ── Fill these in with your real values ────────────────────────────────────
CLIENT_ID     = "ZN3F721F14"
CLIENT_SECRET = "4a55f36f5cacfe1f3de0"
REDIRECT_URI  = "https://digilocker-oauth-test.onrender.com/digilocker/callback"  # must match exactly what you registered

AUTHORIZE_URL = "https://digilocker.meripehchaan.gov.in/public/oauth2/1/authorize"
TOKEN_URL     = "https://digilocker.meripehchaan.gov.in/public/oauth2/2/token"

# In-memory store for PKCE verifier + state, keyed by state.
# Fine for a single-user local test; never do this in real production code.
_pending = {}


def _generate_pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


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

    return JSONResponse({
        "status_code": resp.status_code,
        "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
    })


@app.get("/")
def home():
    return {"message": "Go to /login to start the DigiLocker OAuth test flow"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9000))
    uvicorn.run(app, host="0.0.0.0", port=port)
