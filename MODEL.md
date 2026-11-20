# MODEL.md: the models, in words

This file describes each protocol model in plain language: its state, its actions (guard and effect), its invariants in check
order, and the encoding. Two things are written **from this file**, not from the Fe code: the independent oracle
`tools/ref_model.py` (X6) and the per-handler test suite in `src/tests.fe` (`test_handler_*`). If the Fe model, this text and the
oracle disagree, a test or the oracle's `--check` fails. A misreading shared by all three is not caught (README, Limitations).

## Protocol 1: unit escrow (`src/escrow.fe`)

A buyer puts abstract units into escrow, locks the deal, and then each unit goes either to the seller (Release) or back to the
buyer (Refund), never both kinds in one deal. Nothing moves real ETH or tokens; a unit is a counter.

### State
| Field | Values | Meaning |
|---|---|---|
| `phase` | Open, Locked, Disputed, Settled | where the deal is |
| `escrow` | 0..cap | units held |
| `seller` | 0..cap | units paid to the seller |
| `buyer` | 0..cap | units refunded to the buyer |

`total = escrow + seller + buyer`. The capacity `cap` is a parameter of the model (at most `MAX_CAP = 21`). Initial state:
(Open, 0, 0, 0).

### Actions (digit = the number a counterexample prints)
One call moves at most one unit. A rejected call changes nothing.

| Digit | Action | Accepted when | Effect |
|---|---|---|---|
| 1 | Deposit | phase is Open and `total < cap` | `escrow + 1` |
| 2 | Lock | phase is Open and `escrow > 0` | phase becomes Locked |
| 3 | Release | phase is Locked, `escrow > 0` and `buyer == 0` | `escrow − 1`, `seller + 1`; phase becomes Settled if escrow is now 0, else stays Locked |
| 4 | Refund | phase is Locked or Disputed, `escrow > 0` and `seller == 0` | `escrow − 1`, `buyer + 1`; phase becomes Settled if escrow is now 0, else stays the same |
| 5 | Dispute | phase is Locked and `seller == 0` | phase becomes Disputed |

Settled accepts nothing. Disputed accepts only Refund.

### Invariants, in check order
State invariants are checked on the initial state and on every accepted successor; the transition invariant on every accepted edge
(s, a, s′). The first one that fails is the one the compiler names.

| Id | Name | Kind | Holds when |
|---|---|---|---|
| 1 | `within capacity` (the cap rule) | state | `total ≤ cap` |
| 2 | `in bounds` | state | every unit field `< W` (so the encoding is exact) |
| 3 | `paid once` | state | `seller == 0` or `buyer == 0` |
| 4 | `settled empty` | state | phase is not Settled, or `escrow == 0` |
| 5 | `conserved` | transition | `total(s′) == total(s) + 1` if the action is Deposit, else `total(s′) == total(s)` |

For the escrow, `within capacity` implies `in bounds` at every `cap ≤ 21`, so `in bounds` cannot fire first; it guards the
encoding for future edits.

### Encoding
Radix `W = 22` for every unit field and every capacity: `enc(s) = ((phase · W + escrow) · W + seller) · W + buyer`, with
phase ids Open 0, Locked 1, Disputed 2, Settled 3. The box holds `4 · 22³ = 42,592` indices; the initial state is index 0.

### Search order
Breadth first from the initial state. States are dequeued in the order they were first reached; from each state the actions are
tried in digit order 1..5. The counterexample is the first accepted edge, in this order, that breaks any invariant; its trace is
the path of digits from the initial state, earliest first. This is the first shortest witness under the declared action order.

### Labeled-edge hash
Over every accepted edge (s, a, s′) in search order, with `a` the action id 0..4 (digit − 1), `A = 5`, `SIZE = 42,592`,
`M = 2⁶¹ − 1`, `P = 1,000,003`, starting from `h = 0`:
`h = (h · P + ((enc(s) · A + a) · SIZE + enc(s′))) mod M`.

### Hand-checkable specimen: cap = 2
14 reachable states, 16 accepted edges, 70 attempts (14 × 5), longest shortest path 5 actions.

| # | State (phase, escrow, seller, buyer) | Reached by |
|---|---|---|
| 0 | (Open, 0, 0, 0) | start |
| 1 | (Open, 1, 0, 0) | 1 |
| 2 | (Open, 2, 0, 0) | 1 1 |
| 3 | (Locked, 1, 0, 0) | 1 2 |
| 4 | (Locked, 2, 0, 0) | 1 1 2 |
| 5 | (Settled, 0, 1, 0) | 1 2 3 |
| 6 | (Settled, 0, 0, 1) | 1 2 4 |
| 7 | (Disputed, 1, 0, 0) | 1 2 5 |
| 8 | (Locked, 1, 1, 0) | 1 1 2 3 |
| 9 | (Locked, 1, 0, 1) | 1 1 2 4 |
| 10 | (Disputed, 2, 0, 0) | 1 1 2 5 |
| 11 | (Settled, 0, 2, 0) | 1 1 2 3 3 |
| 12 | (Settled, 0, 0, 2) | 1 1 2 4 4 |
| 13 | (Disputed, 1, 0, 1) | 1 1 2 4 5 |

The 16 accepted edges: 0→1 (1); 1→2 (1), 1→3 (2); 2→4 (2); 3→5 (3), 3→6 (4), 3→7 (5); 4→8 (3), 4→9 (4), 4→10 (5);
7→6 (4); 8→11 (3); 9→12 (4), 9→13 (5); 10→13 (4); 13→12 (4).
