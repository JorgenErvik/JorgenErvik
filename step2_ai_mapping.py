"""
Steg 2: AI-assistert mapping av romdata til FEF arealmodell + NS 3457-4
Leser Excel fra steg 1, foreslår alle 6 parametere via Ollama (lokalt),
skriver ny Excel med forslag + konfidenscore for review.
FEF_OperationalStatus settes til 100 for alle auto-mappede rom.
"""

import requests
import pandas as pd
import json
from config import (
    PARAM_FEF_ROMTYPE, PARAM_FEF_ROMKATEGORI,
    PARAM_NS3457_KODE, PARAM_NS3457_BESKRIVELSE, PARAM_FEF_OPERATIONAL_STATUS,
    OLLAMA_URL, OLLAMA_MODEL,
)
from fef_register import FEF_REGISTER, ROMTYPE_TIL_BESKRIVELSE, NS3457_REGISTER

INPUT_FILE  = "romdata_output.xlsx"
OUTPUT_FILE = "romdata_med_fef_forslag.xlsx"

OPERATIONAL_STATUS_AUTO      = 100  # AI-mappet, ikke validert
OPERATIONAL_STATUS_VALIDERT  = 125  # Manuelt gjennomgått og godkjent


def bygg_system_prompt() -> str:
    fef_tekst = "\n".join(
        f"  {r['Romtype']} | {r['Romtype_beskrivelse']} | {r['Romkategori']}"
        for r in FEF_REGISTER
    )
    ns_tekst = "\n".join(
        f"  {kode} = {beskrivelse}"
        for kode, beskrivelse in NS3457_REGISTER
    )
    return f"""Du er ekspert på norsk arealforvaltning og kjenner FEF arealmodellen og NS 3457-4.

=== FEF Arealmodell (tillatte kombinasjoner) ===
Romtype | Romtype_beskrivelse | Romkategori
{fef_tekst}

=== NS 3457-4 Romfunksjoner (tillatte koder) ===
{ns_tekst}

Din oppgave: Gitt romnavn fra en Revit-modell, velg beste FEF-kombinasjon OG NS 3457-4 kode.

Regler:
- Romtype MÅ være en av: {', '.join(ROMTYPE_TIL_BESKRIVELSE.keys())}
- Romtype_beskrivelse følger automatisk av Romtype — ikke finn opp nye
- Romkategori MÅ være en gyldig kategori for valgt Romtype (se tabellen)
- NS3457_kode MÅ være et tall fra listen over (f.eks. 261, 211, 513)
- NS3457_beskrivelse hentes direkte fra NS-tabellen for valgt kode
- Konfidenscore 0.0–1.0: 1.0 = opplagt, 0.6 = usikkert, 0.0 = vet ikke
- Sett Trenger_review=true hvis konfidenscore < 0.6

Returner alltid gyldig JSON:
{{
  "Romtype": "A",
  "Romtype_beskrivelse": "Behandlingsrom",
  "Romkategori": "Behandling",
  "NS3457_kode": 262,
  "NS3457_beskrivelse": "Medisinsk behandlingsrom",
  "Konfidenscore": 0.92,
  "Trenger_review": false,
  "Begrunnelse": "Tannlegekontor er medisinsk behandlingsrom"
}}"""


def ollama_chat(system: str, user: str) -> str:
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def map_rom(romnavn: str, romnummer: str, etasje: str) -> dict:
    user_msg = f'Romnavn: "{romnavn}" | Nummer: "{romnummer}" | Etasje: "{etasje}"'
    try:
        tekst = ollama_chat(bygg_system_prompt(), user_msg)
        if "```" in tekst:
            tekst = tekst.split("```")[1].replace("json", "").strip()
        return json.loads(tekst)
    except Exception as e:
        return {
            "Romtype": "", "Romtype_beskrivelse": "", "Romkategori": "",
            "NS3457_kode": "", "NS3457_beskrivelse": "",
            "Konfidenscore": 0.0, "Trenger_review": True,
            "Begrunnelse": f"Feil: {e}",
        }


def main():
    print(f"Leser {INPUT_FILE}...")
    df = pd.read_excel(INPUT_FILE)

    resultater = []
    totalt = len(df)

    for i, rad in df.iterrows():
        romnavn = str(rad.get("Eksist_Romnavn", ""))
        nummer  = str(rad.get("Romnummer", ""))
        etasje  = str(rad.get("Etasje", ""))

        # Hopp over rom som allerede er fullstendig mappet
        if str(rad.get(PARAM_FEF_ROMTYPE, "")).strip():
            print(f"  [{i+1}/{totalt}] {romnavn} — allerede mappet, hopper over")
            resultater.append(None)
            continue

        print(f"  [{i+1}/{totalt}] Mapper: {romnavn}...")
        forslag = map_rom(romnavn, nummer, etasje)
        resultater.append(forslag)

    # Bygg forslags-kolonner
    forslag_kolonner = [
        "Romtype", "Romtype_beskrivelse", "Romkategori",
        "NS3457_kode", "NS3457_beskrivelse",
        "Konfidenscore", "Trenger_review", "Begrunnelse",
    ]
    forslag_rader = [r if r is not None else {k: "" for k in forslag_kolonner} for r in resultater]
    forslag_df = pd.DataFrame(forslag_rader)

    for kol in forslag_kolonner:
        df[f"Forslag_{kol}"] = forslag_df.get(kol, "").values

    # FEF_OperationalStatus = 100 for alle auto-mappede rom
    df["Forslag_OperationalStatus"] = df.apply(
        lambda r: OPERATIONAL_STATUS_AUTO if str(r.get(PARAM_FEF_OPERATIONAL_STATUS, "")).strip() == "" else "",
        axis=1,
    )

    df.to_excel(OUTPUT_FILE, index=False)

    antall_mappet   = sum(1 for r in resultater if r is not None)
    antall_review   = sum(1 for r in resultater if r and r.get("Trenger_review"))
    antall_skip     = sum(1 for r in resultater if r is None)

    print(f"\nFerdig! Lagret til {OUTPUT_FILE}")
    print(f"  {totalt} rom totalt")
    print(f"  {antall_mappet} rom AI-mappet (OperationalStatus satt til {OPERATIONAL_STATUS_AUTO})")
    print(f"  {antall_skip} rom hadde allerede FEF-data")
    print(f"  {antall_review} rom flagget for manuell review (konfidenscore < 0.6)")
    print(f"\nNeste steg:")
    print(f"  1. Gjennomgå {OUTPUT_FILE} — korriger Forslag_*-kolonnene ved behov")
    print(f"  2. Endre Forslag_OperationalStatus til {OPERATIONAL_STATUS_VALIDERT} for godkjente rom")
    print(f"  3. Kjør step3_skriv_til_revit.py for å sende verdiene tilbake til ACC")


if __name__ == "__main__":
    main()
