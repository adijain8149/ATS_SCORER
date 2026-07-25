import httpx
import logging
import jwt
import urllib.parse
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import SUPABASE_JWT_SECRET, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_KEY

logger = logging.getLogger('ats_resume_scorer')

_bearer_scheme = HTTPBearer(auto_error=False)

_ASYMMETRIC_ALGS = ['ES256', 'RS256']

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient | None:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    if not SUPABASE_URL:
        return None
    parsed = urllib.parse.urlparse(SUPABASE_URL)
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else SUPABASE_URL.rstrip('/')
    jwks_url = f"{base_url}/auth/v1/.well-known/jwks.json"
    headers = {}
    anon_key = SUPABASE_ANON_KEY or SUPABASE_KEY
    if anon_key:
        headers['apikey'] = anon_key
    _jwks_client = jwt.PyJWKClient(jwks_url, headers=headers, cache_keys=True, lifespan=3600)
    return _jwks_client


def _verify_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    alg = header.get('alg')

    if alg in _ASYMMETRIC_ALGS:
        jwks_client = _get_jwks_client()
        if jwks_client is None:
            raise jwt.InvalidTokenError(
                'SUPABASE_URL not configured — cannot fetch JWKS to verify token'
            )
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token).key
        except Exception:
            global _jwks_client
            _jwks_client = None
            jwks_client = _get_jwks_client()
            if jwks_client is None:
                raise
            signing_key = jwks_client.get_signing_key_from_jwt(token).key

        return jwt.decode(
            token,
            signing_key,
            algorithms=_ASYMMETRIC_ALGS,
            audience='authenticated',
        )

    if alg == 'HS256':
        if not SUPABASE_JWT_SECRET:
            raise jwt.InvalidTokenError(
                'HS256 token received but SUPABASE_JWT_SECRET is not configured'
            )
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=['HS256'],
            audience='authenticated',
        )

    raise jwt.InvalidTokenError(f'Unsupported JWT algorithm: {alg}')


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing Authorization: Bearer <token> header',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    token = creds.credentials

    # 1. Try local JWT verification first
    try:
        payload = _verify_token(token)
        user_id = payload.get('sub')
        if user_id:
            return user_id
    except Exception as exc:
        logger.debug(f'Local JWT verification failed: {exc}, checking with Supabase Auth API...')

    # 2. Fallback: Verify directly via Supabase Auth API
    if SUPABASE_URL:
        try:
            url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/user"
            anon_key = SUPABASE_ANON_KEY or SUPABASE_KEY
            headers = {"Authorization": f"Bearer {token}"}
            if anon_key:
                headers["apikey"] = anon_key

            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    user_data = resp.json()
                    user_id = user_data.get("id")
                    if user_id:
                        return user_id
                elif resp.status_code in (401, 403):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail='Invalid or expired session token — please sign out and sign in again.',
                        headers={'WWW-Authenticate': 'Bearer'},
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f'Supabase Auth API verification error: {exc}')

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Token verification failed — please sign out and sign in again.',
        headers={'WWW-Authenticate': 'Bearer'},
    )