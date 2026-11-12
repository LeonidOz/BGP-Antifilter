"""Sessions and login rate limiting scoped to one admin application."""

import hmac
import os
import secrets
import time


def cookie_header(name, value, max_age=None):
    parts = [f"{name}={value}", "Path=/", "HttpOnly", "SameSite=Strict"]
    if max_age is not None:
        parts.append(f"Max-Age={max_age}")
    return "; ".join(parts)


def get_cookie(headers, name):
    raw = headers.get("Cookie", "")
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.strip().split("=", 1)
        if key == name:
            return value
    return None


def public_compare(left, right):
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


class AuthService:
    def __init__(self):
        self.sessions = {}
        self.login_attempts = {}

    def new_session(self):
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {"created_at": time.time()}
        return token

    def clean_sessions(self):
        now = time.time()
        expired = [token for token, data in self.sessions.items() if now - data["created_at"] > 24 * 60 * 60]
        for token in expired:
            self.sessions.pop(token, None)

    def is_login_limited(self, client):
        now = time.time()
        attempts = [ts for ts in self.login_attempts.get(client, []) if now - ts < 60]
        self.login_attempts[client] = attempts
        return len(attempts) >= 8

    def record_login_failure(self, client):
        self.login_attempts.setdefault(client, []).append(time.time())

    def authenticated(self, token):
        self.clean_sessions()
        return token in self.sessions

    def login(self, client, password):
        expected = os.environ.get("ADMIN_PASSWORD", "")
        if expected and public_compare(password, expected):
            return self.new_session()
        self.record_login_failure(client)
        return None

    def logout(self, token):
        if token:
            self.sessions.pop(token, None)
