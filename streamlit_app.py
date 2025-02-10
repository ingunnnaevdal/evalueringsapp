import streamlit as st
import pandas as pd
import os
import json
import random
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import ast

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

def fix_json_and_remove_values(text):
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict) and "values" in parsed:
            parsed = parsed["values"]
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except (ValueError, SyntaxError):
        return None

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

st.markdown(f"""
<div class='main-container'>
    <h1 class='article-title'>{row['title']}</h1>
    <div class='lead-text'>{row['byline']}</div>
    <div class='lead-text'>Publisert: {row['creation_date']}</div>
    <div class='lead-text'>{row['lead_text']}</div>
    <div class='article-body'>{row['artikkeltekst']}</div>
</div>
""", unsafe_allow_html=True)

st.subheader("Sammendrag:")
sammendrag_liste = [(col.replace('prompt_', ''), row[col]) for col in row.index if 'prompt' in col]
sammendrag_liste = st.session_state.get(f"sammendrag_rekkefolge_{start_indeks}", random.sample(sammendrag_liste, len(sammendrag_liste)))
st.session_state[f"sammendrag_rekkefolge_{start_indeks}"] = sammendrag_liste

eksisterende_evalueringer = {
    e['sammendrag_kilde']: e for e in evaluering_kolleksjon.find({"uuid": row['uuid']})
}

for i, (kilde, tekst) in enumerate(sammendrag_liste):
    eval_key = f"evaluering_{row['uuid']}_{kilde}"
    
    evaluert = kilde in eksisterende_evalueringer  # Sjekk om sammendraget er evaluert

    expander_tittel = f"Sammendrag {i + 1} {'✅' if evaluert else ''}"

    with st.expander(expander_tittel):
        fixed_json = fix_json_and_remove_values(tekst)
        if fixed_json:
            st.json(json.loads(fixed_json))
        else:
            st.write(tekst)

        disabled = evaluert  # Deaktiver vurdering dersom sammendraget allerede er evaluert

        koherens = st.radio(
            "Koherens:", [1, 2, 3], 
            index=st.session_state[eval_key]['koherens'] - 1 if eval_key in st.session_state else 2,
            key=f"koherens_{start_indeks}_{i}",
            horizontal=True,
            disabled=disabled  # Deaktiver hvis allerede evaluert
        )
        
        konsistens = st.radio(
            "Konsistens:", [1, 2, 3], 
            index=st.session_state[eval_key]['konsistens'] - 1 if eval_key in st.session_state else 2,
            key=f"konsistens_{start_indeks}_{i}",
            horizontal=True,
            disabled=disabled
        )
        
        flyt = st.radio(
            "Flyt:", [1, 2, 3], 
            index=st.session_state[eval_key]['flyt'] - 1 if eval_key in st.session_state else 2,
            key=f"flyt_{start_indeks}_{i}",
            horizontal=True,
            disabled=disabled
        )
        
        relevans = st.radio(
            "Relevans:", [1, 2, 3], 
            index=st.session_state[eval_key]['relevans'] - 1 if eval_key in st.session_state else 2,
            key=f"relevans_{start_indeks}_{i}",
            horizontal=True,
            disabled=disabled
        )
        
        kommentar = st.text_area(
            "Kommentar:", 
            value=st.session_state[eval_key]['kommentar'] if eval_key in st.session_state else "",
            key=f"kommentar_{start_indeks}_{i}",
            disabled=disabled
        )

        if not evaluert and st.button(f"Lagre evaluering (Sammendrag {i + 1})", key=f"lagre_{start_indeks}_{i}"):
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
            st.session_state[eval_key] = evaluering
            st.success(f"Evaluering for Sammendrag {i + 1} lagret!")


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

st.markdown("""
    <style>
        .main-container {
            max-width: 800px;
            margin: auto;
            padding: 20px;
            background-color: #f9f9f9;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            max-height: 800px;
            overflow-y: auto;
        }
        .article-title {
            font-size: 28px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }
        .lead-text {
            font-size: 18px;
            color: #555;
            margin-bottom: 20px;
        }
        .article-body {
            font-size: 16px;
            line-height: 1.6;
            color: #444;
            margin-bottom: 30px;
        }
    </style>
""", unsafe_allow_html=True)
