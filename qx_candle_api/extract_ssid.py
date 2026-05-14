"""
Extract SSID manually - keeps browser open for you to copy token.
"""

import asyncio
import json
from api_quotex.login import get_ssid


async def main():
    print("=" * 60)
    print("SSID Manual Extraction")
    print("=" * 60)
    print("\nBrowser will open. After you log in:")
    print("1. Wait for the page to fully load (you should see your account)")
    print("2. Press F12 to open Developer Tools")
    print("3. Go to Application tab (or Console)")
    print("4. In Console, type: localStorage.getItem('token')")
    print("5. Copy the token value (it starts with 'eyJ...' or similar)")
    print("\nThen come back here and paste the token below.")
    print("-" * 60)

    # Use keep_browser_on_error to keep browser open
    success, result = await get_ssid(
        email="bcdoy9@gmail.com", password="roshan@123@@", keep_browser_on_error=True
    )

    print(f"\nSuccess: {success}")
    print(f"Result keys: {result.keys() if isinstance(result, dict) else result}")

    # If still failed, ask user to manually input
    if not success or not result.get("ssid"):
        print("\n" + "=" * 60)
        print("Please manually extract the token:")
        print("1. In the still-open browser, press F12")
        print("2. Go to Console tab")
        print("3. Type: localStorage.getItem('token')")
        print("4. Copy the result and paste it here:")
        print("=" * 60)

        manual_token = input("Paste token here: ").strip()

        if manual_token:
            # Save manually
            session_data = {
                "bcdoy9@gmail.com": {
                    "cookies": None,
                    "token": manual_token,
                    "user_agent": "Quotex/1.0",
                    "is_demo": True,
                    "ssid": f'42["authorization",{{"session":"{manual_token}","isDemo":1}}]',
                }
            }
            with open("session.json", "w") as f:
                json.dump(session_data, f, indent=2)
            print("\nToken saved to session.json!")
            print(f"SSID: {session_data['bcdoy9@gmail.com']['ssid'][:50]}...")


if __name__ == "__main__":
    asyncio.run(main())
