#!/usr/bin/env python3
"""A scorer that reads ONLY the exported model file plus observations.

This exists to prove the model export is COMPLETE. It imports nothing from the engine: if a
rule still lives in engine code rather than in the model file, this scorer produces a
different answer and `test_model_parity.py` fails. That is the whole point — it is the guard
that keeps `DAMM-v1.7-model.json` canonical rather than merely descriptive, and it is the
reference any consumer (DAR Studio) implements against.

Observations payload: {indicator_id: {value, cls, level, year, src, tier, url}} — the same
shape the engine consumes, kept separate from the model as the release gate requires.
"""
import json
from decimal import Decimal, ROUND_HALF_UP


def r2(x):
    """Half-up to 2dp — the workbook is the source of truth and Python's banker's rounding
    disagrees with it at exact .xx5, which would band a mean differently."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class Scorer:
    def __init__(self, model):
        self.m = model
        self.ind = {i["id"]: i for i in model["indicators"]}
        self.cfg = model["config"]
        self.uc_ids = list(model["use_cases"].keys())

    # --- per-row -----------------------------------------------------------------
    def evidence_class(self, r):
        v = r.get("value")
        if v is None or v == "":                      return ""
        if isinstance(v, (int, float)):               return "Measured"
        if "DATA GAP" in str(v).upper():              return "Gap"
        if r.get("src") and r.get("tier") != "T5":    return "Documented"
        return "Judged"

    def level(self, iid, r, cls):
        if cls in ("", "Gap"):                        return None
        d = self.ind[iid]
        if cls == "Measured" and d["thresholds"]:
            v, th = r["value"], d["thresholds"]
            hi = d["direction"] == "higher-is-better"
            lv = 1
            for k, t in enumerate(th):
                if (hi and v >= t) or (not hi and v <= t):
                    lv = k + 2
            return lv
        return r.get("level")

    def stale(self, r, cls):
        y = r.get("year")
        return bool(y and cls != "Gap" and y < self.cfg["assessment_year"] - self.cfg["staleness_years"])

    def band(self, x):
        for b in self.m["bands"]:
            if b["lo"] <= x < b["hi"]:
                return b["name"]
        return "—"

    # --- assessment --------------------------------------------------------------
    def run(self, obs):
        rows = {}
        for iid, d in self.ind.items():
            r = obs[iid]
            cls = r.get("cls") or self.evidence_class(r)
            lvl = r["level"] if "level" in r else self.level(iid, r, cls)
            rows[iid] = {"cls": cls, "level": lvl, "stale": self.stale(r, cls),
                         "pillar": d["pillar"], "layer": d["layer"]}

        out = {"pillars": {}, "layers": {}, "prereq": {}, "matrix": {}}

        for p in self.m["pillars"]:
            rs = [v for v in rows.values() if v["pillar"] == p]
            lv = [v["level"] for v in rs if v["level"] is not None]
            comp = {c: sum(1 for v in rs if v["cls"] == c) for c in ("Measured", "Documented", "Judged", "Gap")}
            rated = len(lv)
            held = sum(1 for v in rs if v["level"] is None and v["cls"] != "Gap")
            jr = sum(1 for v in rs if v["cls"] == "Judged" and v["level"] is not None)
            mean = r2(sum(lv) / len(lv)) if lv else None
            out["pillars"][p] = {
                "n": len(rs), "rated": rated, "held": held, "mean": mean,
                "band": self.band(mean) if mean else "Not rated",
                "weak": (jr + comp["Gap"] + held) > (rated - jr),
                "comp": comp, "stale": sum(1 for v in rs if v["stale"]),
            }

        for L in self.m["layers"]:
            lv = [v["level"] for v in rows.values() if v["layer"] == L and v["level"] is not None]
            out["layers"][L] = r2(sum(lv) / len(lv)) if lv else None

        F, T = out["layers"]["Foundation"], out["layers"]["Transformation"]
        out["leapfrog"] = {"gap": r2(F - T) if F and T else None}

        for iid, d in self.ind.items():
            if not d["prerequisite"]:
                continue
            v = rows[iid]
            if v["cls"] == "Gap" or v["level"] is None: st = "Unverified"
            elif v["level"] >= 3:                       st = "Present"
            elif v["level"] == 2:                       st = "Present (narrow)"
            else:                                       st = "Absent"
            out["prereq"][iid] = {"kind": d["prerequisite"], "status": st}

        P = out["prereq"]
        uni = lambda s: [i for i, v in P.items() if v["kind"] == "UNIVERSAL" and v["status"] == s]
        blk, unv, nrw = uni("Absent"), uni("Unverified"), uni("Present (narrow)")

        for uc in self.uc_ids:
            pres = [(i, v["status"]) for i, v in P.items()
                    if v["kind"].startswith("UC:")
                    and (uc in v["kind"] or (v["kind"] == "UC:AI" and uc == "AGI"))]
            bear = [i for i, d in self.ind.items()
                    if (uc in d["use_cases"] or "ALL" in d["tags"]) and rows[i]["level"] is not None]
            lv = [rows[i]["level"] for i in bear]
            mean = r2(sum(lv) / len(lv)) if lv else None
            enab = [rows[i]["level"] for i in bear if self.ind[i]["pillar"] not in ("A1", "O1")]

            if blk:                                        st, why = "Blocked", "Universal: " + ", ".join(blk)
            elif any(s == "Absent" for _, s in pres):      st, why = "Blocked", ", ".join(i for i, s in pres if s == "Absent")
            elif unv:                                      st, why = "Unverified", "universal unverified: " + ", ".join(unv)
            elif any(s == "Unverified" for _, s in pres):  st, why = "Unverified", ", ".join(i for i, s in pres if s == "Unverified")
            elif any("narrow" in s for _, s in pres) or (mean and mean < self.cfg["readiness_threshold"]):
                st = "Partial"; why = ", ".join(i for i, s in pres if "narrow" in s) or "thin enablers"
            elif nrw:                                      st, why = "Partial", "universal narrow: " + ", ".join(nrw)
            else:                                          st, why = "Ready", ""

            out["matrix"][uc] = {
                "status": st, "why": why, "mean": mean,
                "mean_enabler": r2(sum(enab) / len(enab)) if enab else None,
                "n_bearing": len(bear),
            }
        out["counts"] = {c: sum(1 for v in rows.values() if v["cls"] == c)
                         for c in ("Measured", "Documented", "Judged", "Gap")}
        out["rated"] = sum(1 for v in rows.values() if v["level"] is not None)
        out["held"] = sum(1 for v in rows.values() if v["level"] is None and v["cls"] != "Gap")
        return out
