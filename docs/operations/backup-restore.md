# Backup and Restore

The modernization baseline now includes local scripts for backing up PostgreSQL plus app metadata/cache directories.

## What Gets Backed Up

- PostgreSQL data via `pg_dump --format=custom`
- selected local metadata/cache paths such as `data/translations`, `data/object-storage`, docs, and runtime config references

Video media files are intentionally not included. Canonical media identity stays in PostgreSQL, while the original video assets should remain in their storage backend or watched directories.

## Backup

```bash
./scripts/backup-local.sh
```

Optional custom destination:

```bash
./scripts/backup-local.sh /absolute/path/to/backup-dir
```

## Restore

```bash
./scripts/restore-local.sh /absolute/path/to/backup-dir
```

## Notes

- The scripts expect `DATABASE_URL` to be set, typically via `.env`.
- `pg_dump` and `pg_restore` must be installed on the machine running the scripts.
- Restore uses `pg_restore --clean --if-exists`, so it should only be run against the database you intend to replace.
