# SporeNet Account Summarizer

This project provides a standalone Python utility that converts a directory of
textual account artifacts into a structured report. It extracts sentences from
``.txt``, ``.md`` and ``.json`` files, assigns them to thematic domains, and
generates both Markdown and JSON summaries suitable for SporeNet OS
documentation workflows.

## Usage

```bash
python account_summarizer.py --input ./account_dump --out ./summary --title "SporeNet Canon v1.1.8+AENG"
```

### Command-line options

- `--input` / `-i`: Directory containing the source account files.
- `--out` / `-o`: Destination directory for the generated Markdown and JSON
  reports (created if missing).
- `--title` / `-t`: Optional report title. Defaults to `SporeNet Account Summary`.
- `--no-llm`: Skip the optional OpenAI-assisted refinement step even if an
  `OPENAI_API_KEY` environment variable is present.

The command emits two files into the output directory:

1. `SporeNet_Account_Summary.md` — a human-readable report with executive
   bullets, a canonical 100-sentence summary, domain inventories, and a timeline
   section.
2. `SporeNet_Account_Summary.json` — a machine-readable representation of the
   same structure.
