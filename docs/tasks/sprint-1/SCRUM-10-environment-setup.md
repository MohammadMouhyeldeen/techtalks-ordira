# SCRUM-10 — Environment Example and Local Setup Instructions

**Owner:** Reem Saijary<br>
**Sprint:** Sprint 1<br>
**Status:** Completed and merged<br>
**Related ticket:** SCRUM-10<br>

## Task objective

The purpose of SCRUM-10 was to provide developers with secure and clear instructions for configuring and running Ordira locally with PostgreSQL.

This task ensured that every team member could reproduce the required development environment without receiving or exposing another developer’s private database credentials.

## Environment example

A `.env.example` file was added to the project.

The file documents the required environment variables using safe placeholder values:

```env
DB_NAME=ordira_db
DB_USER=ordira_user
DB_PASSWORD=your_private_password
DB_HOST=localhost
DB_PORT=5432
```

Developers use this file as a reference when creating their private local `.env` file.

The `.env.example` file can safely be committed because it does not contain real credentials.

## README setup instructions

The project `README.md` was expanded with local setup instructions covering:

- Required software
- Repository cloning
- Switching to the correct Git branch
- Creating and activating a Python virtual environment
- Installing dependencies
- Creating the PostgreSQL database and database user
- Creating the local `.env` file
- Running the Django system check
- Verifying the PostgreSQL connection
- Understanding the initial migration warning

These instructions provide a consistent onboarding process for all developers working on Ordira.

## Security considerations

The real `.env` file remains excluded through `.gitignore`.

Each developer must create their own `.env` file and use their private PostgreSQL password.

The following information must never be committed:

- Real database passwords
- Private environment values
- Local PostgreSQL data files
- Machine-specific configuration files

Only `.env.example`, containing safe placeholder values, should be tracked in Git.

## Validation

The following verification steps were completed:

```powershell
python manage.py check
```

The Django system check completed successfully.

The repository changes were also checked using:

```powershell
git diff --check
```

The validation confirmed that:

- No whitespace errors were present.
- The real `.env` file remained ignored.
- `.env.example` contained no private credentials.
- The documented setup steps matched the project configuration.

## Files changed

- `.env.example`
- `README.md`

## Migration note

No migrations were created or applied during SCRUM-10.

Initial migrations were postponed until the Custom User model and required database models were finalized.

## Final result

Ordira now includes a secure and repeatable local setup process.

Developers can configure PostgreSQL and environment variables independently without sharing private credentials, reducing onboarding problems and configuration inconsistencies across the team.