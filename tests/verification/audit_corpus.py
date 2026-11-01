"""
Independent verification script: Corpus Audit
Validates all corpus files against schema, quality, deduplication, injection, and live source checks.
"""
from __future__ import annotations

import difflib
import glob
import os
import random
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

AGREED_VULN_CLASSES = {
    "reentrancy",
    "unchecked-calls",
    "access-control",
    "delegatecall",
    "uninitialized-state",
    "uninitialized-storage",
    "upgrade-safety",
    "tokenomics-logic",
    "initialization",
    "centralization-risk",
}

REQUIRED_FIELDS = [
    "doc_id",
    "kind",
    "title",
    "vuln_class",
    "swc_ids",
    "source_url",
    "license",
    "summary",
    "root_cause",
    "exploit_pattern",
    "remediation",
]

INJECTION_PATTERNS = [
    r"ignore\s+(?:previous|all)\s+instructions",
    r"you\s+are\s+(?:a|an)\s+",
    r"system\s+prompt",
    r"assistant:",
]


def find_longest_common_word_sequence(s1: str, s2: str) -> tuple[int, str]:
    w1 = [w.lower() for w in re.findall(r"\b\w+\b", s1)]
    w2 = [w.lower() for w in re.findall(r"\b\w+\b", s2)]
    if not w1 or not w2:
        return 0, ""

    matcher = difflib.SequenceMatcher(None, w1, w2)
    match = matcher.find_longest_match(0, len(w1), 0, len(w2))
    longest_words = w1[match.a : match.a + match.size]
    return match.size, " ".join(longest_words)


def strip_html_tags(html: str) -> str:
    clean = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<script.*?</script>", "", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


def run_corpus_audit(corpus_dir: str | Path) -> dict[str, Any]:
    corpus_path = Path(corpus_dir)
    yaml_files = sorted(corpus_path.glob("*.yaml"))

    report: dict[str, Any] = {
        "total_files": len(yaml_files),
        "kinds": Counter(),
        "schema_errors": [],
        "vuln_class_issues": [],
        "length_exceeded": [],
        "near_duplicates": [],
        "duplicate_urls": [],
        "injection_hits": [],
        "sample_checks": [],
        "coverage": {
            "vuln_class_dist": Counter(),
            "year_dist": Counter(),
            "under_represented_classes": [],
            "missing_remediation": [],
        },
    }

    docs: list[dict[str, Any]] = []
    seen_urls: dict[str, str] = {}
    doc_texts: dict[str, str] = {}

    for f in yaml_files:
        try:
            with open(f, encoding="utf-8") as fp:
                data = yaml.safe_load(fp)
        except Exception as e:
            report["schema_errors"].append(f"{f.name}: YAML parse error: {e}")
            continue

        if not isinstance(data, dict):
            report["schema_errors"].append(f"{f.name}: root is not a mapping")
            continue

        docs.append(data)
        doc_id = data.get("doc_id", "")
        kind = data.get("kind", "unknown")
        report["kinds"][kind] += 1

        # Check required fields
        for rf in REQUIRED_FIELDS:
            if rf not in data or data[rf] is None or data[rf] == "":
                report["schema_errors"].append(f"{f.name}: missing or empty required field '{rf}'")

        if doc_id != f.stem:
            report["schema_errors"].append(f"{f.name}: doc_id '{doc_id}' != filename '{f.stem}'")

        # Validate vuln_class
        vclasses = data.get("vuln_class")
        if isinstance(vclasses, list):
            for vc in vclasses:
                report["coverage"]["vuln_class_dist"][vc] += 1
                if vc not in AGREED_VULN_CLASSES:
                    report["vuln_class_issues"].append(
                        f"{doc_id}: vuln_class '{vc}' NOT in agreed class list {sorted(AGREED_VULN_CLASSES)}"
                    )
        else:
            report["schema_errors"].append(f"{doc_id}: vuln_class must be a list")

        # Validate URL
        url = str(data.get("source_url") or "")
        parsed = urllib.parse.urlparse(url)
        if not (parsed.scheme in ("http", "https") and parsed.netloc):
            report["schema_errors"].append(f"{doc_id}: malformed source_url '{url}'")

        if url:
            if url in seen_urls:
                report["duplicate_urls"].append(f"Duplicate URL '{url}' in {doc_id} and {seen_urls[url]}")
            else:
                seen_urls[url] = doc_id

        # Validate license
        lic = data.get("license")
        if not lic:
            report["schema_errors"].append(f"{doc_id}: empty license")

        # Validate date
        dt = data.get("date")
        if dt is not None:
            if isinstance(dt, datetime):
                year_str = str(dt.year)
                report["coverage"]["year_dist"][year_str] += 1
            elif isinstance(dt, str):
                try:
                    parsed_dt = datetime.fromisoformat(dt)
                    report["coverage"]["year_dist"][str(parsed_dt.year)] += 1
                except ValueError:
                    report["schema_errors"].append(f"{doc_id}: invalid date format '{dt}'")
            else:
                report["schema_errors"].append(f"{doc_id}: date must be string, datetime, or null")
        else:
            report["coverage"]["year_dist"]["undated"] += 1

        # Validate loss_usd
        loss = data.get("loss_usd")
        if loss is not None and not isinstance(loss, (int, float)):
            report["schema_errors"].append(f"{doc_id}: loss_usd must be numeric or null, got {type(loss).__name__}")

        # Validate excerpts
        excerpts = data.get("excerpts") or []
        for i, ex in enumerate(excerpts):
            if len(ex) > 300:
                report["length_exceeded"].append(f"{doc_id}: excerpt[{i}] exceeds 300 chars ({len(ex)} chars)")

        # Validate text fields length and style
        for text_col in ["summary", "root_cause", "exploit_pattern", "remediation"]:
            text_val = str(data.get(text_col) or "").strip()
            if not text_val:
                if text_col == "remediation":
                    report["coverage"]["missing_remediation"].append(doc_id)
            if len(text_val) > 1200:
                report["length_exceeded"].append(
                    f"{doc_id}: {text_col} is {len(text_val)} chars (> 1200 chars limit)"
                )

        combined_text = " ".join(
            str(data.get(k) or "") for k in ["summary", "root_cause", "exploit_pattern", "remediation"]
        )
        doc_texts[doc_id] = combined_text

        # Detect prompt injection or instruction-like text
        for pat in INJECTION_PATTERNS:
            if re.search(pat, combined_text, re.IGNORECASE):
                report["injection_hits"].append(f"{doc_id}: matches prompt injection pattern '{pat}'")

        # Check for unexpected foreign URLs inside narrative text
        embedded_urls = re.findall(r"https?://[^\s)\]]+", combined_text)
        for eu in embedded_urls:
            if eu != url:
                report["injection_hits"].append(f"{doc_id}: embedded foreign URL '{eu}' in text")

    # Near-duplicates detection
    doc_ids = list(doc_texts.keys())
    for i in range(len(doc_ids)):
        for j in range(i + 1, len(doc_ids)):
            id1, id2 = doc_ids[i], doc_ids[j]
            ratio = difflib.SequenceMatcher(None, doc_texts[id1], doc_texts[id2]).ratio()
            if ratio >= 0.90:
                report["near_duplicates"].append(f"High text similarity ({ratio:.2f}) between {id1} and {id2}")

    # Underrepresented classes
    for vc in AGREED_VULN_CLASSES:
        cnt = report["coverage"]["vuln_class_dist"].get(vc, 0)
        if cnt < 3:
            report["coverage"]["under_represented_classes"].append(f"{vc} ({cnt} entries)")

    # Sample 12 entries with fixed seed
    random.seed(42)
    sample_size = min(12, len(docs))
    sampled_docs = random.sample(docs, sample_size)

    for sdoc in sampled_docs:
        sid = sdoc.get("doc_id")
        surl = sdoc.get("source_url")
        sum_text = str(sdoc.get("summary") or "")

        sample_info: dict[str, Any] = {
            "doc_id": sid,
            "title": sdoc.get("title"),
            "vuln_class": sdoc.get("vuln_class"),
            "source_url": surl,
            "license": sdoc.get("license"),
            "url_status": None,
            "longest_shared_words": 0,
            "longest_shared_snippet": "",
            "error": None,
        }

        if surl:
            try:
                req = urllib.request.Request(surl, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    sample_info["url_status"] = resp.status
                    html_content = resp.read().decode("utf-8", errors="replace")
                    plain_text = strip_html_tags(html_content)
                    run_len, run_str = find_find = find_longest_common_word_sequence(sum_text, plain_text)
                    sample_info["longest_shared_words"] = run_len
                    sample_info["longest_shared_snippet"] = run_str
            except Exception as e:
                sample_info["error"] = str(e)

        report["sample_checks"].append(sample_info)

    return report


def main() -> int:
    corpus_dir = sys.argv[1] if len(sys.argv) > 1 else "defi/corpus/seed"
    print(f"Auditing corpus in: {corpus_dir}")
    report = run_corpus_audit(corpus_dir)

    print("\n" + "=" * 60)
    print("CORPUS AUDIT SUMMARY REPORT")
    print("=" * 60)
    print(f"Total YAML files found: {report['total_files']}")
    print(f"Counts by kind: {dict(report['kinds'])}")
    print(f"Minimum requirement: 35+ SWC, ~100 incidents")
    swc_count = report["kinds"].get("swc", 0)
    incident_count = report["kinds"].get("postmortem", 0)
    print(f"SWC minimum met? {'YES' if swc_count >= 35 else 'FAIL (' + str(swc_count) + ' < 35)'}")
    print(f"Incident minimum met? {'YES' if incident_count >= 100 else 'FAIL (' + str(incident_count) + ' < 100)'}")

    print("\n--- Schema and Validation Errors ---")
    if report["schema_errors"]:
        for err in report["schema_errors"]:
            print(f"  [ERROR] {err}")
    else:
        print("  None. All basic schema fields conform.")

    print("\n--- Vuln Class Taxonomy Alignment ---")
    if report["vuln_class_issues"]:
        for err in report["vuln_class_issues"]:
            print(f"  [MISMATCH] {err}")
    else:
        print("  All vuln classes belong to the agreed taxonomy.")

    print("\n--- Field Length & Style Checks ---")
    if report["length_exceeded"]:
        for item in report["length_exceeded"]:
            print(f"  [LENGTH] {item}")
    else:
        print("  All field lengths within bounds (<= 1200 chars, excerpts <= 300 chars).")

    print("\n--- Duplicates and Near-Duplicates ---")
    if report["duplicate_urls"]:
        for item in report["duplicate_urls"]:
            print(f"  [DUP URL] {item}")
    if report["near_duplicates"]:
        for item in report["near_duplicates"]:
            print(f"  [NEAR DUP] {item}")
    if not report["duplicate_urls"] and not report["near_duplicates"]:
        print("  None detected.")

    print("\n--- Prompt Injection / Instruction Checks ---")
    if report["injection_hits"]:
        for hit in report["injection_hits"]:
            print(f"  [ALERT] {hit}")
    else:
        print("  Clean. No prompt injection or instruction patterns found.")

    print("\n--- Coverage by Agreed Vuln Class ---")
    for vc, count in report["coverage"]["vuln_class_dist"].items():
        print(f"  {vc}: {count}")
    print("\n--- Under-represented Agreed Classes (< 3 entries) ---")
    for u in report["coverage"]["under_represented_classes"]:
        print(f"  [WARN] {u}")

    print("\n" + "=" * 60)
    print("RANDOM SAMPLE 12 ENTRIES (Seed=42)")
    print("=" * 60)
    for s in report["sample_checks"]:
        print(f"\nDocument ID: {s['doc_id']}")
        print(f"  Title: {s['title']}")
        print(f"  Vuln Class: {s['vuln_class']}")
        print(f"  Source URL: {s['source_url']}")
        print(f"  License: {s['license']}")
        print(f"  HTTP Status: {s['url_status'] or s['error']}")
        print(f"  Longest shared word run with live source: {s['longest_shared_words']} words")
        if s["longest_shared_snippet"]:
            print(f"  Shared snippet: \"{s['longest_shared_snippet']}\"")

    return 0


if __name__ == "__main__":
    sys.exit(main())

