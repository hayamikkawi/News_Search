# GlobalSearch Frontend

Frontend for the TTDS news search engine.

## Overview

This frontend provides:

- Free text search and boolean search builder
- Date filtering and search pagination
- Search history (stored in browser `localStorage`)
- Latest news home feed
- Article detail modal (`View Content`)
- Article summary modal (`View Summary`)
- `AI Smart Summary Area` (summarizes top 3 current search results)

## Project Structure

```text
frontend/
├── GlobalSearch.html          # Main search page
├── LatestNews.html            # Latest news page
├── css/
│   └── styles.css             # Custom styles
├── js/
│   ├── app.js                 # UI behavior, modals, filters, boolean builder
│   ├── api-integration.js     # Search flow, rendering, pagination, modal data binding
│   └── api-service.js         # HTTP client and API methods
├── nginx.conf                 # Nginx config used by UI container
├── DEPLOYMENT.md              # Deployment notes
└── README.md
```

## Runtime Flow

1. Browser loads `GlobalSearch.html`.
2. `js/api-service.js` calls backend through relative `/api/*` routes.
3. Nginx proxies `/api/` to backend service (configured in `frontend/nginx.conf`).
4. `js/api-integration.js` renders results and binds per-result actions.
5. `js/app.js` handles top-level UI interactions (summary modal, filters, modes).

## API Endpoints Used

- `GET /api/search`
- `GET /api/news/latest`
- `GET /api/article/content`
- `POST /api/summarize`

Expected summary payload:

```json
{
  "summary": "...",
  "sources": [123, 456, 789]
}
```

## AI Smart Summary Area

`AI Smart Summary Area` works on the current search results only:

- It takes the top 3 IDs from the current search page
- Calls `POST /api/summarize`
- Renders summary text in `#summary-output`
- Renders source count in `#summary-meta`

Notes:

- If no search has been run yet, summary cannot be generated.
- Summary requests may be slow; frontend timeout is currently `60000ms` in `js/api-service.js`.

## Local Development

### Option A: Run with project Docker Compose (recommended)

From project root:

```bash
cd /opt/ttds-project
docker compose up -d ttds-ui ttds-ir
```

Then open:

- `http://localhost/GlobalSearch.html`

### Option B: Serve frontend only (backend must already exist)

From this directory:

```bash
cd /opt/ttds-project/frontend
python3 -m http.server 3000
```

Then open:

- `http://localhost:3000/GlobalSearch.html`

If you use Option B, make sure your backend and proxy/CORS settings allow `/api/*` calls from that origin.

## Troubleshooting

### AI Smart Summary Area shows no result

Check in order:

1. You performed a search first (there are result IDs).
2. Backend `POST /api/summarize` is reachable.
3. Browser console has no timeout/network error.
4. `GlobalSearch.html` includes `#summary-output` and `#summary-meta`.

### Page updates not reflected

If HTML changes are not visible while using Docker bind mounts:

```bash
cd /opt/ttds-project
docker compose up -d --force-recreate ttds-ui
```

Then hard refresh browser (`Ctrl+F5`).

## Related Docs

- See [DEPLOYMENT.md](./DEPLOYMENT.md) for deployment-specific setup.
