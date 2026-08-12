# LifeManager V1 Refactor Impact Audit

## 1. Status, scope, and authority

This document records the Stage 2 audit of the repository as it exists on 2026-08-11. It is an implementation-impact report, not a migration specification. No migration or compatibility behavior is authorized by this document.

The authoritative target is defined by `docs/requirements/Functional.md`, ADR-005, `docs/database/V1-Target-Data-Model.md`, and ADR-006. Historical documents and existing implementation behavior describe the source state only.

Classification terms:

- **KEEP**: usable without a product-semantic change.
- **KEEP_WITH_CHANGES**: the component remains, but its contract or fields change.
- **REFACTOR**: its responsibility remains but requires substantial internal redesign.
- **REPLACE**: the current contract or data shape cannot represent the target safely.
- **REMOVE_AFTER_MIGRATION**: retain temporarily for data/API compatibility, then retire.
- **NEW**: no current equivalent exists.

## 2. Executive technical summary

LifeManager already has sound reusable infrastructure: FastAPI routing and dependencies, SQLAlchemy 2.x sessions and typed models, Alembic, JWT authentication, password hashing, workspace membership authorization, transaction ownership in routers, Pydantic validation, React/Vite/PWA infrastructure, route guards, Axios authentication, TanStack Query, forms, responsive layout, and broad tests.

The implemented product domain is nevertheless materially different from the approved Personal Workspace V1. Current Tasks are free-text, timestamped records with direct Category, Project, and persistent TaskSeries relationships. The daily experience is a configurable questionnaire coupled to recurring-task generation. The current Dashboard is task analytics. Settings expose reminder, week-start, daily-form, task-generation, and Workspace-timezone controls. The frontend exposes multiple Workspace selection.

The target instead requires MasterTask plus date-only Task occurrences, PendingItem, Project plus ProjectStep, a domain-composed Review, Personal Workspace registration, Workspace tracking metadata, and a compact Inicio. This is a staged replacement, not a field-renaming exercise. Existing migrations must remain immutable; compatibility and data backfills need new migrations and explicit cutover boundaries.

## 3. Current architecture inventory

### Backend

- Application entry and configuration: `backend/app/main.py`, `backend/app/core/config.py`.
- Persistence: `backend/app/db/session.py`, `backend/app/models/base.py`, SQLAlchemy `Session`, PostgreSQL-specific UUID/ENUM/ARRAY usage.
- Shared API dependencies: `backend/app/api/dependencies.py` provides session and current-user resolution.
- Authentication: `backend/app/api/routes/auth.py`, `backend/app/services/user.py`, `backend/app/core/security.py`, `backend/app/core/tokens.py`.
- Versioned API composition: `backend/app/api/v1/router.py`.
- Authorization: workspace membership lookup in `backend/app/services/workspace.py`, reused by domain services.
- Transaction convention: services add/delete/flush; write routers commit/refresh and roll back errors; read routes do not write.
- Domain modules: Workspace, Category, Task, TaskSeries, Project, Daily Form, Daily Workflow, Dashboard, Reminder, User Settings, Workspace Settings.
- No repository abstraction is present; services construct SQLAlchemy `select()` expressions directly.

### Current API surface

All versioned domain routes are mounted below `/api/v1`. The active surface is:

- Authentication: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`.
- Workspaces: create, list, detail, patch, and delete at `/workspaces`.
- Tasks: create/list/detail/patch plus `complete`, `not-complete`, and `cancel` actions at `/workspaces/{workspace_id}/tasks`.
- TaskSeries: create/list/detail/patch, activate/deactivate, Workspace/series materialization, and synchronization at `/workspaces/{workspace_id}/task-series`.
- Categories and Projects: create/list/detail/patch and activate/deactivate at their Workspace-scoped collections.
- Daily Form: get/replace definition and get/replace dated submission at `/workspaces/{workspace_id}/daily-form`.
- Daily task generation and workflow: dated POST actions under their Workspace-scoped resources.
- Dashboard: summary and statistics GET endpoints.
- Reminders: a read-only evaluation endpoint.
- User Settings and Workspace Settings: GET/PUT replacement endpoints.

`backend/app/main.py` also mounts the same auth router directly, so authentication is currently reachable both under `/api/v1/auth/*` and unversioned `/auth/*`. The frontend contract uses the versioned API base. Stage 3 should treat the duplicate unversioned mount as a compatibility/security-surface cleanup decision rather than silently retaining two public contracts. Root, health, and database-test endpoints are also mounted directly; `/db` and the startup database-name print are operational diagnostics to review before production hardening, although they are not product-domain blockers.

### Frontend

- React/TypeScript/Vite/PWA under `frontend/`.
- Router and guards: `frontend/src/router/`.
- Authentication and Workspace state: `frontend/src/contexts/AuthContext.tsx`, `frontend/src/hooks/useAuth.ts`, `frontend/src/hooks/useWorkspaces.ts`.
- API and cache layer: Axios clients in `frontend/src/api/`, query keys in `frontend/src/api/queryKeys.ts`, TanStack Query.
- Authenticated shell: `frontend/src/layouts/AuthenticatedLayout.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `Topbar.tsx`.
- Implemented pages: Login, Dashboard, Tasks, Recurring Tasks, Projects, Daily Workflow, Categories, Settings, Reports.
- Shared styling is in `frontend/src/styles/`; pages currently own much of their domain-specific UI.

## 4. Backend component matrix

| Component | Current implementation | Approved target | Class | Required change and impact |
|---|---|---|---|---|
| BaseEntity/session/config/CORS | UUID/audit base, shared session dependency, settings, restricted development CORS | Same infrastructure | KEEP | Preserve. Add target models to metadata without changing transaction ownership. Existing infrastructure tests remain valuable. |
| Application startup/diagnostics | Versioned API plus duplicate unversioned auth mount, root/health/DB diagnostic routes, DB-name startup print | One explicit supported API contract and production-safe health diagnostics | KEEP_WITH_CHANGES | Preserve app/middleware composition; decide compatibility removal for duplicate auth and harden `/db`/startup diagnostics separately from domain migration. |
| JWT/security/current user | Bearer JWT, active-user lookup, `/auth/login`, `/auth/me` | Same authentication basis | KEEP | Preserve generic security and 401 behavior. |
| Registration | `UserCreate` accepts email, password, first/last name; `register_user` creates only User and fills legacy `username`/`full_name` | Atomically create User, `Personal` Workspace with `kind=PERSONAL`, OWNER membership, and tracking metadata | REFACTOR | Registration service needs a single transaction boundary spanning all records. Existing users without a Workspace require remediation. Registration route still owns commit. |
| User | Authentication fields plus legacy username/full_name/language; timezone defaults to `America/Lima` | Authentication/profile fields and the sole V1 IANA timezone source | KEEP_WITH_CHANGES | Retain IDs, email, hash, names, active flags, timezone. Deprecate legacy identity/language only after compatibility/backfill review. Expose/update timezone through approved profile contract. |
| Workspace | Name, description, timezone; multiple workspaces exposed | Technical isolation with `kind`; V1 creates one Personal Workspace | KEEP_WITH_CHANGES | Add/backfill `kind`; stop using Workspace timezone in V1; hide collaborative creation/selection behavior without destroying future membership infrastructure. |
| WorkspaceMember | OWNER/ADMIN/MEMBER/VIEWER and scoped membership queries | Keep technical ownership; V1 product creates OWNER only | KEEP_WITH_CHANGES | Preserve authorization and isolation helpers. Reassess FK delete behavior and V2-only roles, but do not remove them. |
| WorkspaceTrackingMetadata | Absent | One row per Workspace with review and Pending tracking timestamps | NEW | Add model/service behavior after Personal Workspace foundation. `last_review_saved_at` is V1 Workspace-level only because there is one active product member. |
| Category | Name, normalized name, description, `is_active`; create/read/update/activate/deactivate | Name/normalized name only; editable/deletable before first use, immutable after any MasterTask/PendingItem/Project reference | REPLACE | Preserve normalization, scoped uniqueness, membership checks, list/query patterns, IntegrityError translation. Remove lifecycle/description from target contracts; replace activate/deactivate with pre-use update/delete rules. Data must retain referenced/inactive category identities. |
| MasterTask | No equivalent | Workspace/category/name/normalized name; immutable after first occurrence | NEW | Candidate source is distinct cleaned current Task/TaskSeries title plus Category, but collisions and inconsistent historical naming require a Stage 3 mapping policy. |
| Task | Free-text title/description; `scheduled_at` TIMESTAMPTZ; direct Category/Project/TaskSeries; nullable outcome including CANCELLED | Date-only occurrence referencing MasterTask; nullable result COMPLETED/NOT_COMPLETED; actors and lock version | REPLACE | Retain row identity/audit where safe, workspace isolation, query construction, pagination, transaction patterns. Replace schema/service/routes and all semantic filters. Data conversion is high risk. |
| Task resolution | Complete/not-complete/cancel endpoints; any resolved Task becomes immutable | Initial resolution plus correction between two terminal results; no cancellation | REPLACE | Remove cancellation after compatibility; add correction pencil flow with optimistic locking and renewed actor/timestamp. |
| TaskSeries | Persistent recurrence definition, materialization, synchronization, activation lifecycle | No persistent recurrence/provenance; temporary bulk creation inserts independent Tasks | REMOVE_AFTER_MIGRATION | Keep until existing series data and future materializations are resolved. Then remove model, services, endpoints, schemas, relationships, exports, frontend, and active tests. Historical migration remains. |
| Project | Standalone normalized-name record with description and `is_active`; Tasks/TaskSeries point to it | Category-owned Project with current comment, tracking timestamp, lock version, and ProjectSteps; no Task relation | REPLACE | Workspace authorization/CRUD shell and some normalization UI can be reused. Data shape and operations are fundamentally different. Remove Task/TaskSeries coupling only after Task migration. |
| ProjectStep | Absent | Weighted, dated, trackable Project component | NEW | Add after target Project/Category foundation; requires structure validation, derived progress, batch tracking, and optimistic concurrency. |
| PendingItem | Absent | Category-owned current-state tracked item with progress/date/comment/version | NEW | Category/project list, filter, pagination, form, route, and transaction patterns are reusable; no existing data entity is semantically equivalent. |
| Daily Form definitions/questions | Workspace questionnaire with ordered BOOLEAN/TEXT/NUMBER questions | No configurable questionnaire | REMOVE_AFTER_MIGRATION | Do not reuse question semantics for Review. Definition CRUD, schemas, models, and routes become obsolete. |
| Daily Form submissions/answers | One submission per workspace/user/date with answer snapshots | Review saves current Tasks/PendingItems/ProjectSteps and Workspace metadata atomically | REMOVE_AFTER_MIGRATION | Submission timestamps are not automatically equivalent to Review completion. Preserve/retire data according to an explicit archival policy. |
| Daily Task Generation | Generates TaskSeries occurrences for a workflow date | No scheduler or persistent recurrence; planning bulk request creates dates once | REMOVE_AFTER_MIGRATION | Recurrence date algorithms may inform a request calculator but current materialization side effects and provenance must not survive. |
| Daily Workflow | Orchestrates Workspace settings, generation, form readiness | Review composition and atomic batch save | REPLACE | Reuse membership, timezone/date validation, router transaction pattern, and batch-test ideas. Replace readiness/questionnaire/generation semantics. |
| Dashboard summary/statistics | SQL aggregates over Task outcome and `scheduled_at`; cancellation and UTC-now semantics | Inicio operational rows across Tasks, PendingItems, Projects; Reports own analytics | REPLACE | SQL aggregate patterns are reusable for Reports. Existing response contracts and cards do not match Inicio. |
| Reminder engine | Computes form/task reminders using settings and timestamps | Outside approved V1 | REMOVE_AFTER_MIGRATION | Retire route/schema/service after callers and settings are removed. No reminder table exists. |
| User Settings | Separate one-to-one timezone/locale/week start/reminder configuration | Profile fields plus User timezone only | REMOVE_AFTER_MIGRATION | Merge authoritative timezone to User under a conflict-resolution policy; other fields are obsolete V1. |
| Workspace Settings | Workspace timezone, week start, form/generation flags/time | No V1 Workspace settings surface or timezone | REMOVE_AFTER_MIGRATION | Remove after Daily Workflow/TaskSeries retirement. Preserve no duplicate timezone source. |
| Workspace CRUD routes | Create/list/detail/update/delete-like behavior with authenticated current user | Personal Workspace resolved automatically in V1 UI | KEEP_WITH_CHANGES | Keep technical API as needed for infrastructure/V2, but V1 clients should not offer selection or collaboration flows. |

Cross-cutting reusable behavior includes scoped lookup by both resource and Workspace IDs, 403 for nonmembership, 404 for scoped missing resources, 409 for domain conflicts, Pydantic `extra="forbid"`, deterministic ordering, DB-side filters/counts, and router-owned commits.

## 5. Current database and Alembic audit

### Chronological migration history

The repository has one linear chain:

1. `30b0a8ec85aa_create_users_table.py`: users with email, username, full name, password hash, timezone, language, flags, UUID/audit fields.
2. `813f6ce3a35b_create_workspaces_and_workspace_members.py`: workspaces and role-based membership.
3. `5ff19898899a_prepare_users_for_authentication.py`: renames password hash, adds first/last names, preserves legacy identity/preferences, and establishes the current email constraint/index.
4. `6fc7f7599458_create_tasks_table.py`: original status/priority/due/completion/position/archive Task shape.
5. `25776ea3a156_create_categories_table.py`: current Category table.
6. `85484c8a04b9_add_category_to_tasks.py`: nullable Category FK and Workspace/category index.
7. `b3a41f2c9d70_create_projects_table.py`: current Project table.
8. `c7d9e2a4f681_add_project_to_tasks.py`: nullable Project FK and index.
9. `e5b8c1d3a902_finalize_manual_task_contract.py`: replaces legacy status/priority/due/archive columns with `scheduled_at`, `outcome`, and `resolved_at`.
10. `f6c9d2e4b713_create_task_series_table.py`: persistent recurrence definitions.
11. `a7d0e3f5c824_link_tasks_to_task_series.py`: TaskSeries FK and occurrence uniqueness.
12. `d4e8f1a2b3c4_create_daily_form_definition.py`: definition and questions.
13. `e5f9a2b3c4d5_create_daily_form_submissions.py`: submissions and answers.
14. `f7a0b1c2d3e4_add_workspace_timezone.py`: Workspace timezone.
15. `0a1b2c3d4e5f_create_user_settings.py`: user preferences/reminders.
16. `1b2c3d4e5f60_create_workspace_settings.py`: daily workflow/generation/workspace preferences; current head.

Historical migrations must remain unchanged even when their tables or PostgreSQL enum types later become obsolete.

### Current-versus-target table matrix

| Current table | Current physical contract | Target disposition | Important gap/data implication |
|---|---|---|---|
| `users` | Required legacy and auth columns; unique email/username; timezone/language; flags | KEEP_WITH_CHANGES | Select canonical timezone if User and UserSettings differ; eventually remove legacy required fields only after registrations/backfills no longer depend on them. |
| `workspaces` | Name, nullable description, timezone, audit | KEEP_WITH_CHANGES | Add/backfill `kind`; Personal ownership mapping is not derivable for every multi-member/multi-workspace case without policy. Target does not use description/timezone. |
| `workspace_members` | UUID FKs, role enum, unique `(user_id, workspace_id)`, both FK indexes | KEEP_WITH_CHANGES | OWNER representation is reusable. Existing membership topology may violate the V1 one-person product assumption and must not be silently collapsed. |
| `categories` | Workspace/name/normalized/description/active; unique, nonblank check, listing index; Workspace CASCADE | REPLACE shape | Name and normalization are reusable. Description/active need retirement; used/inactive rows must retain referential history. Target needs composite parent uniqueness for workspace-aware FKs. |
| `projects` | Workspace/name/normalized/description/active; unique; list index; Workspace CASCADE | REPLACE shape | Target adds required Category, current comment, tracking timestamp, actor/version; removes normalized uniqueness/description semantics and adds steps. Existing rows have no target Category or Steps. |
| `tasks` | Workspace/creator/category/project/series; title/description; `scheduled_at` TIMESTAMPTZ; PG outcome enum including cancelled; consistency check; scope/filter indexes; series/time unique | REPLACE shape | Convert timestamp to local `planned_date`, create MasterTask references, remove direct relationships/text/provenance, map terminal results, add actors/version and workspace-aware FK. Existing IDs may be preserved if transformation is safe. |
| `task_series` | Workspace/creator/category/project/title/description/timezone; PG frequency; interval/weekdays/month day; start and nullable end timestamps; active flag; checks/indexes | REMOVE_AFTER_MIGRATION | Target has no series table. Already materialized Tasks remain candidates; unmaterialized intended occurrences and open-ended series require an explicit cutover decision. |
| `daily_form_definitions` | One per Workspace | REMOVE_AFTER_MIGRATION | No target equivalent. |
| `daily_form_questions` | Ordered typed questions, unique position, title check, definition CASCADE | REMOVE_AFTER_MIGRATION | Questionnaire content cannot populate target Review rows. |
| `daily_form_submissions` | Unique Workspace/user/date; definition RESTRICT; submission time | REMOVE_AFTER_MIGRATION | May be archived; must not be treated as proof of target Review without a conscious semantic mapping. |
| `daily_form_answers` | Per-question typed snapshot values and consistency check | REMOVE_AFTER_MIGRATION | No target equivalent. |
| `user_settings` | One per User; timezone, locale, week-start enum, reminder flags/time/minutes | REMOVE_AFTER_MIGRATION | Only timezone is a candidate for merge to User; conflicts need deterministic precedence and validation. |
| `workspace_settings` | One per Workspace; timezone, daily form/generation toggles/time, week start | REMOVE_AFTER_MIGRATION | No target settings table; values govern legacy services until their cutover. |
| none | — | NEW `workspace_tracking_metadata` | Create one row for each retained V1 Personal Workspace. |
| none | — | NEW `master_tasks` | Backfill before making Task reference mandatory. |
| none | — | NEW `pending_items` | No source data can be inferred. |
| none | — | NEW `project_steps` | Existing Task associations cannot be reinterpreted as Steps automatically. |

Dashboard, Reports, Reminder, Daily Workflow, and daily generation have no dedicated tables beyond the Task, form, series, and settings tables listed above.

### Constraint and migration observations

- Current PostgreSQL-native enums include Workspace role, Task outcome, TaskSeries frequency, Daily Form answer type, and week-start settings. Target Task result is `VARCHAR` plus check; obsolete enum types require explicit later cleanup.
- Current Task foreign keys use Workspace CASCADE, creator RESTRICT, and Category/Project/TaskSeries SET NULL. The target uses actor SET NULL, critical composite workspace-aware references, and RESTRICT for MasterTask history.
- `scheduled_at` is non-null timezone-aware `TIMESTAMPTZ`; target `planned_date` is non-null `DATE`. This requires a data migration, not a rename.
- Existing Task unique `(task_series_id, scheduled_at)` does not enforce target unique `(workspace_id, master_task_id, planned_date)`.
- Current schema does not enforce same-Workspace Category/Project/TaskSeries references at the database level; services scope lookups. Target critical references require composite Workspace-aware constraints.
- Existing server defaults and audit columns can generally be retained. New `lock_version` columns require a safe default/backfill before non-null enforcement.

## 6. User, authentication, and Personal Workspace impact

`UserCreate` accepts exactly email, password, first name, and last name. `register_user()` normalizes email, checks duplicates, hashes the password, creates a User, generates a UUID-hex legacy username, composes legacy full name, adds and flushes, and never commits. The route commits and refreshes. It does **not** create Workspace, WorkspaceMember, WorkspaceSettings, UserSettings, or tracking metadata.

OWNER is the `WorkspaceRole.OWNER` enum value on `workspace_members`. `create_workspace()` can create an OWNER membership, but registration never calls it. Therefore a newly registered user has no Workspace until another client/API operation creates one; the frontend cannot infer a Personal Workspace from authentication alone.

Login normalizes credentials through `authenticate_user()`, verifies the stored hash, rejects inactive users uniformly, and returns a JWT whose subject is the User UUID. `/auth/me` resolves the token to the real active User and returns `UserRead`. These flows are reusable.

Timezone currently exists in three places: `users.timezone`, `user_settings.timezone`, and `workspaces.timezone`. The frontend loads Workspaces separately, selects one (normally the first), and Topbar exposes a selector when multiple exist. Stage 3 must define precedence for existing conflicting timezone values; target runtime reads only `User.timezone`.

Required boundary: expand registration orchestration atomically to User + Personal Workspace + OWNER membership + WorkspaceTrackingMetadata, while preserving router-owned commit. Add a compatibility/bootstrap path for existing users with no suitable Workspace rather than relying only on new registration.

## 7. Detailed Task and recurrence impact

### Current Task fields

| Field | Current semantics | Target action |
|---|---|---|
| `id`, audit timestamps | Stable UUID/audit identity | Reuse where migration preserves rows. |
| `workspace_id` | Required scope, CASCADE | Keep; add composite-target support. |
| `created_by_id` | Required User, RESTRICT | Keep concept but target permits nullable actor with SET NULL. |
| `category_id` | Optional direct classification | Remove after MasterTask backfill; Category is reached through MasterTask. |
| `project_id` | Optional direct Project grouping | Remove; normal Tasks never belong to Projects. |
| `task_series_id` | Optional persistent recurrence provenance | Remove after occurrence/cutover validation. |
| `title` | Required free-text identity | Transform into MasterTask candidate, then remove from Task. |
| `description` | Optional Task text | No target field; requires explicit discard/archive policy. |
| `scheduled_at` | Required timezone-aware instant | Replace with local-date `planned_date`; conversion source must be defined. |
| `outcome` | Nullable completed/not-completed/cancelled native enum | Replace with nullable completed/not-completed result; CANCELLED has no direct target mapping. |
| `resolved_at` | Required whenever outcome exists | Keep concept; corrections update it. |
| none | — | Add `master_task_id`, `resolved_by_id`, `lock_version`. |

Current public status is calculated in the Pydantic read schema from outcome and current UTC time: unresolved `scheduled_at` at/before now is pending, future is scheduled; otherwise it mirrors outcome. Status is not stored. This calculation pattern is reusable, but both comparison granularity and timezone semantics change to User-local date.

`task_service.py` provides scoped creation, DB-side filtering, text search, count/pagination, allowed SQL ordering, and partial update. It filters direct Category/Project and uses old statuses/timestamps. `task_resolution_service.py` permits one resolution only and exposes cancellation. Current update rejects all changes after resolution; target requires controlled result correction. Current routes are Workspace-scoped and expose list/create/detail/patch plus complete/not-complete/cancel. There is no delete endpoint.

All Task service/schema/route tests need semantic replacement, while preserving high-value assertions for membership, workspace isolation, database-side filtering, deterministic ordering, validation, no service commit/rollback, exactly-one router commit, rollback mapping, and serialization.

### TaskSeries dependency inventory

Active runtime files include:

- Model/export: `backend/app/models/task_series.py`, `backend/app/models/__init__.py`, relationships in Task/User/Workspace/Category/Project.
- Schema/export: `backend/app/schemas/task_series.py`, `backend/app/schemas/__init__.py`.
- Services: `task_series_service.py`, `task_materialization_service.py`, `task_series_sync_service.py`, plus `daily_task_generation_service.py`.
- Router/registration: `backend/app/api/v1/task_series.py`, `backend/app/api/v1/router.py`.
- Frontend: `frontend/src/api/taskSeriesApi.ts`, `types/taskSeries.ts`, `pages/tasks/RecurringTasksPage.tsx`, router/sidebar links, tests.
- Tests: all `test_task_series_*`, `test_task_materialization_service.py`, `test_task_series_sync_service.py`, and daily generation/workflow tests.
- Historical migrations: `f6c9d2e4b713` and `a7d0e3f5c824` must remain forever.

Materialized Tasks copy title, description, Category, Project, creator, and scheduled instant, so existing occurrence rows retain most displayed information after the series disappears. They do not solve MasterTask identity, date conversion, CANCELLED results, or not-yet-materialized dates. Synchronization mutates/deletes unresolved future occurrences; that behavior must stop at cutover.

## 8. Category, PendingItem, and Project impact

Category normalization already implements the desired whitespace/NFC/casefold behavior and uniqueness races are translated. These utilities and tests should be extracted/reused without retaining description or activation semantics. Current activate/deactivate routes and filters are obsolete. New use detection must include MasterTask, PendingItem, and Project and must be race-safe; FK RESTRICT is the final guard.

No current model represents PendingItem. A Task is a punctual occurrence, Project is currently only a named container, and Daily Form answers are questionnaire snapshots; none is a safe data source. PendingItem is **NEW**. Reusable infrastructure includes Workspace authorization, Category resolution, list/count/pagination, active filtering patterns, compact table/form components, query keys, transaction/error mapping, and aggregate/report query patterns.

Current Project should be treated as a **REPLACE shape**, preferably with a compatibility migration around the same durable identity only if Category remediation and Step creation are defined. Existing Project rows lack required Category and Steps. Existing `description` may be a candidate for `general_comment` only with an explicit semantic decision; it is not an automatic rename. Current direct Task/TaskSeries links must be removed, not converted to Steps. ProjectStep is **NEW** and drives all target progress, dates, Review, Tracking, Inicio, and Reports.

## 9. Review and Tracking impact

The current Daily Form is a configurable questionnaire. Definitions, questions, answer snapshots, and completion readiness are incompatible with target Review. Daily Workflow also invokes recurring-task generation conditionally through Workspace settings. Target Review instead queries relevant Tasks, active unfinished PendingItems, and unfinished Steps of relevant active Projects, then saves current domain records plus metadata atomically.

Reusable pieces are limited but valuable: Workspace membership checks, explicit workflow date input, timezone/date utility patterns, replace/batch request validation, transaction ownership in the router, all-or-nothing service tests, and query-cache invalidation. Form definition/question/answer concepts, readiness status, generation counts, and form settings must be removed after migration.

Current Task listing is the closest base for `Seguimiento > Tareas`, but must switch to planned-date/result/MasterTask/Category semantics and allow terminal-result correction. `Seguimiento > Pendientes`, Project general tracking, Project detail/Step tracking, last-saved timestamps, and optimistic version conflicts are **NEW**. Target batch updates must not reuse the current single-record mutation pattern without atomic batch/version validation.

## 10. Dashboard/Inicio and Reports impact

`dashboard_service.py` and `dashboard_statistics_service.py` execute efficient scoped SQL aggregates, but only over current Tasks and UTC timestamps, including CANCELLED. `DashboardPage.tsx` presents analytics cards and quick links. Target Inicio is an operational home across Tasks, PendingItems, and Projects. Aggregate cards that represent history belong in Reports; quick links and the Workspace selector disappear. The current endpoints should be retained only during frontend compatibility, then replaced or retired.

Current Reports are frontend-composed from existing dashboard statistics and paged Task queries (`frontend/src/api/reportApi.ts`, `ReportsPage.tsx`). Their filters, period utilities, charts/cards, and metrics assume old Task status/outcome and `scheduled_at`; they have no PendingItem or ProjectStep data. Reuse request-state, date-period, query/cache, loading/error, and visualization primitives. Replace metrics and backend queries domain by domain; do not calculate full reports from client-side page remainders.

## 11. Settings impact

Target Configuration retains authentication profile data and User IANA timezone. Current User Settings also expose locale, week start, form reminders, task due/overdue reminders, reminder time, and lead minutes. Current Workspace Settings expose Workspace timezone, week start, daily form enable/time, and daily task generation enable. These settings and their APIs/tests are outside V1 after dependent legacy workflows retire.

The target source of operational local date is `User.timezone`. Stage 3 must sequence timezone convergence before converting `scheduled_at` or enabling date-only business rules. Removing settings too early would change current Daily Workflow and Reminder behavior, so their retirement belongs after those consumers are cut over.

## 12. Frontend route and component matrix

| Current route/page | Current behavior | Target destination | Class |
|---|---|---|---|
| `/login` / `LoginPage` | Email/password auth, restore session | Same, plus registration flow alignment | KEEP_WITH_CHANGES |
| Authenticated layout/guards | Sidebar/topbar/outlet/mobile navigation | Same shell with target navigation | KEEP_WITH_CHANGES |
| `/dashboard` / `DashboardPage` | Task analytics, quick links, Workspace selector context | `/` or target Inicio route with operational lists | REPLACE |
| `/tasks` / `TasksPage` | Timed free-text Task CRUD/filter/resolution/cancel | Split Planning Tasks and Tracking Tasks around MasterTask/date/result | REPLACE |
| `/tasks/recurring` / `RecurringTasksPage` | Persistent TaskSeries CRUD/materialize/sync | Temporary bulk creation inside Planning Tasks | REMOVE_AFTER_MIGRATION |
| `/projects` / `ProjectsPage` | Standalone active-name CRUD | Planning Projects/Steps and separate Tracking views | REPLACE |
| `/daily-workflow` / `DailyWorkflowPage` | Generation + questionnaire workflow | Review | REPLACE |
| `/settings/categories` / `CategoriesPage` | Description, active filter/toggle | Tables > Categories with pre-use immutability | REFACTOR |
| `/settings` / `SettingsPage` | User and Workspace workflow/reminder settings | Limited Configuration: profile/timezone | REPLACE |
| `/reports` / `ReportsPage` | Combined old Task analytics | Reports > Tasks/PendingItems/Projects | REPLACE |
| none | — | Planning PendingItems | NEW |
| none | — | Tracking PendingItems | NEW |
| none | — | Tracking Projects/detail | NEW |
| none | — | Tables > Master Tasks | NEW |

The target navigation is Inicio; Review; Planning (Tasks, PendingItems, Projects); Tracking (Tasks, PendingItems, Projects); Reports (Tasks, PendingItems, Projects); Tables (Master Tasks, Categories); Configuration. Router, Sidebar, query-key hierarchy, types, and API clients must change together to avoid stale-cache collisions.

Reusable frontend assets include AuthContext/token invalidation, protected-route return location, Axios Bearer/401 behavior, QueryClient infrastructure, PWA setup, responsive drawer/focus management, form resolver/error patterns, modal/dialog/table/card styling, pagination controls, loading/empty/error states, and Workspace-scoped query keys. Reuse visual/infrastructure components only; do not preserve obsolete payload semantics.

## 13. UI behavior conflicts with exact locations

- Multiple Workspace selection: `frontend/src/components/layout/Topbar.tsx`, `frontend/src/hooks/useWorkspaces.ts`, and Workspace state in `AuthContext.tsx`. V1 must resolve Personal automatically and display no selector.
- Obsolete navigation/labels: `Sidebar.tsx` and `router/index.tsx` expose Dashboard, Recurring Tasks, Daily Workflow, single Projects/Tasks, Settings, and combined Reports rather than the approved hierarchy.
- Dashboard analytics and quick actions: `pages/dashboard/DashboardPage.tsx`; target Inicio is operational, while analytics move to Reports.
- Task time/title/description/Category/Project controls and cancellation: `pages/tasks/TasksPage.tsx`, `types/task.ts`, `api/taskApi.ts`, and `utils/taskDateTime.ts`. Tasks become MasterTask selections plus date; timezone conversion is no longer a Task input concern.
- Separate recurrence UI: `pages/tasks/RecurringTasksPage.tsx` and related API/types. Bulk date generation belongs inside Planning Tasks and persists no series.
- Category lifecycle/description: `pages/settings/CategoriesPage.tsx` conflicts with target pre-use immutability and no description/Vigencia.
- Project cards/forms based on name/description/active only: `pages/projects/ProjectsPage.tsx`; target needs Category, Steps, weights, dates, progress, and separate Planning/Tracking operations.
- Questionnaire and generation-centric Review: `pages/daily-workflow/DailyWorkflowPage.tsx`, `api/dailyFormApi.ts`, `api/dailyWorkflowApi.ts`.
- Obsolete settings controls: `pages/settings/SettingsPage.tsx`, `types/settings.ts`, settings API clients.
- Reports based on current Task outcomes/time: `pages/reports/ReportsPage.tsx`, `api/reportApi.ts`, `utils/reportPeriod.ts`.
- Several current pages favor large metric cards/action panels. Approved dense Planning, Tracking, Tables, and Review screens need compact responsive rows/tables and dropdown filters; shared CSS can be retained but page composition must change.

## 14. Test impact matrix

| Test group | Classification | What survives / what changes |
|---|---|---|
| `test_security.py`, `test_tokens.py`, CORS | KEEP | Security primitives and restricted origins remain valid. |
| `test_api_dependencies.py`, most auth login/me tests | KEEP | Current-user lookup, 401 uniformity, and read-only behavior survive. |
| Registration service/router tests | UPDATE | Preserve hashing, normalization, duplicates, transaction ownership; add atomic Personal Workspace/OWNER/metadata assertions. |
| Workspace model/service/router tests | UPDATE | Preserve isolation/membership/roles; add kind/bootstrap and remove V1 client selection assumptions. |
| Category model/schema/service/routes | REPLACE | Preserve normalization, uniqueness race, scoping, transaction/error tests; replace description/active lifecycle with use-based immutability/delete rules. |
| Task model/schema/service/routes/resolution | REPLACE | Preserve validation/scoping/pagination/DB-filter/transaction patterns; replace fields, date/status/result/correction/delete semantics. |
| TaskSeries/materialization/sync | REMOVE_WITH_LEGACY_FEATURE | Retain only until data/API cutover; historical migration validation remains. |
| Project tests | REPLACE | Preserve authorization, isolation, error and transaction patterns; replace model/contracts and add ProjectStep/derived/batch/version tests. |
| Daily Form definition/submission | REMOVE_WITH_LEGACY_FEATURE | Questionnaire assertions are obsolete; keep generic atomic-replacement test ideas for new Review batches. |
| Daily generation/workflow | REMOVE_WITH_LEGACY_FEATURE | Generation/readiness/settings rules are obsolete; replace with Review composition/save/date/atomicity tests. |
| Dashboard summary/statistics | REPLACE | SQL single-query/read-only/isolation assertions remain useful; metrics and time semantics change. |
| Reminder tests | REMOVE_WITH_LEGACY_FEATURE | Entire product behavior is outside V1. |
| User/Workspace Settings tests | REPLACE | Keep timezone validation concepts; remove week-start/reminder/form/generation/workspace-timezone contracts. |
| Frontend auth/layout/route guard tests | UPDATE | Preserve session restoration, logout, 401, protected return location, drawer/accessibility; update workspace/nav assumptions. |
| Frontend domain page/API tests | REPLACE | Reuse mocking/query isolation/form accessibility patterns; payload and behavior assertions encode obsolete domains. |
| PWA/typecheck/lint/build | KEEP | Remain release gates. |
| `taskDateTime.test.ts` | REMOVE_WITH_LEGACY_FEATURE for Task input | DST-safe utility may remain generic, but Tasks no longer accept wall-clock time. |
| `reportPeriod.test.ts`, `reportApi.test.ts` | UPDATE | Retain deterministic period/cache/error mechanics; replace old metrics and timestamp assumptions. |

Tests must not be weakened during transition. Old tests should remain until their old route/model is intentionally retired; new target tests should run alongside compatibility tests where both surfaces coexist.

## 15. Legacy/dead-surface inventory

### Active backend expected to retire

- Persistent recurrence: `models/task_series.py`, `schemas/task_series.py`, `services/task_series_service.py`, `task_materialization_service.py`, `task_series_sync_service.py`, `api/v1/task_series.py`, recurrence relationships/exports.
- Daily generation/workflow: `services/daily_task_generation_service.py`, `daily_workflow_service.py`, corresponding schemas/routes.
- Generic Daily Form: `models/daily_form.py`, both daily-form schema modules, both services, `api/v1/daily_form.py`, exports/relationships.
- Reminder engine: `schemas/reminder.py`, `services/reminder_service.py`, `api/v1/reminders.py`.
- Obsolete settings: `models/user_settings.py`, `workspace_settings.py`, schemas/services/routes and relationships.
- Old Task semantics in Task model/schema/services/routes: `scheduled_at`, title/description, direct Category/Project/TaskSeries, CANCELLED, immutable-once-resolved behavior, old search/order/status contracts.
- Old Project and Category lifecycle contracts, Dashboard/statistics contracts, and Workspace-timezone consumers.

### Active frontend expected to retire or replace

- `api/taskSeriesApi.ts`, `types/taskSeries.ts`, `pages/tasks/RecurringTasksPage.tsx`.
- `api/dailyFormApi.ts`, `api/dailyWorkflowApi.ts`, their types, and `pages/daily-workflow/DailyWorkflowPage.tsx`.
- Reminder/form/generation/week-start/workspace-timezone controls in settings types/page/APIs.
- Old Dashboard/report APIs/types/pages and current Task/Project/Category domain contracts.
- Workspace selector behavior in Topbar/useWorkspaces for the V1 product experience.

### Tests expected to retire with those features

All TaskSeries/materialization/sync tests; Daily Form definition/submission tests; daily task generation/workflow tests; reminder tests; obsolete settings tests; and frontend Recurring Tasks/Daily Workflow behavior tests. Replacement occurs only after target coverage exists.

### Historical artifacts retained

All files in `backend/alembic/versions/` remain immutable. `docs/database/Legacy-V1-Target-Data-Model.md` and superseded ADR-004 may retain clearly identified historical concepts. Searches for TaskSeries, materialization, synchronization, CANCELLED, `project_id`, priority, `due_at`, `scheduled_at`, DailyChecklist/Daily Form, and settings must distinguish those historical records from live code.

## 16. Dependency graph and recommended order

```text
Auth/User timezone ─┬─> Personal Workspace kind/bootstrap ─> WorkspaceTrackingMetadata
                    └─> effective local-date policy

Category target ─> MasterTask ─> Task migration ─┬─> Planning Tasks / bulk creation
                                                 ├─> Review Tasks
                                                 ├─> Tracking Tasks
                                                 ├─> Inicio
                                                 └─> Task Reports

Category target ─> PendingItem ─┬─> Review
                                ├─> Tracking PendingItems
                                ├─> Inicio
                                └─> Pending Reports

Category target ─> Project ─> ProjectStep ─┬─> Review
                                           ├─> Tracking Projects
                                           ├─> Inicio
                                           └─> Project Reports

Target Review + target Tasks ─> retire Daily Form / Daily Workflow / generation
Target Task bulk creation + migrated occurrences ─> retire TaskSeries
Target User timezone + retired consumers ─> retire User/Workspace Settings and Reminder
All target APIs stable ─> target navigation/pages ─> retire legacy frontend routes
```

Recommended dependency order for Stage 3 planning:

1. Freeze the source inventory and define compatibility/API version boundaries and data-quality probes.
2. Converge timezone policy and add Personal Workspace kind/bootstrap plus tracking metadata.
3. Introduce target Category compatibility and MasterTask without yet removing old Task fields.
4. Backfill MasterTasks and date-only Task columns/result/version/actors; dual-read or compatibility responses as needed.
5. Cut Task writes/read APIs to target semantics; add bulk creation and correction; then freeze TaskSeries writes.
6. Introduce PendingItem and target Project/ProjectStep, independently after Category is available.
7. Implement atomic Review over the three target domains.
8. Implement Tracking, then Inicio and domain Reports on stable target queries.
9. Cut frontend navigation/pages and remove Workspace selection from V1 UX.
10. Retire TaskSeries, Daily Form/Workflow, Reminder, obsolete settings, direct Task relations, and compatibility columns only after data/API verification.

## 17. High-risk refactor and data-migration areas

1. **Time to date conversion.** `scheduled_at` is an instant. `planned_date` depends on an authoritative IANA zone. Existing User, UserSettings, Workspace, and TaskSeries zones can disagree. Conversion must be audited before dropping time.
2. **MasterTask identity.** Grouping by title alone may merge distinct concepts; grouping by title and Category may split renamed concepts. Unicode normalization creates possible collisions. No final backfill algorithm is approved yet.
3. **Target uniqueness.** Multiple current Tasks can collapse onto the same Workspace/MasterTask/local date. Stage 3 needs collision reports and a resolution policy before adding the unique constraint.
4. **CANCELLED data.** Target has no CANCELLED result. Mapping it to NOT_COMPLETED, deleting it, or archiving it changes history. This is an unresolved migration-policy decision, not permission to reintroduce cancellation.
5. **Descriptions and direct associations.** Task descriptions and Task→Project links have no target destination. Category moves through MasterTask. Data preservation/export policy must be explicit.
6. **TaskSeries cutover.** Existing generated Tasks are usable candidates, but unmaterialized future recurrence intent exists only in TaskSeries. Decide whether to materialize a bounded final horizon, discard future intent, or offer user-assisted conversion before retirement.
7. **Project conversion.** Current Projects lack required Category/Steps; Task associations cannot become ProjectSteps automatically. Description-to-comment mapping is semantically uncertain.
8. **Personal Workspace cardinality.** Existing users may have zero, one, or multiple owned/member Workspaces. Automatic selection or merging risks cross-workspace data loss.
9. **Timezone convergence.** Copying UserSettings or Workspace timezone over User blindly can change dates. Define precedence, user confirmation, and invalid-IANA remediation.
10. **Daily Form history.** Questionnaire submissions do not prove the target Review was saved and must not populate `last_review_saved_at` without an approved interpretation.
11. **Optimistic concurrency rollout.** Adding `lock_version` to single and batch mutations affects every write client and error contract; mixed old/new clients need a boundary.
12. **Composite workspace FKs.** They require compatible parent uniqueness and ordered backfills. Adding them before cleaning cross-workspace references can block deployment.

## 18. API transition risks and Stage 3 boundaries

Current public APIs encode obsolete fields and routes. Changing them in place will break the shipped frontend, cache keys, validation tests, and stored client state. The largest breaks are Task request/response shape, datetime filters/order, cancellation, TaskSeries endpoints, questionnaire workflow, settings, and Dashboard/Reports metrics.

Stage 3 should define explicit boundaries rather than migration SQL:

- Decide whether target resources use new routes/contracts beside legacy routes or a coordinated hard cutover. Prefer parallel compatibility where data backfill spans releases.
- Treat MasterTask IDs and date-only values as a new Task write contract; never accept both `scheduled_at` and `planned_date` ambiguously.
- Freeze TaskSeries create/update/materialize/synchronize before removing it, and make the cutover state observable.
- Preserve old read endpoints until the frontend no longer calls them; remove router registrations and query keys together.
- Introduce target Project routes separately from old contracts if IDs are retained but semantics are incomplete.
- Use consistent 409 optimistic-lock and uniqueness responses; preserve 401/403/404 isolation behavior.
- Keep write commit ownership in routers and atomic multi-entity orchestration in services via flush-only operations.
- Define cache invalidation across Review, Tracking, Inicio, and Reports because a single batch save affects all four.
- Add data-quality verification and rollback criteria to every compatibility phase. Dropping columns/tables and PostgreSQL enum types is the last, least reversible step.

Recommended Stage 3 work packages:

1. Data profiling queries and migration decision log (read-only against representative data).
2. Personal Workspace/timezone/bootstrap compatibility plan.
3. Category/MasterTask/Task expand-backfill-cutover-contract plan.
4. TaskSeries freeze and retirement plan.
5. PendingItem and Project/ProjectStep introduction plan.
6. Review/Tracking transactional and concurrency plan.
7. Inicio/Reports query and API plan.
8. Frontend route/cache/navigation cutover plan.
9. Legacy table/column/API removal and rollback plan.

## 19. Reusable infrastructure

- UUID/audit base model and Alembic registration patterns.
- SQLAlchemy 2.x `select()`, aggregation, scoped joins, count/pagination, deterministic ordering, and metadata tests.
- Session dependency and router-owned transactions.
- Membership authorization and resource scoping.
- JWT, password hashing, current-user resolution, CORS, and error hygiene.
- Normalized-name algorithm and expected-constraint IntegrityError translation.
- Pydantic strict schemas, nullable-versus-omitted update handling, and ORM serialization.
- React auth restoration, protected routing, Axios interceptors, TanStack Query, query invalidation, React Hook Form/Zod, PWA shell, responsive layout, accessibility patterns, and safe Spanish error handling.
- Tests asserting no service commit/rollback, read-only behavior, workspace isolation, API serialization, validation, timezone conversion, cache isolation, and build quality.

## 20. Contradictions and open decisions

No material contradiction was found among `Functional.md`, ADR-005, the current target data model, and ADR-006. The current implementation contradicts the approved target in the areas documented above; those are expected source-to-target gaps.

Stage 3 needs explicit migration/transition decisions that do not change the approved product model:

- How existing CANCELLED Tasks are preserved or transformed.
- Which existing timezone wins when User, UserSettings, Workspace, and TaskSeries differ.
- How MasterTask candidates and same-day collisions are resolved.
- Whether/how unmaterialized TaskSeries future intent is offered for one-time conversion.
- How current Projects receive required Categories and initial ProjectSteps; whether descriptions seed current comments.
- Whether legacy Daily Form submissions are archived only or used as non-authoritative historical context.
- How users with zero/multiple Workspaces are assigned a V1 Personal Workspace without data loss.
- Whether target APIs coexist temporarily with legacy endpoints or use a coordinated hard cutover.

These are migration and release-policy questions. They do not authorize CANCELLED, TaskSeries, Workspace timezone, questionnaires, or direct Task→Project association in the target.

## 21. Files inspected

Authoritative documentation listed in Section 1; current database/ERD/Roadmap/Glossary/navigation/screens; all files under `backend/app/models`, `backend/app/schemas`, `backend/app/services`, `backend/app/api`, `backend/tests`, and `backend/alembic/versions`; and the frontend router, contexts/hooks, API clients/query keys, types, utilities, layouts/components, pages, styles/configuration, and tests under `frontend/src`.
