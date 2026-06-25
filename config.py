APS_CLIENT_ID = "YOUR_CLIENT_ID"
APS_CLIENT_SECRET = "YOUR_CLIENT_SECRET"

# Trenger du ikke sette denne manuelt — velg hub i web-appen,
# eller kjør find_hub.py for å finne ID-en.
ACC_HUB_ID = ""

OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"  # Bytt til f.eks. "mistral" eller "gemma2" hvis du foretrekker

OUTPUT_FILE = "romdata_output.xlsx"

# Eksakte Revit shared parameter-navn fra MRFK_Shared_parameters.txt
PARAM_FEF_ROMTYPE              = "FEF Romtype"             # GUID: aa2d2be5 — GROUP 7
PARAM_FEF_ROMTYPE_BESKRIVELSE  = "FEF Romtype beskrivelse" # GUID: ca84972e — GROUP 7
PARAM_FEF_ROMKATEGORI          = "FEF_Romkategori"         # GUID: 5dffa700 — GROUP 6
PARAM_NS3457_KODE              = "NS3457_Romfunksjon"      # GUID: 0e0b25a8 — GROUP 6
PARAM_NS3457_BESKRIVELSE       = "NS3457_Beskrivelse"      # GUID: 081da900 — GROUP 6
PARAM_FEF_OPERATIONAL_STATUS   = "FEF_OperationalStatus"   # GUID: b6c4d0ec — GROUP 5
