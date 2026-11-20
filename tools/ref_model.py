#!/usr/bin/env python3
"""Reference model of the exhaust escrow in Python, following MODEL.md (its own tuple representation, not the Fe encoding).

Standard library only. Usage:
  python3 tools/ref_model.py                 counts for every pinned capacity (table)
  python3 tools/ref_model.py --cap 2 --list  the full reachable set at one capacity (MODEL.md specimen)
  python3 tools/ref_model.py --bug NAME      expected invariant + digits for a demo bug (see BUGS)
  python3 tools/ref_model.py --check         compare with the pins in src/escrow_explore.fe; exit 1 on any mismatch
  python3 tools/ref_model.py --json FILE     write every number above as JSON
  python3 tools/ref_model.py --graph FILE --cap N   write the reachable graph (nodes + labeled edges) as JSON
  python3 tools/ref_model.py --graph FILE --model vault --b 10 --t 3   the same for the vault
  python3 tools/ref_model.py --bug vault-approve-twice   expected invariant + digits for a vault bug (B=10, T=3)
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
                chain = [n, s]
                p = s
                while parent[p] is not None:
                    prev, act = parent[p]
                    digits.append(act + 1)
                    chain.append(prev)
                    p = prev
                return {"violation": v, "digits": "".join(str(d) for d in reversed(digits)), "path": list(reversed(chain))}
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
        "depth": depth,
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


# ---- Protocol 2: the 2-of-3 approval + timelock vault (MODEL.md "Vault"), same independence rules as the escrow ----
IDLE, PROPOSED, QUEUED = 0, 1, 2
VPHASES = ["Idle", "Proposed", "Queued"]
VACTIONS = ["Propose", "ApproveA", "ApproveB", "ApproveC", "Tick", "Execute", "Cancel"]  # digit = index + 1
VINVARIANTS = ["in bounds", "counted once", "conserved", "idle clean", "queued means quorum",
               "proposed below quorum", "two distinct approvals", "timelock respected", "pays one unit",
               "only execute pays"]  # check order, ids 1..10
K = 2
MAX_B, MAX_T = 10, 3
RB, RT = MAX_B + 1, MAX_T + 1
VSIZE = 3 * 8 * 4 * RT * RB * RB
VBUGS = {
    "vault-approve-twice": "an approver's bit is not checked before counting the approval (count still += 1)",
    "vault-execute-early": "Execute no longer requires clock >= T",
    "vault-pay-twice": "Execute pays out two units (bal - 2, paid + 2) instead of one",
    "vault-cancel-pays": "Cancel pays the pending unit out (bal - 1, paid + 1) instead of dropping it",
    "vault-execute-unguarded": "Execute loses its phase, quorum and timelock guards (only bal > 0 remains)",
}


def popcount(m):
    return bin(m).count("1")


def venc(s):
    ph, mask, count, clock, bal, paid = s
    return ((((ph * 8 + mask) * 4 + count) * RT + clock) * RB + bal) * RB + paid


def vstep(s, a, t, bug=None):
    """One transition attempt: the next state tuple, or None when the guard rejects it."""
    ph, mask, count, clock, bal, paid = s
    if a == 0:  # Propose
        return (PROPOSED, 0, 0, 0, bal, paid) if ph == IDLE and bal > 0 else None
    if a in (1, 2, 3):  # Approve{A,B,C}
        bit = 1 << (a - 1)
        if ph == IDLE:
            return None
        if mask & bit and bug != "vault-approve-twice":
            return None
        queue = ph == PROPOSED and count + 1 >= K
        return (QUEUED if queue else ph, mask | bit, count + 1, 0 if queue else clock, bal, paid)
    if a == 4:  # Tick
        return (QUEUED, mask, count, clock + 1, bal, paid) if ph == QUEUED and clock < t else None
    if a == 5:  # Execute
        if bug == "vault-execute-unguarded":
            return (IDLE, 0, 0, 0, bal - 1, paid + 1) if bal > 0 else None
        if ph != QUEUED or count < K or bal <= 0:
            return None
        if clock < t and bug != "vault-execute-early":
            return None
        if bug == "vault-pay-twice":
            return (IDLE, 0, 0, 0, bal - 2, paid + 2) if bal >= 2 else None
        return (IDLE, 0, 0, 0, bal - 1, paid + 1)
    if ph == IDLE:  # Cancel
        return None
    if bug == "vault-cancel-pays" and bal > 0:
        return (IDLE, 0, 0, 0, bal - 1, paid + 1)
    return (IDLE, 0, 0, 0, bal, paid)


def vstate_violation(s, b):
    ph, mask, count, clock, bal, paid = s
    if mask >= 8 or count >= 4 or clock >= RT or bal >= RB or paid >= RB:
        return 1
    if count != popcount(mask):
        return 2
    if bal + paid != b:
        return 3
    if ph == IDLE and (mask != 0 or clock != 0):
        return 4
    if ph == QUEUED and popcount(mask) < K:
        return 5
    if ph == PROPOSED and (popcount(mask) >= K or clock != 0):
        return 6
    return 0


def vviolation(s, a, n, b, t):
    v = vstate_violation(n, b)
    if v:
        return v
    if a == 5:
        if popcount(s[1]) < K:
            return 7
        if s[3] < t:
            return 8
        if n[4] + 1 != s[4] or n[5] != s[5] + 1:
            return 9
    elif n[4] != s[4] or n[5] != s[5]:
        return 10
    return 0


def vsearch(b, t, bug=None):
    """BFS in the vault's action order. Stops at the first violating edge (returns its trace)."""
    start = (IDLE, 0, 0, 0, b, 0)
    if vstate_violation(start, b):
        return {"violation": vstate_violation(start, b), "digits": "9"}
    order = [start]
    depth = {start: 0}
    parent = {start: None}
    edges = []
    h = 0
    q = deque([start])
    while q:
        s = q.popleft()
        for a in range(7):
            n = vstep(s, a, t, bug)
            if n is None:
                continue
            v = vviolation(s, a, n, b, t)
            if v:
                digits = [a + 1]
                chain = [n, s]
                p = s
                while parent[p] is not None:
                    prev, act = parent[p]
                    digits.append(act + 1)
                    chain.append(prev)
                    p = prev
                return {"violation": v, "digits": "".join(str(d) for d in reversed(digits)), "path": list(reversed(chain))}
            edges.append((s, a, n))
            h = (h * HASH_P + ((venc(s) * 7 + a) * VSIZE + venc(n))) % HASH_M
            if n not in depth:
                depth[n] = depth[s] + 1
                parent[n] = (s, a)
                order.append(n)
                q.append(n)
    return {"b": b, "t": t, "states": len(order), "edges": len(edges), "edge_hash": h, "attempts": 7 * len(order),
            "diameter": max(depth.values()), "depth": depth, "order": order, "edge_list": edges, "parent": parent}


CONTRACT_ACTIONS = [0, 1, 2, 3, 5, 6]  # the vault contract has no Tick handler


def vcontract_graph(b, t, ready):
    """The graph the deployed vault can walk: six handlers (no Tick), the clock only ever 0 or, for Execute after the
    lock period (`ready`), t. Returns states, accepted edges and attempts; the same two counts the EVM differential prints."""
    start = (IDLE, 0, 0, 0, b, 0)
    seen = {start}
    q = deque([start])
    edges = 0
    while q:
        s = q.popleft()
        for a in CONTRACT_ACTIONS:
            cur = (s[0], s[1], s[2], t if (a == 5 and ready) else s[3], s[4], s[5])
            n = vstep(cur, a, t)
            if n is None:
                continue
            edges += 1
            if n not in seen:
                seen.add(n)
                q.append(n)
    return {"states": len(seen), "edges": edges, "attempts": len(CONTRACT_ACTIONS) * len(seen)}


def vfe_pins(root):
    """Pins grepped from src/vault_explore.fe: (kind, b, t, expected value)."""
    src = (root / "src" / "vault_explore.fe").read_text()
    consts = {k: int(v) for k, v in re.findall(r"pub const (V[BT]): u32 = (\d+)", (root / "src" / "vault.fe").read_text())}
    val = lambda x: consts[x] if x in consts else int(x)
    pins = []
    for kind, b, t, n in re.findall(r"static_assert\((vexplore|vcounterexample)\((\w+), (\w+)\) == (\d+)\)", src):
        pins.append((kind, val(b), val(t), int(n)))
    for name in re.findall(r"static_assert\(vexplore\(VB, VT\) == (VSTATES)\)", src):
        pins.append(("vexplore", consts["VB"], consts["VT"], int(re.search(r"VSTATES: usize = (\d+)", src).group(1))))
    named = {k: int(v) for k, v in re.findall(r"pub const (\w+): u128 = (\d+)", src)}
    for mode, name in re.findall(r"static_assert\(vsearch\(VB, VT, (V_COUNT_EDGES|V_HASH_EDGES)\) == (\w+)\)", src):
        pins.append(("vedges" if mode == "V_COUNT_EDGES" else "vedge_hash", consts["VB"], consts["VT"], named[name]))
    return pins, src[src.index("// ---- pins"):].count("static_assert(")


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
    ap.add_argument("--bug", choices=sorted(BUGS) + sorted(VBUGS))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--graph")
    ap.add_argument("--model", choices=["escrow", "vault"], default="escrow", help="which protocol --graph writes")
    ap.add_argument("--b", type=int, default=10)
    ap.add_argument("--t", type=int, default=3)
    ap.add_argument("--emit-fe", dest="emit_fe", metavar="FILE",
                    help="write the labeled-edge table (every attempt at --cap, default 21) as a Fe test module")
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent

    if args.bug in VBUGS:
        r = vsearch(args.b, args.t, args.bug)
        if "digits" not in r:
            print(f"{args.bug} at B={args.b}, T={args.t}: no violation found")
            return 1
        print(f"{args.bug} at B={args.b}, T={args.t}: invariant '{VINVARIANTS[r['violation'] - 1]}', digits {r['digits']}")
        return 0

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

    if args.graph and args.model == "vault":
        r = vsearch(args.b, args.t)
        idx = {st: i for i, st in enumerate(r["order"])}
        g = {
            "model": "vault", "b": args.b, "t": args.t, "k": K, "source": "tools/ref_model.py (Python oracle following MODEL.md)",
            "legend": {str(i + 1): name for i, name in enumerate(VACTIONS)},
            "nodes": [{"id": i, "phase": VPHASES[st[0]], "mask": st[1], "count": st[2], "clock": st[3], "bal": st[4],
                       "paid": st[5], "enc": venc(st), "depth": r["depth"][st]} for i, st in enumerate(r["order"])],
            "edges": [{"from": idx[st], "to": idx[n], "digit": a + 1} for st, a, n in r["edge_list"]],
        }
        node = lambda st: {"phase": VPHASES[st[0]], "mask": st[1], "count": st[2], "clock": st[3], "bal": st[4], "paid": st[5]}
        g["attacks"] = []
        for name in sorted(VBUGS):
            ar = vsearch(args.b, args.t, name)
            g["attacks"].append({"bug": name, "invariant": VINVARIANTS[ar["violation"] - 1], "digits": ar["digits"],
                                 "states": [dict(node(st), id=idx.get(st), new=st not in idx) for st in ar["path"]]})
        g["attack"] = g["attacks"][0]
        Path(args.graph).write_text(json.dumps(g, indent=1) + "\n")
        print(f"wrote {args.graph}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")
        return 0

    if args.graph:
        cap = args.cap if args.cap is not None else 19
        r = search(cap)
        idx = {s: i for i, s in enumerate(r["order"])}
        g = {
            "model": "escrow", "cap": cap, "source": "tools/ref_model.py (Python oracle following MODEL.md)",
            "legend": {str(i + 1): name for i, name in enumerate(ACTIONS)},
            "nodes": [{"id": i, "phase": PHASES[s[0]], "escrow": s[1], "seller": s[2], "buyer": s[3], "enc": enc(s),
                       "depth": r["depth"][s]} for i, s in enumerate(r["order"])],
            "edges": [{"from": idx[s], "to": idx[n], "digit": a + 1} for s, a, n in r["edge_list"]],
        }
        node = lambda st: {"phase": PHASES[st[0]], "escrow": st[1], "seller": st[2], "buyer": st[3]}
        g["attacks"] = []
        for name in ("refund-after-release", "settle-early", "mint-release", "cap-off-by-one"):
            ar = search(cap, name)
            g["attacks"].append({"bug": name, "invariant": INVARIANTS[ar["violation"] - 1], "digits": ar["digits"],
                                 "states": [dict(node(st), id=idx.get(st), new=st not in idx) for st in ar["path"]]})
        g["attack"] = g["attacks"][0]
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

    print()
    print("# vault (2-of-3 + timelock)")
    print("   B  T  states  edges  attempts  diameter")
    vrows = []
    for b, t in [(8, 2), (10, 1), (10, 2), (10, 3)]:
        r = vsearch(b, t)
        vrows.append({k: r[k] for k in ("b", "t", "states", "edges", "attempts", "diameter")})
        print(f"{b:4d} {t:2d}  {r['states']:6d}  {r['edges']:5d}  {r['attempts']:8d}  {r['diameter']:8d}")
    vbugs = []
    for name in sorted(VBUGS):
        r = vsearch(10, 3, name)
        vbugs.append({"bug": name, "b": 10, "t": 3, "invariant": VINVARIANTS[r["violation"] - 1], "digits": r["digits"]})
        print(f"bug {name:22s} B=10 T=3: '{vbugs[-1]['invariant']}' {r['digits']}")

    vcg = {m: vcontract_graph(10, 3, m == "ready") for m in ("ready", "locked")}
    for m, g in vcg.items():
        print(f"vault contract graph B=10 T=3 lock {m}: {g['states']} states, {g['edges']} edges, {g['attempts']} attempts")

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
        vpins, vasserts = vfe_pins(root)
        if len(vpins) != vasserts:
            print(f"check: parsed {len(vpins)} vault pins but the pins section has {vasserts} static_asserts -> MISMATCH")
            status = 1
        else:
            print(f"check: all {vasserts} pins in src/vault_explore.fe parsed")
        for kind, b, t, val in vpins:
            if kind == "vexplore":
                got = vsearch(b, t)["states"]
            elif kind == "vedges":
                got = vsearch(b, t)["edges"]
            elif kind == "vedge_hash":
                got = vsearch(b, t)["edge_hash"]
            else:
                r = vsearch(b, t)
                got = int(r["digits"]) if "digits" in r else 0
            ok = got == val
            status |= 0 if ok else 1
            print(f"check {kind}({b}, {t}) == {val}: oracle {got} -> {'AGREE' if ok else 'MISMATCH'}")
        # The generated edge table in src/oracle_edges.fe must be what this oracle emits now (no drift after an edit).
        table = (root / "src" / "oracle_edges.fe").read_text()
        cap_t = int(re.search(r"const CAP_TABLE: u32 = (\d+)", table).group(1))
        arrays = {name: [int(x) for x in re.findall(r"\d+", body)]
                  for name, body in re.findall(r"const (FROM|ACT|OKS|TO): \[u32; ROWS\] = \[([^\]]*)\]", table)}
        want = {"FROM": [], "ACT": [], "OKS": [], "TO": []}
        pk = lambda st: (st[0] << 24) | (st[1] << 16) | (st[2] << 8) | st[3]
        for st in search(cap_t)["order"]:
            for a in range(5):
                n = step(st, a, cap_t)
                want["FROM"].append(pk(st)); want["ACT"].append(a); want["OKS"].append(0 if n is None else 1)
                want["TO"].append(pk(st if n is None else n))
        same = arrays == want
        status |= 0 if same else 1
        print(f"check src/oracle_edges.fe (cap {cap_t}, {len(want['FROM'])} rows) == oracle's table now: {'AGREE' if same else 'DRIFT: re-run --emit-fe'}")
        print("RESULT: oracle agrees with every Fe pin" if status == 0 else "RESULT: MISMATCH")

    if args.json:
        Path(args.json).write_text(json.dumps({"python": platform.python_version(), "escrow": rows, "bugs": bugs, "vault": vrows, "vault_bugs": vbugs, "vault_contract_graph": vcg, "differential": w, "shards": sh}, indent=1) + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
