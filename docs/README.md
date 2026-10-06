# Ordira Project Documentation

This directory contains the shared technical, product, and task documentation for Ordira.

Ordira is a Django-based sales, order, customer, and inventory-management platform designed primarily for small online shops in Lebanon.

## Documentation index

### Shared project documentation

- [Requirements](requirements.md) — product scope, users, functional requirements, and business rules.
- [Architecture](architecture.md) — application structure, Django apps, responsibilities, and important technical decisions.
- [Database](database.md) — data model, entity relationships, constraints, snapshots, and ownership boundaries.
- [Application Interfaces](api.md) — routes, services, inputs, outputs, validation rules, and access restrictions.

### Task documentation template

Team members should copy the following template when documenting a completed Jira task:

- [Task documentation template](task-template.md)

### Sprint task documentation

Task documentation is organized by sprint under `docs/tasks/`.

#### Sprint 1

- [SCRUM-8 — Django Project and App Structure](tasks/sprint-1/SCRUM-8-django-project-structure.md)
- [SCRUM-9 — PostgreSQL and Environment Configuration](tasks/sprint-1/SCRUM-9-postgresql-configuration.md)
- [SCRUM-10 — Environment Example and Local Setup Instructions](tasks/sprint-1/SCRUM-10-environment-setup.md)


#### Sprint 2

- [SCRUM-36 — Final ERD and Database Implementation](tasks/sprint-2/SCRUM-36-final-erd-database-implementation.md)
- [SCRUM-38 — User Status Enforcement Middleware](tasks/sprint-2/SCRUM-38-user-status-middleware.md)


#### Sprint 3

- [SCRUM-45 — Product, Category, and Variant CRUD](tasks/sprint-3/SCRUM-45-product-category-variant-crud.md)
- [SCRUM-49 — Inventory Stock Adjustment and Audit Trail](tasks/sprint-3/SCRUM-49-inventory-stock-adjustment.md)

#### Sprint 4

- [SCRUM-45 — CRUD Interface Integration Follow-up](tasks/sprint-4/SCRUM-45-crud-interface-follow-up.md)
- [SCRUM-65 — Atomic Order Checkout Service](tasks/sprint-4/SCRUM-65-order-checkout.md)
- [SCRUM-73 — Create the New Documentation System](tasks/sprint-4/SCRUM-73-documentation-system.md)

#### Sprint 5

- [SCRUM-77 — Order Cancellation Service](tasks/sprint-5/SCRUM-77-order-cancellation.md)


## Documentation structure

```text
docs/
├── README.md
├── requirements.md
├── architecture.md
├── database.md
├── api.md
├── assets/
└── tasks/
    ├── sprint-1/
    ├── sprint-2/
    ├── sprint-3/
    ├── sprint-4/
    └── sprint-5/
```

Shared files such as `requirements.md`, `architecture.md`, `database.md`, and `api.md` describe the current project as a whole.

Files under `docs/tasks/` record the objective, implementation, validation, and result of individual Jira tasks.

## Documentation workflow

Documentation is maintained in the same GitHub repository as the application.

When implementing a feature:

1. Create a feature branch from `develop`.
2. Implement and test the feature.
3. Create or update the Jira task document under the appropriate sprint folder.
4. Update shared project documentation if the task changes requirements, architecture, database design, routes, or business rules.
5. Commit the code and documentation changes.
6. Open a pull request targeting `develop`.
7. Review the documentation together with the implementation.
8. Merge the pull request after approval.

Each teammate is responsible for documenting the Jira tasks they complete.

Older Notion documentation should be reviewed and migrated into the appropriate sprint folder. It should not be copied without confirming that its details still match the implemented code.

## Task file naming

Use the following naming format:

```text
SCRUM-XX-short-task-name.md
```

Examples:

```text
SCRUM-8-django-project-structure.md
SCRUM-38-user-status-middleware.md
SCRUM-49-inventory.md
```

## Documentation principles

Documentation should:

- Describe behavior that is implemented or clearly identify behavior that is still planned.
- Explain important business, security, access-control, and validation rules.
- Avoid exposing passwords, secret keys, database credentials, or private `.env` values.
- Be updated whenever a feature changes existing behavior.
- Reference the related Jira ticket and pull request when available.
- Include the verification commands and test results for the task.
- Remain clear enough for a new contributor to understand the system.

## Project tools

- **Source control:** Git and GitHub
- **Task management:** Jira
- **Backend:** Django
- **Database:** PostgreSQL
- **Frontend:** Django templates, HTML, CSS, and JavaScript