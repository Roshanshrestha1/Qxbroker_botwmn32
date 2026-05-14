"""
Manual SSID Extractor - Opens browser so you can copy the SSID manually.
"""

import asyncio
from api_quotex.login import get_ssid


async def main():
    print("=" * 60)
    print("Manual SSID Extraction")
    print("=" * 60)
    print("\nThis will open a browser. After logging in:")
    print("1. Press F12 to open Developer Tools")
    print("2. Go to Console tab")
    print("3. Type: localStorage.getItem('token')")
    print("4. Copy the token value shown")
    print("\nPress Enter when done...")
    input()

    # Try with keep_browser option
    success, result = await get_ssid(
        email="bcdoy9@gmail.com", password="roshan@123@@", keep_browser_on_error=True
    )

    print(f"\nSuccess: {success}")
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
