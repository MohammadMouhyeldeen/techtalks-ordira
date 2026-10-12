# SCRUM-73 — Create the New Documentation System

**Owner:** Reem Saijary<br>
**Sprint:** Sprint 4<br>
**Date:** October 1, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-73<br>
**Branch:** `docs/project-documentation`<br>
**Target branch:** `develop`

## Task objective

The purpose of SCRUM-73 is to create a centralized, version-controlled documentation system for Ordira using Markdown files stored inside the GitHub repository.

The new system replaces the team’s dependency on Notion for technical and Sprint documentation.

It allows documentation to:

- Remain accessible without requiring a paid Notion upgrade.
- Be stored beside the project source code.
- Follow the same Git review process as code changes.
- Preserve a visible history of documentation updates.
- Be organized consistently across all Sprints and Jira tasks.
- Remain available to current and future team members.

## Why this task was needed

The team previously documented project requirements, architecture, database decisions, and completed Sprint tasks in Notion.

Continuing to use the shared Notion workspace required an upgrade, so the team needed a free and maintainable alternative.

GitHub Markdown documentation was selected because it:

- Does not require another paid workspace.
- Is already available to every repository contributor.
- Supports headings, lists, tables, links, images, and code blocks.
- Tracks every change through Git commits.
- Allows documentation changes to be reviewed through pull requests.
- Keeps technical decisions close to the implementation.

## Documentation structure

A new `docs/` directory was organized as follows:

```text
docs/
├── README.md
├── requirements.md
├── architecture.md
├── database.md
├── api.md
├── task-template.md
├── assets/
│   └── ordira-erd.webp
└── tasks/
    ├── sprint-1/
    ├── sprint-2/
    ├── sprint-3/
    └── sprint-4/
```

## Central documentation index

Created:

```text
docs/README.md
```

This file acts as the entry point for the Ordira documentation.

It explains:

- The purpose of the documentation directory
- The available project documents
- How task documentation is organized
- The expected workflow for adding documentation
- Folder and filename conventions
- Links to completed Jira task documents by Sprint
- The reusable task-documentation template

This allows team members to find the required information without searching through unrelated files.

## Core project documentation

The following project-level documents were added or organized:

### Requirements

```text
docs/requirements.md
```

Contains the project scope, roles, functional requirements, validation rules, workflows, and MVP boundaries.

### Architecture

```text
docs/architecture.md
```

Explains the Django project structure, domain applications, authentication, ownership boundaries, service layers, templates, and important technical decisions.

### Database

```text
docs/database.md
```

Documents the main database entities, relationships, constraints, snapshots, ownership rules, and inventory behavior.

### API and route documentation

```text
docs/api.md
```

Documents the main application routes and expected request behavior.

Although Ordira uses Django templates rather than a separate REST frontend, this document provides a central reference for the available URLs and application actions.

## ERD asset

The Ordira Entity Relationship Diagram was added to:

```text
docs/assets/ordira-erd.webp
```

The database documentation and ERD task documentation reference this repository asset using relative Markdown paths.

Keeping the image inside the repository ensures that the diagram remains available with the rest of the project documentation.

## Sprint task organization

Historical task documentation was migrated and organized by Sprint.

### Sprint 1

- SCRUM-8 — Django Project Structure
- SCRUM-9 — PostgreSQL Configuration
- SCRUM-10 — Environment Setup

### Sprint 2

- SCRUM-36 — Final ERD and Database Implementation
- SCRUM-38 — User Status Enforcement Middleware

### Sprint 3

- SCRUM-45 — Product, Category, and Variant CRUD
- SCRUM-49 — Inventory Stock Adjustment and Audit Trail

### Sprint 4

- SCRUM-45 — CRUD Interface Integration Follow-up
- SCRUM-73 — Create the New Documentation System

Each task has its own Markdown file under the corresponding Sprint directory.

## Historical documentation cleanup

The migrated task documents were reviewed and cleaned before being added to the repository.

The cleanup included:

- Updating task statuses to reflect merged work
- Correcting outdated descriptions
- Separating the original SCRUM-45 implementation from its Sprint 4 follow-up
- Distinguishing historical behavior from current behavior
- Adding Sprint information
- Adding branch and target-branch information where known
- Organizing files using consistent names
- Correcting formatting and encoding problems
- Preserving accurate test and verification results
- Adding links between related task documents

No missing pull-request or branch information was invented.

## Reusable task template

Created:

```text
docs/task-template.md
```

The template provides a standard structure for future Jira task documentation.

It includes sections for:

- Task metadata
- Objective
- Business need
- Requirements
- Implementation details
- Models and migrations
- Forms and validation
- Views and URLs
- Templates and styling
- Security and data isolation
- Automated testing
- Manual verification
- Files changed
- Dependencies
- Known limitations
- Final result
- Documentation checklist

Team members can copy this file when documenting future tasks and remove any sections that do not apply.

## Naming conventions

Task documents use the following naming style:

```text
SCRUM-XX-short-description.md
```

Examples:

```text
SCRUM-38-user-status-middleware.md
SCRUM-49-inventory-stock-adjustment.md
SCRUM-73-documentation-system.md
```

General rules:

- Use the Jira ticket number at the beginning.
- Use lowercase words after the ticket number.
- Separate words with hyphens.
- Use the `.md` extension.
- Store the file in the correct Sprint folder.
- Add the new document to `docs/README.md`.

## Documentation workflow

When a teammate completes a Jira task, they should:

1. Copy `docs/task-template.md`.
2. Rename it using the Jira ticket number and a short description.
3. Place it in the correct Sprint directory.
4. Replace all template placeholders with actual information.
5. Remove sections that do not apply.
6. Record only checks and tests that were actually completed.
7. Add the document link to `docs/README.md`.
8. Commit the documentation with the related work or through a documentation branch.
9. Open a pull request into `develop`.

## Security considerations

The documentation must not contain:

- Database passwords
- Private `.env` values
- API keys
- Authentication tokens
- Personal credentials
- Other confidential information

Safe placeholder values may be used when explaining environment configuration.

## Verification performed

The documentation directory was checked to confirm that:

- All expected files exist.
- Every migrated task file contains content.
- Task documents are stored in the correct Sprint directories.
- The ERD asset exists.
- The central README links to the documentation sections.
- Completed task documents do not contain template placeholders.
- No broken encoding characters were detected.
- The task template contains the intended reusable placeholders.

The staged documentation passed `git diff --cached --check` with no whitespace errors.

## Files added

- `docs/README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/api.md`
- `docs/task-template.md`
- `docs/assets/ordira-erd.webp`
- `docs/tasks/sprint-1/SCRUM-8-django-project-structure.md`
- `docs/tasks/sprint-1/SCRUM-9-postgresql-configuration.md`
- `docs/tasks/sprint-1/SCRUM-10-environment-setup.md`
- `docs/tasks/sprint-2/SCRUM-36-final-erd-database-implementation.md`
- `docs/tasks/sprint-2/SCRUM-38-user-status-middleware.md`
- `docs/tasks/sprint-3/SCRUM-45-product-category-variant-crud.md`
- `docs/tasks/sprint-3/SCRUM-49-inventory-stock-adjustment.md`
- `docs/tasks/sprint-4/SCRUM-45-crud-interface-follow-up.md`
- `docs/tasks/sprint-4/SCRUM-73-documentation-system.md`

## Current result

Ordira now has a centralized Markdown documentation system stored in the project repository.

Project requirements, architecture, database information, routes, ERD assets, and completed Sprint tasks are organized in one location. Team members also have a reusable template and clear workflow for documenting future work consistently.

The documentation system is ready to be submitted through a pull request into `develop`.