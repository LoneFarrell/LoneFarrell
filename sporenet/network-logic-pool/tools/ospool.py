#!/usr/bin/env python3
import json, sys, pathlib, re
from jsonschema import validate, Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = ROOT/"sporenet/network-logic-pool/registry.schema.json"
REGISTRY = ROOT/"sporenet/network-logic-pool/registry.json"

def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))

def validate_registry():
    schema = _load(SCHEMA)
    data = _load(REGISTRY)
    Draft202012Validator.check_schema(schema)
    validate(instance=data, schema=schema)
    print("OK: registry.json valid")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if cmd == "validate":
        validate_registry()
    else:
        print("usage: ospool.py validate")
