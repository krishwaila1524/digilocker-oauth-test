# DigiLocker / MeriPehchaan OAuth test app

Throwaway app to test your API Setu credentials. Not part of VerifyX.

## Files in this folder
- `test_digilocker.py` — the app itself
- `requirements.txt` — dependencies for Render to install

## Before deploying
Open `test_digilocker.py` and fill in these three lines near the top:

```python
CLIENT_ID     = "YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"
REDIRECT_URI  = "https://xxxx.ngrok-free.app/digilocker/callback"
```

- `CLIENT_ID` / `CLIENT_SECRET` — from your Authpartner details on API Setu
- `REDIRECT_URI` — set this to `https://<your-render-app-name>.onrender.com/digilocker/callback`
  (you'll know the exact Render URL only after step 3 below, so come back and fill this in then)

## Deploy on Render
1. Push this folder to a new GitHub repo
2. On render.com: New + → Web Service → connect the repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn test_digilocker:app --host 0.0.0.0 --port $PORT`
5. Instance Type: Free
6. Deploy — note the URL Render gives you, e.g. `https://digilocker-oauth-test.onrender.com`
7. Go back into `test_digilocker.py`, set `REDIRECT_URI` to that URL + `/digilocker/callback`, commit + push (Render auto-redeploys)

## Register on API Setu
On the "Add Authpartner" screen:
- Website URL / App Domain: `https://<your-render-app-name>.onrender.com`
- Call Back URL: `https://<your-render-app-name>.onrender.com/digilocker/callback`
- Scope: check `Openid` at minimum

## Test it
Visit `https://<your-render-app-name>.onrender.com/login` in your browser.
Check the Render dashboard's Logs tab for the `📥 CALLBACK RECEIVED` and `🔑 TOKEN RESPONSE` output.
