"""
Kjør dette første gang for å finne din ACC Hub ID.
Trenger bare APS_CLIENT_ID og APS_CLIENT_SECRET i config.py.

Kjør: python find_hub.py
"""

import requests
from config import APS_CLIENT_ID, APS_CLIENT_SECRET

BASE_URL = "https://developer.api.autodesk.com"

def get_token():
    resp = requests.post(
        f"{BASE_URL}/authentication/v2/token",
        data={
            "client_id": APS_CLIENT_ID,
            "client_secret": APS_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "data:read",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def main():
    print("Autentiserer...")
    token = get_token()
    print("OK\n")

    resp = requests.get(
        f"{BASE_URL}/project/v1/hubs",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    hubs = resp.json()["data"]

    if not hubs:
        print("Ingen hubs funnet for disse credentials.")
        return

    print(f"Fant {len(hubs)} hub(s):\n")
    for h in hubs:
        attrs = h["attributes"]
        print(f"  Navn:    {attrs['name']}")
        print(f"  Hub ID:  {h['id']}")
        print(f"  Type:    {attrs.get('extension', {}).get('type', 'ukjent')}")
        print()

    if len(hubs) == 1:
        print(f"Legg denne linjen i config.py:")
        print(f'  ACC_HUB_ID = "{hubs[0]["id"]}"')

if __name__ == "__main__":
    main()
