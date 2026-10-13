"""Moteur de priorités hebdomadaires : agrège la semaine et classe ce qui compte, comme un épidémiologiste.

Pour chaque semaine (lundi → dimanche) et chaque province :

1. Indicateurs de riposte évalués contre leur cible (statut vert / orange / rouge / gris = non rapporté).
   Cibles du tableau de suivi de la riposte Bundibugyo 2026 (CDC, MMWR 75(35), août 2026) et règles de l'OMS
   (21 jours = durée maximale d'incubation et de suivi des contacts ; 42 jours sans nouveau cas = fin de
   transmission, critère OMS de fin d'épidémie) :
     - incidence (nouveaux cas confirmés par jour) et tendance par rapport à la semaine précédente ;
     - zones de santé en transmission active (dernier cas ≤ 21 j), en vigilance (22–42 j), contrôlées (> 42 j) ;
     - extension géographique (nouvelles ZS touchées) et résurgence (ZS de nouveau active) ;
     - contacts suivis : cible > 95 % ;
     - alertes vérifiées / investiguées : cible > 90 % ;
     - suspects validés isolés (transférés au CTE/CT) : cible > 90 % ;
     - positivité des échantillons : cible 0 % ;
     - décès communautaires (hors CTE) : cible 0 ;
     - agents de santé nouvellement infectés : cible 0 ;
     - complétude des présentations reçues.
2. Signaux priorisés : chaque écart à une cible ou évolution défavorable devient un signal noté
   (gravité × poids épidémiologique), du plus urgent au moins urgent. Les bonnes nouvelles (ZS qui
   passent en vigilance ou sous contrôle, baisse de l'incidence) sont gardées à part.
3. Points remontés par les provinces (défis, points saillants, recommandations…) : regroupés quand ils
   se répètent d'un jour à l'autre ou d'une province à l'autre, classés par thème épidémiologique
   (décès communautaires, agents de santé, extension, résistance communautaire, contacts non suivis…).
4. Une lecture de la semaine en quelques phrases.

Tout est calculé en Python standard au moment du build ; le navigateur ne fait qu'afficher.
"""

from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata

REFERENCE = ("Cibles : tableau de suivi de la riposte Bundibugyo 2026, CDC MMWR 75(35) (août 2026) ; "
             "21 et 42 jours : critères de l'OMS (incubation maximale, fin de transmission).")

# id, libellé court, unité, description de la cible
INDICATEURS = [
    ("incidence", "Tendance des cas", "", "baisse des nouveaux cas confirmés d'une semaine à l'autre"),
    ("zs_actives", "ZS en transmission active", "", "aucune ZS avec un cas confirmé dans les 21 derniers jours"),
    ("extension", "Nouvelles ZS touchées", "", "aucune nouvelle ZS touchée"),
    ("suivi_contacts", "Suivi des contacts", "%", "> 95 % des contacts vus chaque jour"),
    ("alertes", "Alertes vérifiées", "%", "> 90 % des alertes vérifiées / investiguées"),
    ("isolement", "Suspects isolés", "%", "> 90 % des suspects validés transférés au CTE/CT"),
    ("positivite", "Positivité labo", "%", "0 % d'échantillons positifs"),
    ("deces_communautaires", "Décès communautaires", "", "0 décès hors CTE"),
    ("agents_sante", "Agents de santé infectés", "", "0 nouvel agent de santé infecté"),
    ("completude", "Présentations reçues", "%", "une présentation chaque jour"),
]
LIBELLES = {i: lib for i, lib, _, _ in INDICATEURS}
CIBLES = {i: c for i, _, _, c in INDICATEURS}

THEMES = [
    # id, libellé, poids, mots-clés (texte simplifié)
    ("deces", "Décès communautaires et enterrements", 5.0,
     ["deces communautaire", "deces communaut", "dcd communaut", "corps", "enterrement", "inhumation", "eds ", "ecumr"]),
    ("agents_sante", "Agents de santé infectés", 5.0,
     ["agent de sante", "agents de sante", "prestataire infect", "ppl infect", "personnel de sante", "ias "]),
    ("extension", "Extension, nouveaux foyers", 5.0,
     ["nouvelle zs", "nouvelles zs", "nouvelle aire", "nouvelles aires", "nouveau foyer", "hotspot", "foyer",
      "flambee", "propagation", "extension de l", "cas importe", "importe"]),
    ("communaute", "Résistance communautaire et sécurité", 4.0,
     ["reticen", "resistance", "refus", "insecurit", "securitaire", "attaque", "hostil", "menace", "conflit"]),
    ("contacts", "Contacts non suivis", 4.0,
     ["perdus de vue", "pdv", "jamais vus", "non vus", "contacts non", "non suivi", "suivi des contacts", "listage",
      "contact"]),
    ("isolement", "Isolement et prise en charge", 3.5,
     ["isolement", "isole", "evade", "fugue", "transfert", "ambulance", "lits", "cte", "prise en charge", "pec"]),
    ("labo", "Laboratoire et délais", 3.0,
     ["delai de rendu", "delai des resultats", "delai entre", "prelevement", "echantillon", "resultats de", "reactif",
      "laboratoire", "labo ", "genexpert", "swab"]),
    ("surveillance", "Surveillance et alertes", 3.0,
     ["alerte", "recherche active", "notification", "investigation", "completude", "promptitude", "surveillance"]),
    ("pci", "PCI / WASH", 2.5,
     ["pci", "epi", "hygien", "decontamin", "triage", "dechet", "kit pci", "kits pci", "kits d hygiene", "wash", "chlore",
      "latrine", "incinerat"]),
    ("vaccination", "Vaccination", 2.5, ["vaccin", "ervebo", "ring vaccin"]),
    ("ressources", "Logistique et ressources", 2.0,
     ["carburant", "motivation", "prime", "paie", "paiement", "intrant", "rupture", "moyen de transport", "moto",
      "vehicule", "internet", "ordinateur", "tablette", "mobilite", "logisti", "financ", "budget"]),
    ("autres", "Coordination et autres", 1.0, []),
]
THEME_LIBELLE = {t: lib for t, lib, _, _ in THEMES}
SECTION_POIDS = {"defis": 1.0, "points_saillants": 0.8, "recommandations": 0.7, "planification": 0.4, "realisations": 0.3}
NIVEAUX = ("critique", "eleve", "modere", "info")


# ------------------------------------------------------------------ utilitaires
def simp(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").replace("’", "'")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def isnum(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def lundi(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def jours_entre(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def date_fr(iso: str) -> str:
    try:
        return dt.date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(iso or "")


def pct(n, d):
    return round(100 * n / d, 1) if isnum(n) and isnum(d) and d > 0 else None


def statut_pct(v, vert, orange):
    """vert si v ≥ vert, orange si v ≥ orange, sinon rouge (gris si inconnu)."""
    if v is None:
        return "nd"
    return "ok" if v >= vert else "attention" if v >= orange else "critique"


def fmt(v) -> str:
    if not isnum(v):
        return "–"
    return f"{v:,.0f}".replace(",", " ") if abs(v - round(v)) < 1e-9 else f"{v:.1f}".replace(".", ",")


# ------------------------------------------------------------------ données d'une province à une date
class Donnees:
    def __init__(self, summary, cases, extraction):
        self.summary = {(r["date"], r["province"]): r for r in summary}
        self.cases: dict[tuple, list] = {}
        for r in cases:
            self.cases.setdefault((r["date"], r["province"]), []).append(r)
        self.ext = {(r["date"], r["province"]): r for r in extraction}
        self.dates = sorted({d for d, _ in self.summary} | {d for d, _ in self.ext})
        self.provinces = sorted({p for _, p in self.summary} | {p for _, p in self.ext})

    def recue(self, d, p) -> bool:
        s = self.summary.get((d, p))
        return bool((s and s.get("presentation_recue")) or (d, p) in self.ext)

    def cle(self, d, p, k):
        v = ((self.ext.get((d, p)) or {}).get("cles") or {}).get(k) or {}
        return v.get("n") if isnum(v.get("n")) else None

    def cle_du_jour(self, d, p, k):
        """Valeur du jour seulement : « 583 (58,5 %) » ou une étiquette « cumul » désignent un cumul."""
        v = ((self.ext.get((d, p)) or {}).get("cles") or {}).get(k) or {}
        if not isnum(v.get("n")) or "%" in str(v.get("v") or "") or "cumul" in simp(v.get("l") or "") \
                or "cumul" in simp(str(v.get("v") or "")):
            return None
        return v["n"]

    def kpi(self, d, p, pil, k):
        return (((self.ext.get((d, p)) or {}).get("kpi") or {}).get(pil) or {}).get(k)

    def cumul(self, d, p, k="cumul_confirmes"):
        s = self.summary.get((d, p)) or {}
        if isnum(s.get(k)):
            return s[k]
        return self.cle(d, p, k)

    def dernier_avant(self, p, avant: str, k="cumul_confirmes"):
        """(date, valeur) de la dernière valeur connue strictement avant `avant`."""
        for d in reversed([x for x in self.dates if x < avant]):
            v = self.cumul(d, p, k)
            if isnum(v):
                return d, v
        return None, None

    def zones(self, d, p) -> list[dict]:
        return self.cases.get((d, p)) or []


def statut_zone(r: dict, date: str):
    """active (dernier cas ≤ 21 j), vigilance (22–42 j), controlee (> 42 j), None si inconnu."""
    j = r.get("jours_depuis_dernier_cas")
    if not isnum(j) and r.get("date_dernier_cas"):
        try:
            j = jours_entre(r["date_dernier_cas"], date)
        except ValueError:
            j = None
    if not isnum(j):
        if isnum(r.get("confirmes_21j")):
            return "active" if r["confirmes_21j"] > 0 else None
        return None
    return "active" if j <= 21 else "vigilance" if j <= 42 else "controlee"


# ------------------------------------------------------------------ signal ZS : nouvelle ZS touchée, ZS réactivée
def _cle_zone(nom: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", simp(nom))


def alertes_zs(summary: list[dict], cases: list[dict], extraction: list[dict]) -> list[dict]:
    """Événements « zone de santé » jour par jour, le signal le plus important d'une riposte Ebola :

    - nouvelle : ZS qui apparaît avec au moins un cas confirmé alors qu'elle n'en avait jamais eu dans les
      tableaux précédents de la province (extension géographique) ;
    - reactivee : ZS de nouveau en transmission active (dernier cas ≤ 21 j, ou cumul en hausse) alors qu'elle
      était en vigilance (22–42 j) ou sous contrôle (> 42 j) au tableau précédent (résurgence) ;
    - carte : hausse du nombre de ZS touchées sur la carte de synthèse, quand la province n'a pas de tableau par
      ZS ce jour-là (ZS non nommée).

    Le premier tableau de chaque province sert de référence (pas d'événement). Une « nouvelle » ZS qui arrive
    avec plus de 3 cas, ou dont le nom n'est pas reconnu, est marquée à vérifier (ligne absente des tableaux
    précédents ou nom écrit autrement ?)."""
    par_pd: dict[tuple, list] = {}
    for r in cases:
        par_pd.setdefault((r["date"], r["province"]), []).append(r)
    cartes = {(r["date"], r["province"]): r.get("cles") or {} for r in extraction}
    dates = sorted({d for d, _ in par_pd} | {d for d, _ in cartes} | {r["date"] for r in summary})
    provinces = sorted({p for _, p in par_pd} | {p for _, p in cartes})
    out = []
    for p in provinces:
        vues: dict[str, tuple] = {}          # clé ZS -> (date, ligne) du dernier tableau où elle avait des cas
        ref = ref_der = None                  # date du premier tableau (référence), du dernier tableau
        carte_prec = None                     # (date, nombre de ZS touchées) de la dernière carte lue
        for d in dates:
            lignes = par_pd.get((d, p)) or []
            if lignes:
                for r in lignes:
                    cum, c21 = r.get("cumul_confirmes"), r.get("confirmes_21j")
                    if not ((isnum(cum) and cum > 0) or (isnum(c21) and c21 > 0)):
                        continue
                    k = _cle_zone(r["zone"])
                    q = vues.get(k)
                    base = {"date": d, "province": p, "zone": r["zone"], "cumul": cum if isnum(cum) else None,
                            "date_dernier_cas": r.get("date_dernier_cas") or None}
                    if q is None and ref is not None:
                        out.append({**base, "type": "nouvelle", "depuis": ref_der, "_cum": cum,
                                    "_hors_ref": r.get("zone_resolved") is False})
                    elif q is not None:
                        dq, rq = q
                        avant, maintenant = statut_zone(rq, dq), statut_zone(r, d)
                        hausse = isnum(cum) and isnum(rq.get("cumul_confirmes")) and cum > rq["cumul_confirmes"]
                        if avant in ("vigilance", "controlee") and (maintenant == "active" or hausse):
                            j = rq.get("jours_depuis_dernier_cas")
                            out.append({**base, "type": "reactivee", "depuis": dq, "statut_avant": avant,
                                        "a_verifier": False,
                                        "texte": f"de nouveau active ; elle était {'en vigilance (22–42 j)' if avant == 'vigilance' else 'sous contrôle (> 42 j)'}"
                                                 + (f", {fmt(j)} j sans cas" if isnum(j) else "") + f" au {date_fr(dq)}"})
                    vues[k] = (d, r)
                if ref is None:
                    ref = d
                ref_der = d
            else:
                n = ((cartes.get((d, p)) or {}).get("zs_touchees") or {}).get("n")
                if isnum(n) and carte_prec and n > carte_prec[1] and (d, p) in cartes:
                    out.append({"date": d, "province": p, "zone": None, "type": "carte", "depuis": carte_prec[0],
                                "n": n - carte_prec[1], "a_verifier": True, "cumul": None, "date_dernier_cas": None,
                                "texte": f"ZS touchées sur la carte de synthèse : {fmt(carte_prec[1])} → {fmt(n)} "
                                         "(pas de tableau par ZS ce jour-là : ZS non nommée)"})
            n = ((cartes.get((d, p)) or {}).get("zs_touchees") or {}).get("n")
            if isnum(n):
                # la carte de synthèse confirme-t-elle les nouvelles ZS du tableau ? (ZS touchées 16 → 17)
                nouv = [e for e in out if e["date"] == d and e["province"] == p and e["type"] == "nouvelle"]
                if nouv and carte_prec and n - carte_prec[1] >= len(nouv):
                    for e in nouv:
                        e["carte"] = f"ZS touchées sur la carte de synthèse : {fmt(carte_prec[1])} → {fmt(n)}"
                carte_prec = (d, n)
    for e in out:
        if e["type"] != "nouvelle":
            continue
        cum, hors_ref = e.pop("_cum"), e.pop("_hors_ref")
        raisons = []
        if isnum(cum) and cum > 3 and not e.get("carte"):
            raisons.append("arrive avec plus de 3 cas : ligne absente des tableaux précédents ?")
        if hors_ref:
            raisons.append("nom non reconnu dans le référentiel des ZS (à rattacher)")
        e["a_verifier"] = bool(raisons)
        e["texte"] = (f"première apparition dans le tableau des cas ({fmt(cum)} confirmé(s))"
                      + (f" ; confirmée par la carte ({e['carte'].split(' : ')[1]})" if e.get("carte") else "")
                      + (" — à vérifier : " + " ; ".join(raisons) if raisons else ""))
    out.sort(key=lambda e: (e["date"], e["province"], e["zone"] or ""))
    return out


# ------------------------------------------------------------------ indicateurs d'une province sur une semaine
def indicateurs_province(D: Donnees, p: str, jours: list[str], jours_prec: list[str], evts: list[dict] | None = None) -> dict:
    recus = [d for d in jours if D.recue(d, p)]
    ind: dict[str, dict] = {}
    if not recus:
        return {"recus": 0, "attendus": len(jours), "indicateurs": {}, "zs": {}, "dernier": None}
    der = recus[-1]

    # incidence : hausse du cumul depuis la dernière valeur connue avant la semaine, rapportée au nombre de jours
    def incidence(jj):
        dates = [d for d in jj if isnum(D.cumul(d, p))]
        if not dates:
            return None
        fin = dates[-1]
        d0, v0 = D.dernier_avant(p, jj[0])
        if d0 is None:
            if len(dates) < 2:
                return None
            d0, v0 = dates[0], D.cumul(dates[0], p)
        n = D.cumul(fin, p) - v0
        nb_j = jours_entre(d0, fin)
        if nb_j <= 0 or n < 0:
            return None
        return {"n": n, "jours": nb_j, "par_jour": n / nb_j, "de": d0, "a": fin}

    def par_cas_du_jour(jj):
        vals = [(d, D.cle(d, p, "cas_jour")) for d in jj if D.recue(d, p)]
        vals = [(d, v) for d, v in vals if isnum(v)]
        if not vals:
            return None
        n = sum(v for _, v in vals)
        return {"n": n, "jours": len(vals), "par_jour": n / len(vals), "de": vals[0][0], "a": vals[-1][0],
                "source": "cas du jour"}

    inc = incidence(jours) or par_cas_du_jour(jours)
    inc_prec = (incidence(jours_prec) or par_cas_du_jour(jours_prec)) if jours_prec else None
    tendance = None
    if inc and inc_prec and inc_prec["par_jour"] > 0:
        tendance = round(100 * (inc["par_jour"] - inc_prec["par_jour"]) / inc_prec["par_jour"])
    elif inc and inc_prec and inc_prec["par_jour"] == 0:
        tendance = 100 if inc["par_jour"] > 0 else 0
    # comparaison fragile : moins de 5 cas, ou semaine précédente estimée sur moins de 3 jours
    fragile = bool(inc and (inc["n"] < 5 or (inc_prec and inc_prec["jours"] < 3)))
    if inc:
        if inc["par_jour"] == 0:
            st = "ok"
        elif tendance is None:
            st = "attention"
        else:
            st = ("attention" if fragile else "critique") if tendance > 20 else "ok" if tendance < -20 else "attention"
        ind["incidence"] = {"statut": st, "valeur": round(inc["par_jour"], 1), "n": inc["n"], "jours": inc["jours"],
                            "tendance": tendance, "periode": [inc["de"], inc["a"]],
                            "precedent": round(inc_prec["par_jour"], 1) if inc_prec else None, "fragile": fragile,
                            "texte": f"{fmt(inc['n'])} nouveaux cas confirmés en {inc['jours']} j ({fmt(inc['par_jour'])}/j)"
                                     + (f", {'+' if tendance > 0 else ''}{tendance} % vs semaine précédente" if tendance is not None else "")}

    # zones de santé : statut 21 / 42 jours, extension, résurgence
    zs = {"active": [], "vigilance": [], "controlee": []}
    jour_zs = next((d for d in reversed(recus) if D.zones(d, p)), None)
    if jour_zs:
        for r in D.zones(jour_zs, p):
            s = statut_zone(r, jour_zs)
            if s:
                zs[s].append(r["zone"])
    # extension et résurgence : événements jour par jour (alertes_zs), datés dans la semaine
    ev = [e for e in (evts or []) if e["province"] == p and e["date"] in jours]
    nouvelles = list(dict.fromkeys(e["zone"] + (" (à vérifier)" if e["a_verifier"] else "") for e in ev if e["type"] == "nouvelle"))
    nouvelles += [f"{fmt(e['n'])} ZS (carte de synthèse)" for e in ev if e["type"] == "carte"]
    resurgence = list(dict.fromkeys(e["zone"] for e in ev if e["type"] == "reactivee"))
    connus = sum(len(v) for v in zs.values())
    if connus or nouvelles or resurgence:
        n_act = len(zs["active"])
        if connus:
            ind["zs_actives"] = {"statut": "ok" if n_act == 0 else "critique" if nouvelles or resurgence else "attention",
                                 "valeur": n_act, "texte": f"{n_act} ZS active(s), {len(zs['vigilance'])} en vigilance, "
                                                           f"{len(zs['controlee'])} contrôlée(s)"}
        ind["extension"] = {"statut": "critique" if nouvelles or resurgence else "ok", "valeur": len(nouvelles) + len(resurgence),
                            "zones": nouvelles, "resurgence": resurgence,
                            "evenements": [{"type": e["type"], "zone": e["zone"], "date": e["date"], "texte": e["texte"]} for e in ev],
                            "texte": (f"nouvelle(s) ZS : {', '.join(nouvelles)}" if nouvelles else "aucune nouvelle ZS")
                                     + (f" ; de nouveau active(s) : {', '.join(resurgence)}" if resurgence else "")}

    # contacts suivis (build)
    vus = sum(D.summary[(d, p)]["contacts_vus"] for d in recus
              if (d, p) in D.summary and isnum(D.summary[(d, p)].get("contacts_vus")) and isnum(D.summary[(d, p)].get("contacts_a_suivre")))
    a_suivre = sum(D.summary[(d, p)]["contacts_a_suivre"] for d in recus
                   if (d, p) in D.summary and isnum(D.summary[(d, p)].get("contacts_vus")) and isnum(D.summary[(d, p)].get("contacts_a_suivre")))
    v = pct(vus, a_suivre)
    if v is not None:
        ind["suivi_contacts"] = {"statut": statut_pct(v, 95, 80), "valeur": v, "n": vus, "d": a_suivre,
                                 "texte": f"{fmt(v)} % des contacts vus ({fmt(vus)} / {fmt(a_suivre)} sur la semaine)"}

    # KPI de l'extraction : sommes n / d sur la semaine
    def petit(x):
        """Moins de 10 événements : l'écart à la cible n'est pas interprétable seul (au plus « attention »)."""
        if x.get("d") is not None and x["d"] < 10 and x["statut"] == "critique":
            x["statut"] = "attention"
            x["texte"] += " — effectif faible"
        return x

    def somme_kpi(pil, k):
        n = d_ = 0
        ok = False
        for d in recus:
            x = D.kpi(d, p, pil, k)
            if x and isnum(x.get("n")) and isnum(x.get("d")) and x["d"] > 0:
                n += x["n"]
                d_ += x["d"]
                ok = True
        return (n, d_) if ok else (None, None)

    n, d_ = somme_kpi("surveillance", "taux_verification")
    if d_:
        v = pct(n, d_)
        ind["alertes"] = petit({"statut": statut_pct(v, 90, 70), "valeur": v, "n": n, "d": d_,
                                "texte": f"{fmt(v)} % des alertes vérifiées ({fmt(n)} / {fmt(d_)})"})
    n, d_ = somme_kpi("surveillance", "taux_transfert")
    if d_:
        v = pct(n, d_)
        ind["isolement"] = petit({"statut": statut_pct(v, 90, 70), "valeur": v, "n": n, "d": d_,
                                  "texte": f"{fmt(v)} % des suspects validés transférés ({fmt(n)} / {fmt(d_)})"})
    n, d_ = somme_kpi("laboratoire", "taux_positivite")
    if d_:
        v = pct(n, d_)
        ind["positivite"] = petit({"statut": "ok" if v < 5 else "attention" if v < 10 else "critique", "valeur": v,
                                   "n": n, "d": d_, "texte": f"{fmt(v)} % de positifs ({fmt(n)} / {fmt(d_)} analysés)"})

    # décès communautaires (cartes) : somme des valeurs du jour
    dc = [D.cle_du_jour(d, p, "deces_communautaires") for d in recus]
    dc = [x for x in dc if isnum(x)]
    if dc:
        tot = sum(dc)
        ind["deces_communautaires"] = {"statut": "ok" if tot == 0 else "critique", "valeur": tot,
                                       "texte": f"{fmt(tot)} décès communautaire(s) rapporté(s) sur {len(dc)} jour(s)"}

    # agents de santé : hausse du cumul sur la semaine
    ppl = [(d, D.cle(d, p, "ppl_touches")) for d in recus]
    ppl = [(d, x) for d, x in ppl if isnum(x)]
    if ppl:
        d0, x0 = None, None
        for d in reversed([x for x in D.dates if x < jours[0]]):
            if isnum(D.cle(d, p, "ppl_touches")):
                d0, x0 = d, D.cle(d, p, "ppl_touches")
                break
        base = x0 if x0 is not None else ppl[0][1]
        hausse = ppl[-1][1] - base
        if hausse >= 0 and (x0 is not None or len(ppl) > 1):
            ind["agents_sante"] = {"statut": "ok" if hausse == 0 else "critique", "valeur": hausse,
                                   "texte": f"+{fmt(hausse)} agent(s) de santé infecté(s) (cumul {fmt(base)} → {fmt(ppl[-1][1])})"}

    # complétude des présentations
    v = pct(len(recus), len(jours))
    ind["completude"] = {"statut": statut_pct(v, 100, 60), "valeur": v, "n": len(recus), "d": len(jours),
                         "texte": f"{len(recus)} présentation(s) reçue(s) sur {len(jours)} jour(s) de rapport"}
    for k, x in ind.items():
        x["cible"] = CIBLES[k]
    return {"recus": len(recus), "attendus": len(jours), "indicateurs": ind, "zs": zs, "dernier": der}


# ------------------------------------------------------------------ signaux priorisés
def signaux(prov: str, res: dict) -> tuple[list[dict], list[dict]]:
    ind, zs = res["indicateurs"], res["zs"]
    out, bons = [], []

    def ajouter(niveau, score, theme, titre, detail, indicateur):
        out.append({"province": prov, "niveau": niveau, "score": round(score, 1), "theme": theme, "titre": titre,
                    "detail": detail, "indicateur": indicateur, "cible": CIBLES.get(indicateur, "")})

    x = ind.get("extension")
    if x and x["statut"] == "critique":
        def detail(types):
            ev = [e for e in x.get("evenements", []) if e["type"] in types]
            return " ; ".join(f"{e['zone'] or 'ZS non nommée'} (le {date_fr(e['date'])}) : {e['texte']}" for e in ev) or x["texte"]
        if x["zones"]:
            ajouter("critique", 95 + len(x["zones"]), "Extension géographique",
                    f"Nouvelle(s) zone(s) de santé touchée(s) : {', '.join(x['zones'])}", detail(("nouvelle", "carte")), "extension")
        if x["resurgence"]:
            ajouter("critique", 93, "Résurgence", f"Transmission de nouveau active : {', '.join(x['resurgence'])}",
                    detail(("reactivee",)), "extension")
    x = ind.get("incidence")
    if x and x.get("tendance") is not None:
        if x["tendance"] > 20 and x["valeur"] > 0:
            if x.get("fragile"):
                ajouter("eleve", 66 + min(10, x["n"]), "Transmission", "Hausse des cas à confirmer",
                        x["texte"] + " — comparaison à confirmer (moins de 5 cas ou semaine précédente incomplète)",
                        "incidence")
            else:
                ajouter("critique", 90 + min(20, x["tendance"] / 10), "Transmission",
                        "Les nouveaux cas augmentent", x["texte"], "incidence")
        elif x["tendance"] < -20:
            bons.append({"province": prov, "titre": "Les nouveaux cas diminuent", "detail": x["texte"]})
    elif x and x["valeur"] > 0:
        ajouter("modere", 40 + min(10, x["valeur"]), "Transmission", "Nouveaux cas confirmés cette semaine",
                x["texte"] + " (pas de semaine précédente pour comparer)", "incidence")
    x = ind.get("agents_sante")
    if x and x["statut"] == "critique":
        ajouter("critique", 85 + x["valeur"], "PCI : agents de santé", "Nouvel(s) agent(s) de santé infecté(s)",
                x["texte"], "agents_sante")
    x = ind.get("deces_communautaires")
    if x and x["statut"] == "critique":
        ajouter("critique", 80 + min(15, x["valeur"]), "Décès communautaires", "Décès confirmés hors CTE",
                x["texte"], "deces_communautaires")
    for k, theme, titre, s_crit, s_att in (
            ("suivi_contacts", "Suivi des contacts", "Contacts insuffisamment suivis", 75, 55),
            ("alertes", "Surveillance", "Alertes insuffisamment vérifiées", 70, 50),
            ("isolement", "Isolement", "Suspects validés non isolés", 72, 52),
            ("positivite", "Laboratoire", "Positivité des échantillons élevée", 65, 45)):
        x = ind.get(k)
        if x and x["statut"] in ("critique", "attention"):
            ecart = abs((x["valeur"] or 0) - {"suivi_contacts": 95, "alertes": 90, "isolement": 90, "positivite": 0}[k])
            ajouter("eleve" if x["statut"] == "critique" else "modere",
                    (s_crit if x["statut"] == "critique" else s_att) + min(10, ecart / 3), theme, titre, x["texte"], k)
    x = ind.get("completude")
    if x and x["statut"] in ("critique", "attention"):
        ajouter("info", 30 + (100 - x["valeur"]) / 10, "Données", "Présentations manquantes", x["texte"], "completude")
    if zs.get("vigilance"):
        bons.append({"province": prov, "titre": f"{len(zs['vigilance'])} ZS en vigilance (22–42 j sans cas)",
                     "detail": ", ".join(zs["vigilance"])})
    if zs.get("controlee"):
        bons.append({"province": prov, "titre": f"{len(zs['controlee'])} ZS sous contrôle (> 42 j sans cas)",
                     "detail": ", ".join(zs["controlee"])})
    return out, bons


def agreger(sig: list[dict]) -> list[dict]:
    """Regroupe les signaux de même nature (même thème, même niveau) : une priorité = un problème, avec la liste
    des provinces concernées, comme dans un rapport épidémiologique. Triées par niveau puis par score."""
    groupes: dict[tuple, dict] = {}
    for x in sig:
        cle = (x["niveau"], x["theme"], re.sub(r"\s*:.*$", "", x["titre"]))
        g = groupes.setdefault(cle, {"niveau": x["niveau"], "theme": x["theme"], "titre": cle[2], "score": 0.0,
                                     "provinces": [], "details": [], "indicateur": x["indicateur"], "cible": x["cible"]})
        g["score"] = max(g["score"], x["score"]) + 1          # plusieurs provinces = plus prioritaire
        if x["province"] not in g["provinces"]:
            g["provinces"].append(x["province"])
        g["details"].append({"province": x["province"], "texte": x["detail"], "titre": x["titre"]})
    out = sorted(groupes.values(), key=lambda g: (NIVEAUX.index(g["niveau"]), -g["score"]))
    for g in out:
        g["score"] = round(g["score"], 1)
    return out


# ------------------------------------------------------------------ points remontés par les provinces
def theme_de(texte: str) -> str:
    texte = re.sub(r"\(responsable[^)]*\)", " ", texte or "")       # « (responsable : …, délai : 30 jours) »
    s = " " + re.sub(r"[^a-z0-9]+", " ", simp(texte)) + " "
    meilleur, score = "autres", 0.0
    for t, _, poids, mots in THEMES:
        n = sum(1 for m in mots if re.search(r"(?<![a-z])" + re.escape(m.strip()), s))
        if n and n * poids > score:
            meilleur, score = t, n * poids
    return meilleur


def mots(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", simp(t))}


def jaccard(a: set, b: set) -> float:
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def points_remontes(extraction: list[dict], jours: list[str], limite: int = 40) -> list[dict]:
    """Défis, points saillants, recommandations… de la semaine : regroupés (même idée répétée d'un jour ou
    d'une province à l'autre), classés par thème puis par score (poids du thème × rubrique × répétition)."""
    items = []
    for r in extraction:
        if r["date"] not in jours:
            continue
        for pl in r.get("piliers") or []:
            for sec, liste in (pl.get("sections") or {}).items():
                if sec not in SECTION_POIDS:
                    continue
                for it in liste:
                    t = (it.get("t") or "").strip()
                    if len(t) < 12 or it.get("o"):
                        continue
                    items.append({"t": t, "date": r["date"], "province": r["province"], "pilier": pl.get("libelle"),
                                  "section": sec, "s": it.get("s")})
    groupes: list[dict] = []
    for it in items:
        m = mots(it["t"])
        g = next((g for g in groupes if g["section"] == it["section"] and jaccard(m, g["mots"]) >= 0.6), None)
        if g is None:
            g = {"section": it["section"], "mots": set(m), "textes": {}, "provinces": set(), "dates": set(),
                 "piliers": set()}
            groupes.append(g)
        g["textes"].setdefault(it["province"], (it["date"], it["t"]))
        if it["date"] >= g["textes"][it["province"]][0]:
            g["textes"][it["province"]] = (it["date"], it["t"])
        g["provinces"].add(it["province"])
        g["dates"].add(it["date"])
        g["piliers"].add(it["pilier"] or "")
        g["mots"] |= m
    out = []
    for g in groupes:
        texte = max(g["textes"].values())[1]
        th = theme_de(" ".join(t for _, t in g["textes"].values()))
        poids = next(p for t, _, p, _ in THEMES if t == th)
        n_j, n_p = len(g["dates"]), len(g["provinces"])
        score = poids * SECTION_POIDS[g["section"]] * (1 + 0.5 * (n_p - 1)) * (1 + 0.2 * min(4, n_j - 1))
        out.append({"texte": texte, "theme": th, "theme_libelle": THEME_LIBELLE[th], "section": g["section"],
                    "provinces": sorted(g["provinces"]), "jours": n_j, "dates": sorted(g["dates"]),
                    "piliers": sorted(x for x in g["piliers"] if x), "score": round(score, 2),
                    "persistant": n_j >= 3 and g["section"] == "defis"})
    out.sort(key=lambda x: -x["score"])
    return out[:limite]


# ------------------------------------------------------------------ semaine complète
def lecture(semaine: dict) -> list[str]:
    """Quelques phrases, comme les écrirait un épidémiologiste en tête de rapport."""
    g = semaine["global"]
    ph = []
    ev = semaine.get("alertes_zs") or []
    nv = [f"{e['zone']} ({e['province']})" for e in ev if e["type"] == "nouvelle"]
    nv += [f"{fmt(e['n'])} ZS non nommée(s) ({e['province']}, carte de synthèse)" for e in ev if e["type"] == "carte"]
    ra = [f"{e['zone']} ({e['province']})" for e in ev if e["type"] == "reactivee"]
    if nv or ra:
        ph.append("Signal à ne pas manquer : " + " ; ".join(
            ([f"nouvelle(s) zone(s) de santé touchée(s) : {', '.join(dict.fromkeys(nv))}"] if nv else [])
            + ([f"zone(s) de santé de nouveau active(s) après plus de 21 jours sans cas : {', '.join(dict.fromkeys(ra))}"] if ra else []))
            + ".")
    if isnum(g.get("nouveaux_cas")):
        t = f"{fmt(g['nouveaux_cas'])} nouveaux cas confirmés rapportés"
        if g.get("provinces_en_hausse"):
            t += f" ; hausse dans : {', '.join(g['provinces_en_hausse'])}"
        if g.get("provinces_en_baisse"):
            t += f" ; baisse dans : {', '.join(g['provinces_en_baisse'])}"
        ph.append(t + ".")
    if g.get("zs_actives") is not None:
        ph.append(f"Transmission active dans {g['zs_actives']} zone(s) de santé (cas dans les 21 derniers jours), "
                  f"{g['zs_vigilance']} en vigilance (22–42 jours), {g['zs_controlees']} sous contrôle (> 42 jours).")
    def minus(t):
        return t[:1].lower() + t[1:]
    crit = [g for g in semaine["priorites"] if g["niveau"] == "critique"]
    if crit:
        ph.append("Priorités : " + " ; ".join(f"{minus(g['titre'])} ({', '.join(g['provinces'])})" for g in crit[:4]) + ".")
    elev = [g for g in semaine["priorites"] if g["niveau"] == "eleve"]
    if elev:
        ph.append("À renforcer : " + " ; ".join(f"{minus(g['titre'])} ({', '.join(g['provinces'])})" for g in elev[:4]) + ".")
    if g.get("provinces_absentes"):
        ph.append("Données incomplètes : " + ", ".join(g["provinces_absentes"]) + ".")
    return ph


def semaines(summary: list[dict], cases: list[dict], extraction: list[dict]) -> dict:
    """{lundi ISO: {jours, provinces: {p: indicateurs}, signaux, bonnes_nouvelles, points, global, lecture}}."""
    D = Donnees(summary, cases, extraction)
    evts = alertes_zs(summary, cases, extraction)
    par_semaine: dict[str, list[str]] = {}
    for d in D.dates:
        par_semaine.setdefault(lundi(d), []).append(d)
    cles = sorted(par_semaine)
    out = {}
    for i, l in enumerate(cles):
        jours = par_semaine[l]
        prec = par_semaine[cles[i - 1]] if i else []
        provs, sig, bons = {}, [], []
        for p in D.provinces:
            res = indicateurs_province(D, p, jours, prec, evts)
            provs[p] = res
            if res["recus"]:
                s, b = signaux(p, res)
                sig += s
                bons += b
        sig.sort(key=lambda s: (NIVEAUX.index(s["niveau"]), -s["score"]))
        zs_tot = {k: sum(len(provs[p]["zs"].get(k, [])) for p in provs) for k in ("active", "vigilance", "controlee")}
        inc = [(p, provs[p]["indicateurs"].get("incidence")) for p in provs]
        inc = [(p, x) for p, x in inc if x]
        g = {
            "nouveaux_cas": sum(x["n"] for _, x in inc) if inc else None,
            "provinces_en_hausse": [p + (" (à confirmer)" if x.get("fragile") else "") for p, x in inc
                                    if (x.get("tendance") or 0) > 20],
            "provinces_en_baisse": [p for p, x in inc if (x.get("tendance") or 0) < -20],
            "zs_actives": zs_tot["active"], "zs_vigilance": zs_tot["vigilance"], "zs_controlees": zs_tot["controlee"],
            "provinces_absentes": [p for p in provs if provs[p]["recus"] < len(jours)],
            "n_critiques": sum(s["niveau"] == "critique" for s in sig),
        }
        sem = {"lundi": l, "dimanche": (dt.date.fromisoformat(l) + dt.timedelta(days=6)).isoformat(), "jours": jours,
               "provinces": provs, "signaux": sig, "priorites": agreger(sig), "bonnes_nouvelles": bons,
               "points": points_remontes(extraction, jours), "global": g,
               "alertes_zs": [e for e in evts if e["date"] in jours]}
        sem["lecture"] = lecture(sem)
        out[l] = sem
    return out


def definitions() -> dict:
    return {"indicateurs": [{"id": i, "libelle": lib, "unite": u, "cible": c} for i, lib, u, c in INDICATEURS],
            "themes": {t: lib for t, lib, _, _ in THEMES}, "reference": REFERENCE}
