"""
Steg 1: Hent alle rom fra Revit-modeller i ACC via APS
Output: Excel-fil med romID, modell, etasje og eksisterende FEF/NS-parametere
"""

import requests
import time
import pandas as pd
from config import (
    APS_CLIENT_ID, APS_CLIENT_SECRET, ACC_HUB_ID,
    PILOT_PROJECT_IDS, OUTPUT_FILE,
    PARAM_FEF_ROMTYPE, PARAM_FEF_ROMKATEGORI,
    PARAM_NS3457_KODE, PARAM_NS3457_BESKRIVELSE, PARAM_FEF_OPERATIONAL_STATUS,
)

BASE_URL = "https://developer.api.autodesk.com"

ALL_FEF_PARAMS = [
    PARAM_FEF_ROMTYPE,
    PARAM_FEF_ROMKATEGORI,
    PARAM_NS3457_KODE,
    PARAM_NS3457_BESKRIVELSE,
    PARAM_FEF_OPERATIONAL_STATUS,
]


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


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def get_projects(token):
    url = f"{BASE_URL}/project/v1/hubs/{ACC_HUB_ID}/projects"
    projects = []
    while url:
        resp = requests.get(url, headers=auth_headers(token))
        resp.raise_for_status()
        data = resp.json()
        projects.extend(data["data"])
        url = data.get("links", {}).get("next", {}).get("href")
    return projects


def get_top_folders(token, project_id):
    resp = requests.get(
        f"{BASE_URL}/project/v1/hubs/{ACC_HUB_ID}/projects/{project_id}/topFolders",
        headers=auth_headers(token),
    )
    resp.raise_for_status()
    return resp.json()["data"]


def find_revit_files(token, project_id, folder_id, results=None):
    if results is None:
        results = []
    url = f"{BASE_URL}/data/v1/projects/{project_id}/folders/{folder_id}/contents"
    while url:
        resp = requests.get(url, headers=auth_headers(token))
        resp.raise_for_status()
        data = resp.json()
        for item in data["data"]:
            if item["type"] == "items":
                name = item["attributes"].get("displayName", "")
                if name.lower().endswith(".rvt"):
                    version_url = (
                        f"{BASE_URL}/data/v1/projects/{project_id}"
                        f"/items/{item['id']}/versions"
                    )
                    v_resp = requests.get(version_url, headers=auth_headers(token))
                    v_resp.raise_for_status()
                    versions = v_resp.json()["data"]
                    if versions:
                        urn = versions[0]["relationships"]["derivatives"]["data"]["id"]
                        results.append({
                            "project_id": project_id,
                            "item_id": item["id"],
                            "model_name": name,
                            "urn": urn,
                        })
            elif item["type"] == "folders":
                find_revit_files(token, project_id, item["id"], results)
        url = data.get("links", {}).get("next", {}).get("href")
    return results


def get_model_guid(token, urn):
    url = f"{BASE_URL}/modelderivative/v2/designdata/{urn}/metadata"
    resp = requests.get(url, headers=auth_headers(token))
    resp.raise_for_status()
    views = resp.json()["data"]["metadata"]
    for v in views:
        if v.get("role") == "3d":
            return v["guid"]
    return views[0]["guid"] if views else None


def get_properties(token, urn, guid):
    url = f"{BASE_URL}/modelderivative/v2/designdata/{urn}/metadata/{guid}/properties"
    params = {"forceget": "true"}
    resp = requests.get(url, headers=auth_headers(token), params=params)
    if resp.status_code == 202:
        print("  Venter på Model Derivative (kan ta opptil 60s)...")
        for _ in range(12):
            time.sleep(10)
            resp = requests.get(url, headers=auth_headers(token), params=params)
            if resp.status_code == 200:
                break
        else:
            print("  Timeout — hopper over modell")
            return []
    resp.raise_for_status()
    return resp.json()["data"]["collection"]


def extract_rooms(objects, model_name, project_id):
    rooms = []
    for obj in objects:
        props = obj.get("properties", {})
        category = props.get("__category__") or props.get("Category", "")
        if "Room" not in str(category):
            continue

        identity = props.get("Identity Data", {})
        dimensions = props.get("Dimensions", {})

        room = {
            "Prosjekt_ID": project_id,
            "Modell": model_name,
            "Revit_ID": obj.get("objectid"),
            "Romnummer": identity.get("Number", ""),
            "Eksist_Romnavn": identity.get("Name", ""),
            "Etasje": props.get("Constraints", {}).get("Level", ""),
            "Areal_m2": dimensions.get("Area", ""),
        }

        # Hent eksisterende FEF/NS-verdier fra modellen (tom = ikke satt enda)
        for p in ALL_FEF_PARAMS:
            room[p] = identity.get(p) or props.get(p, "")

        rooms.append(room)
    return rooms


def main():
    print("Autentiserer mot APS...")
    token = get_token()

    print(f"Henter prosjekter fra hub {ACC_HUB_ID}...")
    all_projects = get_projects(token)

    if PILOT_PROJECT_IDS:
        projects = [p for p in all_projects if p["id"] in PILOT_PROJECT_IDS]
        print(f"Pilotmodus: {len(projects)} prosjekt(er) valgt")
    else:
        projects = all_projects
        print(f"Kjører mot alle {len(projects)} prosjekter")

    all_rooms = []

    for project in projects:
        project_id = project["id"]
        project_name = project["attributes"]["name"]
        print(f"\nProsjekt: {project_name}")

        folders = get_top_folders(token, project_id)
        revit_files = []
        for folder in folders:
            find_revit_files(token, project_id, folder["id"], revit_files)

        print(f"  Fant {len(revit_files)} Revit-filer")

        for model in revit_files:
            print(f"  Behandler: {model['model_name']}")
            try:
                guid = get_model_guid(token, model["urn"])
                if not guid:
                    print("    Ingen view-GUID — hopper over")
                    continue
                objects = get_properties(token, model["urn"], guid)
                rooms = extract_rooms(objects, model["model_name"], project_id)
                print(f"    Fant {len(rooms)} rom")
                all_rooms.extend(rooms)
            except Exception as e:
                print(f"    FEIL: {e}")

    if all_rooms:
        df = pd.DataFrame(all_rooms)
        cols = [
            "Prosjekt_ID", "Modell", "Revit_ID", "Romnummer",
            "Eksist_Romnavn", "Etasje", "Areal_m2",
        ] + ALL_FEF_PARAMS
        df = df[[c for c in cols if c in df.columns]]
        df.to_excel(OUTPUT_FILE, index=False)
        print(f"\nFerdig! {len(all_rooms)} rom lagret til {OUTPUT_FILE}")
    else:
        print("\nIngen rom funnet.")


if __name__ == "__main__":
    main()
