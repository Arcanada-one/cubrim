#!/usr/bin/env python3
"""CUBR-0036 amendment #4 (B3/B4/C5): retarget evolution.json summary onto the
world corpus. Recomputes champion + goal.standings from world-benchmark.json
aggregate_overall. Real numbers only; hypotheses/roadmap/class_race untouched."""
import json

SITE = "/home/dev/cubr-0036-work/cubrim-site"
wb = json.load(open(f"{SITE}/data/world-benchmark.json"))
ev = json.load(open(f"{SITE}/data/evolution.json"))

ov = wb["aggregate_overall"]
flags = wb["archivers"]
ranked = sorted(ov.items(), key=lambda x: x[1])  # best→worst
leader, leader_v = ranked[0]
cub_rank = [a for a, _ in ranked].index("cubrim") + 1
n = len(ranked)

# Short bilingual blurb per archiver (uses the real flag from the JSON).
def desc(a, v, place):
    flag = "competitive scheme selection" if a == "cubrim" else flags.get(a, "")
    flag_ru = "соревновательный выбор схемы" if a == "cubrim" else flags.get(a, "")
    en = f"{a} ({flag}) — aggregate {v:.6f} across silesia/enwik8/canterbury, place #{place}/{n}."
    ru = f"{a} ({flag_ru}) — агрегат {v:.6f} на silesia/enwik8/canterbury, место #{place}/{n}."
    if a == leader:
        en += " The overall leader — the bar Cubrim is chasing."
        ru += " Общий лидер — планка, которую догоняет Cubrim."
    if a == "cubrim":
        en += " That is where Cubrim stands today — no embellishment."
        ru += " Это честное текущее место Cubrim — без прикрас."
    return {"en": en, "ru": ru}

standings = []
for place, (a, v) in enumerate(ranked, start=1):
    standings.append({
        "name": a,
        "aggregate": v,
        "rank": place,
        "is_cubrim": a == "cubrim",
        "is_leader": a == leader,
        "level": "competitive" if a == "cubrim" else flags.get(a, ""),
        "desc": desc(a, v, place),
    })

ev["champion"] = {
    "scheme": ev.get("champion", {}).get("scheme",
              "BwtGeoMix (scheme 11; competitive rail over schemes 7..11)"),
    "aggregate": ov["cubrim"],
    "rank": cub_rank,
    "n_archivers": n,
    "vs_previous_pct": None,
}
ev["goal"] = {
    "beat": f"{leader} · {leader_v:.6f}",
    "leader_name": leader,
    "leader_aggregate": leader_v,
    "standings": standings,
    # legacy keys kept empty so any old consumer degrades gracefully
    "leader_history": [],
    "leader_history_rich": [],
    "rivals": [],
}
ev["corpus"] = wb.get("corpora", [])
ev["source"] = "world-benchmark.json"

json.dump(ev, open(f"{SITE}/data/evolution.json", "w"), ensure_ascii=False, indent=2)
print(f"leader={leader} {leader_v:.6f}  cubrim #{cub_rank}/{n} {ov['cubrim']:.6f}")
print("standings:", " ".join(f"#{s['rank']}{s['name']}={s['aggregate']:.4f}" for s in standings))
print("hypotheses preserved:", len(ev.get("hypotheses", [])), "| class_race:", bool(ev.get("class_race")))
