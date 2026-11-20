#!/usr/bin/env python3
"""Reference model of the exhaust escrow in Python, following MODEL.md (its own tuple representation, not the Fe encoding).

Standard library only. Usage:
  python3 tools/ref_model.py                 counts for every pinned capacity (table)
  python3 tools/ref_model.py --cap 2 --list  the full reachable set at one capacity (MODEL.md specimen)
  python3 tools/ref_model.py --bug NAME      expected invariant + digits for a demo bug (see BUGS)
  python3 tools/ref_model.py --check         compare with the pins in src/escrow_explore.fe; exit 1 on any mismatch
  python3 tools/ref_model.py --json FILE     write every number above as JSON
  python3 tools/ref_model.py --graph FILE --cap N   write the reachable graph (nodes + labeled edges) as JSON
"""
import argparse
import json
import platform
import re
import sys
from collections import deque
from pathlib import Path

OPEN, LOCKED, DISPUTED, SETTLED = 0, 1, 2, 3
PHASES = ["Open", "Locked", "Disputed", "Settled"]
ACTIONS = ["Deposit", "Lock", "Release", "Refund", "Dispute"]  # digit = index + 1
MAX_CAP = 21
W = MAX_CAP + 1
SIZE = 4 * W ** 3
HASH_M = (1 << 61) - 1
HASH_P = 1_000_003
INVARIANTS = ["within capacity", "in bounds", "paid once", "settled empty", "conserved"]  # check order, ids 1..5

# The demo bugs, each as the one guard/effect change MODEL.md's table would need.
BUGS = {
    "refund-after-release": "Refund no longer requires seller == 0",
    "settle-early": "Release settles when escrow becomes <= 1 instead of 0",
    "cap-off-by-one": "Deposit accepted when total <= cap instead of total < cap",
    "mint-release": "Release pays the seller without debiting escrow",
}


def step(s, a, cap, bug=None):
    """Return the successor tuple, or None when the guard rejects. s = (phase, escrow, seller, buyer)."""
    ph, e, se, bu = s
    total = e + se + bu
    if a == 0:  # Deposit
        ok = total <= cap if bug == "cap-off-by-one" else total < cap
        if ph == OPEN and ok:
            return (OPEN, e + 1, se, bu)
    elif a == 1:  # Lock
        if ph == OPEN and e > 0:
            return (LOCKED, e, se, bu)
    elif a == 2:  # Release
        if ph == LOCKED and e > 0 and bu == 0:
            ne = e if bug == "mint-release" else e - 1
            settles = ne <= 1 if bug == "settle-early" else ne == 0
            return (SETTLED if settles else LOCKED, ne, se + 1, bu)
    elif a == 3:  # Refund
        seller_ok = True if bug == "refund-after-release" else se == 0
        if ph in (LOCKED, DISPUTED) and e > 0 and seller_ok:
            ne = e - 1
            return (SETTLED if ne == 0 else ph, ne, se, bu + 1)
    elif a == 4:  # Dispute
        if ph == LOCKED and se == 0:
            return (DISPUTED, e, se, bu)
    return None


def state_violation(s, cap):
    ph, e, se, bu = s
    if e + se + bu > cap:
        return 1
    if not (e < W and se < W and bu < W):
        return 2
    if not (se == 0 or bu == 0):
        return 3
    if ph == SETTLED and e != 0:
        return 4
    return 0


def violation(s, a, n, cap):
    v = state_violation(n, cap)
    if v:
        return v
    if sum(n[1:]) != sum(s[1:]) + (1 if a == 0 else 0):
        return 5
    return 0


def enc(s):
    ph, e, se, bu = s
    return ((ph * W + e) * W + se) * W + bu


def search(cap, bug=None):
    """BFS in MODEL.md's search order. Stops at the first violating edge (returns its trace)."""
    start = (OPEN, 0, 0, 0)
    if state_violation(start, cap):
        return {"violation": state_violation(start, cap), "digits": "9"}
    order = [start]
    depth = {start: 0}
    parent = {start: None}
    edges = []
    h = 0
    q = deque([start])
    while q:
        s = q.popleft()
        for a in range(5):
            n = step(s, a, cap, bug)
            if n is None:
                continue
            v = violation(s, a, n, cap)
            if v:
                digits = [a + 1]
                p = s
                while parent[p] is not None:
                    prev, act = parent[p]
                    digits.append(act + 1)
                    p = prev
                return {"violation": v, "digits": "".join(str(d) for d in reversed(digits))}
            edges.append((s, a, n))
            h = (h * HASH_P + ((enc(s) * 5 + a) * SIZE + enc(n))) % HASH_M
            if n not in depth:
                depth[n] = depth[s] + 1
                parent[n] = (s, a)
                order.append(n)
                q.append(n)
    layers = [0] * (max(depth.values()) + 1)
    for d in depth.values():
        layers[d] += 1
    return {
        "cap": cap,
        "states": len(order),
        "edges": len(edges),
        "attempts": 5 * len(order),
        "diameter": max(depth.values()),
        "edge_hash": h,
        "layers": layers,
        "order": order,
        "edge_list": edges,
        "parent": parent,
    }


def diff_workload(cap):
    """Calls the exhaustive-edge differential makes (architecture: per state, one deployment replays the path, tries
    every rejected action, then the first accepted one; each further accepted action gets its own deployment)."""
    r = search(cap)
    depth = {}
    for s in r["order"]:
        depth[s] = 0 if r["parent"][s] is None else depth[r["parent"][s][0]] + 1
    deployments = actions = 0
    for s in r["order"]:
        k = sum(1 for a in range(5) if step(s, a, cap) is not None)
        if k == 0:
            deployments += 1
            actions += depth[s] + 5
        else:
            deployments += k
            actions += k * depth[s] + (5 - k) + k
    return {"cap": cap, "deployments": deployments, "action_calls": actions, "reads": actions, "calls": 2 * actions}


def reach(seeds, cap):
    seen, q = set(seeds), deque(seeds)
    while q:
        s = q.popleft()
        for a in range(5):
            n = step(s, a, cap)
            if n is not None and n not in seen:
                seen.add(n)
                q.append(n)
    return seen


SHARDS = [(1, 7), (8, 14), (15, 21)]  # locked amount k ranges, seeds (Locked, k, 0, 0)


def shards(cap=MAX_CAP):
    """Locked-amount shards: counts, pairwise disjointness, and whether shards + Open states == the reachable set."""
    full = set(search(cap)["order"])
    sets = [reach([(LOCKED, k, 0, 0) for k in range(lo, hi + 1)], cap) for lo, hi in SHARDS]
    opens = {s for s in full if s[0] == OPEN}
    disjoint = all(not (a & b) for i, a in enumerate(sets) for b in sets[i + 1:]) and not any(s & opens for s in sets)
    return {"cap": cap, "shards": [{"k": f"{lo}..{hi}", "states": len(s)} for (lo, hi), s in zip(SHARDS, sets)],
            "open_states": len(opens), "disjoint": disjoint, "union_is_reachable_set": set().union(*sets) | opens == full}


def trace(parent, s):
    out = []
    while parent[s] is not None:
        prev, act = parent[s]
        out.append(str(act + 1))
        s = prev
    return " ".join(reversed(out)) or "start"


def fmt(s):
    return f"({PHASES[s[0]]}, {s[1]}, {s[2]}, {s[3]})"


def fe_pins(root):
    """Pins grepped from the Fe source: (kind, capacity, expected value)."""
    src = (root / "src" / "escrow_explore.fe").read_text()
    consts = {k: int(v) for k, v in re.findall(r"pub const (\w+): u32 = (\d+)", (root / "src" / "escrow.fe").read_text())}
    pins = []
    for kind, arg, val in re.findall(r"static_assert\((explore|counterexample)\((\w+)(?: as u32)?\) == (\d+)\)", src):
        cap = int(arg) if arg.isdigit() else consts[arg]
        pins.append((kind, cap, int(val)))
    for k0, val in re.findall(r"static_assert\(explore_seeds\(LOCKED_BASE \+ (?:(\d+) \* )?LOCKED_STRIDE, \d+, LOCKED_STRIDE, CAP\) == (\d+)\)", src):
        pins.append(("shard", int(k0 or 1), int(val)))
    named = {k: int(v) for k, v in re.findall(r"pub const (\w+): u(?:size|128) = (\d+)", src)}
    for arg, flag, name in re.findall(r"static_assert\(or_deferred\(fingerprint\((\w+), (false|true), STATES\), (\w+)\) == \3\)", src):
        cap = int(arg) if arg.isdigit() else consts[arg]
        pins.append(("edge_hash" if flag == "true" else "edges", cap, named[name]))
    for name in re.findall(r"static_assert\(explore\(CAP\) == (STATES)\)", src):
        pins.append(("explore", consts["CAP"], named[name]))
    return pins


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cap", type=int)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--bug", choices=sorted(BUGS))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--graph")
    ap.add_argument("--emit-fe", dest="emit_fe", metavar="FILE",
                    help="write the labeled-edge table (every attempt at --cap, default 21) as a Fe test module")
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent

    if args.bug:
        cap = args.cap if args.cap is not None else 19
        r = search(cap, args.bug)
        if "digits" not in r:
            print(f"{args.bug} at cap {cap}: no violation found")
            return 1
        print(f"{args.bug} at cap {cap}: invariant '{INVARIANTS[r['violation'] - 1]}', digits {r['digits']}")
        return 0

    if args.emit_fe:
        cap = args.cap if args.cap is not None else MAX_CAP
        r = search(cap)
        pack = lambda s: (s[0] << 24) | (s[1] << 16) | (s[2] << 8) | s[3]
        frm, act, oks, to = [], [], [], []
        for s in r["order"]:
            for a in range(5):
                n = step(s, a, cap)
                frm.append(pack(s)); act.append(a); oks.append(0 if n is None else 1); to.append(pack(s if n is None else n))
        rows = len(frm)
        arr = lambda name, ty, xs: f"const {name}: [{ty}; ROWS] = [" + ", ".join(map(str, xs)) + "]\n"
        src = (
            "// GENERATED by `python3 tools/ref_model.py --emit-fe src/oracle_edges.fe && fe fmt` (the Python oracle, which follows MODEL.md).\n"
            "// Do not edit by hand. Every (state, action) attempt from every reachable state at capacity "
            f"{cap}, in search order:\n"
            "// the state as phase << 24 | escrow << 16 | seller << 8 | buyer (independent of encode()), the action id,\n"
            "// whether the guard accepts, and the next state (the same state when rejected).\n"
            "use core::hint::black_box\n"
            "use ingot::escrow::{State, step, action_of, phase_of, phase_id}\n\n"
            f"const CAP_TABLE: u32 = {cap}\nconst ROWS: usize = {rows}\n"
            + arr("FROM", "u32", frm) + arr("ACT", "u32", act) + arr("OKS", "u32", oks) + arr("TO", "u32", to) +
            "\nfn unpack(_ x: u32) -> State {\n"
            "    State { phase: phase_of(x >> 24), escrow: (x >> 16) & 255, seller: (x >> 8) & 255, buyer: x & 255 }\n}\n\n"
            "fn pack(_ s: State) -> u32 {\n"
            "    (phase_id(s.phase) << 24) | (s.escrow << 16) | (s.seller << 8) | s.buyer\n}\n\n"
            "/// step() agrees with the oracle on every row: same accept/reject, same next state, field by field.\n"
            "#[test]\nfn test_oracle_edges() {\n"
            "    var i: usize = 0\n    var accepted: u32 = 0\n"
            "    while i < black_box(ROWS) {\n"
            "        let n = step(unpack(FROM[i]), action_of(ACT[i]), CAP_TABLE)\n"
            "        assert!((n.ok && OKS[i] == 1) || (!n.ok && OKS[i] == 0))\n"
            "        assert!(pack(n.s) == TO[i])\n"
            "        if n.ok { accepted += 1 }\n"
            "        i += 1\n    }\n"
            f"    assert!(accepted == {r['edges']})\n}}\n"
        )
        Path(args.emit_fe).write_text(src)
        print(f"wrote {args.emit_fe}: {rows} rows, {r['edges']} accepted, cap {cap}")
        return 0

    if args.graph:
        cap = args.cap if args.cap is not None else 19
        r = search(cap)
        idx = {s: i for i, s in enumerate(r["order"])}
        g = {
            "model": "escrow", "cap": cap, "source": "tools/ref_model.py (Python oracle following MODEL.md)",
            "legend": {str(i + 1): name for i, name in enumerate(ACTIONS)},
            "nodes": [{"id": i, "phase": PHASES[s[0]], "escrow": s[1], "seller": s[2], "buyer": s[3], "enc": enc(s)}
                      for i, s in enumerate(r["order"])],
            "edges": [{"from": idx[s], "to": idx[n], "digit": a + 1} for s, a, n in r["edge_list"]],
        }
        Path(args.graph).write_text(json.dumps(g, indent=1) + "\n")
        print(f"wrote {args.graph}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")
        return 0

    if args.cap is not None and args.list:
        r = search(args.cap)
        print(f"cap {args.cap}: {r['states']} states, {r['edges']} edges, {r['attempts']} attempts, diameter {r['diameter']}")
        for i, s in enumerate(r["order"]):
            print(f"{i:3d}  {fmt(s):26s} {trace(r['parent'], s)}")
        idx = {s: i for i, s in enumerate(r["order"])}
        print("edges: " + "; ".join(f"{idx[s]}->{idx[n]} ({a + 1})" for s, a, n in r["edge_list"]))
        return 0

    caps = sorted({2, 4, 10, 17, 18, 19, 20, 21} | ({args.cap} if args.cap is not None else set()))
    rows = []
    print(f"# oracle: tools/ref_model.py, python {platform.python_version()}")
    print("cap  states  edges  attempts  diameter  edge_hash")
    for c in caps:
        r = search(c)
        rows.append({k: r[k] for k in ("cap", "states", "edges", "attempts", "diameter", "edge_hash", "layers")})
        print(f"{c:3d}  {r['states']:6d}  {r['edges']:5d}  {r['attempts']:8d}  {r['diameter']:8d}  {r['edge_hash']}")
    bugs = []
    for name in sorted(BUGS):
        for cap in (18, 19):
            b = search(cap, name)
            bugs.append({"bug": name, "cap": cap, "invariant": INVARIANTS[b["violation"] - 1], "digits": b["digits"]})
            print(f"bug {name:22s} cap {cap}: '{bugs[-1]['invariant']}' {b['digits']}")

    w = diff_workload(max(c for c in caps if c <= MAX_CAP))
    print(f"differential workload at cap {w['cap']}: {w['deployments']} deployments, {w['action_calls']} action calls, "
          f"{w['reads']} raw_state() reads, {w['calls']} calls")

    sh = shards()
    print("shards at cap 21: " + ", ".join(f"k={x['k']} {x['states']}" for x in sh["shards"])
          + f", Open {sh['open_states']}; disjoint {sh['disjoint']}, union == reachable set {sh['union_is_reachable_set']}")

    status = 0
    if not (sh["disjoint"] and sh["union_is_reachable_set"]):
        status = 1
    if args.check:
        pins = fe_pins(root)
        src = (root / "src" / "escrow_explore.fe").read_text()
        asserts = src[src.index("// ---- pins"):].count("static_assert(")
        if len(pins) != asserts:
            print(f"check: parsed {len(pins)} pins but the pins section has {asserts} static_asserts -> MISMATCH")
            status = 1
        else:
            print(f"check: all {asserts} pins in src/escrow_explore.fe parsed")
        for kind, cap, val in pins:
            if kind in ("edges", "edge_hash"):
                got = search(cap)[kind]
            elif kind == "shard":
                lo, hi = next(r for r in SHARDS if r[0] == cap)
                got = len(reach([(LOCKED, k, 0, 0) for k in range(lo, hi + 1)], MAX_CAP))
            elif kind == "explore":
                got = search(cap)["states"]
            else:
                r = search(cap)
                got = int(r["digits"]) if "digits" in r else 0
            ok = got == val
            status |= 0 if ok else 1
            print(f"check {kind}({cap}) == {val}: oracle {got} -> {'AGREE' if ok else 'MISMATCH'}")
        print("RESULT: oracle agrees with every Fe pin" if status == 0 else "RESULT: MISMATCH")

    if args.json:
        Path(args.json).write_text(json.dumps({"python": platform.python_version(), "escrow": rows, "bugs": bugs, "differential": w, "shards": sh}, indent=1) + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
