import streamlit as st
import pandas as pd
import os
import json
import random
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from dotenv import load_dotenv

st.set_page_config(layout="wide")

load_dotenv()
password = os.getenv("MONGODB_PASSWORD")
uri = f"mongodb+srv://ingunn:{password}@samiaeval.2obnm.mongodb.net/?retryWrites=true&w=majority&tlsAllowInvalidCertificates=true"

client = MongoClient(uri, server_api=ServerApi('1'))
evaluering_kolleksjon = client['SamiaEvalDB']['evalueringer']

def lagre_evaluering_mongodb(kolleksjon, evaluering):
    """Lagrer evalueringer i MongoDB."""
    try:
        kolleksjon.insert_one(evaluering)
        print("Evaluering lagret i MongoDB!")
    except Exception as e:
        print(f"Feil under lagring i MongoDB: {e}")

def les_datasett(filsti):
    return pd.read_csv(filsti)



st.title("Evaluering av sammendrag")

filsti = 'data.csv'
data = les_datasett(filsti)

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
st.write(row['artikkeltekst_clean'])

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
                lagre_evaluering_mongodb(evaluering_kolleksjon, evaluering)
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