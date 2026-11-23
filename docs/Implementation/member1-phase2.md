# Member 1 Phase 2 handoff

**23 November 2026 · SQLite baseline `f5e9806`**

Member 1 completed the Identity and Sessions refactor on SQLite. Auth and Sessions use cases now own their transaction boundaries, session details have a dedicated read service, and every registered HTTP route has an access policy. This baseline is ready for the PostgreSQL lifecycle and snapshot checks in Phase 3. [Phase 2 implementation plan](../Architecture_Phase2/ke-hoach-trien-khai.md) · [Phase 1 contract handoff](member-1-phase-1.md)

## Transaction boundaries

| Operation | Phase 2 behavior |
| --- | --- |
| Register | Validate the request and hash the password with Argon2 before opening the write transaction. Check email uniqueness, insert the user, and commit inside `AuthService.register()`. Duplicate registration still returns `409 EMAIL_ALREADY_EXISTS`, with hashing now occurring before the duplicate check. [Auth service](../../app/features/auth/service.py) |
| Log in | Read the user ID and stored hash in a short read transaction. Close that transaction, verify the password, then issue the token on success. An unknown email and a wrong password still produce the same `401 INVALID_CREDENTIALS` response. [Auth service](../../app/features/auth/service.py) |
| Create or cancel a session | `SessionService` starts the write transaction, checks the rules, applies the changes, and builds the response using the current transaction. It commits before returning the result. [Session command service](../../app/features/sessions/session_service.py) |
| Read session details | `SessionDetailService` opens its own read transaction. The detail reader fetches the session, host, venue, and participations from one SQLite snapshot. Create and cancel reuse the same reader and response builder inside their existing write transaction. [Detail service](../../app/features/sessions/session_detail_service.py) · [SQLAlchemy detail reader](../../app/features/sessions/session_detail_reader.py) |
| Join, approve, reject, or withdraw | `ParticipationService` keeps the state checks, mutations, and response read within its write transaction. The service commits before returning. [Participation service](../../app/features/sessions/participation_service.py) |

The dependencies construct the Unit of Work and its adapters. Repositories use the active SQLAlchemy session and flush when they need an ID or need to surface a constraint violation. SQLite writes begin with `BEGIN IMMEDIATE`. If a write or commit fails before the transaction becomes durable, the Unit of Work rolls back the pending changes and propagates the error. Lock contention maps to `503 DATABASE_BUSY` with `Retry-After: 1`. An unexpected technical failure maps to a redacted `500 INTERNAL_ERROR`. [Auth wiring](../../app/features/auth/dependencies.py) · [Composition root](../../app/composition.py) · [Unit of Work](../../app/db/unit_of_work.py) · [API error handlers](../../app/api/error_handlers.py)

## Lifecycle rules and module boundaries

- Creating a session inserts the host's `ACCEPTED` participation in the same transaction. The host already occupies one place in the new session. [Session repository](../../app/features/sessions/session_repository.py)
- A join records `gender_at_join` and `quoted_fee_vnd`. Approval checks the player's current eligibility, capacity, and schedule overlap while preserving those recorded values. [Participation service](../../app/features/sessions/participation_service.py) · [Approval regression test](../../tests/sessions/test_service.py)
- Repeating a cancel or withdraw as the authorized caller preserves the original `cancelled_at`, including after the scheduled start. Ownership checks still apply on a repeat. Session cancellation marks active participations as cancelled and preserves rejected history. [Cancellation regression test](../../tests/integration/test_main.py) · [Withdrawal regression test](../../tests/sessions/test_service.py)
- Session creation closes the host's overlapping active matching requests. Approval closes the approved player's overlapping active requests. Both call `MatchingRequestWriter.close_overlapping()` through the caller's Unit of Work and record `CONFIRMED` as the reason. A failed transaction rolls back the booking and the matching closure together. Cancel and withdraw leave previously closed matching requests closed. [Matching writer port](../../app/domain/ports.py) · [Matching writer adapter](../../app/features/matching/infrastructure/matching_request_writer.py)
- Sessions and Matching get profiles through Identity's `PlayerProfileReader`. The DTO contains only ID, display name, skill level, and gender. The composition root wires the SQLAlchemy reader, repositories, and `SystemClock`. Eligibility and transition rules live in the Sessions domain package and have database-free tests, including a fake clock for cancellation timing. [Identity profile contract](../../app/features/auth/contracts.py) · [Composition root](../../app/composition.py) · [Sessions policies](../../app/features/sessions/domain/policies.py) · [Policy tests](../../tests/sessions/test_policies.py)

## API access and compatibility

| Request or condition | Expected behavior |
| --- | --- |
| `GET /sessions` without `host_me` or with `host_me=false` | Public search. |
| `GET /sessions?host_me=true` | Requires a valid JWT and scopes results to sessions hosted by the authenticated viewer. Truthy spellings `true`, `1`, `yes`, `on`, `t`, and `y` are recognized case-insensitively. |
| `GET /sessions/{session_id}` | Requires a valid JWT. The host sees `management`. Each viewer sees only their own `my_participations`, including history. Non-host viewers receive `management: null`. |
| Missing or invalid authentication on a protected route | Returns `401 UNAUTHORIZED` before body, path, or query validation. An invalid supplied token also returns `401` on public routes. |
| Malformed `POST /auth/register` or an authenticated malformed `POST /sessions` while the SQLite writer lock is held | Returns `422 VALIDATION_ERROR`. Both endpoints now validate the request before trying to obtain the write lock. A valid request whose write lock times out still returns `503 DATABASE_BUSY`. |

The route access table declares public, protected, and conditional access by HTTP method and route path. An inventory test compares it with FastAPI's registered routes, including generated documentation routes. Object-level authorization still happens in the use cases. For example, a valid JWT lets a viewer read session details, while only the host can cancel the session. [Route access table](../../app/features/auth/route_access.py) · [JWT middleware](../../app/features/auth/middleware.py) · [Access tests](../../tests/auth/test_jwt_middleware.py)

## Verification

Run from the repository root with the development and load-test dependencies installed.

```bash
python -m pip install -r requirements-load.txt
python -m pytest -q
python -m ruff check .
python -m scripts.check_architecture
```

On Windows, enable Python UTF-8 mode for the suite with `$env:PYTHONUTF8 = '1'` in PowerShell. The full suite for `f5e9806` passed **411 tests** on SQLite.

| Check | Evidence |
| --- | --- |
| Commit failures and rollback | Injects busy and unexpected commit failures, checks the HTTP status, and compares the committed database before and after. Includes registration, session create and cancel, and participation commands. [Commit and API regression tests](../../tests/integration/test_member1_baseline.py) |
| Password work outside transactions | Records Argon2 hashing before the registration transaction starts and verification after the login read transaction closes. [Auth integration tests](../../tests/auth/test_integration.py) |
| Privacy, response parity, and matching | Covers host, participant, and uninvolved viewer detail responses. Checks that the create and cancel responses match a subsequent GET and that create and approval close overlapping matching requests. [Privacy regression test](../../tests/integration/test_member1_baseline.py) · [Lifecycle integration tests](../../tests/integration/test_main.py) |
| Lifecycle concurrency on SQLite | Exercises the last available spot, one player's overlapping approvals, approval versus cancellation or withdrawal, and a lock wait that crosses the session start. [Concurrency tests](../../tests/sessions/test_concurrency.py) |

## PostgreSQL integration handoff

1. Keep the use cases in charge of opening and committing transactions. Move the SQLite-specific `BEGIN IMMEDIATE` behavior and busy-error detection behind the database implementation. Wire PostgreSQL row locks through the repositories and keep them in the same transaction as the mutations.
2. Apply the proposed lock order for existing resources. Join, approve, reject, and withdraw lock the session before the user. Cancellation locks the session first, then locks affected users in ascending ID order. Session creation locks the host before checking overlap. Matching creation takes the same user lock so it coordinates with session creation and approval.
3. Re-read the clock and relevant state after acquiring locks. Run race checks with independent PostgreSQL connections and inspect the committed state for over-capacity, overlapping accepted bookings, and matching requests left active after a confirmed booking.
4. Verify the detail read uses one consistent snapshot on PostgreSQL. Under the default `READ COMMITTED` isolation, successive queries can see different snapshots. Use one query or a read transaction with `REPEATABLE READ` where the detail projection needs to combine several queries.
5. Verify JWT precedence, conditional `host_me` access, and host and owner enforcement through the integrated ingress path. Keep PostgreSQL race and ingress results separate from the SQLite test baseline above.

[Lock protocol and isolation design](../Architecture_Phase2/du-lieu-va-nhat-quan.md) · [Phase 3 integration checklist](../Architecture_Phase2/ke-hoach-trien-khai.md#phase-3--postgresql-integration--2324-november)
