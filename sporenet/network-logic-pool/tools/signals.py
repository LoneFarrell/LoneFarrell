#!/usr/bin/env python3
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT/"sporenet/network-logic-pool/registry.json"
OUT = ROOT/"sporenet/network-logic-pool/signals.json"

PERMISSIVE = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0"}
GRAPH_TAGS = {"graph", "network", "topology"}
RUNTIME_TAGS = {"compiler", "gpu", "runtime", "vm"}

# Simple deterministic heuristics (0..1)
def score_symq1(p):
    tags = set((p.get('tags') or []))
    s = 0.3
    if tags & GRAPH_TAGS: s += 0.3
    if tags & RUNTIME_TAGS: s += 0.2
    if len(tags) >= 3: s += 0.1
    return min(1.0, s)

def score_iso(p):
    # Favor projects with docs/homepage and clear category
    s = 0.2
    if p.get('docs') or p.get('homepage'): s += 0.3
    if p.get('category'): s += 0.2
    if isinstance(p.get('license'), str) and p['license'] in PERMISSIVE: s += 0.2
    return min(1.0, s)

def score_seif(p):
    # Prefer permissive licenses and described repos
    s = 0.2
    if isinstance(p.get('license'), str) and p['license'] in PERMISSIVE: s += 0.4
    if len((p.get('description') or '').split()) >= 5: s += 0.2
    if p.get('homepage'): s += 0.1
    return min(1.0, s)

if __name__ == '__main__':
    data = json.loads(REGISTRY.read_text(encoding='utf-8'))
    out = []
    for proj in data.get('projects', []):
        out.append({
            'name': proj.get('name'),
            'repo': proj.get('repo'),
            'license': proj.get('license'),
            'scores': {
                'symq1': round(score_symq1(proj), 2),
                'iso_4447_s': round(score_iso(proj), 2),
                'seif': round(score_seif(proj), 2),
            },
            'tags': proj.get('tags', []),
            'category': proj.get('category'),
        })
    OUT.write_text(json.dumps({'generated_by':'signals.py','items':out}, indent=2), encoding='utf-8')
    print(f'Wrote {OUT}')
