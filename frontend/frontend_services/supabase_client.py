import os
import logging
import time
from pathlib import Path
from typing import Any, Dict
import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger('ats_resume_scorer')

# Resolve project paths relative to this file, not CWD
_THIS_DIR = Path(__file__).resolve().parent          # frontend_services/
_FRONTEND_DIR = _THIS_DIR.parent                      # frontend/
_PROJECT_ROOT = _FRONTEND_DIR.parent                  # D:\\ATS Score

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(_PROJECT_ROOT / '.env')
    load_dotenv(_FRONTEND_DIR / '.env')
except ImportError:
    pass


def _secret(key: str, section: str = 'supabase') -> str:
    """Read from env first, then fall back to st.secrets[section][key] or top-level st.secrets[key]."""
    val = os.getenv(key, '')
    if val:
        return val.strip(" '\"\t\r\n")

    try:
        if hasattr(st, "secrets"):
            if section in st.secrets and key in st.secrets[section]:
                return str(st.secrets[section][key]).strip(" '\"\t\r\n")
            if key in st.secrets:
                return str(st.secrets[key]).strip(" '\"\t\r\n")
    except Exception:
        pass

    for secrets_path in [
        _FRONTEND_DIR / ".streamlit" / "secrets.toml",
        _PROJECT_ROOT / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    ]:
        if secrets_path.exists():
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib
                except ImportError:
                    tomllib = None
            if tomllib:
                try:
                    data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
                    if section in data and key in data[section]:
                        return str(data[section][key]).strip(" '\"\t\r\n")
                    if key in data:
                        return str(data[key]).strip(" '\"\t\r\n")
                except Exception:
                    pass

    return ''


def get_supabase_url() -> str:
    return _secret('SUPABASE_URL')


def get_supabase_anon_key() -> str:
    return _secret('SUPABASE_ANON_KEY')


SUPABASE_URL = get_supabase_url()
SUPABASE_ANON_KEY = get_supabase_anon_key()

def get_oauth_redirect_url() -> str:
    url = (
        os.getenv('AUTH_REDIRECT_URL', '').strip(" '\"\t\r\n")
        or _secret('redirect_uri', 'google_oauth')
        or _secret('redirect_url', 'google_oauth')
        or _secret('REDIRECT_URI')
    )
    if url and url != 'http://localhost:8501':
        return url

    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers
            host = headers.get("host") or headers.get("Host") or ""
            if host and "streamlit.app" in host:
                return f"https://{host}"
    except Exception:
        pass

    return url or 'http://localhost:8501'


def _missing_config() -> str | None:
    url = get_supabase_url()
    key = get_supabase_anon_key()
    if not url or not key:
        return 'Supabase is not configured — set SUPABASE_URL and SUPABASE_ANON_KEY in .env or .streamlit/secrets.toml'
    return None


@st.cache_resource
def get_client() -> Client | None:
    """Cached singleton — preserves PKCE state across Streamlit reruns."""
    if _missing_config():
        return None
    return create_client(get_supabase_url(), get_supabase_anon_key())


def _session_dict(session, user) -> Dict[str, Any]:
    return {
        'access_token':  session.access_token,
        'refresh_token': session.refresh_token,
        'user_id':       user.id,
        'email':         user.email,
    }


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect Supabase rate‑limit errors by checking the message."""
    msg = str(exc).lower()
    return 'rate' in msg and 'limit' in msg


def _with_retries(func, *args, **kwargs):
    """Execute a Supabase call with up to 3 retries on rate‑limit errors.
    Uses exponential backoff (1s, 2s, 4s). Returns the function's result
    or re‑raises the last exception.
    """
    max_attempts = 3
    delay = 1
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if _is_rate_limit_error(exc) and attempt < max_attempts:
                logger.warning(f'Rate limit hit, retry {attempt}/{max_attempts} after {delay}s: {exc}')
                time.sleep(delay)
                delay *= 2
            else:
                raise


def sign_in_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        client = get_client()
        if client is None:
            return {'error': 'Supabase client not available'}
        resp = _with_retries(client.auth.sign_in_with_password, {'email': email, 'password': password})
        if not resp.session or not resp.user:
            return {'error': 'Invalid credentials'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'sign_in_with_password failed: {exc}')
        return {'error': _humanize(exc)}


def sign_up_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        client = get_client()
        if client is None:
            return {'error': 'Supabase client not available'}
        resp = _with_retries(client.auth.sign_up, {'email': email, 'password': password})
        if resp.session and resp.user:
            return _session_dict(resp.session, resp.user)
        if resp.user:
            return {'pending_confirmation': True, 'email': email}
        return {'error': 'Sign-up failed'}
    except Exception as exc:
        logger.warning(f'sign_up failed: {exc}')
        return {'error': _humanize(exc)}


def google_oauth_url() -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        client = get_client()
        if client is None:
            return {'error': 'Supabase client not available'}
        resp = _with_retries(client.auth.sign_in_with_oauth, {
            'provider': 'google',
            'options': {'redirect_to': get_oauth_redirect_url()},
        })
        # Backup code_verifier to disk in case of server restart during redirect
        try:
            storage_key = f'{client.auth._storage_key}-code-verifier'
            code_verifier = client.auth._storage.get_item(storage_key)
            if code_verifier:
                verifier_file = _FRONTEND_DIR / ".streamlit" / "code_verifier.txt"
                verifier_file.parent.mkdir(parents=True, exist_ok=True)
                verifier_file.write_text(code_verifier, encoding='utf-8')
        except Exception as backup_err:
            logger.warning(f'Failed to backup code verifier: {backup_err}')
        return {'url': resp.url}
    except Exception as exc:
        logger.warning(f'oauth url generation failed: {exc}')
        return {'error': _humanize(exc)}


def exchange_code_for_session(auth_code: str) -> Dict[str, Any]:
    """Called once after the OAuth provider redirects back with `?code=...`."""
    err = _missing_config()
    if err:
        return {'error': err}
    client = get_client()
    if client is None:
        return {'error': 'Supabase client not available'}
    try:
        storage_key = f'{client.auth._storage_key}-code-verifier'
        code_verifier = client.auth._storage.get_item(storage_key) or ''
        
        # Restore backup verifier if memory was cleared (e.g. server restarted)
        if not code_verifier:
            verifier_file = _FRONTEND_DIR / ".streamlit" / "code_verifier.txt"
            if verifier_file.exists():
                code_verifier = verifier_file.read_text(encoding='utf-8').strip()
                client.auth._storage.set_item(storage_key, code_verifier)
                try:
                    verifier_file.unlink()
                except Exception:
                    pass

        resp = _with_retries(client.auth.exchange_code_for_session, {
            'auth_code': auth_code,
            'code_verifier': code_verifier,
            'redirect_to': get_oauth_redirect_url(),
        })
        if not resp.session or not resp.user:
            return {'error': 'OAuth exchange returned no session'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'exchange_code_for_session failed: {exc}')
        return {'error': _humanize(exc)}


def refresh_session(refresh_token: str) -> Dict[str, Any]:
    """Refresh an expired access token using the refresh token."""
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        client = get_client()
        if client is None:
            return {'error': 'Supabase client not available'}
        resp = _with_retries(client.auth.refresh_session, refresh_token)
        if not resp.session or not resp.user:
            return {'error': 'Failed to refresh session'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'refresh_session failed: {exc}')
        return {'error': _humanize(exc)}


def sign_out() -> None:
    if _missing_config():
        return
    try:
        client = get_client()
        if client is None:
            return
        _with_retries(client.auth.sign_out)
    except Exception as exc:
        logger.warning(f'sign_out failed: {exc}')


def _humanize(exc: Exception) -> str:
    msg = str(exc)
    # supabase errors arrive as "<status>: {json blob}" — surface the human bit
    if 'getaddrinfo failed' in msg.lower() or 'name resolution' in msg.lower() or 'gaierror' in msg.lower():
        return 'Network connection failed — please check your internet connection, VPN, or DNS settings'
    if 'invalid_grant' in msg.lower() or 'invalid login' in msg.lower():
        return 'Wrong email or password'
    if 'user already registered' in msg.lower() or 'already been registered' in msg.lower():
        return 'An account with this email already exists — try signing in'
    if 'password should be at least' in msg.lower():
        return 'Password too short (Supabase default is 6 characters)'
    if 'rate' in msg.lower() and 'limit' in msg.lower():
        return 'Too many requests — please wait a moment and try again'
    if '429' in msg:
        return 'Rate limit reached — please wait a few seconds and try again'
    return msg