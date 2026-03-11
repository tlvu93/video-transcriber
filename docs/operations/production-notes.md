# Production Notes

## PostgreSQL Upgrade

The foundation sprint moves the default runtime from PostgreSQL 14 to PostgreSQL 16.

For this sprint, PostgreSQL 14 to 16 migration is handled by logical dump and restore, not by in-place automation.

Recommended sequence:

1. Stop writers.
2. Run `pg_dump` against the PostgreSQL 14 database.
3. Restore into a clean PostgreSQL 16 instance with `pg_restore` or `psql`.
4. Start the upgraded stack and let Alembic apply application schema changes.

## Queue Leasing

- PostgreSQL is the supported multi-worker database for leased job processing.
- SQLite is still useful for development, but queue concurrency is explicitly unsupported.
