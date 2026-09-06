# PoultryFarm

## Vercel database setup

This app requires a persistent Postgres database when deployed to Vercel.
SQLite is only used for local development.

Set one of these environment variables in Vercel before deploying:

- `DATABASE_URL`
- `POSTGRES_URL`
- `POSTGRES_URL_NON_POOLING`

You can use Vercel Postgres, Neon, Supabase, or any hosted Postgres provider.
After adding the database URL, redeploy the project. The app runs migrations on
startup in Vercel.
