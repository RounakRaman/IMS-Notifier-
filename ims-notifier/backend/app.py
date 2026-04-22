"""
FastAPI web server.

Endpoints:
  GET  /                  -> dashboard (HTML) to manage keywords
  POST /keywords          -> add keyword (form)
  POST /keywords/delete   -> remove keyword (form)
  POST /api/device        -> register FCM device token (JSON, called by Android app)
  POST /api/check         -> manually trigger a check (auth-protected)
  GET  /api/health        -> health check

Auth:
  Dashboard is protected by a single shared password (ADMIN_PASSWORD env var)
  stored as a signed cookie. No user accounts for simplicity.
"""

import logging
import os
import secrets
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db
from check import main as run_check

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("app")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(16))
COOKIE_NAME = "ims_auth"

app = FastAPI(title="IMS Notifier")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()
    logger.info("Startup complete")


# Auth helpers (dead simple shared-password gate)
def _issue_session(resp: Response) -> None:
    resp.set_cookie(
        COOKIE_NAME,
        SESSION_SECRET,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        secure=False,
    )


def _require_auth(auth_cookie: Optional[str] = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    if not ADMIN_PASSWORD:
        # If no password configured, allow everything (dev mode)
        return
    if auth_cookie != SESSION_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


# Dashboard pages
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, auth_cookie: Optional[str] = Cookie(default=None, alias=COOKIE_NAME)):
    authed = (not ADMIN_PASSWORD) or (auth_cookie == SESSION_SECRET)
    if not authed:
        return templates.TemplateResponse("login.html", {"request": request, "error": None})

    keywords = db.list_keywords()
    recent = db.recent_matches(limit=30)
    device_count = len(db.list_device_tokens())

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "keywords": keywords,
            "recent": recent,
            "device_count": device_count,
        },
    )


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    if ADMIN_PASSWORD and password != ADMIN_PASSWORD:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Wrong password."},
            status_code=401,
        )
    resp = RedirectResponse(url="/", status_code=303)
    _issue_session(resp)
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# Keyword mgmt (HTML form actions)
@app.post("/keywords")
def add_keyword(
    keyword: str = Form(...),
    _auth: None = Depends(_require_auth),
):
    db.add_keyword(keyword)
    return RedirectResponse(url="/", status_code=303)


@app.post("/keywords/delete")
def delete_keyword(
    keyword: str = Form(...),
    _auth: None = Depends(_require_auth),
):
    db.remove_keyword(keyword)
    return RedirectResponse(url="/", status_code=303)


# API
class DeviceRegister(BaseModel):
    fcm_token: str


@app.post("/api/device")
def register_device(payload: DeviceRegister):
    """
    Called by the Android app after it obtains a Firebase registration token.
    This is intentionally unauthenticated (the app has no password).
    """
    ok = db.register_device(payload.fcm_token)
    return {"ok": ok}


@app.post("/api/check")
def api_check(_auth: None = Depends(_require_auth)):
    """Trigger a scrape + notify cycle on demand, for testing."""
    exit_code = run_check()
    return {"exit_code": exit_code}


@app.get("/api/health")
def health():
    try:
        db.list_keywords()
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
