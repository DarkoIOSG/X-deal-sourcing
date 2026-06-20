import os
import sys
from datetime import datetime, timedelta
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests as http
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeSerializer, BadSignature
from pydantic import BaseModel

from config import (
    TEAM_MEMBERS, TEAM_EMAILS,
    SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, APP_URL,
)
from shared.notion import (
    query_voting_projects,
    get_project,
    sync_votes,
    flag_reviewed,
)

app = FastAPI(title="IOSG Deal Radar")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")), name="static")

_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
_REVIEW_DAYS = 14
_COOKIE = "voter_session"
_signer = URLSafeSerializer(SECRET_KEY, salt="voter-session")


# ── Session helpers ────────────────────────────────────────────────────────

def _get_voter(request: Request) -> str | None:
    raw = request.cookies.get(_COOKIE)
    if not raw:
        return None
    try:
        return _signer.loads(raw)
    except BadSignature:
        return None


def _set_voter_cookie(response: RedirectResponse, voter_name: str):
    response.set_cookie(
        _COOKIE,
        _signer.dumps(voter_name),
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=APP_URL.startswith("https"),
    )


# ── Auth routes ────────────────────────────────────────────────────────────

@app.get("/auth/login")
def auth_login():
    params = urlencode({
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  f"{APP_URL}/auth/callback",
        "response_type": "code",
        "scope":         "email",
        "access_type":   "online",
        "hd":            "iosg.vc",  # hint: restrict to iosg.vc accounts in the picker
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@app.get("/auth/callback")
def auth_callback(code: str = None, error: str = None):
    if error or not code:
        return RedirectResponse("/?auth_error=cancelled")

    # Exchange code for access token
    token_r = http.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  f"{APP_URL}/auth/callback",
            "grant_type":    "authorization_code",
        },
        timeout=15,
    )
    if not token_r.ok:
        return RedirectResponse("/?auth_error=token_exchange_failed")
    access_token = token_r.json().get("access_token")

    # Fetch email from Google
    user_r = http.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not user_r.ok:
        return RedirectResponse("/?auth_error=userinfo_failed")
    email = user_r.json().get("email", "").lower()

    voter_name = TEAM_EMAILS.get(email)
    if not voter_name:
        return RedirectResponse(f"/?auth_error=not_in_team&email={email}")

    redirect = RedirectResponse(url="/", status_code=302)
    _set_voter_cookie(redirect, voter_name)
    return redirect


@app.get("/auth/logout")
def auth_logout():
    redirect = RedirectResponse(url="/", status_code=302)
    redirect.delete_cookie(_COOKIE)
    return redirect


# ── App routes ─────────────────────────────────────────────────────────────

@app.get("/")
def index():
    with open(_HTML_PATH) as f:
        return HTMLResponse(f.read())


@app.get("/api/config")
def get_config():
    return {"team_members": TEAM_MEMBERS}


@app.get("/api/me")
def get_me(request: Request):
    return {"voter": _get_voter(request)}


@app.get("/api/projects")
def get_projects(request: Request):
    projects = query_voting_projects()
    for p in projects:
        if not p.get("vote_reviewed") and _should_auto_review(p):
            p["vote_reviewed"] = True
            try:
                flag_reviewed(p["notion_id"])
            except Exception:
                pass
    return projects


class VoteRequest(BaseModel):
    notion_id: str
    vote: str  # "up" or "down"


@app.post("/api/vote")
def submit_vote(req: VoteRequest, request: Request):
    voter_name = _get_voter(request)
    if not voter_name:
        raise HTTPException(status_code=401, detail="not authenticated")
    if req.vote not in ("up", "down"):
        raise HTTPException(status_code=400, detail="vote must be 'up' or 'down'")

    project = get_project(req.notion_id)
    voters = dict(project.get("voters") or {})
    voters[voter_name] = req.vote

    up   = sum(1 for v in voters.values() if v == "up")
    down = sum(1 for v in voters.values() if v == "down")

    sync_votes(req.notion_id, up, down, voters)

    reviewed = len(voters) >= len(TEAM_MEMBERS)
    if reviewed and not project.get("vote_reviewed"):
        flag_reviewed(req.notion_id)

    return {"vote_up": up, "vote_down": down, "voters": voters, "reviewed": reviewed}


def _should_auto_review(project: dict) -> bool:
    if len(project.get("voters", {})) >= len(TEAM_MEMBERS):
        return True
    processed_at = project.get("processed_at")
    if processed_at:
        try:
            age = datetime.utcnow() - datetime.strptime(processed_at[:10], "%Y-%m-%d")
            if age > timedelta(days=_REVIEW_DAYS):
                return True
        except ValueError:
            pass
    return False
