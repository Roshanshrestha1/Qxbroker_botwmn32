"""
Debug script to test QxBroker connection with detailed error handling.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def debug_connection():
    print("=" * 50)
    print("QxBroker Debug Connection Test")
    print("=" * 50)

    email = os.getenv("QX_EMAIL")
    password = os.getenv("QX_PASSWORD")

    print(f"\nEmail: {email}")
    print(f"Password length: {len(password) if password else 0}")
    print(f"Password chars: {list(password) if password else []}")

    # Try importing pyquotex
    try:
        from pyquotex.stable_api import Quotex

        print("\n✓ pyquotex imported successfully")
    except Exception as e:
        print(f"\n✗ Failed to import pyquotex: {e}")
        return

    # Create client
    client = Quotex(email=email, password=password, lang="en")

    print("\nAttempting connection...")
    check_connect, message = await client.connect()

    print(f"\nResult: check_connect={check_connect}")
    print(f"Message: {message}")

    if check_connect:
        print("\n✓ Connected successfully!")
        balance = await client.get_balance()
        print(f"Balance: ${balance}")
        await client.close()
    else:
        print("\n✗ Connection failed")
        print("\nPossible causes:")
        print("1. Wrong email/password")
        print("2. Account is blocked")
        print("3. Network issues")
        print("4. QxBroker server issues")


if __name__ == "__main__":
    asyncio.run(debug_connection())
