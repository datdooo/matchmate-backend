# Member 1 · Phase 1 baseline and contract handoff

[Bản tiếng Việt](member-1-phase-1.vi.md)

Reviewed **19 November 2026** against starting commit
`696fbb1683eff430012f4db9db0701ec9a98fb01`.
The working tree already contained a newline-only change in `pyproject.toml`;
this review leaves it untouched. This handoff adds documentation and regression
tests; application behavior and schema have not been changed.

## Checklist status

| Phase 1 item | Status | Evidence / next action |
| --- | --- | --- |
| Trace transactions and list lifecycle invariants | Complete | Sections below link the current owners and record each command's invariants. |
| Run Auth/lifecycle tests, capture responses, identify commit-failure regressions | Complete | Existing tests plus the new baseline tests verify rollback and error responses when commit fails. Reproduction command below. |
| Agree UoW and session/user lock operations with Member 2 | Complete | Final signatures and transaction guarantees are recorded in the consolidated report. |
| Inventory profile consumers and route access, and agree profile/Catalog contracts with Member 3 | Complete | Consumer and route tables below. Final interfaces are recorded in the consolidated report. |

[Phase 1 consolidated handoff and final decisions](phase1.md).

## 1. Current transaction boundaries

| Operation | Starts transaction | Commits | What happens inside |
| --- | --- | --- | --- |
| Register | `provide_registration_service()` in [Auth dependencies](../../app/features/auth/dependencies.py) calls `uow.write()` before yielding | Dependency commits after route returns, with FastAPI function dependency scope | Duplicate email lookup, Argon2 hash, insert/flush, response construction. Hashing currently holds the write transaction. |
| Login | `provide_login_service()` calls `uow.read()` before yielding | No commit; read scope rolls back/closes on exit | Credential lookup, password verification, token issue. Verification currently holds the read transaction. |
| JWT user lookup | `lookup_authenticated_user()` opens its own read UoW in middleware | No commit | Loads current account, then closes the transaction before endpoint execution. This lookup is not the mutation's authoritative state check. |
| Create session | `provide_create_session_service()` in [session router](../../app/features/sessions/session_router.py) calls `uow.write()` | Dependency commits after endpoint constructs detail | Validate time/venue/profile/overlap, create session and host participation, close overlapping matching request, construct detail. |
| Cancel session | Same write dependency | Same dependency | Check host ownership before idempotency, cancel session and active participations, construct detail. |
| Session detail | `provide_read_session_service()` in session router calls `uow.read()` | No commit | Multiple reads of session, host, venue, and participations. SQLite currently has an explicit transaction snapshot. |
| Join / approve / reject / withdraw | [ParticipationService](../../app/features/sessions/participation_service.py) opens `uow.write()` itself | `_finish()` constructs detail, calls `uow.commit()`, then returns | Dependencies only wire adapters; repositories and matching writer share this UoW. |
| Discovery searches | [DiscoveryService](../../app/features/discovery/service.py) opens `uow.read()` | No commit | DTO queries, including count and page reads. |
| Create matching | Discovery service opens `uow.write()` | Service commits after replacement, insert, and group selection | Currently a single atomic command including suggestion computation. Member 3 owns its extraction. |

[SqlAlchemyUnitOfWork](../../app/db/unit_of_work.py) opens `BEGIN IMMEDIATE` for
writes and `BEGIN` for reads. Its `finally` rolls back and clears the session,
including when commit raises. Repositories flush but do not commit. SQLite busy
errors are translated to `DatabaseBusyError`. No PostgreSQL row locks exist yet.

### Lifecycle commands and invariants

| Command | Rules to preserve |
| --- | --- |
| Register | Normalize email; unique email enforced in DB; persist a password hash; never expose credentials. A failed commit must not leave an account. |
| Create session | Future window of 60–240 minutes; existing active venue; complete and eligible host; no accepted overlap. Insert the OPEN session and host's ACCEPTED participation with fee/gender snapshots, and close overlapping ACTIVE matching requests, in one transaction. |
| Join | Existing OPEN session before start; capacity available; current profile eligible; no active participation for the same user/session; no accepted schedule overlap. Insert PENDING with fee/gender snapshots. PENDING does not reserve capacity and may overlap another PENDING request. |
| Approve | Host only; participation PENDING; session OPEN and before start. Recheck current profile, capacity, and accepted overlap. Set ACCEPTED and close overlapping matching in one commit. Preserve the original fee/gender quote. |
| Reject | Host only; participation PENDING; session OPEN and before start. Set REJECTED without requiring current eligibility, free capacity, or lack of overlap. Preserve snapshots. |
| Withdraw | Participation owner only; host must cancel the session instead. PENDING/ACCEPTED becomes CANCELLED before start. An already CANCELLED record returns its existing state even after start; do not change its timestamp or reopen matching. REJECTED cannot be withdrawn. |
| Cancel session | Host only, including on repeated calls. Cancel before start; update the session and all PENDING/ACCEPTED participations atomically, preserving REJECTED/CANCELLED history and snapshots. Already CANCELLED returns the existing result even after start. Do not reopen matching. |

Across all lifecycle commands: accepted count never exceeds capacity (2 singles,
4 doubles, including host); accepted intervals overlap only when
`start_a < end_b and start_b < end_a`, so adjacent intervals are allowed.
One active participation per user/session preserves historical records.
Display status stays derived from time/counts rather than a stored FULL/STARTED state.

## 2. HTTP baseline and regression evidence

Errors use `{"error": {"code", "message", "details", "request_id"}}` with a
matching `X-Request-ID` response header. Exact dynamic IDs and timestamps are not
fixed fixtures. [Error handlers](../../app/api/error_handlers.py) define mappings.

| Trigger | Current response |
| --- | --- |
| Invalid body/query/path with authentication satisfied and no competing lock | `422 VALIDATION_ERROR`; invalid business time window uses `422 INVALID_TIME_WINDOW`. Validation details omit original sensitive input. |
| Missing/invalid JWT on a protected route, even with malformed body/path | `401 UNAUTHORIZED`, `WWW-Authenticate: Bearer`, before endpoint validation. |
| Unknown login email or wrong password | `401 INVALID_CREDENTIALS`, `WWW-Authenticate: Bearer`; same message for both cases. |
| Duplicate normalized registration email | `409 EMAIL_ALREADY_EXISTS`. |
| Duplicate join while the previous participation is active and earlier eligibility/capacity checks pass | `409 PARTICIPATION_ALREADY_EXISTS`. Validation order matters; a full session can instead fail first with `SESSION_FULL`. |
| Repeated creation for the same host/time | Current create logic rejects the accepted overlap with `409 TIME_CONFLICT`; there is no request-key replay. |
| Repeated decision on a non-PENDING participation | `409 INVALID_STATE`. |
| Repeated matching creation | `201` with a new ID; old ACTIVE request is CLOSED/REPLACED. Member 3 owns matching parity tests. |
| Repeated withdrawal / session cancellation by the authorized owner | `200`, same record/state/timestamps, including after start. Ownership is still checked. |
| Outsider decides/cancels/withdraws another user's object | `403 FORBIDDEN`; no mutation. Host withdrawal uses `409 HOST_PARTICIPATION_REQUIRED`. |
| SQLite write lock times out | `503 DATABASE_BUSY`, `Retry-After: 1`; no partial writes. |
| Unexpected commit failure | `500 INTERNAL_ERROR`, redacted; no successful response and no partial writes. |

**Error-ordering exception to carry into Phase 2:** while another writer holds
`BEGIN IMMEDIATE`, an invalid `{}` body currently produces `503` on registration
and session creation because their dependencies open the write transaction
before body validation. The same body on participation creation produces `422`
because its use case starts the transaction after validation. The proposed
refactor intentionally changes the first two to `422`; retain `401` precedence
on protected routes and update this baseline test when that change is implemented.

Existing evidence includes:

- [Auth tests](../../tests/auth/) for registration, normalization, uniqueness,
  JWT claims/signatures, and invalid authorization on public routes.
- [Sessions tests](../../tests/sessions/) for lifecycle transitions, snapshots,
  overlap/capacity, permissions, idempotent withdrawal, SQLite races and lock timeout.
- [Integrated routes](../../tests/integration/test_main.py) for cancel history and
  idempotency, matching closure, public searches, and consistent display status.
- [UoW tests](../../tests/foundation/test_unit_of_work.py) for commit, missing
  commit rollback, exception rollback, read transactions, and busy timeout.
- [New Member 1 baseline tests](../../tests/integration/test_member1_baseline.py)
  inject failure at `Session.commit()` after a real flush for register, create,
  cancel, join, approve, reject, and withdraw. Each tests both SQLite busy and
  unexpected failure; a fresh DB session verifies all five tables match the
  pre-command snapshot, including matching status and timestamps. They also cover
  401-before-validation, the 422/503 distinction, invalid login, and detail privacy.

The injected commit failures establish rollback when commit has **not succeeded**.
They do not establish recovery from an unknown commit outcome after connection loss.
SQLite races do not establish PostgreSQL concurrency correctness.

### Verification

Use Python 3.11+ and install `requirements-dev.txt` in an isolated environment.
The review used Python 3.12.3 and the repository's constrained dependencies.

```bash
python -m pytest tests/auth tests/sessions tests/foundation/test_unit_of_work.py tests/integration/test_main.py tests/integration/test_member1_baseline.py -q
ruff check tests/integration/test_member1_baseline.py
```

Results on 19 November 2026: **160 passed in 6.39 seconds**, including 29 new
Member 1 baseline cases; Ruff passed. Two dependency/test warnings remain:
Starlette's deprecated AnyIO portal alias and a short test key used deliberately
for the rejected HS512 token case. No test failed or was skipped.

## 3. Original contract proposal for Member 2

The target [UoW port](../../app/domain/ports.py) keeps `write()`, `read()`, and
`commit()`. Change its documentation to transaction guarantees rather than SQLite
SQL. Application commands open the write scope and explicitly commit once after
constructing the result. No automatic commit, nested UoW, or independent repository
transactions. Any exception or exit without commit rolls back; commit errors
propagate before a success response. An adapter session is usable only during
the scope and before commit. Dependencies construct adapters only.

`read()` must have a documented snapshot guarantee for composed detail/count/page
reads. SQLite already supplies it. Member 2 should explicitly provide PostgreSQL
REPEATABLE READ for those read scopes, or agree a distinct snapshot-read scope /
single-statement query implementation. PostgreSQL READ COMMITTED alone does not
give a transaction-wide snapshot. Write scopes use READ COMMITTED plus row locks.

Proposed injected port in `app/domain/ports.py` (not yet implemented):

```python
class TransactionLocks(Protocol):
    def lock_session(self, session_id: int) -> bool: ...
    def lock_user(self, user_id: int) -> bool: ...
```

- `True` means the row exists and is locked until this UoW ends; `False` means
  absent and lets the application select the existing not-found/auth error.
- The adapter uses the caller's connection and transaction; no commit and no new
  UoW. SQLite's existing database write lock can satisfy the synchronization
  requirement with an existence check. PostgreSQL uses row locks in its adapter.
- Read state again after locking. A pre-lock participation lookup is only for
  locating session/user IDs; it must not decide authorization or state transitions.
  Ensure ORM caching does not return pre-lock state.
- Lock existing sessions in ascending ID order, then users in ascending ID order,
  then participations and matching rows. Never acquire an existing session after
  holding a user lock. Read the clock after the required locks have been acquired.
- Join/decision/withdraw: session then target user. Cancel: session, discover active
  users, then users sorted/deduplicated. Create: host user only before inserting a
  new session. Matching creation: caller user only. This follows the
  [consistency design](du-lieu-va-nhat-quan.md#32-quy-tắc-thứ-tự-và-từng-use-case).
- Lock/pool/statement waits must be bounded. Member 2 must map PostgreSQL timeout
  errors deliberately; do not reuse SQLite error-code detection. Roll back the
  whole operation on failure. Never blindly retry an unknown commit outcome.
- Member 1 owns the application contract/call ordering; Member 2 owns SQL,
  dialect handling and independent-connection integration fixtures.

Matching's existing `MatchingRequestWriter.close_overlapping(user_id, starts_at,
ends_at, now)` is the proposed shared writer contract without signature changes:
same transaction, no internal commit, strict overlap, ACTIVE only, CLOSED/CONFIRMED
using the supplied clock. Inject it directly into create and approve rather than
making `SessionRepository` inherit it. Member 3 supplies its module-owned adapter;
Member 2 verifies it shares the persistence transaction.

## 4. Identity consumers and original Member 3 contract proposal

| Current consumer | Current dependency / information | Target |
| --- | --- | --- |
| Session create | `SessionService.users: UserRepository`, wired with `SqlAlchemyUserRepository`; needs ID, gender, skill | Inject Identity's profile reader, not the credential-capable repository. |
| Participation join/approve | `ParticipationRepository.get_user()` delegates to Auth's internal SQLAlchemy repository; needs gender and skill | Inject the same Identity profile reader into the application service. |
| Matching caller | Matching repository loads `UserModel` and returns `PlayerSummary` | Use the agreed profile contract; preserve current numeric-rank semantics in group selection. |
| Matching candidates | Matching repository joins request rows with `UserModel` | Agree an Identity-owned public projection/read contract for candidate joins; avoid one profile lookup per candidate. |
| Session/participation detail and Discovery search | Read adapters join `UserModel` for host/player ID, display name, skill, gender | Agreed public projection into DTOs; no email/hash/ORM objects escape. |
| JWT middleware and Auth register/login | Auth repository / credentials | Remain inside Identity; mutation use cases re-read the relevant profile after locking. |

Proposed Identity export in `app/features/auth/contracts.py`:

```python
@dataclass(frozen=True)
class PlayerProfile:
    id: int
    display_name: str
    skill_level: SkillLevel
    gender: Gender

class PlayerProfileReader(Protocol):
    def get_by_id(self, user_id: int) -> PlayerProfile | None: ...
```

No email, password hash, or credential lookup method. Return `None` for missing
accounts; allow legacy `UNSPECIFIED` gender so existing PROFILE_INCOMPLETE checks
remain effective. Sessions uses `skill_to_rank()` for its host-defined bounds;
Matching currently uses integer ranks in `PlayerSummary`, so its adapter must map
explicitly without changing ordering or rank-spread rules. Bind the reader to the
caller's UoW for authoritative mutation checks. Display-only joins may use the
agreed read projection in a consistent snapshot.

Proposed minimal Catalog export, owned by Member 3:

```python
class VenueStatusReader(Protocol):
    def is_active(self, venue_id: int) -> bool | None: ...
```

`None` means VENUE_NOT_FOUND (404); `False` means VENUE_INACTIVE (409); `True`
allows creation. Use the same transaction. Today Sessions implements this through
`SessionRepository.venue_is_active()` and Matching loads a Discovery `VenueRecord`.
Catalog also owns the richer venue projection (ID, name, address, district,
active status) used by Discovery/detail reads. Keep that read projection separate
from the minimal status check; no new venue administration API is needed.

## 5. Current route and object access rules

| Method / path | Authentication | Object/data rule |
| --- | --- | --- |
| POST `/auth/register`, POST `/auth/login` | Public | Invalid supplied Authorization still fails in middleware. |
| GET `/venues` | Public | Public venue DTOs. |
| GET `/sessions` | Public by default | `host_me=true` requires JWT; viewer ID comes from principal and limits results to that host. Other searches do not expose private participation management. |
| POST `/sessions` | JWT | Principal becomes host; payload cannot choose a different host. |
| GET `/sessions/{id}` | JWT | Any authenticated viewer; host alone receives `management`; each viewer sees only their own `my_participations`, including history. |
| DELETE `/sessions/{id}` | JWT | Host only, including repeated cancellation. |
| POST `/participations` | JWT | Principal is the joining user. |
| POST `/participations/{id}/decision` | JWT | Session host only. |
| DELETE `/participations/{id}` | JWT | Participation owner only; host cannot withdraw their host participation. |
| POST `/matching/requests` | JWT | Principal owns the request/replacement; suggestions omit email and other users' budgets. |
| GET `/health` | Public | Process liveness. |
| `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` | Public generated documentation | Current framework routes; include them when declaring route policy coverage. |

[JWT middleware](../../app/features/auth/middleware.py) currently infers protected
routes from method/path regexes. For session search, it recognizes truthy `host_me`
spellings `true`, `1`, `yes`, `on`, `t`, `y` case-insensitively. Invalid supplied
Authorization is rejected even on public routes; OPTIONS skips authentication.
Phase 2 should declare access policy explicitly and fail tests for undeclared new
routes, preserving these conditional-authentication rules.

## Final handoff decisions

The agreed contracts for UoW/locks, Identity, Catalog, Matching writer and database
errors are recorded in [the consolidated report](phase1.md). During the Phase 2
refactor, Members 1 and 2 will apply the agreed registration/create `503 → 422`
change for invalid payloads while preserving protected-route `401` precedence.
