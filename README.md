# Bundibugyo Ebola virus outbreak 2026 — Dashboard des présentations provinciales

![Logos des organisations](Data/Branding/all_logos.png)

Ce tableau de bord statique (GitHub Pages) est construit à partir de [`BDBV2026-Provincial_Reports`](https://github.com/INRB-UMIE/BDBV2026-Provincial_Reports). Il présente les chiffres extraits automatiquement des présentations quotidiennes des DPS.

Il fonctionne **exactement comme** [`BDBV2026-Epidemic_Dashboard`](https://github.com/INRB-UMIE/BDBV2026-Epidemic_Dashboard) :

| | Epidemic_Dashboard | Provincial_Dashboard |
|---|---|---|
| Dépôt de données | `BDBV2026-Data` (`build/`) | `BDBV2026-Provincial_Reports` (`build/` + `qa/`) |
| Déclencheur | `repository_dispatch: data-updated` envoyé par `release.yml` | idem |
| Build | `python Scripts/build_dashboard.py` → `output/` | idem |
| Publication | copies à la racine du dépôt, servies par GitHub Pages | idem |
| Aperçu de PR | `pr-preview.yml` → `pr-preview/pr-<n>/` | idem |

> ⚠️ **Confidentialité.** Les chiffres sont agrégés par zone de santé, sans données individuelles, mais ils sont **préliminaires et non publiés**. Sur un plan GitHub Free, Team ou Pro, un site Pages est **public**, même si le dépôt est privé. Avant d'activer Pages, il faut vérifier que l'organisation a Enterprise Cloud (Pages à accès restreint) ou décider que ces agrégats peuvent être publics. Le dépôt de données, lui, doit rester privé.

## Pages

| Page | Fichier | Contenu |
|---|---|---|
| **Situation actuelle** | `index.html` | **carte plein écran, comme `BDBV2026-Epidemic_Dashboard/index.html`** : Leaflet, **silhouette de la RDC** (provinces non concernées en gris clair) avec les **provinces concernées colorées** par ZS (sans fond de carte ni pays voisins), panneau **Couche** (recherche d'une ZS + source : cas cumulés, décès, cas sur 21 j, statut, nouvelles alertes, contacts à suivre, taux de suivi), **Légende** à barre en dégradé, panneau **Zone** au clic (cas, alertes, contacts de la ZS) ; compteur des chiffres clés dans l'en-tête |
| Synthèse | `synthese.html` | indicateurs clés (avec variation depuis la date précédente, calculée sur les mêmes provinces), cas et taux de suivi par province, synthèse avec les tableaux extraits par province |
| Zones de santé | `zones.html` | confirmés sur 21 jours par ZS ; tableau triable avec statut *Active* (≤ 21 j), *Surveillance* (22–42 j) ou *Sans cas > 42 j* |
| Tendances | `tendances.html` | une courbe pour l'ensemble des provinces et une courbe par province, au choix : confirmés, décès, 21 jours, alertes, contacts, taux de suivi |
| Alertes et contacts | `alertes-contacts.html` | sources des alertes (barres 100 %, avec le tableau), contacts à suivre et vus, alertes et contacts par ZS (ou par AS si la province ne donne pas le niveau ZS) |
| Qualité des données | `qualite.html` | tableaux extraits, collés en image ou absents par province, et constats de la QA |
| **Piliers et fiabilité** | `piliers.html` | **synthèse générale tirée du texte des présentations** : indicateurs clés par province (cas du jour, cumul, décès, ZS/AS touchées, alertes, guéris, patients aux lits, avec la diapositive d'origine au survol), **fiabilité de l'extraction** par province (4 méthodes de lecture comparées, dont l'OCR), **contrôles de cohérence**, puis coordination et piliers (points saillants, réalisations, défis, planification, recommandations) de toutes les provinces, filtrables par pilier et rubrique |
| **KPI Surveillance · Labo · PCI** | `kpi-piliers.html` | **KPI des piliers Surveillance, Laboratoire et PCI / WASH** tirés des présentations : alertes du jour, taux de vérification, de validation et de transfert, part de la recherche active, complétude ; échantillons reçus, analysés, en cours, positifs et taux de positivité ; rings ouverts, ESS et ménages décontaminés, ménages dotés, prestataires infectés. Tuiles toutes provinces (sur les provinces qui rapportent la valeur), graphique et tableau par province, diapositive, source et confirmations au survol. Les mêmes KPI figurent sur chaque page province |
| **Résumé de la semaine** | `semaine.html` | **une fenêtre par pilier pour la semaine (lundi → dimanche) qui contient la date choisie** : KPI jour par jour avec total de la semaine (sommes pour les flux comme les alertes et les échantillons, dernière valeur et variation pour les cumuls, taux recalculés sur la semaine ; indicateurs clés pour la coordination), puis points saillants, réalisations, défis, planification et recommandations de toutes les provinces. Un point repris plusieurs jours n'apparaît qu'une fois avec le nombre de jours (« 5 j. »), un défi présent chaque jour est marqué *persistant*. Filtres province, rubrique et pilier ; tuiles « la semaine en chiffres » (cas, hausse du cumul, alertes, positivité, fiabilité) |
| **Résumé par province** | `province-<nom>.html` (`province-nord-kivu.html`, `province-ituri.html`…) | une page par province : **résumé rédigé automatiquement** (cumul et variation depuis la veille, 21 derniers jours, ZS la plus touchée, alertes et principale source, suivi des contacts et ZS les plus faibles, tableaux non lus) ; indicateurs clés, cas par ZS, tendance, contacts, sources, alertes, constats QA de la province |

On accède aux pages province par le menu **Provinces** de la barre d'onglets, ou en cliquant sur le nom d'une province dans la Vue d'ensemble. Elles sont générées automatiquement pour chaque province présente dans les données : une nouvelle province reçoit sa page au build suivant.

Un sélecteur de date en haut de chaque page propose toutes les dates du `manifest.json`. La date choisie suit la navigation entre les pages grâce au paramètre `?date=`.

Quand une province n'a pas de tableau extrait (collé en image, par exemple), elle apparaît comme « non extrait ». Les totaux affichent toujours le nombre de provinces qui y contribuent, par exemple « 3/5 provinces le rapportent » : un chiffre manquant n'est jamais compté comme un zéro.

## Extraction des présentations : piliers, points saillants et fiabilité

Les tableaux par ZS (`build/`) ne disent rien de la coordination ni des piliers. Pour cela, le pipeline
`extraire_rapports.py` (dans `BDBV2026-Provincial_Reports/data/presentations/`, avec `ia_extraction.py` et
`methodes_texte.py`) lit chaque jour le dossier `PRESENTATION_JJMMAAAA` et écrit
`PRESENTATION_JJMMAAAA/extraction/extraction_JJMMAAAA.json` (avec un rapport HTML et un Excel). Modules :
`methodes_texte.py` (lecture et comparaison), `ocr_diapos.py` (OCR), `kpi_piliers.py` (KPI), `ia_extraction.py` (IA). Le build du dashboard
lit ces JSON (`EXTRACTION_DIR`, par défaut `../BDBV2026-Provincial_Reports/data/presentations`) en Python standard.

- **4 méthodes de lecture**, comparées diapositive par diapositive : python-pptx (formes, tableaux, graphiques),
  XML brut de l'archive `.pptx`, rendu LibreOffice → PDF (pypdf) et **OCR** des pages de ce PDF rendues en image
  (Tesseract `fra+eng`, ou EasyOCR ; 300 dpi, niveaux de gris, correction des confusions lettre/chiffre, cache par
  fichier). Chaque indicateur et chaque phrase portent le nombre de méthodes qui les retrouvent (« 4/4 »). L'OCR lit ce
  qui est **visible à l'écran** : il confirme visuellement le texte natif et lit les **diapositives en image** (captures,
  tableaux collés), dont le contenu est rangé dans les rubriques et marqué « OCR ». Sans LibreOffice : 2 méthodes, sans
  OCR, score plafonné à 80. `--ocr non` désactive l'OCR.
- **Score de fiabilité /100** par province : éléments confirmés par ≥ 2 méthodes (40 %), accord du texte natif (15 %),
  éléments vus à l'écran par l'OCR (15 %), diapositives lisibles (20 % ; une diapositive en image lue par OCR compte
  pour moitié), cohérence des chiffres (10 %). Sans OCR : 50 / 20 / – / 20 / 10. ≥ 85 élevée, ≥ 65 moyenne.
- **KPI Surveillance, Laboratoire, PCI** (`kpi_piliers.py`) : en-têtes de tableaux sur plusieurs lignes reconstitués
  (cellules fusionnées), ligne Total, tableaux et graphiques d'évolution (colonne du jour), cartes, phrases, OCR ;
  plusieurs laboratoires additionnés ; taux recalculés (jamais au-dessus de 100 %).
- **Logique « IA »** pour des présentations qui changent d'un jour à l'autre :
  - classifieur des piliers auto-apprenant (TF-IDF + k plus proches voisins, Python standard) : les diapositives classées
    avec certitude enrichissent `memoire_ia.json` ; une diapositive au titre nouveau est comparée à tout ce qui a déjà été vu ;
  - correspondance approximative des en-têtes mal orthographiés (« REALISATION/CAPACITE ») et des étiquettes
    d'indicateurs (« CUMUL DES CAS », « Cumul des confirmés » → `cumul_confirmes`), apprises comme alias ;
  - contrôles de cohérence : vivants + décès = total, carte vs ligne Total du tableau par ZS, date de la page de garde,
    cumul en baisse ou variation incompatible avec les cas du jour (par rapport à la veille) ;
  - facultatif, `--llm` : un modèle de langage propose le pilier des diapositives incertaines (variable
    `ANTHROPIC_API_KEY`). Désactivé par défaut, car les données sont confidentielles.
- En CI, `data/presentations` est ajouté au sparse checkout du dépôt de données (les `.pptx` ne sont jamais
  téléchargés : pas de LFS). Les fichiers `extraction_*.json` doivent donc être versionnés dans ce dépôt.

L'extraction n'est embarquée que dans `piliers.html`, `kpi-piliers.html` et `semaine.html` (toutes provinces) et dans chaque page
province (sa province seulement), pour garder les autres pages légères.

## Cartes (zones de santé et provinces)

Les cartes reprennent **le design de `BDBV2026-Epidemic_Dashboard/index.html`** :
- même bibliothèque (Leaflet 1.9.4 depuis unpkg). En revanche, **pas de fond de carte** (pas de tuiles CARTO/OSM ni pays voisins). Deux vues :
  - **vue générale** (`index.html`, et Zones de santé avec « Toutes les provinces ») : la **forme de la RDC**, où les autres provinces forment une silhouette gris clair avec leurs limites, et où les **provinces concernées sont colorées** par zone de santé et cernées d'un contour brun. La vue est cadrée et bornée sur la RDC ;
  - **vue d'une province** (pages `province-<nom>.html`, et Zones de santé avec une province choisie) : **seule la province est découpée**. On voit ses ZS et son contour rouge, rien d'autre. Le cadrage, les limites de déplacement et la recherche de ZS se limitent à la province ;
- même rampe de couleurs de la marque (`OUTBREAK`, en échelle logarithmique pour les effectifs) ;
- mêmes bordures de ZS (`#111`, épaisseur qui suit le zoom) et mêmes contours de province (`#9b7d4e`, dans leur propre couche) ;
- même survol ambre (`#ffae42`) avec infobulle, et même bordure foncée sur la ZS sélectionnée ;
- mêmes panneaux flottants Couche, Légende et Zone, qu'on peut replier.

On les trouve à trois endroits :
- `index.html` : en plein écran, vue générale ;
- **Zones de santé** : vue générale, ou la province choisie seule ;
- **pages province** : la province seule.

Les couches ne mélangent jamais « 0 » et « absent » :
- **gris** : 0 / aucun cas rapporté ;
- **pointillés** : tableau non extrait (collé en image) ou indicateur non rapporté (les 21 jours en Ituri, par exemple) ;
- **sans remplissage** : présentation non reçue à cette date.

**Hors ligne**, si unpkg n'est pas joignable, la page bascule automatiquement sur une carte SVG simplifiée, avec la même géométrie et la même rampe de couleurs.

- **Source de la géométrie : le shapefile de `BDBV2026-Data`**, soit `data/shapefiles/DRC_Health_zones.shp` avec ses fichiers `.dbf`, `.shx`, `.prj` et `.cpg` (GRID3 COD health zones v8.0, colonnes `Nom` / `PROVINCE` / `ZSCode`). Ce sont les mêmes noms de ZS que `BDBV2026-Provincial_Reports/config/health_zones.csv`, qui est extrait du même `.dbf`. Le fichier est lu directement par `Scripts/common/shapefile_reader.py`, en Python standard (sans pyshp ni geopandas). Le lecteur vérifie que le `.prj` est bien en WGS84 et lit l'encodage dans le `.cpg`.
  - **En local :** il suffit que `BDBV2026-Data` soit cloné à côté de ce dépôt (chemin par défaut). La variable `GEO_SOURCE` permet de pointer vers un autre `.shp`, ou vers un GeoJSON aux mêmes colonnes.
  - **En CI :** `build-dashboard.yml` et `pr-preview.yml` ne récupèrent que `data/shapefiles/DRC_Health_zones.*`. Le dépôt est public et le shapefile n'est pas en LFS.
- **Traitement :** `Scripts/common/geo.py`. Le shapefile compte ~4,1 millions de sommets. Ils sont d'abord ramenés sur une grille de 0,001° (~110 m). Cette étape est déterministe : deux ZS voisines gardent exactement les mêmes sommets sur leur frontière commune. Ensuite :
  - les ZS sont simplifiées *par segment partagé*, si bien que deux voisines gardent une seule et même frontière ;
  - le contour d'une province est fait de toutes les arêtes de ses ZS, sauf les arêtes intérieures (partagées avec une autre ZS de la même province, ou qui la longent à moins de ~330 m, car les polygones source se chevauchent un peu).

  C'est l'équivalent, sans shapely, de `_clean_coverage` et `build_province_boundaries` du dashboard épidémique.
- **Sortie et cache :** `assets/geo.js` (~1,7 Mo) contient les polygones des ZS et les contours **des provinces présentes dans les données**. Il contient aussi, sous `country`, la silhouette du reste de la RDC : les ZS des autres provinces, simplifiées à ~1 km et sans attributs, ainsi que leurs contours de province. Une nouvelle province apparaît automatiquement au build suivant. Le calcul prend ~40 s. La première ligne de `geo.js` porte une clé (empreinte du `.shp` et du `.dbf`, de la liste des provinces et du code). Tant que rien ne change, le fichier est réutilisé tel quel au build suivant.

Lecture de la carte : une ZS **hachurée** appartient à une province dont la présentation a été reçue mais dont le tableau n'a pas pu être lu (collé en image), ou qui ne rapporte pas l'indicateur choisi (par exemple les 21 jours pour l'Ituri). Une ZS **grise** n'a aucun cas rapporté. Une ZS **blanche** appartient à une province dont la présentation n'a pas été reçue à cette date.

## Structure

```
Scripts/
  build_dashboard.py      orchestrateur : payload -> assets -> pages
  common/
    paths.py              chemins + variables d'environnement (BUILD_DIR, QA_LOG, DATA_ROOT)
    data_sources.py       lecture de build/manifest.json, build/timeseries/*.csv, qa/qa_log.csv
                          et des extraction_*.json des présentations (load_extractions)
    shapefile_reader.py   lecture du shapefile (.shp/.dbf/.prj/.cpg), bibliothèque standard
    geo.py                géométrie des cartes (ZS + contours de provinces) -> assets/geo.js
    payload.py            un payload JSON partagé, embarqué dans chaque page (window.PAYLOAD)
    chrome.py             en-tête, onglets, pied de page
    theme.py              couche CSS de marque optionnelle (Data/Branding/dashboard-theme.css)
  pages/                  un module par page (overview, zones, trends, alerts_contacts, quality, pillars)
                          + province.py : une page province-<nom>.html par province
  assets/
    dashboard.css         styles (thèmes clair et sombre)
    engine.js             moteur JS : graphiques SVG, tableaux triables, sélecteur de date
Data/Branding/            logos (+ dashboard-theme.css facultatif)
output/                   artefacts du build (versionnés)
index.html, zones.html, province-*.html …  copies servies par GitHub Pages
```

Aucune dépendance externe : le build n'utilise que la bibliothèque standard de Python, et les pages n'appellent aucun CDN.

## Build local

Il faut cloner `BDBV2026-Provincial_Reports` **à côté** de ce dépôt, comme pour l'Epidemic Dashboard avec `BDBV2026-Data` :

```
Ebola/
  BDBV2026-Data/                 (data/shapefiles/DRC_Health_zones.* pour les cartes)
  BDBV2026-Provincial_Reports/
  BDBV2026-Provincial_Dashboard/
```

```bash
python Scripts/build_dashboard.py          # écrit output/
open output/index.html
```

Les variables `BUILD_DIR`, `QA_LOG`, `GEO_SOURCE`, `EXTRACTION_DIR` et `DATA_ROOT` permettent de pointer vers d'autres emplacements. Tests : `pip install -r requirements.txt && python -m pytest`.

## Mise en place (une seule fois)

1. Créer `INRB-UMIE/BDBV2026-Provincial_Dashboard` et pousser ce dossier (avec `git lfs install` pour les logos).
2. Créer les secrets :
   - sur **ce** dépôt : `EXTERNAL_REPO_TOKEN`, un PAT fine-grained avec *Contents: Read* sur `BDBV2026-Provincial_Reports`, qui est privé ;
   - sur **BDBV2026-Provincial_Reports** : `DASHBOARD_DISPATCH_TOKEN`, un PAT avec *Contents: Read and write* sur ce dépôt (il sert à envoyer le `repository_dispatch`).
3. *Settings → Actions → General* : **Read and write permissions**.
4. *Settings → Pages* : *Deploy from a branch*, `main`, `/ (root)`. Lire d'abord l'avertissement de confidentialité ci-dessus.
5. Lancer une première fois *Actions → Build dashboard → Run workflow*.
