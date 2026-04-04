# Scripts

## start.sh

Start the backend server (and optionally the frontend).

```bash
# Backend only
./scripts/start.sh

# Backend + frontend dev server
./scripts/start.sh --with-web
```

On first run, copies `.env.example` to `.env` if no `.env` exists.

## clean_runtime_data.sh

Clean runtime-generated data (databases, agent data, logs, caches).

```bash
# Preview what would be deleted
./scripts/clean_runtime_data.sh --dry-run

# Actually delete
./scripts/clean_runtime_data.sh
```
