# Open Source Network Logic Pool (OSNLP)

A public registry + scripts for discovering, curating, and scoring open‑source projects relevant to SporeNet OS (symbolic/emotive computing, legal standards, certification, recursion engines).

**Goals**
- Map the ecosystem (projects, licenses, maintainers, maturity).
- Provide signals for SYMQ‑1 / SEIF / ISO‑4447‑S alignment.
- Enable community contributions via PRs.

**Structure**
- `registry.json` — canonical list of projects.
- `signals.json` — computed signals (scores, tags, synergies).
- `tools/ospool.py` — local CLI to validate/update the pool.
- `.github/workflows/osnlp.yml` — CI: schema validation + link checks.

**Contribute**
1. Fork and edit `registry.json` (add your project entry).
2. Run `python tools/ospool.py validate`.
3. Open a PR.

**License**: MIT
