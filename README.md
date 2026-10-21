# scheduler

Small Flask app that triggers configured URLs (simple GET) at chosen UTC hours.
An external hourly cron calls `/tick`; the app does the rest.

## Setup

1. `pip install -r requirements.txt`
2. `cp appsettings.example.py appsettings.py` and fill in `SECRET_KEY` and `ADMIN_EMAIL`.
3. In Google Cloud Console create an OAuth client (Web application), add redirect URI
   `https://<your-domain>/oauth2callback` (and `http://localhost:8000/oauth2callback` for local),
   download the JSON as `client_secret.json`.

Local run: `python index.py --local` → http://localhost:8000

On Loopia the app runs as CGI via `cgi_serve.py`. Point the cron at `https://<your-domain>/tick` every hour.

## How `/tick` works

- Each URL has its own time zone (default UTC); the current hour in that zone is used (minutes ignored).
- If a URL has the current hour configured and its last triggered timestamp is not from
  this hour today, the timestamp is updated and the URL is requested with GET.
