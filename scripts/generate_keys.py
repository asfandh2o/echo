#!/usr/bin/env python3

import secrets
from cryptography.fernet import Fernet

print("🔑 ECHO Security Keys Generator")
print("=" * 50)
print()

secret_key = secrets.token_hex(32)
print(f"SECRET_KEY={secret_key}")
print()

encryption_key = Fernet.generate_key().decode()
print(f"ENCRYPTION_KEY={encryption_key}")
print()

print("Copy these to your .env file")
