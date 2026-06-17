import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import TEAM_MEMBERS
from shared.notion import (
    query_voting_projects,
    get_project,
    sync_votes,
    flag_reviewed,
)

app = FastAPI(title="IOSG Deal Radar")

_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
_REVIEW_DAYS = 14


class VoteRequest(BaseModel):
    notion_id: str
    voter_name: str
    vote: str  # "up" or "down"


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


@app.get("/")
def index():
    with open(_HTML_PATH) as f:
        return HTMLResponse(f.read())


@app.get("/api/config")
def get_config():
    return {"team_members": TEAM_MEMBERS}


@app.get("/api/projects")
def get_projects():
    projects = query_voting_projects()
    for p in projects:
        # Auto-flag reviewed projects that aren't flagged yet.
        # Skipped on Vercel cold starts to keep latency low — the vote
        # endpoint handles the "all voters voted" case synchronously.
        if not p.get("vote_reviewed") and _should_auto_review(p):
            p["vote_reviewed"] = True
            # fire-and-forget; acceptable to miss occasionally on serverless
            try:
                flag_reviewed(p["notion_id"])
            except Exception:
                pass
    return projects


@app.post("/api/vote")
def submit_vote(req: VoteRequest):
    if req.vote not in ("up", "down"):
        raise HTTPException(status_code=400, detail="vote must be 'up' or 'down'")
    if not req.voter_name or req.voter_name not in TEAM_MEMBERS:
        raise HTTPException(status_code=400, detail="unknown voter")

    # Read current state from Notion, update, write back — all synchronous
    project = get_project(req.notion_id)
    voters = dict(project.get("voters") or {})
    voters[req.voter_name] = req.vote

    up   = sum(1 for v in voters.values() if v == "up")
    down = sum(1 for v in voters.values() if v == "down")

    sync_votes(req.notion_id, up, down, voters)

    reviewed = len(voters) >= len(TEAM_MEMBERS)
    if reviewed and not project.get("vote_reviewed"):
        flag_reviewed(req.notion_id)

    return {"vote_up": up, "vote_down": down, "voters": voters, "reviewed": reviewed}
