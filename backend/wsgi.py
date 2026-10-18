# Flask app for PythonAnywhere (or Vercel/Render)
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from main import app

# Create a WSGI application for deployment
application = WSGIMiddleware(app)
