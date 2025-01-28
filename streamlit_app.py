import streamlit as st
import pandas as pd
import os
import json
import random

# Funksjoner for å håndtere data

def les_datasett(filsti):
    """Leser inn datasettet."""
    return pd.read_csv(filsti)

def last_evalueringer(filsti):
    """Laster tidligere evalueringer hvis de finnes."""
    if os.path.exists(filsti):
        return pd.read_csv(filsti).to_dict(orient='records')
    return []

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

def lagre_evalueringer(filsti, evalueringer):
    """Lagrer evalueringer til en fil som int."""
    evaluerings_df = pd.DataFrame(evalueringer)

    # Sørg for at relevante kolonner er lagret som int
    for kol in ['koherens', 'konsistens', 'flyt', 'relevans']:
        if kol in evaluerings_df.columns:
            evaluerings_df[kol] = evaluerings_df[kol].dropna().astype(int)

    evaluerings_df.to_csv(filsti, index=False)

# Streamlit-applikasjon
st.set_page_config(layout="wide")
st.title("Evaluering av sammendrag")

# Filstier
filsti = 'data.csv'
eval_fil = "evalueringer.csv"
progresjon_fil = "progresjon.json"

# Last inn data
data = les_datasett(filsti)
evalueringer = last_evalueringer(eval_fil)
progresjon = last_progresjon(progresjon_fil)

# Finn startindeks basert på tidligere progresjon
vurderte_kombinasjoner = {(e['uuid'], e['sammendrag_kilde']) for e in evalueringer}

# Sidebar med artikkelvalg
st.sidebar.header("Artikler")
if 'selected_article' not in st.session_state:
    st.session_state['selected_article'] = f'Artikkel 1'
artikkel_valg = st.sidebar.radio("Velg en artikkel:", [f"Artikkel {i+1} {'✅' if all((data.iloc[i]['uuid'], col.replace('prompt_', '')) in vurderte_kombinasjoner for col in data.iloc[i].index if 'prompt' in col) else ''}" for i in range(len(data))])
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
                evalueringer.append(evaluering)
                lagre_evalueringer(eval_fil, evalueringer)
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
    # Hent kilde for valgte sammendrag
    kilde_liste = [
        sammendrag_liste[int(valg.split()[1]) - 1][0] for valg in beste_sammendrag
    ]
    
    # Lagre evaluering for beste sammendrag
    evaluering = {
        'uuid': row['uuid'],
        'sammendrag_kilde': 'Beste Sammendrag',
        'kommentar': f"Foretrukne sammendrag: {json.dumps(kilde_liste)}"
    }
    
    evalueringer.append(evaluering)
    lagre_evalueringer(eval_fil, evalueringer)
    st.success("Beste sammendrag lagret!")
