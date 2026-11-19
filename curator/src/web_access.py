"""Fail-closed, loopback-only access policy for the entire browser application."""
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from datetime import timedelta
import ipaddress
import os
import secrets
import time

from flask import g, jsonify, redirect, request, session
from werkzeug.exceptions import RequestEntityTooLarge

SESSION_SECONDS = 60 * 60
_SESSION_SECRET = secrets.token_bytes(32)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_UNLOCK_HTML = """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Unlock curator</title>
<h1>Unlock curator</h1><p>Paste the operator access token for this local server.</p>
<form id="unlockForm" method="post" action="/unlock" autocomplete="off">
<label>Access token <input type="password" name="token" required maxlength="1024"
 autocomplete="off" autocapitalize="off" spellcheck="false"></label>
<button type="submit">Unlock</button></form>
<p id="unlockStatus" role="status" aria-live="polite"></p>
<noscript>JavaScript is required for the protected same-origin unlock request.</noscript>
<script src="/static/js/unlock.js" defer></script></html>"""


@dataclass(frozen=True)
class AccessSettings:
    host: str
    port: int
    token: bytes = field(repr=False)

    @property
    def bind_host(self):
        # Never ask DNS to decide whether a configured hostname is local.
        return "127.0.0.1" if self.host == "localhost" else self.host

    @property
    def authority(self):
        host = f"[{self.host}]" if ":" in self.host else self.host
        return host if self.port == 80 else f"{host}:{self.port}"

    @property
    def origin(self):
        return f"http://{self.authority}"


def load_access_settings(host=None, port=None, debug=False):
    """Validate before importing services or performing any startup effects."""
    token = os.environ.get("CURATOR_ACCESS_TOKEN", "")
    if (not 32 <= len(token) <= 1024 or not token.isascii()
            or any(ord(char) <= 32 or ord(char) == 127 for char in token)):
        raise RuntimeError("CURATOR_ACCESS_TOKEN must contain 32–1024 non-space ASCII characters")
    host = os.environ.get("WEB_HOST", "127.0.0.1") if host is None else host
    if host != "localhost":
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError("WEB_HOST must be a literal loopback address or localhost") from None
        if not address.is_loopback or "%" in host:
            raise ValueError("WEB_HOST must be loopback")
    if port is None:
        try:
            port = int(os.environ.get("WEB_PORT", "4000"))
        except ValueError:
            raise ValueError("WEB_PORT must be an integer from 1 to 65535") from None
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("WEB_PORT must be an integer from 1 to 65535")
    if debug or any(os.environ.get(key, "false").lower() not in {"false", "0", ""}
                    for key in ("WEB_DEBUG", "FLASK_DEBUG")):
        raise ValueError("Web debug mode is disabled")
    if os.environ.get("FLASK_RUN_FROM_CLI") == "true":
        # Flask CLI can override both the listener and debugger outside app.run.
        raise RuntimeError("Use curator's protected run_server entrypoint, not flask run")
    return AccessSettings(host, port, token.encode("ascii"))


def _equal_secret(value, expected):
    return (isinstance(value, str) and len(value) <= 1024
            and secrets.compare_digest(value.encode("utf-8"), expected))


def bounded_request_body(limit):
    """Bound boundary payloads on Flask 3.0 too (no per-request size setter)."""
    if request.content_length is not None and request.content_length > limit:
        raise RequestEntityTooLarge()
    # The application's 1 MiB ceiling also bounds chunked/unknown-length reads.
    data = request.get_data()
    if len(data) > limit:
        raise RequestEntityTooLarge()
    return data


def install_web_access(app, settings):
    sessions = OrderedDict()
    sessions_lock = Lock()

    def prune_sessions():
        now = time.time()
        for sid, expires in list(sessions.items()):
            if expires <= now:
                del sessions[sid]

    app.extensions["web_access"] = settings
    app.config.update(
        SECRET_KEY=_SESSION_SECRET,
        SESSION_COOKIE_NAME="curator_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=False,  # HTTP bound to loopback, never a remote listener.
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=SESSION_SECONDS),
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=1024 * 1024,
        DEBUG=False,
    )

    @app.before_request
    def guard_web_access():
        policy = app.extensions["web_access"]
        g.web_authenticated = False
        try:
            local_peer = ipaddress.ip_address(request.remote_addr or "").is_loopback
        except ValueError:
            local_peer = False
        # Deliberately inspect the actual peer and Host, never Forwarded/X-Forwarded-*.
        if (not local_peer or request.environ.get("HTTP_HOST") != policy.authority
                or request.scheme != "http"):
            return jsonify(error="Local origin required"), 403
        origin = request.headers.get("Origin")
        if origin is not None and origin != policy.origin:
            return jsonify(error="Local origin required"), 403
        if request.headers.get("Sec-Fetch-Site") not in {None, "none", "same-origin"}:
            return jsonify(error="Same-origin request required"), 403

        if request.endpoint == "unlock":
            if request.query_string:
                return jsonify(error="Query parameters are not accepted"), 400
            if request.method not in _SAFE_METHODS and origin != policy.origin:
                return jsonify(error="Local origin required"), 403
            return None
        if request.endpoint == "static":
            return None

        expires = session.get("expires_at")
        with sessions_lock:
            prune_sessions()
            registered = sessions.get(session.get("sid")) == expires and expires is not None
        if (not registered or not isinstance(session.get("sid"), str)
                or not isinstance(session.get("csrf"), str)
                or type(expires) not in (float, int) or expires <= time.time()):
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify(error="Authentication required"), 401
            return redirect("/unlock", code=303)
        if request.method not in _SAFE_METHODS:
            if origin != policy.origin or not _equal_secret(
                request.headers.get("X-CSRF-Token"), session["csrf"].encode("utf-8")
            ):
                return jsonify(error="Origin and session CSRF token required", code="csrf_required"), 403
        g.web_authenticated = True

    @app.after_request
    def protect_web_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; base-uri 'self'"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.endpoint == "unlock":
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; connect-src 'self'; "
                "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
            )
        return response

    @app.route("/unlock", methods=["GET", "POST"])
    def unlock():
        if request.method == "GET":
            return _UNLOCK_HTML
        # Only a manual form POST; never echo, store, or log the operator token.
        bounded_request_body(4096)
        if (request.mimetype != "application/x-www-form-urlencoded"
                or set(request.form) != {"token"} or len(request.form.getlist("token")) != 1):
            return jsonify(error="Access token form required"), 400
        if not _equal_secret(request.form["token"], app.extensions["web_access"].token):
            return jsonify(error="Invalid access token"), 401
        with sessions_lock:
            prune_sessions()
            sessions.pop(session.get("sid"), None)
            session.clear()
            session.permanent = True
            session.update(sid=secrets.token_urlsafe(32), csrf=secrets.token_urlsafe(32),
                           expires_at=time.time() + SESSION_SECONDS)
            while len(sessions) >= 256:
                sessions.popitem(last=False)
            sessions[session["sid"]] = session["expires_at"]
        return redirect("/", code=303)

    @app.get("/api/session")
    def session_info():
        return jsonify(csrf_token=session["csrf"])
