import requests
import streamlit as st

from frontend_services import api_client
from frontend.components.dashboard import display_results_dashboard


def _show_backend_error(exc: Exception) -> None:
    if isinstance(exc, requests.ConnectionError):
        st.error("Could not reach the backend. Is it running on port 8000?")
    elif isinstance(exc, requests.HTTPError) and exc.response is not None:
        st.error(f"Backend returned {exc.response.status_code}: {exc.response.text}")
    else:
        st.error(f"Unexpected error: {exc}")


def render() -> None:
    st.title("📊 Analysis History")
    st.markdown("Past analyses saved against your account.")

    access_token = st.session_state.get("access_token")
    if not access_token:
        st.warning("⚠️ Sign in from the sidebar to view your history.")
        return

    try:
        history = api_client.get_history(access_token)
    except requests.RequestException as exc:
        if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code == 401:
            refresh_token = st.session_state.get("refresh_token")
            refreshed = False
            if refresh_token:
                from frontend_services import supabase_client
                res = supabase_client.refresh_session(refresh_token)
                if res and isinstance(res, dict) and "access_token" in res:
                    st.session_state.access_token = res["access_token"]
                    st.session_state.refresh_token = res.get("refresh_token", refresh_token)
                    st.session_state.user_id = res.get("user_id")
                    st.session_state.user_email = res.get("email")
                    try:
                        history = api_client.get_history(res["access_token"])
                        refreshed = True
                    except Exception:
                        refreshed = False

            if not refreshed:
                st.session_state.access_token = None
                st.session_state.refresh_token = None
                st.session_state.user_id = None
                st.session_state.user_email = None
                st.warning("⚠️ Your login session has expired. Please sign in again from the sidebar.")
                return
        else:
            _show_backend_error(exc)
            return

    if not history:
        st.info("No analyses yet for this account. Run a scoring on the ATS Scorer page first.")
        if st.button("🎯 Go to ATS Scorer"):
            st.session_state.current_view = "scorer"
            st.rerun()
        return

    st.markdown(f"**Total analyses:** {len(history)}")
    st.markdown("---")

    for idx, entry in enumerate(history):
        filename = entry.get("filename", "resume")
        ats_score = float(entry.get("ats_score", 0))
        created_at = entry.get("created_at", "")
        analysis = entry.get("analysis_result", {}) or {}

        with st.expander(f"📄 {filename} — Score: {ats_score:.0f}/100 — {created_at}"):
            # Render the identical dashboard as when it was generated
            display_results_dashboard(analysis)

            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                pdf_key = f"pdf_bytes_{entry.get('id', idx)}"
                if pdf_key not in st.session_state:
                    if st.button("📑 Generate PDF Report", key=f"gen_pdf_{idx}", use_container_width=True, type="primary"):
                        with st.spinner("Generating PDF..."):
                            try:
                                pdf_bytes = api_client.generate_pdf(analysis, access_token)
                                st.session_state[pdf_key] = pdf_bytes
                                st.rerun()
                            except Exception as exc:
                                _show_backend_error(exc)
                else:
                    st.download_button(
                        "⬇️ Download PDF Report",
                        data=st.session_state[pdf_key],
                        file_name=f"ats_report_{filename}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"download_pdf_{idx}",
                    )
            with c2:
                if st.button("🗑️ Delete Analysis", key=f"delete_{idx}", use_container_width=True, type="secondary"):
                    try:
                        entry_id = entry.get("id")
                        if entry_id:
                            api_client.delete_history_entry(str(entry_id), access_token)
                            st.success("Deleted successfully.")
                            st.rerun()
                    except requests.RequestException as exc:
                        _show_backend_error(exc)