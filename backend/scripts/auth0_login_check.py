"""Live login check against a real Auth0 tenant (no secrets, no passwords).

Runs the same browser login the frontend will use (authorization code + PKCE), then calls this
API with the resulting access token and reports what it accepted. The token is never printed.

    uv run python -m scripts.auth0_login_check --client-id <ECHO Web client id>

Requirements: the ECHO Web app allows http://localhost:5173 as a callback URL (so stop any
frontend dev server on that port first), and the API is running with AUTH_MODE=auth0.
"""

import argparse
import base64
import hashlib
import http.server
import secrets
import threading
import urllib.parse
import webbrowser

import httpx
import jwt

from app.config import settings

REDIRECT = "http://localhost:5173"


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def wait_for_code(state: str, timeout: float = 600) -> str:
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Login received. You can close this tab and return to the terminal.")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("localhost", 5173), Handler)
    server.timeout = timeout
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    thread.join(timeout + 5)
    server.server_close()
    if result.get("state") != state or "code" not in result:
        raise SystemExit(f"Login did not complete: {result.get('error_description') or result}")
    return result["code"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--api-url", default="http://localhost:8000")
    args = parser.parse_args()
    domain, audience = settings.auth0_domain, settings.auth0_audience
    if not domain or not audience:
        raise SystemExit("Set AUTH0_DOMAIN and AUTH0_AUDIENCE in backend/.env first")

    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    url = f"https://{domain}/authorize?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": args.client_id,
            "redirect_uri": REDIRECT,
            "scope": "openid profile email",
            "audience": audience,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    print("Open this URL and sign in as one of your test users:\n\n" + url + "\n", flush=True)
    webbrowser.open(url)
    code = wait_for_code(state)

    token_response = httpx.post(
        f"https://{domain}/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": args.client_id,
            "code_verifier": verifier,
            "code": code,
            "redirect_uri": REDIRECT,
        },
    )
    if token_response.status_code != 200:
        raise SystemExit(f"Token exchange failed: {token_response.text}")
    token = token_response.json()["access_token"]

    claims = jwt.decode(token, options={"verify_signature": False})
    ns = settings.auth_claim_namespace.rstrip("/")
    print("Token claims the API will read:")
    print("  audience   :", claims.get("aud"))
    print("  physician  :", claims.get(f"{ns}/physician_id"))
    print("  roles      :", claims.get(f"{ns}/roles"))

    headers = {"Authorization": f"Bearer {token}"}
    referrals = httpx.get(f"{args.api_url}/referrals", headers=headers)
    print(f"\nGET /referrals -> {referrals.status_code}")
    if referrals.status_code == 200:
        print("  referrals visible to this login:", [r["id"] for r in referrals.json()])
    else:
        print("  ", referrals.text)
    foreign = httpx.get(f"{args.api_url}/referrals/ref_demo_knee", headers=headers)
    print(f"GET /referrals/ref_demo_knee (doc_001's) -> {foreign.status_code}")


if __name__ == "__main__":
    main()
