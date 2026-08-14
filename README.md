# LifeManager V1

## Deployment configuration

LifeManager does not require a specific hosting provider. Apply the Alembic
migrations before starting the API; application startup never creates, drops,
or migrates the schema automatically.

### Backend

Copy `backend/.env.example` only for local development. In production, inject
environment variables through the hosting platform:

- `DATABASE_URL`: PostgreSQL connection URL. Alternatively, provide all five
  `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` values.
- `SECRET_KEY`: required random JWT signing secret of at least 32 characters.
- `CORS_ALLOWED_ORIGINS`: JSON array containing the deployed frontend origin.
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM`, `SQL_ECHO`, and
  `TASK_BULK_MAX_OCCURRENCES` have safe documented defaults.

From `backend`, a provider-neutral production startup sequence is:

```sh
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

Keep `SQL_ECHO=false` in production. Do not expose `.env`, database URLs, or
JWT secrets to the frontend.

### Frontend

Set `VITE_API_BASE_URL` at build time to the public versioned API URL, for
example `https://api.example.com/api/v1`. If omitted in production, the build
uses same-origin `/api/v1`, suitable when a reverse proxy serves both apps.
Local Vite development uses same-origin `/api/v1`; the development server
proxies that path to `http://localhost:8000`. This proxy is development-only
and is not included in production assets.

The static host must route unknown application paths to `index.html` so React
Router navigation works. The generated PWA service worker uses the same SPA
navigation fallback.
