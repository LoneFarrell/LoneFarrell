#!/usr/bin/env python3
"""Generate an orbital operating-systems summary from account artifacts."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence

STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "let",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "with",
    "would",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
}

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[(])")
TOKEN_RE = re.compile(r"[A-Za-z0-9_+/.-]+")

DEFAULT_OS_KEYWORDS: Mapping[str, Sequence[str]] = {
    "Orbit 01 · Linux": (
        "linux",
        "nixos",
        "ubuntu",
        "debian",
        "docker",
        "podman",
        "tailscale",
        "wireguard",
        "kubernetes",
        "self-host",
        "gitops",
    ),
    "Orbit 02 · macOS": (
        "macos",
        "mac",
        "logic pro",
        "affinity",
        "raycast",
        "runway",
        "stable diffusion",
        "final cut",
        "creative",
        "photography",
    ),
    "Orbit 03 · Windows": (
        "windows",
        "excel",
        "power bi",
        "power automate",
        "vscode",
        "wsl2",
        "wsl",
        "ledger",
        "finance",
        "compliance",
    ),
}

SHARED_ORBIT = "Orbit 00 · Shared Systems"


@dataclass
class OrbitSummary:
    """Structured payload describing the OS-formatted summary."""

    generated_at: str
    files_read: int
    total_sentences: int
    top_sentences: Mapping[str, List[str]]
    keyword_hits: Mapping[str, int]

    def to_markdown(self, title: str) -> str:
        header = [
            f"# {title}",
            f"**Generated:** {self.generated_at}",
            f"**Files processed:** {self.files_read} · **Total sentences:** {self.total_sentences}",
            "",
        ]
        sections: List[str] = []
        for orbit, sentences in self.top_sentences.items():
            sections.append(f"## {orbit}")
            sections.append(
                "\n".join(f"- {sent}" for sent in sentences)
                if sentences
                else "- (No highlights captured)"
            )
            sections.append("\n")
        sections.append("## Keyword Telemetry")
        if self.keyword_hits:
            sections.append(
                "\n".join(
                    f"- **{orbit}**: {count} matched sentences"
                    for orbit, count in self.keyword_hits.items()
                )
            )
        else:
            sections.append("- No keyword matches detected")
        sections.append("\n")
        return "\n".join(header + sections).strip() + "\n"

    def to_json(self, title: str) -> str:
        payload = {
            "title": title,
            "generated_at": self.generated_at,
            "files_read": self.files_read,
            "total_sentences": self.total_sentences,
            "top_sentences": self.top_sentences,
            "keyword_hits": self.keyword_hits,
        }
        return json.dumps(payload, indent=2)


def discover_files(source: Path) -> Iterable[Path]:
    for path in source.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json"}:
            yield path


def load_text(path: Path) -> str:
    try:
        data = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if path.suffix.lower() != ".json":
        return data
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return data
    if isinstance(parsed, Mapping):
        if "messages" in parsed and isinstance(parsed["messages"], Sequence):
            return "\n".join(_extract_message_content(parsed["messages"]))
    if isinstance(parsed, Sequence):
        return "\n".join(_extract_message_content(parsed))
    return data


def _extract_message_content(items: Sequence[object]) -> List[str]:
    out: List[str] = []
    for item in items:
        if isinstance(item, Mapping):
            content = item.get("content")
            if isinstance(content, str):
                out.append(content)
        else:
            out.append(str(item))
    return out


def split_sentences(text: str) -> List[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = SENTENCE_SPLIT_RE.split(compact)
    return [segment.strip() for segment in parts if len(segment.strip()) >= 12]


def tokenize(text: str) -> List[str]:
    return [token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in STOPWORDS]


def rank_sentences(sentences: Sequence[str]) -> List[Tuple[str, float]]:
    tokenized = [tokenize(sentence) for sentence in sentences]
    doc_freq: Counter[str] = Counter()
    for tokens in tokenized:
        for token in set(tokens):
            doc_freq[token] += 1
    scores: List[Tuple[str, float]] = []
    for sentence, tokens in zip(sentences, tokenized):
        if not tokens:
            continue
        tf = Counter(tokens)
        score = 0.0
        for token, count in tf.items():
            idf = 1.0 + len(sentences) / (1 + doc_freq[token])
            score += count * idf
        scores.append((sentence, score))
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores


def assign_orbits(
    sentences: Sequence[str],
    keyword_map: Mapping[str, Sequence[str]],
    shared_label: str,
) -> MutableMapping[str, List[str]]:
    compiled = {
        orbit: [kw.lower() for kw in keywords]
        for orbit, keywords in keyword_map.items()
    }
    buckets: MutableMapping[str, List[str]] = defaultdict(list)
    for sentence in sentences:
        lower = sentence.lower()
        matched = [orbit for orbit, keywords in compiled.items() if any(kw in lower for kw in keywords)]
        target_orbits = matched or [shared_label]
        for orbit in target_orbits:
            buckets[orbit].append(sentence)
    return buckets


def build_summary(
    directory: Path,
    keyword_map: Mapping[str, Sequence[str]],
    shared_label: str,
    top_k: int,
) -> OrbitSummary:
    files = list(discover_files(directory))
    texts = [load_text(path) for path in files]
    sentences: List[str] = []
    for text in texts:
        sentences.extend(split_sentences(text))
    orbit_buckets = assign_orbits(sentences, keyword_map, shared_label)
    ranked: Dict[str, List[str]] = {}
    keyword_hits: Dict[str, int] = {}

    ordered_orbits: List[str] = list(keyword_map.keys())
    remaining = [orbit for orbit in orbit_buckets.keys() if orbit not in keyword_map]
    if shared_label not in ordered_orbits:
        ordered_orbits.append(shared_label)
    for orbit in remaining:
        if orbit not in ordered_orbits:
            ordered_orbits.append(orbit)

    for orbit in ordered_orbits:
        items = orbit_buckets.get(orbit, [])
        keyword_hits[orbit] = len(items)
        ranked_sentences = [sentence for sentence, _ in rank_sentences(items)[:top_k]] if items else []
        ranked[orbit] = ranked_sentences
    generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return OrbitSummary(
        generated_at=generated_at,
        files_read=len(files),
        total_sentences=len(sentences),
        top_sentences=ranked,
        keyword_hits=keyword_hits,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Directory containing .md/.txt/.json artifacts")
    parser.add_argument("output", type=Path, help="Destination folder for the summary files")
    parser.add_argument(
        "--title",
        default="Orbital Operating Systems Account Summary",
        help="Title used in the generated documents",
    )
    parser.add_argument(
        "--keywords",
        type=Path,
        help="Optional JSON file mapping orbit names to keyword arrays",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of highlighted sentences to keep per orbit",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.keywords:
        if not args.keywords.exists():
            raise SystemExit(f"Keyword file not found: {args.keywords}")
        try:
            with args.keywords.open("r", encoding="utf-8") as handle:
                keywords = json.load(handle)
                if not isinstance(keywords, Mapping):
                    raise ValueError
        except (json.JSONDecodeError, ValueError):
            raise SystemExit("Keyword file must be a JSON object mapping orbit names to keyword arrays")
    else:
        keywords = DEFAULT_OS_KEYWORDS

    summary = build_summary(args.source, keywords, SHARED_ORBIT, args.top)

    args.output.mkdir(parents=True, exist_ok=True)
    markdown_path = args.output / "orbital_summary.md"
    json_path = args.output / "orbital_summary.json"

    markdown_path.write_text(summary.to_markdown(args.title), encoding="utf-8")
    json_path.write_text(summary.to_json(args.title), encoding="utf-8")

    print(f"Wrote {markdown_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
