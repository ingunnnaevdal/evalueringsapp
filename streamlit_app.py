import streamlit as st
import pandas as pd
import os
import json
import random
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
from googleapiclient.http import MediaIoBaseDownload

st.set_page_config(layout="wide")

# 🔹 Last inn miljøvariabler
load_dotenv()
password = os.getenv("MONGODB_PASSWORD")
uri = f"mongodb+srv://ingunn:{password}@samiaeval.2obnm.mongodb.net/?retryWrites=true&w=majority&tlsAllowInvalidCertificates=true"

client = MongoClient(uri, server_api=ServerApi('1'))
evaluering_kolleksjon = client['SamiaEvalDB']['evalueringer']

# 🔹 Funksjon for å hente CSV-filen fra Google Drive
def hent_csv_fra_google_drive(file_id):
    """Laster ned CSV-filen fra Google Drive og returnerer en Pandas DataFrame."""
    try:
        # 🔹 Hent Google Cloud-nøkkel fra GitHub Secrets
        GCP_CREDENTIALS = os.getenv("GCP_CREDENTIALS")
        credentials_dict = json.loads(GCP_CREDENTIALS)

        # 🔹 Autentiser med Service Account
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        drive_service = build("drive", "v3", credentials=credentials)

        # 🔹 Last ned CSV-filen
        request = drive_service.files().get_media(fileId=file_id)
        file_data = io.BytesIO()
        downloader = MediaIoBaseDownload(file_data, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        file_data.seek(0)
        return pd.read_csv(file_data)

    except Exception as e:
        st.error(f"Feil ved henting av CSV fra Google Drive: {e}")
        return pd.DataFrame()

# 🔹 Google Drive-fil-ID (sett inn din egen)
FILE_ID = "16_ZzDh4sQXp3ajIs_8coxxST_NIUq73a"

st.title("Evaluering av sammendrag")

# 🔹 Hent data fra Google Drive
data = hent_csv_fra_google_drive(FILE_ID)

# 🔹 Sjekk at dataen er lastet inn riktig
if data.empty:
    st.error("Kunne ikke laste inn data. Sjekk Google Drive-fil-ID og tilgangsrettigheter.")
    st.stop()

# 🔹 Hent vurderte kombinasjoner fra MongoDB
vurderte_kombinasjoner = {
    (e['uuid'], e.get('sammendrag_kilde')) for e in 
    evaluering_kolleksjon.find({}, {'uuid': 1, 'sammendrag_kilde': 1}) if 'sammendrag_kilde' in e
}

st.sidebar.header("Artikler")
artikkel_valg = st.sidebar.radio(
    "Velg en artikkel:",
    [f"Artikkel {i+1} {'✅' if all((data.iloc[i]['uuid'], col.replace('prompt_', '')) in vurderte_kombinasjoner for col in data.iloc[i].index if 'prompt' in col) else ''}" for i in range(len(data))]
)

start_indeks = int(artikkel_valg.split()[1]) - 1
row = data.iloc[start_indeks]

st.header(f"Artikkel {start_indeks + 1}/{len(data)}")
st.subheader("Artikkeltekst:")
st.write(row['artikkeltekst'])

st.subheader("Sammendrag:")
sammendrag_liste = [(col.replace('prompt_', ''), row[col]) for col in row.index if 'prompt' in col]
sammendrag_liste = st.session_state.get(f"sammendrag_rekkefolge_{start_indeks}", random.sample(sammendrag_liste, len(sammendrag_liste)))
st.session_state[f"sammendrag_rekkefolge_{start_indeks}"] = sammendrag_liste

for i, (kilde, tekst) in enumerate(sammendrag_liste):
    with st.expander(f"Sammendrag {i + 1}"):
        st.write(tekst)
        if (row['uuid'], kilde) in vurderte_kombinasjoner:
            st.warning("✅ Dette sammendraget er allerede evaluert.")
        else:
            koherens = st.radio("Koherens:", [1, 2, 3, 4, 5], index=2, key=f"koherens_{start_indeks}_{i}", horizontal=True)
            konsistens = st.radio("Konsistens:", [1, 2, 3, 4, 5], index=2, key=f"konsistens_{start_indeks}_{i}", horizontal=True)
            flyt = st.radio("Flyt:", [1, 2, 3, 4, 5], index=2, key=f"flyt_{start_indeks}_{i}", horizontal=True)
            relevans = st.radio("Relevans:", [1, 2, 3, 4, 5], index=2, key=f"relevans_{start_indeks}_{i}", horizontal=True)
            kommentar = st.text_area("Kommentar:", key=f"kommentar_{start_indeks}_{i}")

            if st.button(f"Lagre evaluering (Sammendrag {i + 1})", key=f"lagre_{start_indeks}_{i}"):
                evaluering = {
                    'uuid': row['uuid'],
                    'sammendrag_kilde': kilde,
                    'koherens': koherens,
                    'konsistens': konsistens,
                    'flyt': flyt,
                    'relevans': relevans,
                    'kommentar': kommentar
                }
                evaluering_kolleksjon.insert_one(evaluering)
                st.success(f"Evaluering for Sammendrag {i + 1} lagret!")
                st.session_state['selected_article'] = artikkel_valg
                st.rerun()

st.subheader("Beste Sammendrag")
beste_sammendrag = st.multiselect(
    "Hvilke sammendrag likte du best?", 
    [f"Sammendrag {i + 1}" for i in range(len(sammendrag_liste))],
    key=f"beste_sammendrag_{start_indeks}"
)

if st.button("Lagre beste sammendrag", key=f"lagre_beste_{start_indeks}"):
    evaluering_kolleksjon.insert_one({
        'uuid': row['uuid'],
        'sammendrag_kilde': 'Beste Sammendrag',
        'kommentar': f"Foretrukne sammendrag: {json.dumps([sammendrag_liste[int(valg.split()[1]) - 1][0] for valg in beste_sammendrag])}"
    })
    st.success("Beste sammendrag lagret!")
