"""
Debug SSID extraction.
"""

import asyncio
import json
from api_quotex.login import get_ssid


async def main():
    print("Getting SSID...")
    success, ssid_info = await get_ssid(
        email="bcdoy9@gmail.com", password="roshan@123@@", keep_browser_on_error=True
    )

    print(f"\nSuccess: {success}")
    print(f"Full result: {json.dumps(ssid_info, indent=2)}")

    # Check each key
    for key in ssid_info:
        print(f"\n{key}: {ssid_info[key]}")


if __name__ == "__main__":
    asyncio.run(main())
