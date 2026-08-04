import streamlit as st
import sys
from pathlib import Path

# Put the repo root on sys.path so `from frontend.views import ...` resolves
# regardless of the directory streamlit was launched from.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Backward compatibility for Streamlit < 1.29.0 where st.query_params does not exist
if not hasattr(st, "query_params"):
    class QueryParamsDict:
        def __contains__(self, key):
            return key in st.experimental_get_query_params()
        
        def __getitem__(self, key):
            params = st.experimental_get_query_params()
            vals = params.get(key, [])
            return vals[0] if vals else ""
        
        def get(self, key, default=None):
            params = st.experimental_get_query_params()
            vals = params.get(key, [])
            return vals[0] if vals else default
            
        def clear(self):
            st.experimental_set_query_params()
            
    st.query_params = QueryParamsDict()

# Configure page
st.set_page_config(
    page_title="ATS Resume Scorer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auth state. Populated by Supabase sign-in / sign-up / OAuth.
# All four are None when signed out, all four are set when signed in.
for key, default in [
    ("access_token", None),
    ("refresh_token", None),
    ("user_id", None),       # Supabase auth user id (uuid); also used by api_client
    ("user_email", None),
    ("auth_error", None),
    ("auth_info", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Auto-refresh session token globally if expired or near expiry (less than 60s left)
if st.session_state.access_token and st.session_state.refresh_token:
    try:
        import jwt
        import time
        payload = jwt.decode(st.session_state.access_token, options={"verify_signature": False})
        if payload.get("exp", 0) < time.time() + 60:
            from frontend_services import supabase_client
            res = supabase_client.refresh_session(st.session_state.refresh_token)
            if res and isinstance(res, dict) and "access_token" in res:
                st.session_state.access_token = res["access_token"]
                st.session_state.refresh_token = res.get("refresh_token", st.session_state.refresh_token)
                st.session_state.user_id = res.get("user_id")
                st.session_state.user_email = res.get("email")
            else:
                # Clear session state if refresh fails
                st.session_state.access_token = None
                st.session_state.refresh_token = None
                st.session_state.user_id = None
                st.session_state.user_email = None
    except Exception as exc:
        import logging
        logger = logging.getLogger('ats_resume_scorer')
        logger.error(f"Global auto-refresh error: {exc}")

# Flag to defer st.rerun() until after all widgets are rendered.
# Calling st.rerun() while Streamlit is still enqueuing widgets can cause
# the script to re-execute mid-render, hit st.rerun() again, and recurse
# until the stack overflows (RecursionError).
_needs_rerun = False

# Initialize code exchange flag in session state if not present
if "code_exchanged" not in st.session_state:
    st.session_state.code_exchanged = False

# Reset code_exchanged flag if the URL query parameter 'code' is gone
if "code" not in st.query_params:
    st.session_state.code_exchanged = False

# If we just came back from Google OAuth, Supabase appends `?code=<authcode>`
# to the redirect URL. Exchange it for a session before rendering anything.
if (
    not st.session_state.access_token
    and "code" in st.query_params
    and not st.session_state.code_exchanged
):
    st.session_state.code_exchanged = True
    from frontend_services import supabase_client
    result = supabase_client.exchange_code_for_session(st.query_params["code"])

    #Always clear the ?code= param so a refresh doesn't try to re-exchange.
    st.query_params.clear()
    if "error" in result:
        st.session_state.auth_error = f"Google sign-in failed: {result['error']}"
    else:
        st.session_state.access_token  = result["access_token"]
        st.session_state.refresh_token = result["refresh_token"]
        st.session_state.user_id       = result["user_id"]
        st.session_state.user_email    = result["email"]
        _needs_rerun = True

#Load custom CSS
def load_css():
    try:
        css_path = Path(__file__).parent / 'assets' / 'style.css'
        with open(css_path, 'r') as f:
            return f'<style>{f.read()}</style>'
    except FileNotFoundError:
        return ''

st.markdown(load_css(), unsafe_allow_html=True)

# Initialize session state for view management
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'landing'

# Sidebar navigation
with st.sidebar:
    st.markdown("## Navigation")
    
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.current_view = 'landing'
        _needs_rerun = True
    
    if st.button("🎯 ATS Scorer", use_container_width=True):
        st.session_state.current_view = 'scorer'
        _needs_rerun = True
    
    if st.button("📊 History", use_container_width=True):
        st.session_state.current_view = 'history'
        _needs_rerun = True
    
    if st.button("📚 Resources", use_container_width=True):
        st.session_state.current_view = 'resources'
        _needs_rerun = True
    
    st.markdown("---")
    st.markdown("### 👤 Account")

    from frontend_services import supabase_client

    if st.session_state.access_token:
        # Signed-in state: show email + sign-out button.
        st.caption(f"Signed in as **{st.session_state.user_email}**")
        if st.button("Sign out", use_container_width=True):
            supabase_client.sign_out()
            for k in ("access_token", "refresh_token", "user_id", "user_email", "cached_oauth"):
                st.session_state[k] = None
            _needs_rerun = True
    else:
        # Signed-out state: tabs for sign-in vs sign-up + Google OAuth button.
        # Show flash messages (auth_error / auth_info) exactly once, then clear.
        _show_auth_error = st.session_state.auth_error
        _show_auth_info = st.session_state.auth_info
        if _show_auth_error:
            st.error(_show_auth_error)
            st.session_state.auth_error = None
        if _show_auth_info:
            st.info(_show_auth_info)
            st.session_state.auth_info = None

        tab_in, tab_up = st.tabs(["Sign in", "Sign up"])

        with tab_in:
            with st.form("signin_form", clear_on_submit=False):
                email = st.text_input("Email", key="signin_email")
                password = st.text_input("Password", type="password", key="signin_pw")
                submitted = st.form_submit_button("Sign in", use_container_width=True)
            if submitted:
                result = supabase_client.sign_in_with_password(email, password)
                if "error" in result:
                    st.session_state.auth_error = result["error"]
                else:
                    st.session_state.access_token  = result["access_token"]
                    st.session_state.refresh_token = result["refresh_token"]
                    st.session_state.user_id       = result["user_id"]
                    st.session_state.user_email    = result["email"]
                _needs_rerun = True

        with tab_up:
            with st.form("signup_form", clear_on_submit=False):
                email_up = st.text_input("Email", key="signup_email")
                password_up = st.text_input("Password (min 6 chars)", type="password", key="signup_pw")
                submitted_up = st.form_submit_button("Create account", use_container_width=True)
            if submitted_up:
                result = supabase_client.sign_up_with_password(email_up, password_up)
                if "error" in result:
                    st.session_state.auth_error = result["error"]
                elif result.get("pending_confirmation"):
                    st.session_state.auth_info = (
                        f"Check your inbox — confirmation email sent to {result['email']}."
                    )
                else:
                    st.session_state.access_token  = result["access_token"]
                    st.session_state.refresh_token = result["refresh_token"]
                    st.session_state.user_id       = result["user_id"]
                    st.session_state.user_email    = result["email"]
                _needs_rerun = True

        st.markdown("<div style='text-align:center; margin: 8px 0; color:#94a3b8;'>or</div>",
                    unsafe_allow_html=True)

        # Cache OAuth URL in session state to avoid hitting Supabase rate limits.
        # Only fetch once per session; it stays valid for the session duration (retry if cached error).
        oauth = st.session_state.get("cached_oauth")
        if not oauth or (isinstance(oauth, dict) and "error" in oauth):
            oauth = supabase_client.google_oauth_url() or {}
            st.session_state.cached_oauth = oauth

        if isinstance(oauth, dict) and "error" in oauth:
            st.caption(f"Google sign-in unavailable: {oauth['error']}")
        elif isinstance(oauth, dict) and "url" in oauth:
            st.link_button(
                "Continue with Google",
                url=oauth["url"],
                use_container_width=True,
            )
        else:
            st.caption("Google sign-in unavailable.")

# Main content area - render based on current view
if st.session_state.current_view == 'landing':
    # Import and render landing page
    from frontend.views import landing
    landing.render()

elif st.session_state.current_view == 'scorer':
    # Import and render scorer page
    from frontend.views import scorer
    scorer.render()

elif st.session_state.current_view == 'history':
    # Import and render history page
    from frontend.views import history
    history.render()

elif st.session_state.current_view == 'resources':
    # Import and render resources page
    from frontend.views import resources
    resources.render()

# --- Deferred rerun --------------------------------------------------------
# All widgets have been rendered. It is now safe to call st.rerun() without
# risk of recursion from mid-render re-execution.
if _needs_rerun:
    st.rerun()