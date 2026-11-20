#!/usr/bin/env python3
"""Independent reference model of the exhaust escrow (X6), written from MODEL.md, not from the Fe code.

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
    return pins


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cap", type=int)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--bug", choices=sorted(BUGS))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--graph")
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent

    if args.bug:
        cap = args.cap if args.cap is not None else 18
        r = search(cap, args.bug)
        if "digits" not in r:
            print(f"{args.bug} at cap {cap}: no violation found")
            return 1
        print(f"{args.bug} at cap {cap}: invariant '{INVARIANTS[r['violation'] - 1]}', digits {r['digits']}")
        return 0

    if args.graph:
        cap = args.cap if args.cap is not None else 19
        r = search(cap)
        idx = {s: i for i, s in enumerate(r["order"])}
        g = {
            "model": "escrow", "cap": cap, "source": "tools/ref_model.py (oracle written from MODEL.md)",
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

    status = 0
    if args.check:
        for kind, cap, val in fe_pins(root):
            if kind == "explore":
                got = search(cap)["states"]
            else:
                r = search(cap)
                got = int(r["digits"]) if "digits" in r else 0
            ok = got == val
            status |= 0 if ok else 1
            print(f"check {kind}({cap}) == {val}: oracle {got} -> {'AGREE' if ok else 'MISMATCH'}")
        print("RESULT: oracle agrees with every Fe pin" if status == 0 else "RESULT: MISMATCH")

    if args.json:
        Path(args.json).write_text(json.dumps({"python": platform.python_version(), "escrow": rows, "bugs": bugs}, indent=1) + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
