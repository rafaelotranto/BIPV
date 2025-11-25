import streamlit as st

def icon_text(icon_path: str, text: str, size: int = 30):
    st.markdown(
        f"""
        <div style="display: flex; align-items: center;">
            <img src="{icon_path}" width="{size}" style="margin-right:10px">
            <span style="font-size:16px;">{text}</span>
        </div>
        """,
        unsafe_allow_html=True
    )