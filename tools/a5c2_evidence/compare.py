"""Compare to_dict snapshots (fingerprint values masked): per (test, class), the set of outputs must match once
baseline keys absent from the new output are dropped. Dropped keys must name a fingerprint."""
from __future__ import annotations
import json, sys
from collections import defaultdict

PERSISTED_STRICT = {"RollingFCRStudyResult"}

import os
RENAMES = []
if os.environ.get("RENAMES"):
    _ns = {}
    _src = open(os.environ["RENAMES"]).read().split("files = subprocess")[0]
    exec(_src, _ns)
    RENAMES = _ns["MAP"]; RENAME_REGEX = _ns["REGEX"]

def _renamed(text):
    for a, b in RENAMES:
        text = text.replace(a, b)
    if RENAMES:
        for rx, b in RENAME_REGEX:
            text = rx.sub(b, text)
    return text

def load(path, rename=False):
    groups = defaultdict(set)
    for line in open(path):
        if line.strip():
            node, cls, _seq, text = json.loads(line)
            groups[(node, cls)].add(_renamed(text) if rename else text)
    return groups

MASK = "<fingerprint>"
VOLATILE = {"runtime_seconds", "elapsed_seconds"}

import re
HEX = re.compile(r"^(sha256:)?[0-9a-f]{64}$")

def mask(value):
    if isinstance(value, dict):
        return {k: (MASK if "fingerprint" in k or k in VOLATILE else mask(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value if not (isinstance(v, str) and HEX.match(v))]
    if isinstance(value, str) and HEX.match(value):
        return MASK
    return value

def strip(value, template_keys, dropped, path=""):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if path + "." + k in template_keys or "fingerprint" not in k:
                out[k] = strip(v, template_keys, dropped, path + "." + k)
            else:
                dropped.add(k)
        return out
    if isinstance(value, list):
        return [strip(v, template_keys, dropped, path) for v in value]
    return value

def keys_of(value, acc, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            acc.add(path + "." + k); keys_of(v, acc, path + "." + k)
    elif isinstance(value, list):
        for v in value: keys_of(v, acc, path)
    return acc

base, new = load(sys.argv[1], rename=True), load(sys.argv[2])
dropped_by_class = defaultdict(set)
problems = []
for key in sorted(set(base) | set(new)):
    b, n = base.get(key, set()), new.get(key, set())
    if not n:
        problems.append(("no longer called", key)); continue
    if not b:
        problems.append(("new caller", key)); continue
    new_keys = set()
    for t in n: keys_of(json.loads(t), new_keys)
    dropped = set()
    stripped = {json.dumps(mask(strip(json.loads(t), new_keys, dropped)), sort_keys=True) for t in b}
    norm_new = {json.dumps(mask(json.loads(t)), sort_keys=True) for t in n}
    if key[1] in PERSISTED_STRICT and (dropped or stripped != norm_new):
        problems.append(("PERSISTED CHANGED", key))
    if not norm_new <= stripped:
        problems.append(("content differs", key))
    dropped_by_class[key[1]] |= dropped
print("groups:", len(base), "->", len(new))
for cls, keys in sorted(dropped_by_class.items()):
    if keys: print(f"dropped {cls}: {sorted(keys)}")
kinds = defaultdict(list)
for kind, key in problems: kinds[kind].append(key)
for kind, keys in kinds.items():
    print(f"{kind}: {len(keys)}")
    for k in keys[:15]: print("   ", k)
sys.exit(1 if any(k in kinds for k in ("content differs", "PERSISTED CHANGED")) else 0)
