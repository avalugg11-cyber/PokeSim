"""Results exports without generation selection side effects."""
import os, csv, json
import tournament as T
from storage import write_json, atomic_text

def write_results(cards, meta, out):
    os.makedirs(out, exist_ok=True)
    ts = T.type_stats(cards)
    write_json(os.path.join(out,"results.json"),dict(meta=meta,cards=cards,type_stats=ts),indent=1)
    with atomic_text(os.path.join(out, "type_stats.csv"), newline="") as f:
        w = csv.writer(f)
        w.writerow(["type", "pokemon_with_type", "in_top_20", "avg_win_pct"])
        for r in ts:
            w.writerow([r["type"], r["pokemon"], r["top_n"], r["avg_win_pct"]])
    with atomic_text(os.path.join(out, "results.csv"), newline="") as f:
        w = csv.writer(f)
        w.writerow(["tier", "rank", "name", "moves", "ability", "nature", "evs", "required_item", "type", "elo", "wins", "losses", "draws", "win_pct", "top10_win_pct"])
        for c in cards:
            b = c["moves"]
            m_list = b.get("moves", []) if isinstance(b, dict) else b
            ability = b.get("ability", "") if isinstance(b, dict) else ""
            nature = b.get("nature", "") if isinstance(b, dict) else ""
            
            w.writerow([c["tier"], c["rank"], c["name"], "/".join(m_list), ability, nature, json.dumps(b.get("evs",{}),sort_keys=True) if isinstance(b,dict) else "", c.get("required_item") or "", "/".join(c["types"]), c["elo"],
                        c["wins"], c["losses"], c["draws"], c["win_pct"], c["top10_win_pct"]])
