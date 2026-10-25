@echo off
start cmd /k streamlit run app.py
start cmd /k uvicorn main:app --host 0.0.0.0 --port 8000
