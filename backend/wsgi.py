"""WSGI entrypoint for the ATM Wigs API. Run on Zeabur via: gunicorn wsgi:app -b 0.0.0.0:$PORT

Loads .env for local development; on the platform (Zeabur) env vars are provided directly and
load_dotenv() is a harmless no-op when there is no .env file.
"""
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app()
