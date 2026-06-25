"""
Engangs-oppsett av DA4R AppBundle og Activity i APS.
Kjør: py setup_da4r.py

Forutsetning: RoomDataExtractor.dll må være kompilert først.
Se README_DA4R.md for kompileringsinstrukser.
"""

import requests
import zipfile
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import APS_CLIENT_ID, APS_CLIENT_SECRET

BASE_URL   = "https://developer.api.autodesk.com"
DA_URL     = f"{BASE_URL}/da/us-east/v3"
BUNDLE_ZIP = os.path.join(os.path.dirname(__file__), "addin", "RoomDataExtractor.zip")
ADDIN_DIR  = os.path.join(os.path.dirname(__file__), "addin")

NICKNAME   = "FEF_AFRY"          # Unikt kallenavn for din APS-app i DA4R
BUNDLE_ID  = "RoomExtractor"
ACTIVITY_ID = "ExtractRooms"
REVIT_VERSION = "24"              # Revit 2024


def get_token():
    resp = requests.post(
        f"{BASE_URL}/authentication/v2/token",
        data={
            "client_id": APS_CLIENT_ID,
            "client_secret": APS_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "code:all",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def ah(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def lag_bundle_zip():
    """Pakk DLL og .addin inn i zip."""
    dll_path   = os.path.join(ADDIN_DIR, "RoomDataExtractor.dll")
    addin_path = os.path.join(ADDIN_DIR, "RoomDataExtractor.addin")

    if not os.path.exists(dll_path):
        print(f"FEIL: {dll_path} ikke funnet — kompiler prosjektet først")
        print("  cd da4r/addin && dotnet build -c Release")
        sys.exit(1)

    with zipfile.ZipFile(BUNDLE_ZIP, "w") as z:
        z.write(dll_path,   "RoomDataExtractor/RoomDataExtractor.dll")
        z.write(addin_path, "RoomDataExtractor/RoomDataExtractor.addin")

        # Kopier med-DLL-er fra build-output
        build_dir = os.path.join(ADDIN_DIR, "bin", "Release", "net48")
        if os.path.exists(build_dir):
            for f in os.listdir(build_dir):
                if f.endswith(".dll") and f != "RoomDataExtractor.dll":
                    z.write(os.path.join(build_dir, f), f"RoomDataExtractor/{f}")

    print(f"Lagde {BUNDLE_ZIP}")


def registrer_nickname(token):
    resp = requests.patch(
        f"{DA_URL}/forgeapps/me",
        headers=ah(token),
        json={"nickname": NICKNAME},
    )
    if resp.status_code in (200, 409):  # 409 = nickname allerede i bruk
        print(f"Nickname '{NICKNAME}' OK")
    else:
        print(f"Nickname-feil {resp.status_code}: {resp.text}")


def last_opp_bundle(token):
    # Opprett eller oppdater AppBundle
    payload = {
        "id": BUNDLE_ID,
        "engine": f"Autodesk.Revit+{REVIT_VERSION}",
        "description": "FEF Arealmodell Room Data Extractor",
    }
    resp = requests.post(f"{DA_URL}/appbundles", headers=ah(token), json=payload)
    if resp.status_code == 409:
        # Finnes allerede — opprett ny versjon
        resp = requests.post(
            f"{DA_URL}/appbundles/{BUNDLE_ID}/versions",
            headers=ah(token),
            json={"engine": f"Autodesk.Revit+{REVIT_VERSION}", "description": "FEF update"},
        )

    resp.raise_for_status()
    data = resp.json()
    upload_url = data["uploadParameters"]["endpointURL"]
    upload_params = data["uploadParameters"]["formData"]
    version = data.get("version", 1)

    # Last opp zip til S3
    with open(BUNDLE_ZIP, "rb") as f:
        files = {"file": f}
        s3_resp = requests.post(upload_url, data=upload_params, files=files)
        s3_resp.raise_for_status()

    print(f"AppBundle '{BUNDLE_ID}' lastet opp (versjon {version})")

    # Sett alias
    alias_resp = requests.post(
        f"{DA_URL}/appbundles/{BUNDLE_ID}/aliases",
        headers=ah(token),
        json={"id": "prod", "version": version},
    )
    if alias_resp.status_code == 409:
        requests.patch(
            f"{DA_URL}/appbundles/{BUNDLE_ID}/aliases/prod",
            headers=ah(token),
            json={"version": version},
        )
    print("Alias 'prod' satt")


def opprett_activity(token):
    activity = {
        "id": ACTIVITY_ID,
        "commandLine": [
            f"$(engine.path)\\\\revitcoreconsole.exe /i \"$(args[rvtFile].path)\" /al \"$(appbundles[{BUNDLE_ID}].path)\""
        ],
        "parameters": {
            "rvtFile": {
                "verb": "get",
                "description": "Input Revit-fil",
                "localName": "input.rvt",
            },
            "result": {
                "verb": "put",
                "description": "Output JSON med romdata",
                "localName": "output.json",
            },
        },
        "engine": f"Autodesk.Revit+{REVIT_VERSION}",
        "appbundles": [f"{NICKNAME}.{BUNDLE_ID}+prod"],
        "description": "Ekstraher romdata fra Revit-fil",
    }

    resp = requests.post(f"{DA_URL}/activities", headers=ah(token), json=activity)
    if resp.status_code == 409:
        resp = requests.post(
            f"{DA_URL}/activities/{ACTIVITY_ID}/versions",
            headers=ah(token),
            json=activity,
        )

    resp.raise_for_status()
    version = resp.json().get("version", 1)

    alias_resp = requests.post(
        f"{DA_URL}/activities/{ACTIVITY_ID}/aliases",
        headers=ah(token),
        json={"id": "prod", "version": version},
    )
    if alias_resp.status_code == 409:
        requests.patch(
            f"{DA_URL}/activities/{ACTIVITY_ID}/aliases/prod",
            headers=ah(token),
            json={"version": version},
        )
    print(f"Activity '{ACTIVITY_ID}' opprettet (versjon {version})")


def main():
    print("=== DA4R Oppsett ===\n")

    print("1. Lager bundle-zip...")
    lag_bundle_zip()

    print("\n2. Henter token...")
    token = get_token()

    print("\n3. Registrerer nickname...")
    registrer_nickname(token)

    print("\n4. Laster opp AppBundle...")
    last_opp_bundle(token)

    print("\n5. Oppretter Activity...")
    opprett_activity(token)

    print(f"\nFerdig! Activity-ID: {NICKNAME}.{ACTIVITY_ID}+prod")
    print("Kjør nå: py run_extraction.py")


if __name__ == "__main__":
    main()
