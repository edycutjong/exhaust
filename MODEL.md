# MODEL.md: the models, in words

This file describes each protocol model in plain language: its state, its actions (guard and effect), its invariants in check
order, and the encoding. Two things follow this description rather than the Fe code: the oracle `tools/ref_model.py`
(Python, its own tuple representation) and the per-handler test suites in `src/tests.fe` (`test_handler_*`, escrow) and `src/vault_tests.fe` (`test_vault_handler_*`, vault). If the Fe model and the
oracle disagree, a test or the oracle's `--check` fails; this text itself is checked only by reading. A misreading shared by all three is not caught (README, "Limitations").

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

## Protocol 2: 2-of-3 approval + timelock vault (`src/vault.fe`)

A vault holds `B` abstract units. One withdrawal of one unit is pending at a time. A signer proposes it, two of the three
signers (A, B, C) approve it, and then a timelock of `T` ticks must pass before anyone can execute it. A pending withdrawal can
be cancelled at any point before it executes. Nothing moves real ETH or tokens. The identity of the approvers is in the
alphabet: ApproveA, ApproveB and ApproveC are three different actions, so "two distinct approvals" means two distinct signers in
the model. Mapping `msg.sender` to a signer is adapter code in `src/vault_contract.fe`, outside the compile-time check.

### State
`(phase, mask, count, clock, bal, paid)`:

| Field | Range | Meaning |
|---|---|---|
| `phase` | Idle, Proposed, Queued | nothing pending / waiting for approvals / quorum reached, timelock running |
| `mask` | 0..7 | which signers approved: bit 0 = A, bit 1 = B, bit 2 = C |
| `count` | 0..3 | approvals counted: the number the threshold guard reads |
| `clock` | 0..T | ticks since the withdrawal was queued, saturating at `T` |
| `bal`, `paid` | 0..B | units in the vault / units paid out; `bal + paid == B` in every reachable state at the checked configurations |

`count` is a separate field on purpose: it is what the threshold guard (`count ≥ K`, K = 2) reads, and the bug `vault-approve-twice`
(an approver counted twice) needs a count that can disagree with the mask. In the correct model `count == popcount(mask)` in every
reachable state at the checked configurations (B ≤ 10, T ≤ 3; invariant `counted once`). The initial state is `(Idle, 0, 0, 0, B, 0)`.

### Actions (digit = the number a counterexample prints)

| Digit | Action | Guard | Effect |
|---|---|---|---|
| 1 | Propose | Idle and `bal > 0` | Proposed, `mask = count = clock = 0` |
| 2 | ApproveA | Proposed or Queued, bit 0 of `mask` not set | set the bit, `count + 1`; from Proposed with `count + 1 ≥ K`: Queued, `clock = 0` |
| 3 | ApproveB | as ApproveA, bit 1 | as ApproveA |
| 4 | ApproveC | as ApproveA, bit 2 | as ApproveA |
| 5 | Tick | Queued and `clock < T` | `clock + 1` |
| 6 | Execute | Queued, `count ≥ K`, `clock ≥ T`, `bal > 0` | Idle, `mask = count = clock = 0`, `bal − 1`, `paid + 1` |
| 7 | Cancel | Proposed or Queued | Idle, `mask = count = clock = 0` |

A rejected action leaves the state unchanged and adds no edge.

### Invariants, in check order

| Id | Name | Kind | Holds when |
|---|---|---|---|
| 1 | `in bounds` | state | `mask < 8`, `count < 4`, `clock ≤ MAX_T`, `bal` and `paid ≤ MAX_B` (so the encoding is exact) |
| 2 | `counted once` | state | `count == popcount(mask)` |
| 3 | `conserved` | state | `bal + paid == B` |
| 4 | `idle clean` | state | phase Idle ⇒ `mask == 0` and `clock == 0` |
| 5 | `queued means quorum` | state | phase Queued ⇒ `popcount(mask) ≥ K` |
| 6 | `proposed below quorum` | state | phase Proposed ⇒ `popcount(mask) < K` and `clock == 0` |
| 7 | `two distinct approvals` | transition | action Execute ⇒ `popcount(s.mask) ≥ 2` |
| 8 | `timelock respected` | transition | action Execute ⇒ `s.clock ≥ T` |
| 9 | `pays one unit` | transition | action Execute ⇒ `bal′ == bal − 1` and `paid′ == paid + 1` |

`vault-approve-twice` breaks `counted once` and `queued means quorum` on the same state; `counted once` is first in the check
order, so it is the one the compiler names. `vault-execute-early` breaks no state invariant: every state it reaches is also
reachable in the correct model, and the step itself (an Execute before the timelock) is what the transition invariant rejects.
`vault-pay-twice` (Execute pays two units) keeps `conserved` (`bal + paid` is unchanged) and is caught only by `pays one unit`.
`proposed below quorum` and `pays one unit` were added after review: nothing else bounded a Proposed withdrawal or the size of one payout.

### Encoding
Mixed radix `(3, 8, 4, MAX_T + 1, MAX_B + 1, MAX_B + 1)` with `MAX_B = 10`, `MAX_T = 3`, for every `B ≤ 10` and `T ≤ 3`:
`enc(s) = ((((phase · 8 + mask) · 4 + count) · 4 + clock) · 11 + bal) · 11 + paid`; the box holds `3 · 8 · 4 · 4 · 11 · 11 = 46,464`
indices. The initial state is not index 0 (`bal = B`): it is `B · 11`.

### Search order
As the escrow: breadth first, actions tried in digit order 1..7.

### Sizes (oracle, `tools/ref_model.py`)
States `(B + 1) + 4B + 4(T + 1)B`: Idle `B + 1` (every `bal`/`paid` split), Proposed `4B` (the four masks with fewer than two
signers × `bal` 1..B), Queued `4(T + 1)B` (the four masks with at least two signers × clock 0..T × `bal` 1..B).

| B | T | states | accepted edges | attempts (states × 7) | longest shortest path |
|---:|---:|---:|---:|---:|---:|
| 8 | 2 | 137 | 376 | 959 | 48 |
| 10 | 1 | 131 | 360 | 917 | 50 |
| 10 | 2 | 171 | 470 | 1,197 | 60 |
| 10 | 3 | 211 | 580 | 1,477 | 70 |

### The deployed vault is a smaller graph
The contract has six handlers, no `Tick`: `Execute` reads the block time and, once the lock period has passed since the
withdrawal was queued, runs `vstep` on the stored state with `clock = T`; otherwise with the stored clock (always 0). So it can
only walk states with `clock = 0`. The `fe test` harness can neither advance the block time nor change the caller, so the
differential (`test_vault_differential`) replays the contract graph: 91 states and 250 accepted edges with a lock period of zero
(the lock has always passed), 9 states and 21 edges with a lock period that never passes (B = 10, T = 3; the oracle counts the
same, `vault_contract_graph` in `evidence/oracle.json`). In the differential all three signers are the one harness address.
Authorization (who may send which message) is tested only from the refusing side: `test_vault_identity_guards` deploys vaults
where the harness is signer A only, or no signer, and checks that ApproveB / ApproveC from A and Propose from a non-signer are
refused with nothing stored changed (each would be accepted by `vstep`). Untested: an accepted approval from a second address; a
refused non-signer Cancel; where the lock period starts (`queued_at`, set when a withdrawal is queued) and the exact
`>=` boundary of the lock check — every Execute run uses a lock of zero or one that never passes — and signer distinctness: `init` does
not require the three signer addresses to differ, so with two equal addresses one key could supply both approvals. `Propose` and `Cancel`
need any one signer (the model has no owner), so a single signer can cancel a queued withdrawal. The harness limits are recorded in
`FE-NOTES.md`.
