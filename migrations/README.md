# Database Migrations

This directory contains database migration files for the moderator project.

## Overview

Migrations are versioned SQL files that define the database schema and its evolution over time. Each migration file represents a specific version of the database schema.

## Migration Files

Migrations are numbered sequentially using the format: `NNN_description.sql`

- `001_initial_schema.sql` - Initial database schema with all core tables

## Running Migrations

### PostgreSQL

To apply migrations to your PostgreSQL database:

```bash
# Connect to your database
psql -U postgres -d moderator_db

# Run a migration file
\i migrations/001_initial_schema.sql
```

Or from the command line:

```bash
psql -U postgres -d moderator_db -f migrations/001_initial_schema.sql
```

### Migration Tools

For production use, consider using migration management tools:

#### Python (Alembic)
```bash
pip install alembic psycopg2-binary
alembic init alembic
# Configure alembic.ini and env.py
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

#### Node.js (Prisma)
```bash
npm install prisma --save-dev
npx prisma init
# Edit schema.prisma
npx prisma migrate dev --name initial_schema
```

#### Node.js (Knex)
```bash
npm install knex pg
npx knex migrate:make initial_schema
npx knex migrate:latest
```

## Migration Workflow

1. **Create a new migration**
   - Name it with the next sequential number: `00X_description.sql`
   - Add your CREATE/ALTER/DROP statements
   - Include comments explaining the changes

2. **Test the migration**
   - Run it on a development database first
   - Verify all tables and indexes are created correctly
   - Check for any errors or warnings

3. **Apply to production**
   - Backup your database first
   - Run the migration during a maintenance window
   - Verify the schema changes were applied

## Best Practices

- **Always backup** before running migrations on production
- **Test migrations** thoroughly in development first
- **Make migrations reversible** when possible (include DROP statements for rollback)
- **One migration per change** - don't mix unrelated schema changes
- **Document changes** - add comments explaining why changes were made
- **Version control** - commit migration files to git

## Schema Version Tracking

To track which migrations have been applied, you can create a migrations table:

```sql
CREATE TABLE schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

After applying a migration:

```sql
INSERT INTO schema_migrations (version) VALUES ('001_initial_schema');
```

## Rollback

To rollback a migration, you'll need to create a corresponding down migration or manually reverse the changes:

```sql
-- Example: Rollback 001_initial_schema
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS settings CASCADE;
DROP TABLE IF EXISTS replies CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS attachments CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS channels_allowlist CASCADE;
DROP TABLE IF EXISTS discord_connection CASCADE;
DROP TABLE IF EXISTS platform_accounts CASCADE;
DROP TABLE IF EXISTS users CASCADE;
```

## Data Retention

According to the project specifications:
- All data is retained for **90 days**
- Automatic cleanup runs daily at 03:00 UTC
- See `docs/DATABASE.md` for retention policy details

## Support

For questions about the database schema or migrations, refer to:
- `docs/DATABASE.md` - Complete database documentation
- `docs/TECHNICAL_SPEC.md` - Technical specifications
