# MatchMate Phase 2 implementation plan

**Team of 3 · Kickoff Monday, 16 November 2026 · Implementation deadline Friday, 27 November 2026 at 17:00 Vietnam time (UTC+7).**

The team will deliver a single deployable modular monolith, a tested PostgreSQL migration, and an HTTPS demo deployment with evidence for consistency, access control, and recovery. **Friday, 20 November** is the week-one checkpoint for the SQLite refactor and PostgreSQL migration trial. All three members will benchmark together after integration.

## Ownership

| Owner | Workstream | Deliverable |
| --- | --- | --- |
| **Member 1** | **Identity and Sessions application architecture** | Own Unit of Work boundaries, the Identity profile interface, Sessions lifecycle policies and locking, and route/object authorization. Call Matching's writer through a port in the same transaction as session creation or approval. |
| **Member 2** | **Persistence, deployment, and recovery** | Own SQLAlchemy adapters, dialect-specific constraints, locking primitives, versioned migration, history import, PostgreSQL CI, the Compose topology, readiness, and backup/restore. |
| **Member 3** | **Catalog, Matching, and Discovery architecture** | Own venue ownership and read contracts, the first-valid Strategy, the matching writer adapter, read/command separation, and module boundary tests. Own ingress configuration and request telemetry for the demo. |

## Architecture scope and ownership

| Proposal area | Planned application in MatchMate | Owner and checkpoint |
| --- | --- | --- |
| **§3.1–3.4 · Modules, layers, dependencies** | Identity owns accounts, credentials, tokens, and a minimal `PlayerProfileReader` DTO. Catalog owns venues and active status. Sessions owns bookings and participations. Matching owns requests and group selection. Discovery exposes venue/session search as a read facade. Each module separates API, application, domain, and infrastructure responsibilities where needed. The composition root wires adapters into ports. | Member 1 owns Identity, Sessions, and wiring. Member 3 owns Catalog, Matching, Discovery, and import tests. Review on **20 Nov**. |
| **§4.1 · Repository, Unit of Work, Data Mapper, Strategy, and Policy** | Use cases control commit/rollback and speak through business-oriented repository ports. SQLAlchemy stays in adapters and mappers return domain objects or DTOs. Sessions uses host-defined skill bounds and eligibility. Matching uses group rank spread and group budget and keeps first-valid selection. | Member 1 owns use cases and Sessions policies, Member 2 owns persistence/mapping, and Member 3 owns Matching policies and Strategy. Verify the SQLite path on **20 Nov** and PostgreSQL on **24 Nov**. |
| **§4.1 · Logical CQRS** | Separate write use cases from read adapters over the same DB. Search/detail return DTOs. Query code may join module data through agreed read contracts. Read paths needing a consistent snapshot use one statement or an explicit snapshot transaction. | Members 1 and 3 own the Sessions detail and Discovery read paths respectively. Verify contracts and snapshot behavior by **24 Nov**. |
| **§3.3 and §5 · Deployment, Gatekeeper, and operations** | Run HTTPS reverse proxy → one API → PostgreSQL. Keep the API, database, and metrics on private networks. Run migration once before rollout. Keep liveness distinct from DB readiness and demonstrate rate limiting, telemetry, and recovery. | Member 2 owns deployment, CI, and recovery. Member 3 owns ingress and telemetry. Member 1 owns backend auth policy. Demonstrate by **27 Nov**. |
| **§4.2–4.4 · Evidence-based extensions** | Revisit Redis if repeated reads dominate. Consider outbox with a worker when notifications enter scope, or matching process isolation when profiling shows CPU pressure. Distributed options require their own evidence and decision. | All three review after the shared benchmark. |

## Phase 1 · Contracts and regression tests · 16–17 November

**Member 1 — Application transactions**

- [x] Trace where transactions currently start and commit in Auth and Sessions. List the lifecycle commands and the invariants each command must preserve.
- [x] Run the existing lifecycle and Auth tests. Capture expected responses for invalid payloads, unauthenticated callers, duplicate requests, and repeated withdraw/cancel. Identify where a commit failure needs a regression test.
- [ ] Agree with Member 2 on the Unit of Work and the operations for locking sessions and users. Own the application-facing contract in `app/domain/ports.py` and the Sessions contracts.
- [ ] Inventory Identity's profile consumers and existing route access rules, including public searches with authenticated modes. Agree with Member 3 on the profile DTO and the Catalog venue-status contract needed by Sessions.

Member 1's [Phase 1 baseline and contract handoff](member-1-phase-1.md)
([bản tiếng Việt](member-1-phase-1.vi.md)) records the
transaction trace, regression evidence, consumer/access inventory, and proposed
interfaces. The last two items remain open for agreement with Members 2 and 3.

**Member 2 — PostgreSQL persistence**

- [ ] Inspect `app/db/session.py`, `models.py`, `types.py`, and `unit_of_work.py`. List the SQLite-specific engine settings, timestamp type, Boolean checks, and partial indexes that need PostgreSQL equivalents.
- [ ] Start a local PostgreSQL instance. Prepare a SQLite copy with accepted and historical participations and replaced matching requests. Record expected counts and representative values for import verification.
- [ ] Agree on which operations need row locks, how lock timeouts surface through the adapter, and how tests will obtain independent database connections.
- [ ] Sketch the Compose topology and one-shot migration job. Choose a demo backup location outside the application volume/host and record the recovery targets the team will test.

**Member 3 — Matching and Discovery**

- [ ] Trace the create-matching command and the venue/session read queries in `app/features/discovery/`. Record current endpoint responses, candidate order, tie-breaking, replacement behavior, and session-detail privacy rules.
- [ ] Prepare matching cases for no candidates, too few candidates, no valid group, and multiple valid groups. Agree with Member 1 on the port for closing overlapping requests inside the caller's Unit of Work.
- [ ] Define Catalog-owned venue data and Discovery's allowed read joins. Agree with Member 2 on the ingress entry point, private networks, and telemetry fields needed by the benchmark.

**Handoff on 17 November.** Record the starting commit, expected behavior, and agreed Unit of Work, lock, and matching writer interfaces. Members 1 and 3 can then refactor on SQLite while Member 2 builds the database adapter.

## Phase 2 · SQLite refactor and PostgreSQL migration trial · 18–20 November

**Member 1 — Application transactions**

- [ ] Move adapter construction out of the session router. Have the application use case open and commit its Unit of Work, with dependencies responsible for wiring. Ensure failed commits propagate as errors and mutations roll back.
- [ ] Move password hashing and verification outside the corresponding database transactions. Preserve authentication precedence and document any agreed change in 422/503 ordering after moving validation ahead of write transactions.
- [ ] Verify create-session still creates the host's accepted participation, approval preserves fee and gender snapshots, and repeated cancel/withdraw retains its current behavior. Connect create and approve to the matching writer through the agreed port.
- [ ] Expose a minimal `PlayerProfileReader` from Identity so Sessions and Matching consume profile DTOs without credential fields. Wire it, `Clock`, and repository adapters in the composition root. Extract and unit-test the Sessions eligibility and transition rules with fakes where useful.
- [ ] Separate Sessions detail reads from lifecycle commands. Preserve host-only `management` and each viewer's `my_participations`. Declare public/protected route access policies and cover conditional authentication behavior.

**Member 2 — PostgreSQL persistence**

- [ ] Add PostgreSQL connection configuration and versioned schema migrations. Port the timestamp and Boolean handling, foreign keys, and unique predicates for active participation and matching requests.
- [ ] Import a SQLite copy in foreign-key order, preserve IDs and history, and advance sequences beyond imported values. Compare counts and spot-check timestamps, state, and historical records.
- [ ] Prepare real PostgreSQL test fixtures and implement the lock primitives against the agreed contract. Provide startup and migration commands for the other members.
- [ ] Keep queries and row locks in persistence adapters. Reuse mappers to return domain values and DTOs, and configure bounded pool, lock, and statement timeouts with dialect-appropriate error handling.

**Member 3 — Matching and Discovery**

- [ ] Extract the first-valid Strategy into a pure function or class with deterministic candidate ordering. Use the cases from Phase 1 to verify the same selected group and the same no-match responses.
- [ ] Separate matching mutation code from Discovery's read path. Supply the matching writer implementation using the caller's transaction. Verify Discovery DTOs and privacy behavior.
- [ ] Extend `tests/test_architecture.py` to cover dependency direction, module cycles, and direct imports of another module's internal adapters.
- [ ] Move venue ownership and active-status access behind a Catalog contract. Keep Discovery's search joins and DTO mapping in read adapters and verify filter, pagination, and response compatibility. Keep group rank spread and group budget tests distinct from Sessions eligibility tests.
- [ ] Draft the reverse proxy configuration for local TLS, body size limits, request timeouts, and rate limiting. Plan how limits keyed by authenticated user or normalized account identifier will be enforced with backend-validated data.

**Checkpoint on 20 November.** Demo create → join → approve and matching on the refactored SQLite build. Show the matching Strategy tests and PostgreSQL trial import checks. Record this refactored SQLite commit for the later benchmark.

## Phase 3 · PostgreSQL integration · 23–24 November

**Member 1 — Application transactions**

- [ ] Wire locks into join, approve/reject, and withdraw in session-then-user order. For cancellation, take the session lock first, then lock affected users by ascending ID. For creation, lock the host user before checking overlap and inserting the new session.
- [ ] Re-read time and relevant database state after locking. Check authorization, status, available places, and schedule overlap before writing. Include matching closure in the create/approve transaction.
- [ ] Run the first PostgreSQL lifecycle race checks with Member 2's fixtures and review the committed state after both requests finish.
- [ ] Verify the Sessions detail response on PostgreSQL reads a consistent snapshot when it combines queries. Add route-policy coverage that fails when a new endpoint lacks an access declaration. Verify backend JWT and host/owner checks protect mutations behind ingress.

**Member 2 — PostgreSQL persistence**

- [ ] Connect the application to PostgreSQL through environment configuration. Verify lock calls use the same database transaction as the mutation, and confirm lock timeout and rollback behavior with independent connections.
- [ ] Add a reproducible migration and startup smoke test to the existing Compose/CI setup. Run the import on a fresh database and confirm a new insert receives a valid ID after import.
- [ ] Run migration as a single job before API startup. Build and smoke-test the same image digest intended for release. Keep `/health` for process liveness and add a bounded database readiness probe. Expose only ingress in the demo topology.
- [ ] Add DB pool wait, lock wait, and transaction duration measurements for the shared benchmark. Wire lint, architecture tests, SQLite regressions, and PostgreSQL integration into CI.

**Member 3 — Matching and Discovery**

- [ ] Acquire the same user lock in matching creation, check the user's accepted schedule, and replace the active request within one transaction. Keep overlapping-request closure in the caller's Unit of Work.
- [ ] Verify the API still returns the same suggestion shape and meaning, and exercise the create-matching versus approve race with Member 1. Check that the final committed state has no conflicting active matching request.
- [ ] Finish rate-limit policies for login, authenticated writes, and public search. Trust forwarding headers only from ingress. Add structured request logs with correlation ID, route template, status, duration, and error code. Add request and matching metrics, keeping user/session IDs out of metric labels.

**Checkpoint on 24 November.** The integrated build runs create → join → approve and matching against PostgreSQL. Both lifecycle and matching tests use the same documented lock protocol and reproducible test setup.

## Phase 4 · Verification and delivery · 25–27 November

**Member 1 — Application transactions**

- [ ] Complete the last-slot and same-user overlap race repetitions. Also test approve versus cancel/withdraw, create-session versus approve, and a lock wait that crosses the session start time.
- [ ] Inject a failure between the participation update and matching closure, then verify rollback. Submit the lifecycle test results and a short walkthrough of the transaction boundaries.
- [ ] Exercise outsider requests for session detail, approval, withdrawal, and cancellation. Verify rejected requests leave data unchanged. Verify that credentials stay outside the image/logs and document the key-rotation and mutation audit policy with Members 2 and 3.

**Member 2 — PostgreSQL persistence**

- [ ] Re-run migration and integrity checks from a clean database with representative history. Check foreign keys, partial index predicates, timestamp round-trips, and sequences. Save a backup, restore it into a second database, and smoke-test the restored data.
- [ ] Submit migration/setup and backup/restore commands, verification results, and recorded restore time.
- [ ] On the demo stack, interrupt the DB, observe readiness and rollback, restart the API after the DB recovers, and rehearse application rollback against a compatible schema. Record detection, restart, and recovery times. Keep the restore target separate from the backup source.

**Member 3 — Matching and Discovery**

- [ ] Re-run Strategy parity, repeated-request, privacy, and architecture tests on the integrated build. Check that a failed matching replacement preserves the prior request and that a successful booking closes only the overlapping active request.
- [ ] Submit matching test evidence and demo how the Discovery query and Matching command paths are separated.
- [ ] Demonstrate TLS, `429` with retry metadata under a configured burst, and redacted request/error logs. Trace one request through its correlation ID. Show one forbidden import caught by the architecture test and swap the Strategy in wiring with the same router.

**Submission on 27 November at 17:00 Vietnam time.** All three review the integrated build, record its commit, and deliver the run instructions and verification evidence together.

## Acceptance and demo evidence

| Area | Evidence |
| --- | --- |
| **QA-01 · Consistency** | With independent PostgreSQL connections, record zero over-capacity and overlapping `ACCEPTED` bookings over at least 1,000 repetitions each of the last-slot and same-user overlap races. Record infrastructure timeouts separately. Demonstrate rollback on failure and atomic session cancellation and matching closure. Validate imports against foreign keys, counts, UTC timestamps, partial uniqueness, and sequences. |
| **QA-02 · Performance** | Shared post-integration benchmark. Compare the same workloads and resource limits across the three builds and publish successful throughput, latency, errors, and invariant checks. Treat the proposal's latency/error targets as hypotheses to review after the Kaggle baseline. |
| **QA-03 · Modifiability** | Show the five module boundaries, an architecture test catching a forbidden import, a Strategy swap through composition wiring, and existing eligibility/capacity behavior working through both DB adapters. Verify DTO-only reads and compatible matching results on the fixed corpus. |
| **QA-04 · Security** | Preserve 401 precedence on protected routes and document any agreed 422/503 priority change. Show coverage for public/protected routes, authorization denial before mutation, redacted logs/errors, and a configured burst returning `429` with retry metadata over HTTPS. |
| **QA-05 · Recovery and observability** | Show a request/error linked by correlation ID, DB loss causing readiness failure, and restoration into a fresh DB. Record actual times against the proposal's initial targets of 30 sec for DB-loss detection, 60 sec for API recovery once the DB is healthy, 30 min RTO, and 24 h RPO if daily backups are configured. |

If PostgreSQL integration slips past 24 November, prioritize migration and the last-slot, schedule-overlap, and matching-closure tests. At submission, show the verified SQLite checkpoint alongside any completed PostgreSQL evidence and identify outstanding checks. Treat the integrated PostgreSQL build as a test deployment until the cutover criteria in the ADR are met.

## Shared benchmark after implementation

This is ADR milestone **M3**. All three members will run and review it together after implementation. M0 records the baseline commit and current behavior so the original performance baseline can be measured during the same shared session as the other variants.

- Compare **A** (original SQLite commit), **B** (module and transaction refactor on SQLite), and **C** (PostgreSQL with row locks). Keep worker count and limits fixed. Match seed, dataset, load settings, and measurement windows, and use a fresh DB for each run. Record the actual Kaggle CPU and memory limits. Keep ingress settings equivalent across compared runs and measure the rate-limited configuration separately if it changes the workload.
- Prioritize lifecycle 50/100 virtual users. Include lifecycle and Discovery read runs at 10/50/100 users, separate login/register measurements, and matching at 10/50/100/200 candidates with no-solution cases. Pre-issue tokens for lifecycle and read runs. Follow the baseline document for warm-up, repetitions, metrics, and reporting runs that fail to reach the measurement window.
- Review query plans, lock wait, transaction duration, and matching candidate counts before choosing a tuning change. Benchmark an index or Strategy optimization as its own variant and confirm the same API results. Test any two-replica variant separately after correctness checks, with the same total resource and DB connection budgets. A change to matching completion or failure semantics needs an ADR before moving computation outside its transaction.

Sources and follow-up scope are covered in the [architecture overview](README.md), [architecture proposal](de-xuat-kien-truc.md), [data and consistency design](du-lieu-va-nhat-quan.md), [ADR and milestones](adr-va-lo-trinh.md), and [Kaggle CPU benchmark plan](danh-gia-hieu-nang-baseline.md).
