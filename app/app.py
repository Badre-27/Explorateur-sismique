import json
import os
import re
from datetime import datetime, time

import pandas as pd
import streamlit as st
from pymongo import MongoClient

st.set_page_config(page_title="Explorateur sismique", page_icon="🌍", layout="wide")

DB_NAME = "seismic"
COLL_NAME = "events"


# ====================================================================
# Connexion MongoDB
# ====================================================================
def get_uri():
    """Streamlit Cloud : secret MONGO_URI ; Docker / local : variable d'environnement."""
    for key in ("MONGO_URI", "MONGODB_URI"):
        try:
            return st.secrets[key]
        except Exception:
            pass
    return os.getenv("MONGO_URI", "mongodb://localhost:27017")


@st.cache_resource
def get_collection():
    uri = get_uri()
    kwargs = {"serverSelectionTimeoutMS": 10000}
    if uri.startswith("mongodb+srv"):          # Atlas : on force le bundle de certificats certifi
        try:
            import certifi
            kwargs["tlsCAFile"] = certifi.where()
        except ImportError:
            pass
    return MongoClient(uri, **kwargs)[DB_NAME][COLL_NAME]


col = get_collection()

try:
    col.database.client.admin.command("ping")
except Exception as e:
    st.error("Connexion à MongoDB impossible. Vérifiez MONGO_URI et l'accès réseau (Atlas).")
    st.code(f"{type(e).__name__}: {str(e)[:300]}")
    st.stop()


# ====================================================================
# Accès aux données (mis en cache)
# ====================================================================
@st.cache_data(ttl=300)
def get_bounds():
    r = list(col.aggregate([{"$group": {
        "_id": None,
        "d_min": {"$min": "$event_ts"}, "d_max": {"$max": "$event_ts"},
        "m_min": {"$min": "$mag"}, "m_max": {"$max": "$mag"},
    }}]))
    return r[0] if r else None


@st.cache_data(ttl=300)
def get_categories():
    return sorted(col.distinct("mag_category"))


def build_query(d1, d2, mag_lo, mag_hi, cats, text):
    q = {
        "event_ts": {"$gte": datetime.combine(d1, time.min),
                     "$lte": datetime.combine(d2, time.max)},
        "mag": {"$gte": mag_lo, "$lte": mag_hi},
    }
    if cats:
        q["mag_category"] = {"$in": list(cats)}
    if text:
        q["place"] = {"$regex": re.escape(text), "$options": "i"}
    return q


@st.cache_data(ttl=300)
def load_events(d1, d2, mag_lo, mag_hi, cats, text):
    q = build_query(d1, d2, mag_lo, mag_hi, cats, text)
    return pd.DataFrame(list(col.find(q, {"_id": 0})))


bounds = get_bounds()
if bounds is None:
    st.error("La collection « events » est vide. Vérifiez l'import (`docker logs seismic-mongo`).")
    st.stop()

min_mag = float(bounds["m_min"])
max_mag = max(float(bounds["m_max"]), min_mag + 0.1)
all_cats = get_categories()

# ====================================================================
# Filtres (barre latérale)
# ====================================================================
st.sidebar.header("Filtres")
period = st.sidebar.date_input(
    "Période",
    (bounds["d_min"].date(), bounds["d_max"].date()),
    min_value=bounds["d_min"].date(),
    max_value=bounds["d_max"].date(),
    format="DD/MM/YYYY",
)
if len(period) != 2:
    st.info("Sélectionnez une date de fin dans la barre latérale.")
    st.stop()
d1, d2 = period

mag_range = st.sidebar.slider("Magnitude", min_mag, max_mag, (min_mag, max_mag), 0.1)
cats = st.sidebar.multiselect("Catégories de magnitude", all_cats, default=all_cats)
place_text = st.sidebar.text_input("Le lieu contient (ex. : Japan)")
st.sidebar.caption("Les filtres s'appliquent aux onglets Tableau de bord, Tableaux et Données MongoDB.")

query = build_query(d1, d2, mag_range[0], mag_range[1], tuple(cats), place_text)
df = load_events(d1, d2, mag_range[0], mag_range[1], tuple(cats), place_text)

# ====================================================================
# En-tête et onglets
# ====================================================================
st.title("Explorateur de données sismiques")
st.caption("Source : catalogue USGS des séismes | Stockage : MongoDB | Préparation : PySpark")

tab_pres, tab_dash, tab_tables, tab_mongo = st.tabs(
    ["Présentation", "Tableau de bord", "Tableaux de résultats", "Données MongoDB"]
)

# --------------------------------------------------------------------
# 1. Présentation du projet et de ses objectifs
# --------------------------------------------------------------------
with tab_pres:
    st.header("Présentation du projet")
    st.markdown(
        """
Un service scientifique souhaite examiner un **catalogue public de séismes** afin de repérer
les **périodes** et les **zones** présentant le plus d'événements.

**Objectifs**
- Charger et nettoyer les données USGS avec **PySpark** (schéma, lignes incomplètes, timestamp).
- Créer des **catégories de magnitude** et compter les événements **par mois** et par catégorie.
- Étudier les localisations à partir du champ `place`.
- Exécuter **5 requêtes Spark SQL** et exporter les événements sélectionnés en **JSON**.
- Importer les événements dans **MongoDB** et les interroger par date, magnitude et texte de lieu.
- Présenter les résultats dans cette interface **interactive**.
        """
    )

    st.subheader("Architecture")
    st.graphviz_chart(
        """
digraph G {
  rankdir=LR;
  node [shape=box, style="rounded,filled", fillcolor="#eef2f7", fontname="Helvetica"];
  USGS [label="Catalogue USGS\\n(CSV)"];
  Spark [label="PySpark (Colab)\\nnettoyage, agrégations,\\nSpark SQL"];
  JSON [label="events.json\\n(JSON Lines)"];
  Mongo [label="MongoDB\\nbase seismic\\ncollection events"];
  App [label="Interface\\nStreamlit"];
  USGS -> Spark -> JSON -> Mongo -> App;
}
        """
    )

    st.subheader("Jeu de données")
    st.markdown(
        """
- **Source :** USGS Earthquake Catalog, https://earthquake.usgs.gov/earthquakes/search/
- **Colonnes principales :** `time`, `latitude`, `longitude`, `depth`, `mag`, `place`
- **Colonnes ajoutées par Spark :** `event_ts` (timestamp), `mag_category`, `area`
        """
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Événements stockés", f"{col.estimated_document_count():,}".replace(",", " "))
    c2.metric("Du", bounds["d_min"].strftime("%d/%m/%Y"))
    c3.metric("Au", bounds["d_max"].strftime("%d/%m/%Y"))

    st.info(
        "**Précaution géographique :** `place` est une description textuelle de l'USGS "
        "(ex. « 131 km NNW of Tual, Indonesia »), pas une région administrative normalisée. "
        "La colonne `area` est un libellé approximatif extrait de ce texte ; les comparaisons "
        "entre zones sont donc indicatives."
    )

# Les onglets suivants dépendent des filtres
if df.empty:
    for t in (tab_dash, tab_tables, tab_mongo):
        with t:
            st.warning("Aucun événement ne correspond à ces filtres.")
    st.stop()

df["month"] = pd.to_datetime(df["event_ts"]).dt.to_period("M").astype(str)

# --------------------------------------------------------------------
# 2. Tableau de bord : indicateurs, graphiques, carte
# --------------------------------------------------------------------
with tab_dash:
    st.header("Indicateurs statistiques")
    n = len(df)
    strongest = df.loc[df["mag"].idxmax()]
    n_strong = int((df["mag"] >= 6).sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Nombre d'événements", f"{n:,}".replace(",", " "))
    k2.metric("Magnitude moyenne", f"{df['mag'].mean():.2f}")
    k3.metric("Magnitude médiane", f"{df['mag'].median():.2f}")
    k4.metric("Magnitude maximale", f"{df['mag'].max():.1f}")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Profondeur moyenne (km)", f"{df['depth'].mean():.1f}")
    k6.metric("Zones distinctes", f"{df['area'].nunique()}")
    k7.metric("Séismes forts (M ≥ 6)", f"{n_strong}", f"{100 * n_strong / n:.1f} % du total", delta_color="off")
    k8.metric("Mois couverts", f"{df['month'].nunique()}")
    st.caption(f"Événement le plus fort : M {strongest['mag']:.1f}, {strongest['place']} "
               f"({pd.to_datetime(strongest['event_ts']).strftime('%d/%m/%Y %H:%M')} UTC)")

    st.header("Graphiques")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Événements par mois")
        st.bar_chart(df.groupby("month").size())
    with g2:
        st.subheader("Événements par catégorie de magnitude")
        st.bar_chart(df["mag_category"].value_counts())

    g3, g4 = st.columns(2)
    with g3:
        st.subheader("Distribution des magnitudes")
        st.bar_chart(((df["mag"] * 2).round() / 2).value_counts().sort_index())
    with g4:
        st.subheader("Profondeur selon la magnitude")
        st.scatter_chart(df, x="mag", y="depth")

    st.subheader("Top 10 des zones (libellé issu de `place`, indicatif)")
    st.bar_chart(df["area"].value_counts().head(10))

    st.subheader("Carte des événements")
    st.map(df[["latitude", "longitude"]])

# --------------------------------------------------------------------
# 3. Tableaux de résultats
# --------------------------------------------------------------------
with tab_tables:
    st.header("Tableaux de résultats")

    st.subheader("Événements par mois et par catégorie de magnitude")
    pivot = pd.crosstab(df["month"], df["mag_category"], margins=True, margins_name="Total")
    pivot.index.name = "Mois"
    st.dataframe(pivot)

    st.subheader("Zones les plus fréquentes (indicatif)")
    top_areas = (df.groupby("area")
                   .agg(nb_evenements=("mag", "size"),
                        magnitude_moyenne=("mag", "mean"),
                        magnitude_max=("mag", "max"))
                   .sort_values("nb_evenements", ascending=False)
                   .head(15).round(2))
    top_areas.index.name = "Zone"
    st.dataframe(top_areas)

    st.subheader("Statistiques descriptives")
    stats = df[["mag", "depth"]].describe().round(2)
    stats.columns = ["Magnitude", "Profondeur (km)"]
    st.dataframe(stats)

    st.subheader("Les 10 séismes les plus forts")
    top10 = (df.sort_values("mag", ascending=False).head(10)
               [["event_ts", "mag", "depth", "place"]]
               .rename(columns={"event_ts": "Date et heure (UTC)", "mag": "Magnitude",
                                "depth": "Profondeur (km)", "place": "Lieu"}))
    st.dataframe(top10)

    st.download_button(
        "Télécharger les événements filtrés (CSV)",
        df.drop(columns=["month"]).to_csv(index=False).encode("utf-8"),
        file_name="evenements_filtres.csv",
        mime="text/csv",
    )

# --------------------------------------------------------------------
# 4. Visualisation des données stockées dans MongoDB
# --------------------------------------------------------------------
with tab_mongo:
    st.header("Données stockées dans MongoDB")

    m1, m2, m3 = st.columns(3)
    m1.metric("Base", DB_NAME)
    m2.metric("Collection", COLL_NAME)
    m3.metric("Documents (total)", f"{col.estimated_document_count():,}".replace(",", " "))
    st.write("**Index :** " + ", ".join(f"`{k}`" for k in col.index_information().keys()))

    st.subheader("Exemple de document")
    st.json(col.find_one({}, {"_id": 0}))

    st.subheader("Requête MongoDB exécutée avec vos filtres")
    st.code("db.events.find(\n" + json.dumps(query, default=str, indent=2) + "\n)", language="javascript")
    st.caption(f"{len(df)} document(s) correspondent à cette requête.")

    st.subheader("Documents bruts")
    limit = st.slider("Nombre de documents à afficher", 5, 200, 20, 5)
    raw = pd.DataFrame(list(col.find(query, {"_id": 0}).sort("event_ts", -1).limit(limit)))
    st.dataframe(raw)
