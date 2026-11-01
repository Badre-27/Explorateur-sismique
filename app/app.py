import os
import re
from datetime import datetime, time

import pandas as pd
import streamlit as st
from pymongo import MongoClient

st.set_page_config(page_title="Explorateur sismique", page_icon="🌍", layout="wide")

def get_uri():
    for key in ("MONGO_URI", "MONGODB_URI"):
        try:
            return st.secrets[key]
        except Exception:
            pass
    return os.getenv("MONGO_URI", "mongodb://localhost:27017")


@st.cache_resource
def get_collection():
    client = MongoClient(get_uri(), serverSelectionTimeoutMS=10000)
    return client["seismic"]["events"]


col = get_collection()

try:
    col.database.client.admin.command("ping")
except Exception as e:
    st.error("Connexion à MongoDB impossible. Vérifiez MONGO_URI et l'accès réseau (Atlas).")
    st.code(f"{type(e).__name__}: {str(e)[:300]}")
    st.stop()

st.title("Explorateur de données sismiques")
st.caption("Source : catalogue USGS des séismes | Stockage : MongoDB | Préparation : PySpark")

# Bornes du jeu de données (valeurs par défaut des filtres)
first = col.find_one(sort=[("event_ts", 1)])
last = col.find_one(sort=[("event_ts", -1)])
if first is None:
    st.error("La collection « events » est vide. Vérifiez `docker logs seismic-mongo`.")
    st.stop()

min_mag = float(col.find_one(sort=[("mag", 1)])["mag"])
max_mag = float(col.find_one(sort=[("mag", -1)])["mag"])

# ---------- Filtres (barre latérale) ----------
st.sidebar.header("Filtres")
period = st.sidebar.date_input(
    "Période",
    (first["event_ts"].date(), last["event_ts"].date()),
    min_value=first["event_ts"].date(),
    max_value=last["event_ts"].date(),
    format="DD/MM/YYYY",
)
if len(period) != 2:          # l'utilisateur choisit encore la date de fin
    st.info("Sélectionnez une date de fin dans la barre latérale.")
    st.stop()
d1, d2 = period

mag_range = st.sidebar.slider("Magnitude", min_mag, max_mag, (min_mag, max_mag), 0.1)
place_text = st.sidebar.text_input("Le lieu contient (ex. : Japan)")

# ---------- Requête MongoDB ----------
query = {
    "event_ts": {"$gte": datetime.combine(d1, time.min),
                 "$lte": datetime.combine(d2, time.max)},
    "mag": {"$gte": mag_range[0], "$lte": mag_range[1]},
}
if place_text:
    query["place"] = {"$regex": re.escape(place_text), "$options": "i"}

df = pd.DataFrame(list(col.find(query, {"_id": 0})))
if df.empty:
    st.warning("Aucun événement ne correspond à ces filtres.")
    st.stop()

df["mois"] = pd.to_datetime(df["event_ts"]).dt.to_period("M").astype(str)

# ---------- Indicateurs ----------
c1, c2, c3 = st.columns(3)
c1.metric("Nombre d'événements", f"{len(df):,}".replace(",", " "))
c2.metric("Magnitude moyenne", f"{df['mag'].mean():.2f}")
c3.metric("Magnitude maximale", f"{df['mag'].max():.1f}")

# ---------- Graphiques ----------
left, right = st.columns(2)
with left:
    st.subheader("Événements par mois")
    st.bar_chart(df.groupby("mois").size())
with right:
    st.subheader("Événements par catégorie de magnitude")
    st.bar_chart(df["mag_category"].value_counts())

st.subheader("Top 10 des zones (libellé textuel issu de `place`, à titre indicatif)")
st.bar_chart(df["area"].value_counts().head(10))

# ---------- Carte et tableau ----------
st.subheader("Carte")
st.map(df[["latitude", "longitude"]])

st.subheader("Événements (triés par magnitude décroissante)")
table = (df.sort_values("mag", ascending=False)
           [["event_ts", "mag", "depth", "place", "mag_category"]]
           .rename(columns={
               "event_ts": "Date et heure (UTC)",
               "mag": "Magnitude",
               "depth": "Profondeur (km)",
               "place": "Lieu",
               "mag_category": "Catégorie",
           }))
st.dataframe(table, use_container_width=True)
