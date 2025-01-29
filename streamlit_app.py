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

# Last inn miljøvariabler
load_dotenv()

password = os.getenv("MONGODB_PASSWORD")
#st.write("MONGODB_PASSWORD:", st.secrets.get("MONGODB_PASSWORD", "IKKE FUNNET"))

# MongoDB-klient
uri = f"mongodb+srv://ingunn:{password}@samiaeval.2obnm.mongodb.net/?retryWrites=true&w=majority&appName=SamiaEval"
client = MongoClient(uri, server_api=ServerApi('1'))

# Test MongoDB-tilkoblingen
try:
    client.admin.command('ping')
    st.write('tester')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# Funksjon for å koble til MongoDB-kolleksjonen
def hent_evaluering_kolleksjon(client) -> Collection:
    db = client['SamiaEvalDB']  # Bytt ut med ønsket databasenavn
    return db['evalueringer']   # Bytt ut med ønsket kollektionsnavn

# Funksjon for å lagre evalueringer i MongoDB
def lagre_evaluering_mongodb(kolleksjon, evaluering):
    """Lagrer evalueringer i MongoDB."""
    try:
        kolleksjon.insert_one(evaluering)
        print("Evaluering lagret i MongoDB!")
    except Exception as e:
        print(f"Feil under lagring i MongoDB: {e}")

# Funksjoner for å håndtere data
def les_datasett(filsti):
    """Leser inn datasettet."""
    return pd.read_csv(filsti)

def last_progresjon(filsti):
    """Laster lagret progresjon hvis den finnes."""
    if os.path.exists(filsti):
        with open(filsti, 'r') as f:
            return json.load(f)
    return {}

def lagre_progresjon(filsti, data):
    """Lagrer progresjon til en fil."""
    with open(filsti, 'w') as f:
        json.dump(data, f)

# Streamlit-applikasjon
st.title("Evaluering av sammendrag")

# Filstier
filsti = 'data.csv'
progresjon_fil = "progresjon.json"

# Koble til MongoDB-kolleksjonen
evaluering_kolleksjon = hent_evaluering_kolleksjon(client)

# Last inn data
data = les_datasett(filsti)
progresjon = last_progresjon(progresjon_fil)

# Finn startindeks basert på tidligere progresjon
vurderte_kombinasjoner = {(e['uuid'], e['sammendrag_kilde']) for e in evaluering_kolleksjon.find()}

# Sidebar med artikkelvalg
st.sidebar.header("Artikler")
if 'selected_article' not in st.session_state:
    st.session_state['selected_article'] = f'Artikkel 1'
artikkel_valg = st.sidebar.radio(
    "Velg en artikkel:",
    [f"Artikkel {i+1} {'✅' if all((data.iloc[i]['uuid'], col.replace('prompt_', '')) in vurderte_kombinasjoner for col in data.iloc[i].index if 'prompt' in col) else ''}" for i in range(len(data))]
)
start_indeks = int(artikkel_valg.split()[1]) - 1

# Hovedinnhold
row = data.iloc[start_indeks]

st.header(f"Artikkel {start_indeks + 1}/{len(data)}")
st.subheader("Artikkeltekst:")
st.write(row['artikkeltekst'])

# Vis sammendrag
st.subheader("Sammendrag:")
sammendrag_dict = {col.replace('prompt_', ''): row[col] for col in row.index if 'prompt' in col}
sammendrag_liste = list(sammendrag_dict.items())

# Lagre rekkefølgen i session_state hvis den ikke allerede er satt
if f"sammendrag_rekkefolge_{start_indeks}" not in st.session_state:
    random.shuffle(sammendrag_liste)
    st.session_state[f"sammendrag_rekkefolge_{start_indeks}"] = sammendrag_liste
else:
    sammendrag_liste = st.session_state[f"sammendrag_rekkefolge_{start_indeks}"]

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

# Valg for beste sammendrag
st.subheader("Beste Sammendrag")
beste_sammendrag = st.multiselect(
    "Hvilke sammendrag likte du best?", 
    [f"Sammendrag {i + 1}" for i in range(len(sammendrag_liste))], 
    key=f"beste_sammendrag_{start_indeks}"
)

if st.button("Lagre beste sammendrag", key=f"lagre_beste_{start_indeks}"):
    kilde_liste = [
        sammendrag_liste[int(valg.split()[1]) - 1][0] for valg in beste_sammendrag
    ]
    
    evaluering = {
        'uuid': row['uuid'],
        'sammendrag_kilde': 'Beste Sammendrag',
        'kommentar': f"Foretrukne sammendrag: {json.dumps(kilde_liste)}"
    }
    
    lagre_evaluering_mongodb(evaluering_kolleksjon, evaluering)
    st.success("Beste sammendrag lagret!")
