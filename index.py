# -*- coding: utf-8 -*-
'''
pip install -r requirements.txt
'''

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from functools import wraps
from zoneinfo import ZoneInfo, available_timezones

import requests
from authlib.integrations.flask_client import OAuth
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

import appsettings
import database

TIMEZONES = sorted(available_timezones())

current_path = os.path.dirname(os.path.realpath(__file__))

logging.basicConfig(filename=os.path.join(current_path, "app.log"), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

application = Flask(__name__)
application.wsgi_app = ProxyFix(application.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
application.config.update(
    SECRET_KEY=appsettings.SECRET_KEY,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
csrf = CSRFProtect(application)
database.setup_db()

# ---------------------- OAuth ----------------------
with open(os.path.join(current_path, appsettings.CLIENT_SECRETS_FILE)) as f:
    client_secrets = json.load(f)["web"]

oauth = OAuth(application)
google = oauth.register(
    name="google",
    client_id=client_secrets["client_id"],
    client_secret=client_secrets["client_secret"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email"},
)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("email") != appsettings.ADMIN_EMAIL.lower():
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@application.route("/login")
def login():
    return render_template("login.html")


@application.route("/authorize")
def authorize():
    return google.authorize_redirect(url_for("oauth2callback", _external=True))


@application.route("/oauth2callback")
def oauth2callback():
    try:
        user_info = google.authorize_access_token()["userinfo"]
    except Exception as e:
        logger.exception(f"OAuth2 callback error {e}")
        flash("Google login failed.")
        return redirect(url_for("login"))

    email = user_info.get("email", "").lower()
    if not user_info.get("email_verified") or email != appsettings.ADMIN_EMAIL.lower():
        logger.warning(f"Unauthorized login attempt: {email}")
        flash("This account is not authorized.")
        return redirect(url_for("login"))

    session.clear()
    session["email"] = email
    return redirect(url_for("index"))


@application.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------- URLs ----------------------
@application.route("/")
@login_required
def index():
    return render_template("index.html", urls=database.get_urls(), timezones=TIMEZONES)


@application.route("/save", methods=["POST"])
@login_required
def save():
    url = request.form.get("url", "").strip()
    hours = sorted({int(h) for h in request.form.getlist("hours") if h.isdigit() and int(h) < 24})
    tz = request.form.get("timezone", "UTC")
    if tz not in TIMEZONES:
        tz = "UTC"
    if not url.startswith(("http://", "https://")):
        flash("URL must start with http:// or https://")
        return redirect(url_for("index"))

    url_id = request.form.get("id")
    if url_id:
        database.update_url(url_id, url, hours, tz)
    else:
        database.add_url(url, hours, tz)
    return redirect(url_for("index"))


@application.route("/delete/<int:url_id>", methods=["POST"])
@login_required
def delete(url_id):
    database.delete_url(url_id)
    return redirect(url_for("index"))


# ---------------------- Tick ----------------------
@application.route("/tick")
def tick():
    now = datetime.now(timezone.utc)
    results = []
    for item in database.get_urls():
        local_now = now.astimezone(ZoneInfo(item["timezone"]))
        if local_now.hour not in item["hours"]:
            continue
        last = item["last_triggered"]
        if last and last.date() == local_now.date() and last.hour == local_now.hour:
            continue  # already triggered this hour

        database.set_last_triggered(item["id"], now)
        try:
            r = requests.get(item["url"], timeout=30)
            results.append(f"{item['url']} ({item['timezone']} {local_now.hour:02d}h) -> {r.status_code}")
        except requests.RequestException as e:
            results.append(f"{item['url']} ({item['timezone']} {local_now.hour:02d}h) -> ERROR {e}")
    for line in results:
        logger.info(f"tick {now.hour:02d}h UTC: {line}")
    return "\n".join(results) or "nothing to trigger", 200, {"Content-Type": "text/plain"}


# ---------------------- Startup ----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Run in local development mode (http)")
    cmdargs = parser.parse_args()
    if cmdargs.local:
        application.config["SESSION_COOKIE_SECURE"] = False
    application.run(debug=True, use_reloader=True, port=8000)
