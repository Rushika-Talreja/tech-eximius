"""Run from C:\\Dev\\defi:  python check_seed.py
Stage 1 checks every YAML in corpus/seed. Stage 2 checks what is in local Qdrant."""
import glob, os, sys
import yaml

REQUIRED = ["doc_id", "kind", "title", "vuln_class", "swc_ids", "cwe_ids",
            "source_url", "license", "summary", "root_cause",
            "exploit_pattern", "remediation", "excerpts"]
problems = 0

print("=== Stage 1: YAML files ===")
files = sorted(glob.glob("corpus/seed/*.yaml"))
print(f"Found {len(files)} files")
for f in files:
    name = os.path.basename(f)[:-5]
    try:
        d = yaml.safe_load(open(f, encoding="utf-8"))
    except Exception as e:
        print(f"FAIL {name}: YAML error: {e}"); problems += 1; continue
    if not isinstance(d, dict):
        print(f"FAIL {name}: not a YAML mapping (got {type(d).__name__})"); problems += 1; continue
    missing = [k for k in REQUIRED if k not in d]
    errs = [f"missing {missing}"] if missing else []
    if d.get("doc_id") != name: errs.append("doc_id != filename")
    if not str(d.get("source_url", "")).startswith("http"): errs.append("bad source_url")
    if not d.get("license"): errs.append("no license")
    if not d.get("cwe_ids"): errs.append("empty cwe_ids")
    for k in ["summary", "root_cause", "exploit_pattern", "remediation"]:
        if len(str(d.get(k, "")).strip()) < 40: errs.append(f"{k} too short")
    for e in d.get("excerpts") or []:
        if len(e) > 300: errs.append("excerpt over 300 chars")
    if errs:
        print(f"FAIL {name}: {errs}"); problems += 1
    else:
        print(f"ok   {name}  {d['swc_ids']} {d['cwe_ids']} {d['vuln_class']}")

print("\n=== Stage 2: local Qdrant ===")
try:
    from qdrant_client import QdrantClient
    c = QdrantClient(path="qdrant_data")
    col = "security_postmortems"
    print("points in collection:", c.count(col).count)
    pts, _ = c.scroll(col, limit=500, with_payload=True, with_vectors=False)
    docs = {}
    for p in pts:
        pl = p.payload or {}
        docs.setdefault(pl.get("doc_id"), []).append(pl)
    print("distinct doc_ids:", len(docs))
    want = {os.path.basename(f)[:-5] for f in files}
    missing = want - set(docs)
    print("missing from Qdrant:", sorted(missing) or "none")
    need = ["doc_id", "chunk_id", "level", "vuln_class", "swc_ids", "cwe_ids",
            "source_url", "license", "content_hash", "text"]
    for k, v in sorted(docs.items(), key=lambda x: str(x[0])):
        levels = sorted({str(x.get("level")) for x in v})
        absent = [n for n in need if n not in v[0]]
        print(f"  {k}: {len(v)} points, levels={levels}, missing payload fields={absent or 'none'}")
    print("Tip: run ingest a 2nd time, then re-run this. The point count must not change.")
    c.close()
except Exception as e:
    print("Qdrant check could not run:", e)
    print("(If the lock error appears, close any other program using qdrant_data.)")
    problems += 1

print("\nRESULT:", "all good" if problems == 0 else f"{problems} problem(s), see above")