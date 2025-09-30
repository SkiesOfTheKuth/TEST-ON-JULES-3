# Database Migrations

The calculator service is currently stateless. If persistence is introduced:

1. Adopt Alembic (SQLAlchemy) or Prisma (Node) depending on chosen stack.
2. Commit migration scripts to source control (`migrations/`).
3. Enforce migrations in CI using `alembic upgrade head`.
4. Document backward-compatibility expectations for zero-downtime deploys.
