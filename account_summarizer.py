#!/usr/bin/env python3
"""SporeNet Account Summarizer (Codex-ready).

This module ingests a directory of text-based artifacts (``.txt``, ``.md`` and
``.json``) and produces both a Markdown and JSON report describing the content.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple


# -------------------------------
# Simple, built-in stopword list.
# -------------------------------
STOPWORDS = set(
    """
a about above after again against all also am an and any are aren't as at
be because been before being below between both but by
can can't cannot could couldn't
did didn't do does doesn't doing don't down during
each few for from further
had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's
i i'd i'll i'm i've if in into is isn't it it's its itself
let's
me more most mustn't my myself
no nor not now of off on once only or other ought our ours ourselves out over own
same shan't she she'd she'll she's should shouldn't so some such
than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those through to too
under until up very
was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't
you you'd you'll you're you've your yours yourself yourselves
""".split()
)


# -------------------------------
# Thematic domains & keywords
# -------------------------------
THEMATIC_MAP: Dict[str, List[str]] = {
    "OS Core & Runtime": [
        "sporenet",
        "sporecore",
        "sporevm",
        "sporelang",
        "license-gate",
        "k()",
        "runtime",
        "kernel",
        "orchestrator",
        "aeng",
    ],
    "Simulation & Research Engines": [
        "cultivation algebra",
        "operator ide",
        "sim_automata-4447x",
        "reef",
        "mana stream",
        "simulation",
        "operators",
        "recursion",
    ],
    "Index, Market & Exchange": [
        "sci",
        "benchmark",
        "methodology",
        "iosco",
        "futures",
        "market-maker",
        "listing",
        "publication feed",
        "sub-index",
    ],
    "Certification, Identity, Integrity": [
        "sporecert",
        "caas",
        "truthseal",
        "sporeseal",
        "symbolic identity ledger",
        "sil",
        "seif",
        "q-report",
        "treasury ledger",
        "verification",
    ],
    "Developer Docs & Knowledge": [
        "developer handbook",
        "field guide",
        "symbolic systems paradigm",
        "ssp",
        "white paper",
        "api",
        "sdk",
        "binding manifest",
        "docs",
    ],
    "Bio‑mimetic / Cognitive Models": [
        "mendo",
        "plant-brain",
        "morphology",
        "kronos",
        "lineage",
        "forge",
        "polygnome",
        "growth_path",
        "cluster_score",
    ],
    "Topology & Pattern Tools": [
        "topology lab",
        "betti",
        "β₀",
        "β₁",
        "χ",
        "perimeter",
        "png",
        "topology json",
        "simulator",
    ],
    "Standards, Laws, Governance": [
        "iso-4447-s",
        "model law",
        "wipo-sia",
        "seps act",
        "lawbook",
        "governance",
        "treaty",
        "codex",
        "compliance",
    ],
    "Packages, Bundles, Artifacts": [
        ".sporemod",
        ".symq1_packet",
        ".truthseal",
        ".truthbundle",
        ".caas_bundle",
        ".sdk",
        ".sil.json",
        "preamble",
        "archive",
        "capsule",
    ],
    "Compliance & Provenance Plumbing": [
        "c2pa",
        "verifiable credentials",
        "w3c",
        "opentimestamps",
        "originstamp",
        "sha-256",
        "hash",
        "lineage graph",
        "ai disclosure",
        "privacy minimization",
    ],
    "Operating Policies & Governance": [
        "publication policy",
        "restatement",
        "holiday",
        "revocation",
        "audit retention",
        "treasury policy",
        "market comms",
        "circulars",
        "press",
    ],
    "Analytics, Scoring, Wellbeing": [
        "symq-1",
        "telemetry",
        "Δc(t)",
        "s(h,t)",
        "acceptance engine",
        "aeng",
        "metrics",
        "wellbeing",
        "logging keys",
    ],
    "Visual Systems & Narrative": [
        "scene oracle",
        "truthreel",
        "nuclear glyphic emitter",
        "tree→particle→grid",
        "gallery",
        "high hopes",
        "storyboard",
        "cinematic",
    ],
    "Systems, Endpoints, & Files": [
        "/verify/",
        "revocation/list",
        "artifact/",
        "constituents file",
        "ledger digest",
        "architecture diagram",
        "financial forecast",
        "pitch deck",
        "csv",
    ],
}


# Flatten keyword map for quick checks
KEYWORD_TO_DOMAIN: List[Tuple[str, str]] = [
    (kw.lower(), domain) for domain, keywords in THEMATIC_MAP.items() for kw in keywords
]


# -------------------------------
# Helpers
# -------------------------------
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[\(])")


def iter_files(folder: str) -> Iterable[str]:
    """Yield all supported files within ``folder`` recursively."""

    for root, _, files in os.walk(folder):
        for filename in files:
            if filename.lower().endswith((".txt", ".md", ".json")):
                yield os.path.join(root, filename)


def load_text_from_file(path: str) -> str:
    """Return a text representation for *path*.

    JSON files are parsed for ``messages`` arrays when possible. Any errors are
    surfaced to ``stderr`` and an empty string is returned.
    """

    try:
        with open(path, "r", encoding="utf-8") as handle:
            if path.lower().endswith(".json"):
                raw = handle.read()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    return raw  # Not JSON after all – treat as plain text.

                if isinstance(data, dict) and "messages" in data:
                    messages = data["messages"]
                    if isinstance(messages, list):
                        return "\n".join(
                            [
                                msg.get("content", "")
                                if isinstance(msg, dict)
                                else str(msg)
                                for msg in messages
                            ]
                        )

                if isinstance(data, list):
                    return "\n".join(
                        [
                            entry.get("content", "")
                            if isinstance(entry, dict)
                            else str(entry)
                            for entry in data
                        ]
                    )

                return raw

            return handle.read()

    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"[WARN] Failed to read {path}: {exc}\n")
        return ""


def split_sentences(text: str) -> List[str]:
    """Split *text* into sentences using a lightweight heuristic."""

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    tentative = SENTENCE_SPLIT_RE.split(normalized)
    sentences = []
    for sentence in tentative:
        sentence = sentence.strip()
        if len(sentence) >= 10:
            sentences.append(sentence)
    return sentences


def sentence_domain(sentence: str) -> List[str]:
    """Return thematic domains associated with *sentence*."""

    lowered = sentence.lower()
    hits = {domain for keyword, domain in KEYWORD_TO_DOMAIN if keyword in lowered}
    return list(hits) if hits else ["General"]


def tokenize(text: str) -> List[str]:
    """Tokenize *text* into lowercase alphanumeric terms, minus stopwords."""

    tokens = re.findall(r"[A-Za-z0-9_+\-/]+", text.lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def rank_sentences(sentences: List[str], top_k: int = 20) -> List[Tuple[str, float]]:
    """Score sentences by term frequency and return the ``top_k`` best."""

    corpus_tokens: List[str] = []
    for sentence in sentences:
        corpus_tokens.extend(tokenize(sentence))

    frequencies = Counter(corpus_tokens)
    if not frequencies:
        return [(sentence, 0.0) for sentence in sentences[:top_k]]

    scored = []
    for sentence in sentences:
        score = sum(frequencies.get(token, 0) for token in tokenize(sentence))
        scored.append((sentence, float(score)))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]


def balanced_sample(domain_to_ranked: Dict[str, List[Tuple[str, float]]], target_n: int) -> List[str]:
    """Round-robin sampling across domains to gather ``target_n`` sentences."""

    domains = list(domain_to_ranked.keys())
    index = 0
    picked: List[str] = []
    while len(picked) < target_n and any(domain_to_ranked.values()):
        domain = domains[index % len(domains)]
        if domain_to_ranked[domain]:
            sentence, _ = domain_to_ranked[domain].pop(0)
            picked.append(sentence)
        index += 1
        if index > 100_000:  # Safety guard for unexpected loops.
            break

    return picked[:target_n]


DATE_PATTERN = re.compile(
    r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b"
)


def extract_dates(text: str) -> List[str]:
    """Return unique ISO-like dates discovered in *text*."""

    found = {"-".join(match) for match in DATE_PATTERN.findall(text)}
    return sorted(found)


@dataclass
class Report:
    """Structured representation of a summarised account."""

    title: str
    created_at: str
    executive_summary: List[str]
    canonical_100_sentences: List[str]
    inventories: Dict[str, List[str]]
    timeline_dates: List[str]
    totals: Dict[str, Any]


def maybe_refine_with_llm(section_name: str, text: str) -> str:
    """Optionally refine *text* with an OpenAI-powered editor."""

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return text

    try:  # pragma: no cover - network optional
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        prompt = (
            "Refine the following section for clarity, cohesion, and professional tone "
            "while preserving all facts.\n"
            f"Section: {section_name}\n"
            "---\n"
            f"{text}\n"
            "---\n"
            "Constraints: Keep the length roughly the same; use plain, precise American "
            "English; keep bullet numbering intact."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise technical editor."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # pragma: no cover - best effort
        sys.stderr.write(f"[WARN] LLM refinement skipped: {exc}\n")
        return text


def build_report(input_dir: str, title: str, target_sentences: int = 100) -> Report:
    """Assemble a :class:`Report` from the artifacts stored in *input_dir*."""

    all_texts = []
    for path in iter_files(input_dir):
        text = load_text_from_file(path)
        if text:
            all_texts.append(text)

    corpus = "\n\n".join(all_texts)
    sentences = split_sentences(corpus)

    domain_buckets: Dict[str, List[str]] = defaultdict(list)
    for sentence in sentences:
        for domain in sentence_domain(sentence):
            domain_buckets[domain].append(sentence)

    domain_ranked: Dict[str, List[Tuple[str, float]]] = {
        domain: rank_sentences(domain_sentences, top_k=50)
        for domain, domain_sentences in domain_buckets.items()
    }

    domain_order = list(dict.fromkeys(list(THEMATIC_MAP.keys()) + ["General"]))

    executive_summary: List[str] = []
    for domain in domain_order:
        picks = [sentence for sentence, _ in domain_ranked.get(domain, [])[:2]]
        for sentence in picks:
            executive_summary.append(f"{domain}: {sentence}")
        if len(executive_summary) >= 10:
            break

    domain_ranked_copy = {domain: list(items) for domain, items in domain_ranked.items()}
    canonical = balanced_sample(domain_ranked_copy, target_n=target_sentences)

    inventories: Dict[str, List[str]] = {}
    for domain in domain_order:
        seen: set[str] = set()
        items: List[str] = []
        for sentence, _score in domain_ranked.get(domain, []):
            if sentence not in seen:
                items.append(sentence)
                seen.add(sentence)
            if len(items) >= 10:
                break
        if items:
            inventories[domain] = items

    dates: List[str] = []
    for text in all_texts:
        dates.extend(extract_dates(text))
    timeline_dates = sorted(set(dates))

    totals = {
        "files_read": len(list(iter_files(input_dir))),
        "sentences_total": len(sentences),
        "domains": sorted(domain_buckets.keys()),
    }

    return Report(
        title=title,
        created_at=f"{datetime.utcnow().isoformat()}Z",
        executive_summary=executive_summary,
        canonical_100_sentences=canonical,
        inventories=inventories,
        timeline_dates=timeline_dates,
        totals=totals,
    )


def render_markdown(report: Report) -> str:
    """Render *report* into Markdown suitable for human readers."""

    exec_md = (
        "\n".join([f"- {line}" for line in report.executive_summary])
        if report.executive_summary
        else "- (No content)"
    )

    canonical_md = (
        "\n".join(
            [f"{index + 1}. {sentence}" for index, sentence in enumerate(report.canonical_100_sentences)]
        )
        if report.canonical_100_sentences
        else "1. (No content)"
    )

    inventory_sections = []
    for domain, items in report.inventories.items():
        inventory_sections.append(
            f"### {domain}\n" + "\n".join([f"- {item}" for item in items])
        )
    inventories_md = "\n\n".join(inventory_sections) if inventory_sections else "_No inventories_"

    timeline_md = (
        ", ".join(report.timeline_dates)
        if report.timeline_dates
        else "_No dates detected_"
    )

    return (
        f"# {report.title}\n\n"
        f"**Created:** {report.created_at}\n\n"
        f"## Executive Summary (10 bullets)\n{exec_md}\n\n"
        f"## Canonical Account Summary (100 sentences)\n{canonical_md}\n\n"
        f"## Inventories by Domain (Top 10 each)\n{inventories_md}\n\n"
        f"## Timeline (Detected ISO Dates)\n{timeline_md}\n\n"
        "---\n"
        f"**Totals:** files_read={report.totals.get('files_read')}, "
        f"sentences_total={report.totals.get('sentences_total')}\n"
        f"**Domains Covered:** {', '.join(report.totals.get('domains', []))}\n"
    )


def main() -> None:
    """Command-line interface for generating account summaries."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Folder containing .txt/.md/.json files",
    )
    parser.add_argument(
        "--out",
        "-o",
        required=True,
        help="Output folder",
    )
    parser.add_argument(
        "--title",
        "-t",
        default="SporeNet Account Summary",
        help="Report title",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable optional LLM refinement",
    )
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    report = build_report(args.input, title=args.title, target_sentences=100)

    markdown = render_markdown(report)
    if not args.no_llm:
        markdown = maybe_refine_with_llm("Full Report", markdown)

    markdown_path = os.path.join(args.out, "SporeNet_Account_Summary.md")
    json_path = os.path.join(args.out, "SporeNet_Account_Summary.json")

    with open(markdown_path, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(asdict(report), handle, indent=2)

    print(f"Wrote {markdown_path}")
    print(f"Wrote {json_path}")
    print("Done.")


if __name__ == "__main__":
    main()

