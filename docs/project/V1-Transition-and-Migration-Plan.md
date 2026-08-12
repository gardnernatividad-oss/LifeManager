# LifeManager V1 Transition and Schema Refactor Plan

## 1. Status, scope, and durable assumption

This is the authoritative implementation-transition plan for moving the current repository to the approved LifeManager V1 Personal Workspace model. It defines schema transition, code dependencies, Alembic correctness, local database reset, tests, and implementation gates. It does not contain migration SQL and does not authorize Stage 4 implementation by itself.

> **Durable project assumption:** All database content created before the approved Personal Workspace V1 refactor is development/test data and is intentionally disposable.

LifeManager is pre-production. There are no real users, external API consumers, or business records to preserve. Existing User, Workspace, membership, Category, Task, TaskSeries, Project, Daily Form, settings, and other rows may be deleted. The V1 refactor requires no business-data backfill, archival, reconciliation, or compatibility UI.

The following are **preserved**:

- Git and source-code history;
- every historical Alembic migration file;
- approved product/data documentation;
- reusable authentication, authorization, database, API, frontend, and testing infrastructure.

The following are **disposable**:

- every row in the current development database;
- every legacy domain representation and setting that is absent from the approved target;
- local Alembic version state, because it can be rebuilt by replaying the preserved migration chain.

No destructive database operation is performed in this documentation stage.

## 2. Authority and target invariants

The target is defined by `docs/requirements/Functional.md`, ADR-005, `docs/database/V1-Target-Data-Model.md`, ADR-006, and the target ERD. `docs/project/V1-Refactor-Impact-Audit.md` describes the source implementation only.

Implementation must preserve these target rules:

- V1 exposes one Personal Workspace per newly registered user; multi-workspace architecture may remain internally for V2.
- Registration atomically creates User, `Personal` Workspace with target kind, OWNER membership, and WorkspaceTrackingMetadata.
- `User.timezone` is the sole V1 timezone source and must be a controlled valid IANA value; week starts Monday.
- Category and MasterTask are Workspace-specific and immutable after first use.
- Task is date-only and references MasterTask. It has no title, description, priority, time, direct Category, Project, or TaskSeries relationship.
- Programada and Pendiente are derived. Persisted result is nullable and permits only COMPLETED or NOT_COMPLETED.
- Recurrence is a finite request-time bulk-creation helper, never a persistent entity.
- PendingItem is independent. ProjectStep is not Task. Project date, progress, and status are derived from weighted Steps.
- Review is one atomic operational batch, not a questionnaire.
- Tracking is the complete editable registry and updates only the approved timestamps.
- Inicio is compact and operational; Reports are separate analytics.
- No persistent PendingItem/Project progress or comment history is introduced.

## 3. Selected schema-transition strategy

### 3.1 Options considered

**Option A — Incremental field-by-field reshape:** add and drop columns across many migrations while retaining intermediate legacy structures. This is technically valid but creates unnecessary hybrid models and dependency ordering for disposable data.

**Option B — Controlled application-domain reset migration:** preserve infrastructure/authentication structures that already fit the target, explicitly drop obsolete domain tables and constraints in dependency order, reshape retained infrastructure tables, and create the approved target domain directly.

**Option C — Delete/rewrite historical migrations or stamp a new baseline:** rejected. It breaks the repository migration chain and the required base-to-head guarantee.

### 3.2 Decision

Choose **Option B**, implemented through one or a small, tightly ordered set of **new** Alembic revisions after the current head.

This is simplest and safest because the application is pre-production and all rows are disposable. It avoids compatibility columns, staging/archive tables, dual domain models, recurrence export, ambiguous backfills, and duplicate APIs. It still preserves migration integrity:

```text
empty database
→ replay every historical migration unchanged
→ apply new destructive reset/target revisions
→ obtain exactly the approved V1 schema
```

The new revision(s) must use explicit object names and dependency-aware drop order. They may delete LifeManager application data and obsolete schema objects, but must not drop the PostgreSQL database, unrelated schemas/extensions, roles, or infrastructure outside the application-owned objects.

### 3.3 Migration packaging

Before Stage 4 implementation, choose packaging based on reviewability:

- Prefer one **domain reset** revision for obsolete tables/columns/enums and retained-table reshaping, followed by one **target domain creation** revision if a single revision would be difficult to review or round-trip.
- A single revision is acceptable only if upgrade/downgrade behavior stays understandable and testable.
- Authentication tables may be structurally retained and reshaped; their rows remain disposable.
- Every historical revision remains present and byte-for-byte unchanged.

## 4. Current-to-target schema disposition

| Current structure | Target action | Notes |
|---|---|---|
| `users` | RETAIN_STRUCTURE_WITH_CHANGES | Keep authentication/profile fields and UUID/audit conventions. Remove legacy `username`, `full_name`, `language`, and obsolete relationships when code no longer uses them. Keep only controlled `timezone`. All rows may be deleted by reset. |
| `workspaces` | RETAIN_STRUCTURE_WITH_CHANGES | Add target `kind`; retain name/audit/isolation. Remove description and Workspace timezone. No old row needs classification. |
| `workspace_members` | RETAIN_STRUCTURE_WITH_CHANGES | Preserve roles, unique membership, and Workspace isolation for V2 infrastructure. New V1 registration creates OWNER only. Rows may be reset. |
| `workspace_tracking_metadata` | CREATE_NEW | One-to-one Workspace metadata; new registration creates both timestamps null. |
| `categories` | RECREATE_TARGET | Name/normalized name only, Workspace-scoped unique, use-based immutability; remove description and `is_active`. Start empty. |
| `master_tasks` | CREATE_NEW | Workspace, Category, normalized unique name; start empty. No title inference. |
| `tasks` | RECREATE_TARGET | MasterTask, `planned_date`, nullable result, actors, version, audit. Drop every legacy Task row and old timed/free-text/direct-association shape. |
| `task_series` | DROP_OBSOLETE | Drop table, relationships, constraints, indexes, and enum after runtime dependencies are removed. No materialization/export. |
| `projects` | RECREATE_TARGET | Create approved Category/Steps/current-comment/version shape. Start empty. Do not convert old Projects or Task links. |
| `project_steps` | CREATE_NEW | Start empty; weighted target model only. |
| `pending_items` | CREATE_NEW | Start empty. No inference from legacy domains. |
| Daily Form tables | DROP_OBSOLETE | Drop definitions, questions, submissions, answers, constraints, and answer enum. No archive. |
| `user_settings` | DROP_OBSOLETE | No data migration. Approved profile/timezone lives on User. |
| `workspace_settings` | DROP_OBSOLETE | No target table or Workspace timezone. |
| Dashboard/reminder data | NO TABLE BACKFILL | Current services query other tables; remove obsolete runtime contracts. No reminder records exist to preserve. |

Target Category, MasterTask, Task, PendingItem, Project, and ProjectStep tables begin empty. The first application data is produced only through target APIs after a new user registers.

## 5. Personal Workspace and registration

There is no existing-user remediation. After reset, the database may contain zero users.

Every new registration performs in one transaction:

1. validate and normalize email/profile data and controlled IANA timezone;
2. create User;
3. create Workspace named `Personal` with target kind `PERSONAL`;
4. create OWNER WorkspaceMember;
5. create WorkspaceTrackingMetadata with null operational timestamps;
6. flush through services and commit exactly once in the route/application transaction boundary.

Any failure rolls back every record. Tests must prove there is no partial User, Workspace, membership, or metadata row. V1 frontend resolves this Workspace automatically and never presents a selector. Backend membership architecture may continue supporting future collaborative Workspaces without exposing them in V1.

## 6. Timezone

There is no timezone precedence or conversion problem because legacy rows are discarded.

- `users.timezone` is the only target source.
- Registration and Configuration accept only controlled valid IANA selections, not arbitrary free text.
- New-user default/selection follows the approved functional contract.
- Workspace, WorkspaceSettings, UserSettings, and TaskSeries timezone columns disappear with their obsolete consumers.
- Target Task stores `DATE`; no legacy `scheduled_at` conversion occurs.

Tests must cover valid zones, rejected invalid zones, local-date derivation, and relevant UTC/DST boundaries without migrating old timestamps.

## 7. Target domain initialization

### Categories

Create the target table empty. Users create their own Workspace-specific Categories. Enforce normalized uniqueness and nonblank values. Service checks references before edit/delete; database RESTRICT protects races. There is no description, activation lifecycle, or Category backfill.

### MasterTasks

Create the table empty. Users populate `Tablas > Tareas`. Do not infer records from legacy Task or TaskSeries titles. Enforce same-Workspace Category references, normalized uniqueness, and immutability after the first Task.

### Tasks

Create the approved table empty. No datetime conversion, collision remediation, CANCELLED archive, title conversion, or relationship preservation occurs. Target constraints and indexes can be introduced immediately because no legacy rows must satisfy them.

### PendingItems

Create the approved table empty. No legacy entity is equivalent. Add Planning, Review, Tracking, Inicio, and Reports integrations only in their dependency stages.

### Projects and ProjectSteps

Create the approved target shape empty. Drop legacy Projects and Task/TaskSeries relationships. Do not convert descriptions, activation state, or linked Tasks. Target activation validates Category, at least one Step, dates, positive weights, and exact total weight 100.00.

## 8. Legacy domain removal

The following require no data-migration or archive path:

- TaskSeries model, schema, services, materialization, synchronization, generation, routes, frontend page/client/types, and tests;
- legacy timed/free-text Task fields, direct Category/Project/TaskSeries relationships, CANCELLED, and old filtering contracts;
- legacy Project shape and Task/TaskSeries coupling;
- Category description and active/inactive lifecycle;
- Daily Form definition/question/submission/answer domain;
- Daily Task Generation and Daily Workflow;
- UserSettings, WorkspaceSettings, configurable week start, reminder/form/generation settings, and Workspace timezone;
- Reminder engine and endpoints;
- old Dashboard/Reports semantics and obsolete frontend pages/query keys.

Removal should follow code dependencies so each implementation stage remains coherent. No legacy feature is retained solely for compatibility.

## 9. API transition

Use a **coordinated internal cutover**, not parallel legacy/target business APIs.

- Backend and frontend are refactored together by domain stage.
- A stage may temporarily remove an obsolete business route before its final replacement only when the repository remains internally coherent and tests describe that stage.
- Do not create `/api/v2`; this remains V1 development.
- Reuse existing paths when their resource meaning remains clear. Introduce target resources such as `master-tasks`, `pending-items`, and `review` directly.
- Replace the Task contract once, rather than accepting both legacy and target fields.
- Remove TaskSeries, Daily Form/Workflow, reminder, obsolete settings, and old Dashboard contracts when their replacement/dependency stage lands.
- Remove router registrations, schemas, services, query keys, frontend types, and tests together.
- Remove the duplicate unversioned `/auth/*` mount after confirming the frontend uses canonical `/api/v1/auth/*`; no external compatibility period is required.

Authentication, authorization, transaction ownership, CORS, and error hygiene remain operational throughout.

## 10. Frontend transition

Replace pages in target dependency order. No archival or remediation UI is necessary.

- Preserve authentication restoration, protected routes, Axios Bearer handling, QueryClient, PWA, responsive shell, accessibility, forms, and reusable visual primitives.
- Resolve the newly created Personal Workspace automatically; remove selector behavior.
- Replace Sidebar/router with Inicio, Review, Planning, Tracking, Reports, Tables, and Configuration hierarchy.
- Remove Recurring Tasks; finite bulk creation belongs in Planning Tasks.
- Replace timed Task, legacy Project, Daily Workflow, Category lifecycle, settings, Dashboard, and Reports screens as their target backend becomes available.
- Delete obsolete query keys/types/API clients with their pages so caches cannot mix contracts.

## 11. Optimistic concurrency

There is no version backfill. New mutable target rows start with `lock_version = 1` using ORM and server defaults plus a positive check.

- Mutations include the expected version where required.
- Updates scope by ID, Workspace, and expected version, then increment atomically.
- A stale version returns HTTP 409 without leaking cross-Workspace existence.
- Review and Tracking batches are atomic: one stale/invalid row rolls back every row and prevents metadata timestamp advancement.
- Services flush only; routers own commit/rollback.

## 12. Development database reset procedure

Stage 4 must distinguish repository history from local contents:

### Repository migration history

Keep every file in `backend/alembic/versions/`. Add only new revision(s) after the current head. Validate both migration paths:

1. existing local schema at current head → new head;
2. empty LifeManager database → `alembic upgrade head` → final target schema.

### Local PostgreSQL contents

At the approved implementation point:

1. verify the connection identifies the intended local LifeManager development database;
2. stop backend/frontend processes that can write;
3. optionally take a disposable diagnostic backup for troubleshooting, not product retention;
4. reset only the LifeManager development database/schema using the repository's established local procedure;
5. run `alembic upgrade head` from base against the empty database;
6. inspect Alembic current/head and target tables, FKs, checks, indexes, defaults, and enum cleanup;
7. run backend tests and create fresh accounts only through target registration.

Never run reset commands against an unresolved URL, server-wide PostgreSQL objects, another database, or a production environment. Stage 4 must require an explicit environment guard such as a development-only database name/configuration assertion before destructive execution.

An alternative validation path applies the new destructive migration to a disposable database already at the old head. Both paths must produce equivalent target metadata.

## 13. Simplified implementation sequence

### Stage A — Reset migration design and verification harness

- Inventory exact current FK/table/enum dependency order.
- Write new Alembic reset/target revision(s), never historical edits.
- Add schema assertions and test both old-head→new-head and base→new-head paths on disposable databases.
- Gate: final metadata matches ADR-006/target model exactly.

### Stage B — Core target models and infrastructure

- Align User, Workspace, WorkspaceMember, WorkspaceTrackingMetadata, model exports, and target FK conventions.
- Preserve auth/session/authorization transaction patterns.
- Gate: metadata/model tests and one Alembic head.

### Stage C — Personal Workspace registration and Configuration foundation

- Implement atomic registration and `/me`/profile timezone exposure.
- Automatically resolve Personal Workspace; remove V1 selector behavior when frontend stage lands.
- Gate: rollback/no-partial-record tests and controlled IANA validation.

### Stage D — Categories and MasterTasks

- Implement target schemas/services/routes/tests and use-based immutability.
- Start both tables empty.
- Gate: Workspace isolation, normalized uniqueness, RESTRICT, and immutability race tests.

### Stage E — Tasks and finite bulk creation

- Replace legacy Task model/contracts/runtime with date-only target behavior.
- Implement result correction, target deletion rules, derived status, pagination/filtering, and direct finite bulk creation.
- Remove TaskSeries runtime and schema dependencies.
- Gate: no timed/free-text/direct-project/recurrence fields remain in target API or metadata.

### Stage F — PendingItems

- Implement Planning/Tracking-ready current-state model, API, filters, derived values, and versions.
- Gate: consistency constraints, Workspace isolation, and concurrency tests.

### Stage G — Projects and ProjectSteps

- Implement target structure, activation validation, weighted derivations, comments, timestamps, and versions.
- Gate: Steps are independent from Tasks; weights total exactly 100.00 for active Projects.

### Stage H — Review

- Implement composed relevant rows and one atomic final save across target domains.
- Gate: approved row fields only, local-date rules, total rollback on any error, exact metadata behavior.

### Stage I — Tracking

- Implement complete Task/PendingItem/Project registries and batch/detail saves.
- Gate: correction, pagination, filters, concurrency, and timestamp behavior.

### Stage J — Inicio and Reports

- Implement operational Inicio and separate domain analytics using target semantics.
- Gate: database-side query correctness, report/tracking reconciliation, and performance.

### Stage K — Target frontend navigation and pages

- Cut over layout/navigation and domain pages as their APIs stabilize; remove obsolete pages/clients/query keys.
- Gate: typecheck, lint, build, tests, accessibility, responsive behavior, and no Workspace selector.

### Stage L — Remaining legacy runtime cleanup

- Remove Daily Form/Workflow, settings/reminder, old Dashboard/Reports, duplicate auth mount, stale exports/imports/tests, and obsolete database types not already removed.
- Gate: repository-wide legacy reference scan distinguishes only immutable migrations/superseded docs.

### Stage M — Final validation and QA

- Rebuild database from empty through full migration chain.
- Test destructive upgrade from old head on a disposable copy.
- Run complete backend/frontend suites, schema inspection, OpenAPI/route audit, PWA/build checks, and target product acceptance.
- Gate: one Alembic head, exact target schema, zero unexpected legacy runtime, and all approved V1 behavior passing.

Stages may be split into smaller commits, but dependency order must remain. Avoid a long-lived branch where models expect tables not yet supplied by the current migration head.

## 14. Test strategy

- Keep high-value security, auth, current-user, CORS, session, Workspace isolation, transaction, validation, and frontend infrastructure tests.
- Replace domain tests when the corresponding legacy domain is replaced; do not preserve assertions for disposable behavior.
- Add schema-level tests for exact target tables/columns/FKs/checks/indexes/defaults and absence of obsolete tables/columns/enums.
- Test new registration on an empty database and rollback after failures at each record-creation step.
- Test Workspace-aware references and service authorization independently.
- Test date-only/derived Task semantics and finite idempotent bulk creation without TaskSeries.
- Test stale single/batch mutations and total rollback.
- Validate Alembic from base and from old head on isolated disposable PostgreSQL databases.
- Keep frontend typecheck, lint, build, PWA, route guard, cache isolation, responsive, and accessibility gates.

## 15. Rollback and destructive-operation gates

Data rollback is not required, but source/schema rollback remains useful during development.

- Commit history provides code rollback; historical migrations provide reproducible source schema history.
- Before the destructive revision is shared, test its downgrade where technically meaningful. A downgrade may recreate obsolete structure without restoring discarded rows; document that limitation explicitly.
- After reset, the canonical recovery is: fix migration/code, recreate the disposable development database, and replay base→head.
- Do not carry archival tables or compatibility columns merely to support row recovery.
- Do not drop PostgreSQL database/server infrastructure or non-LifeManager schemas/extensions.
- Drop obsolete PostgreSQL enum types only after all dependent columns/defaults are gone.
- Every destructive command must verify the resolved target is the explicit development database.

Go/no-go before Stage 4 destructive execution:

1. product-owner disposal approval is recorded by this plan;
2. target migration review is complete;
3. environment guard proves a development database;
4. base→head and old-head→new-head have passed on disposable databases;
5. no historical migration file changed;
6. rollback/recreate instructions are documented;
7. all active processes using the database are stopped.

## 16. Remaining technical risks

- Incorrect drop order can fail because current Tasks, TaskSeries, Daily Form, settings, Projects, Categories, Users, and Workspaces have intertwined FKs and PostgreSQL enum dependencies.
- A reset migration can appear correct on an existing database but fail during base→head replay; both paths are mandatory.
- Models/routes/tests can become temporarily inconsistent if schema and runtime cleanup are combined without coherent stage boundaries.
- PostgreSQL enum/default dependencies may survive column drops unless explicitly inspected.
- The database reset command could target the wrong database without a strict development guard.
- Removing duplicate/unversioned routes or frontend query keys incompletely can leave hidden runtime surfaces despite disposable data.

These are technical implementation risks only. No product-owner decision about legacy record preservation remains.

## 17. Stage 4 entry criteria

Stage 4 may begin only when:

- this simplified reset strategy is approved;
- the exact application-owned object/drop inventory is reviewed;
- an isolated PostgreSQL database is available for both migration paths;
- the development database guard/reset procedure is agreed;
- migration packaging (one or two new revisions) is selected for reviewability;
- no proposal edits or deletes a historical Alembic revision.

Stage 4 should implement the schema reset/target foundation only. It must not silently expand into all backend/frontend stages.
