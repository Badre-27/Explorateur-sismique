# Sujet 9 : Analyse de données sismiques avec Spark et MongoDB

Analyse d'un catalogue de séismes USGS avec PySpark, stockage dans MongoDB (Docker) et exploration via une interface Streamlit.

> Les explications détaillées (objectifs, dataset, architecture, résultats, difficultés) sont dans `rapport.pdf`.

## Fonctionnement

1. **Google Colab (PySpark)** : le notebook `projet.ipynb` nettoie le CSV USGS, calcule les agrégations et exporte `events.json`.
2. **MongoDB (Docker)** : `events.json` est importé automatiquement dans la base `seismic`, collection `events`.
3. **Application Streamlit (Docker)** : interface qui lit MongoDB et permet de filtrer par période, magnitude et texte du lieu, avec indicateurs, graphiques, carte et tableau.

## Prérequis

- Docker Desktop (avec Docker Compose)
- Un compte Google (pour Google Colab)
- Dépendances Python :
  - Colab : `pyspark` (installé dans le notebook)
  - Application : `streamlit`, `pymongo`, `pandas` (installés automatiquement dans l'image Docker)

## Utilisation

**Lien Google Colab :** [Project.ipynb](https://colab.research.google.com/drive/1E3RXly3pvukFaxq5zX9E-ma7wFI1NNJR)

### 1. Analyse Spark

Ouvrir `projet.ipynb` dans Colab, téléverser `earthquakes.csv`, exécuter toutes les cellules, puis placer le fichier `events.json` généré dans le dossier `data/`.

### 2. Lancer MongoDB et l'application

Depuis la racine du projet :

```bash
docker compose up -d --build
```

Interface : http://localhost:8501

### 3. Commandes de manipulation

```bash
# État des conteneurs
docker compose ps

# Vérifier l'import (chercher "Imported: N")
docker logs seismic-mongo

# Exécuter les requêtes NoSQL documentées
docker exec -it seismic-mongo mongosh seismic --quiet /scripts/queries.js

# Ouvrir le shell MongoDB interactif
docker exec -it seismic-mongo mongosh seismic

# Compter les documents
docker exec -it seismic-mongo mongosh seismic --quiet --eval "db.events.countDocuments()"

# Arrêter (données conservées)
docker compose down

# Réinitialiser (supprime les données, réimport au prochain démarrage)
docker compose down -v
```

> L'import ne s'exécute que sur un volume vide. Si `events.json` change : `docker compose down -v` puis `docker compose up -d --build`.

### 4. Lancer l'application sans Docker (optionnel)

MongoDB doit tourner sur le port 27017 :

```bash
pip install -r app/requirements.txt
streamlit run app/app.py
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `projet.ipynb` | Analyse PySpark et Spark SQL |
| `data/events.json` | Événements exportés, importés dans MongoDB |
| `Dockerfile`, `docker-compose.yml` | Image MongoDB personnalisée et lancement des conteneurs |
| `mongo/init-import.sh` | Import automatique et création des index |
| `mongo/queries.js` | Requêtes NoSQL (lecture, filtres, agrégation, modification, suppression) |
| `app/` | Interface Streamlit (`app.py`, `requirements.txt`, `Dockerfile`) |
