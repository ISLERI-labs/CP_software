import streamlit as st

# Configure the dashboard
st.set_page_config(
    page_title="ISLERI CEREPHYTE DASHBOARD",
    page_icon="../images\logo.jpg",
    layout="wide"
)

# Dashboard title
st.title("ISLERI CEREPHYTE DASHBOARD")

st.caption("Bioelectric Data Acquisition System")

# Welcome section
st.header("Dashboard")

st.write(
    "Welcome to CEREPHYTE. "
    "Your plant health data monitoring workspace."
)

# Display the current application status
st.info("Application initialized successfully.")
