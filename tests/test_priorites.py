"""Moteur de priorités hebdomadaires (common/priorites.py) : règles épidémiologiques sur de petits jeux de données."""
from common import priorites as PR


def _sum(date, prov, **kw):
    r = {"date": date, "province": prov, "presentation_recue": True, "cumul_confirmes": None, "cumul_deces": None,
         "contacts_a_suivre": None, "contacts_vus": None}
    r.update(kw)
    return r


def _zone(date, prov, zone, cumul, jours):
    return {"date": date, "province": prov, "zone": zone, "cumul_confirmes": cumul, "jours_depuis_dernier_cas": jours,
            "date_dernier_cas": None, "confirmes_21j": None}


def test_week_grouping_and_who_rules():
    summary = [_sum("2026-09-29", "A", cumul_confirmes=100, contacts_a_suivre=100, contacts_vus=99),
               _sum("2026-10-06", "A", cumul_confirmes=130, contacts_a_suivre=100, contacts_vus=70),
               _sum("2026-10-08", "A", cumul_confirmes=160, contacts_a_suivre=100, contacts_vus=75)]
    cases = [_zone("2026-09-29", "A", "Z1", 100, 2), _zone("2026-09-29", "A", "Z2", 0, None),
             _zone("2026-10-08", "A", "Z1", 150, 1), _zone("2026-10-08", "A", "Z2", 10, 3),
             _zone("2026-10-08", "A", "Z3", 0, 30)]
    ext = [{"date": "2026-10-08", "province": "A", "cles": {"ppl_touches": {"n": 12, "v": "12", "l": "cumul"},
                                                            "deces_communautaires": {"n": 3, "v": "3", "l": "DECES COMMUNAUTAIRES"}},
            "kpi": {"laboratoire": {"taux_positivite": {"n": 30, "d": 100}}}, "piliers": []},
           {"date": "2026-09-29", "province": "A", "cles": {"ppl_touches": {"n": 10, "v": "10", "l": "cumul"},
                                                            "deces_communautaires": {"n": 583, "v": "583 (58,5%)", "l": "Décès communautaire"}},
            "kpi": {}, "piliers": []}]
    S = PR.semaines(summary, cases, ext)
    assert list(S) == ["2026-09-28", "2026-10-05"]
    w = S["2026-10-05"]["provinces"]["A"]
    ind = w["indicateurs"]
    assert ind["suivi_contacts"]["statut"] == "critique" and ind["suivi_contacts"]["valeur"] == 72.5     # < 80 %
    assert ind["extension"]["zones"] == ["Z2 (à vérifier)"]                      # nouvelle ZS, arrivée avec 10 cas
    assert ind["agents_sante"]["valeur"] == 2 and ind["agents_sante"]["statut"] == "critique"
    assert ind["positivite"]["statut"] == "critique"                             # 30 % ≥ 10 %
    assert ind["deces_communautaires"]["valeur"] == 3                            # valeur du jour seulement
    assert set(w["zs"]["active"]) == {"Z1", "Z2"} and w["zs"]["vigilance"] == ["Z3"]       # 21 / 42 jours
    assert "deces_communautaires" not in S["2026-09-28"]["provinces"]["A"]["indicateurs"]  # « 583 (58,5 %) » = cumul
    prio = S["2026-10-05"]["priorites"]
    assert prio[0]["niveau"] == "critique" and all(p["provinces"] == ["A"] for p in prio)
    niveaux = [p["niveau"] for p in prio]
    assert niveaux == sorted(niveaux, key=PR.NIVEAUX.index)                      # triées par gravité
    assert S["2026-10-05"]["lecture"] and "Priorités" in " ".join(S["2026-10-05"]["lecture"])


def test_small_numbers_are_not_critical():
    summary = [_sum("2026-10-06", "B")]
    ext = [{"date": "2026-10-06", "province": "B", "cles": {},
            "kpi": {"surveillance": {"taux_transfert": {"n": 0, "d": 1}}}, "piliers": []}]
    ind = PR.semaines(summary, [], ext)["2026-10-05"]["provinces"]["B"]["indicateurs"]
    assert ind["isolement"]["statut"] == "attention" and "effectif faible" in ind["isolement"]["texte"]


def test_points_are_grouped_and_ranked_by_theme():
    def row(date, prov, defis):
        return {"date": date, "province": prov, "cles": {}, "kpi": {},
                "piliers": [{"libelle": "Coordination", "sections": {"defis": [{"t": t} for t in defis]}}]}
    ext = [row("2026-10-06", "A", ["Réticence et résistance communautaire à Mambasa", "Pas de kits informatiques"]),
           row("2026-10-07", "A", ["Réticence et résistance communautaire à Mambasa"]),
           row("2026-10-07", "B", ["Réticence et résistance communautaire à Mambasa", "Retard de paiement des primes"])]
    pts = PR.points_remontes(ext, ["2026-10-06", "2026-10-07"])
    assert pts[0]["theme"] == "communaute" and pts[0]["provinces"] == ["A", "B"] and pts[0]["jours"] == 2
    assert PR.theme_de("Pas d’extincteur d’urgence") != "isolement"            # « cte » n'est pas dans « extincteur »
    assert PR.theme_de("Faible capacité d'accueil (responsable : Ministère, délai : 30 jours)") != "labo"


def test_alertes_zs_nouvelle_reactivee_carte():
    summary = []
    cases = [_zone("2026-09-29", "A", "Z1", 10, 2), _zone("2026-09-29", "A", "Z2", 4, 30), _zone("2026-09-29", "A", "Z3", 2, 50),
             _zone("2026-10-06", "A", "Z1", 12, 1), _zone("2026-10-06", "A", "Z2", 5, 3), _zone("2026-10-06", "A", "Z3", 2, 57),
             _zone("2026-10-06", "A", "Z4", 1, 2),
             _zone("2026-09-29", "B", "Y1", 3, 5)]                       # B : un seul tableau = référence
    carte = lambda n: {"zs_touchees": {"n": n, "v": f"{n}/10"}}
    ext = [{"date": "2026-09-29", "province": "A", "cles": carte(3)}, {"date": "2026-10-06", "province": "A", "cles": carte(4)},
           {"date": "2026-09-29", "province": "C", "cles": carte(2)}, {"date": "2026-10-06", "province": "C", "cles": carte(3)}]
    ev = PR.alertes_zs(summary, cases, ext)
    par = {(e["province"], e["zone"], e["type"]) for e in ev}
    assert ("A", "Z4", "nouvelle") in par                       # première apparition
    assert ("A", "Z2", "reactivee") in par                      # vigilance (30 j) -> active (3 j)
    assert not any(e["zone"] in ("Z1", "Z3") for e in ev)       # toujours active / toujours sous contrôle
    assert ("C", None, "carte") in par                          # pas de tableau : hausse sur la carte
    assert not any(e["province"] == "B" for e in ev)            # premier tableau = référence, pas d'alerte
    z4 = next(e for e in ev if e["zone"] == "Z4")
    assert not z4["a_verifier"] and "carte" in z4               # 1 cas, confirmé par la carte 3 -> 4
    S = PR.semaines(summary, cases, ext)
    w = S["2026-10-05"]
    assert w["lecture"][0].startswith("Signal à ne pas manquer")
    assert w["priorites"][0]["niveau"] == "critique" and {e["zone"] for e in w["alertes_zs"]} >= {"Z4", "Z2"}
