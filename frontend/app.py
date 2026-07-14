import streamlit as st
import requests

st.set_page_config(
    page_title="Restaurant SOP Portal",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide Streamlit chrome elements for a professional standalone app look
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding: 0px !important;
        margin: 0px !important;
        max-width: 100% !important;
    }
    iframe {
        border: none;
        width: 100%;
        height: 100vh;
        overflow: hidden;
    }
    body {
        margin: 0;
        padding: 0;
        background-color: #080b11;
    }
</style>
""", unsafe_allow_html=True)

# URL of our FastAPI backend serving the premium dashboard UI
BACKEND_API_URL = "http://127.0.0.1:8000"
BACKEND_UI_URL = "http://127.0.0.1:8000/static/index.html"

try:
    # Verify that the FastAPI backend is running
    res = requests.get(BACKEND_API_URL, timeout=2)
    if res.status_code == 200:
        # Load the backend-served dashboard within the Streamlit frame
        st.components.v1.iframe(src=BACKEND_UI_URL, height=950, scrolling=True)
    else:
        st.error(f"Backend is running but returned status code {res.status_code}")
except Exception as e:
    st.markdown(f"""
    <div style="background-color: #0b0f19; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 3rem 2rem; margin: 3rem auto; max-width: 700px; font-family: sans-serif; text-align: center; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);">
        <div style="font-size: 3rem; margin-bottom: 1.5rem; animation: pulse 2s infinite alternate;">🍽️</div>
        <h2 style="color: #818cf8; font-family: 'Outfit', sans-serif; font-size: 1.8rem; font-weight: 700; margin-bottom: 1rem;">Restaurant SOP Compliance Portal</h2>
        <p style="color: #94a3b8; font-size: 1.1rem; line-height: 1.6; margin-bottom: 2rem;">
            The portal has been upgraded to a premium glassmorphic dashboard with rich animations!
        </p>
        
        <div style="background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 10px; padding: 1.5rem 2rem; display: inline-block; text-align: left; margin: 0 auto 2.5rem auto;">
            <strong style="color: #f1f5f9; display: block; margin-bottom: 0.8rem; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em;">How to start the compliance engine:</strong>
            <div style="font-family: monospace; font-size: 0.9rem; background: #000; padding: 0.75rem 1.2rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); color: #a78bfa; margin-bottom: 8px;">
                cd backend
            </div>
            <div style="font-family: monospace; font-size: 0.9rem; background: #000; padding: 0.75rem 1.2rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); color: #a78bfa;">
                uvicorn main:app --reload
            </div>
        </div>
        
        <p style="color: #64748b; font-size: 0.9rem;">
            Once the FastAPI backend is running, refresh this page or access the interface directly at:<br>
            <a href="{BACKEND_UI_URL}" target="_blank" style="color: #818cf8; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 10px; border-bottom: 2px solid rgba(129, 140, 248, 0.3); padding-bottom: 2px;">{BACKEND_UI_URL}</a>
        </p>
    </div>
    """, unsafe_allow_html=True)