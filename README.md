# HR OS

HR OS uses static HTML/JavaScript, a Django REST API, and MongoDB. The source is
organized into three layers. The ecommerce reference path was not supplied, so
this layout follows the requested frontend/backend/database structure directly.

## Layout

```text
Python/
├── frontend/                   Browser screens; no build step
│   ├── config.js               Public API URL configuration
│   ├── api.js                  Shared headers, logout, 401 and error handling
│   ├── shared.js / shared.css  Shared navigation and presentation
│   ├── *.html                  Existing pages and inline screen handlers
│   └── tests/api.test.cjs       Dependency-free Node checks
├── backend/
│   ├── manage.py               Django command entry point
│   ├── finedge_backend/        Settings, root routes, ASGI/WSGI, storage URLs
│   ├── accounts/               JWT login/current user and current role policy
│   ├── recruitment/            Candidates, requisitions and recruitment services
│   ├── employees/              Profiles, documents and onboarding services
│   ├── positions/              Assignment/release services and holder history
│   ├── separations/            Exit APIs and multi-record exit services
│   ├── lifecycle/              Shared step rules, transitions and audit history
│   ├── workflows/              Snapshot services and legacy template APIs
│   ├── sop/                    Current SOP configuration APIs
│   ├── doc_checklist/          Joining checklist services and public uploads
│   ├── admin_studio/           Departments, branches, roles and JDs
│   ├── compensation/          Salary settings and revision approval
│   ├── increments/            Incentive structures and slabs
│   ├── tasks/                 Tasks, deadlines and shared timing status
│   ├── compliance/            Compliance dates and shared urgency calculation
│   ├── done_board/            Pending-work aggregation service
│   ├── notifications/         On-request alerts using shared services
│   ├── engagement/            Contests, suggestions and activities
│   ├── interview_questions/   Question bank
│   ├── reference_checks/      Checks, discrepancy freeze and letter eligibility
│   ├── policies/              Policy content and acceptance statistics
│   ├── letter_templates/      Letter template configuration
│   └── tests/                 Route/import and real MongoDB workflow checks
├── database/
│   ├── connection.py          One lazy shared MongoDB client
│   ├── collections.py         Existing collection accessors and names
│   ├── queries.py             Shared lookups and readable ID generation
│   ├── create_indexes.py      Existing index plan and initialization command
│   ├── seeds.py               Idempotent SOP seed definitions
│   ├── seed_sop_templates.py  SOP seed command
│   └── check_connection.py    Credential-safe connection check
├── requirements.txt           Unchanged Python dependency pins
├── .env.example               Placeholder configuration only
├── .env                       Private local settings, ignored
├── db.sqlite3                 Existing Django framework database, ignored
└── media/                     Existing uploaded files, ignored
```

`backend/` is the Python import root for Django apps. Their import names,
`AppConfig.name`, app labels and migration history remain unchanged; for example,
the employee app is still `employees`, not `backend.employees`. Do not rewrite
installed app names or historical migration dependencies.

Actual data intentionally remains outside the source layers. The existing root
`.env`, `db.sqlite3` and `media/` are not relocated. Moving Python files does not
migrate employee data. Previously tracked uploads were removed from the Git index
while retaining local files; old Git history may still contain those uploads.

## How the layers connect

The browser calls `/api/v1/` using `fetch`. `backend/finedge_backend/urls.py`
includes feature routes. API views authenticate, validate request serializers and
construct responses. Shared workflows live in feature `services.py` files and
`lifecycle/transitions.py`. Both simple CRUD and services use the database layer's
collection accessors; only `database/connection.py` creates the shared MongoDB
client. No new dependency was added.

The critical workflows retain their original behavior:

* Completing required recruitment steps enters Documents Pending. The explicit
  `candidates/<id>/create-employee/` action validates selection, freeze state and
  required uploads, creates an Onboarding employee, links the candidate and assigns
  a position. Uploaded documents need not be Verified to pass this gate.
* Completing required onboarding steps plus accepting the policy activates the
  employee. Onboarding code is in `employees/services.py` and the lifecycle engine.
* Exit initiation snapshots the Exit SOP. Completing required exit steps sets the
  separation to Completed, employee to Leaver and position to Vacant, preserving
  holder history and audit events.

The MongoDB collection names, stored fields, IDs, status values, API URLs, JSON
payloads and media-relative paths are retained. Workflow snapshots remain separate
from templates. Legacy `workflow_templates` edits still do not alter seeded SOPs
or existing record snapshots.

## Windows setup

Run these commands in PowerShell from the project root. The dependency pins were
verified using the existing Python 3.14 environment. A local MongoDB server is
needed for a new development database.

```powershell
Set-Location 'C:\Users\Aditya\OneDrive\Desktop\Python'
python -m venv venv                    # Skip if the existing venv is ready
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit the local `.env` with your private values. Do not overwrite an existing
configuration or point setup commands at production by accident.

| Variable | Meaning |
| --- | --- |
| `SECRET_KEY` | Required private Django/JWT signing key; there is no embedded fallback |
| `MONGO_URI` | MongoDB URI; use the development instance for setup/testing |
| `MONGO_DB_NAME` | Business database; legacy default remains `finedge` |
| `DEBUG` | Exact string `True` enables development debug and permissive CORS |
| `ALLOWED_HOSTS` | Comma-separated backend hostnames |
| `CORS_ALLOWED_ORIGINS` | Explicit frontend origins when debug is off |
| `SQLITE_PATH` | Optional SQLite path; default is root `db.sqlite3` |
| `MEDIA_ROOT` | Optional upload directory; default is root `media/` |
| `HRMS_TEST_MONGO_URI` | Opt-in integration-test server; not the app's database URI |

The root `.env` is loaded explicitly, so starting from `backend/` also works.
Process environment values take precedence. There is no frontend environment-file
loader: browser configuration is public JavaScript, never credentials.

## Initialize the database layer

From the root with the venv active and a development database selected:

```powershell
python -m database.check_connection
python -m database.create_indexes --dry-run
python -m database.create_indexes
python -m database.seed_sop_templates --dry-run
python -m database.seed_sop_templates
python backend/manage.py migrate
python backend/manage.py check
```

MongoDB creates collections as needed. The index command does not delete or rewrite
records. It skips unique indexes blocked by duplicate keys without printing their
values; resolve those duplicates deliberately before rerunning. Partial unique
indexes have explicit names so they can coexist with ordinary indexes on the same
field. SQLite migrations initialize Django's admin/auth/session tables, not HR
business collections.

SOP seeding copies legacy workflow templates when available, otherwise defaults.
It does nothing once the SOP collection is nonempty. Some API GETs also lazily
initialize defaults, so browsing an empty database is not strictly read-only.

HR login uses MongoDB `users` with Django-compatible password hashes. The project
does not implement signup or a user provisioning command. Retain existing users
or provision a development user deliberately; `createsuperuser` provisions Django
admin in SQLite and does not create an HR API account.

## Start frontend and backend

Terminal 1, from the root:

```powershell
.\venv\Scripts\Activate.ps1
python backend/manage.py runserver 127.0.0.1:8000
```

Terminal 2, from the root:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Open `http://127.0.0.1:5500/login.html`. The database layer is a Python package and
setup commands, not a third HTTP service; keep your MongoDB service running.
If port 5500 is already occupied, use 5501 (or another free port) and update the
frontend URL and, when debug is off, `CORS_ALLOWED_ORIGINS` to match.

`frontend/config.js` is the only browser API configuration. Empty `apiBase` uses
`http://127.0.0.1:8000/api/v1` on localhost, and `/api/v1` at the frontend origin
when deployed. For a separately hosted backend, set its public value there:

```javascript
window.HR_OS_CONFIG = Object.assign({ apiBase: 'https://api.example.invalid/api/v1' },
  window.HR_OS_CONFIG || {});
```

This configuration also applies to public document uploads. Keep frontend pages
at the static site's root: existing upload links use `/doc-upload.html`. No server
addresses remain embedded in individual screens.

Deployment entry points are `finedge_backend.wsgi:application` and
`finedge_backend.asgi:application` with `backend/` as the working directory/Python
import root. Update any existing service working directory or `--chdir` setting
from the project root to `backend/`. Continue supplying the root configuration.
The project does not add a production server dependency. With `DEBUG=False`,
configure your web server to serve existing `/media/` paths from `MEDIA_ROOT`.

## Checks and debugging

```powershell
python backend/manage.py check
python backend/manage.py test
node --test frontend/tests/api.test.cjs

# Enable real MongoDB integration checks on a development server:
$env:HRMS_TEST_MONGO_URI = 'mongodb://127.0.0.1:27017'
python backend/manage.py test --verbosity 1
Remove-Item Env:HRMS_TEST_MONGO_URI
```

Without `HRMS_TEST_MONGO_URI`, integration checks skip explicitly. They never use
the application's `MONGO_URI`: they create a random `hrms_refactor_test_*` database,
temporary uploads and synthetic accounts, then remove those resources. They test
real login, CORS over HTTP, uploads, recruitment-to-onboarding conversion, policy
activation, exit/position release, audit history, snapshot isolation and indexes.
Layout checks compare every pre-refactor route declaration and Django app identity.
Node tests check API configuration, headers, errors and script syntax for all pages.
The original feature `tests.py` files are starter placeholders and remain present.

Verification performed for this refactor: Django system checks, 10 Django
regression/integration tests and 4 Node tests passed. Database setup commands,
repeated index creation, SOP seeding and SQLite migrations passed against disposable
storage. The relocated backend served its login API on port 8000, and the static
frontend served on port 5501 because the first port-5500 startup conflicted. Real
HTTP login/CORS was checked with a synthetic account. Private `.env`, SQLite and
upload file hashes matched their pre-refactor values. Full browser clicking and
visual layout were not tested.

For failures, inspect Browser DevTools Network first: confirm the target URL,
status and JSON body. `401` clears the browser token and returns to login; tokens
still expire after 15 minutes with no refresh flow. Validation errors are now
displayed with field names. Trace server requests through feature routes, views,
services and database accessors. The timing middleware logs method/path/status and
adds `Server-Timing`. Avoid sharing credentials, tokens or employee payloads in logs.

## Behavior changes and remaining limits

Intentional changes beyond moving code:

* Browser API URL defaults to local development or same-origin deployment, replacing
  the old fixed remote HTTP address. Configure a split deployment explicitly.
* Form errors now include serializer field errors rather than only generic messages.
* `SECRET_KEY` must be configured; the insecure source-code fallback was removed.
* Index initialization uses distinct partial-index names to fix its existing name
  collision. Connection/index diagnostics withhold credentials and duplicate values.

The current role policy is deliberately preserved in `backend/accounts/rbac.py`:
all authenticated HR API users have broad access. True role/object authorization
requires a separate change to that gate and other sensitive views, including record
access and salary approval. SOP `who` labels are responsibility descriptions.

Multi-record workflows retain conditional updates and existing rollback behavior,
but are not database transactions. Readable max-plus-one IDs can still race under
concurrent creation. Public upload tokens have no time-based expiry. Salary revision
approval still applies CTC immediately regardless of the stored effective date.
These are existing limitations, not new behavior introduced by the reorganization.
