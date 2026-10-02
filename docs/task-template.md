# SCRUM-XX — Task Title

**Owner:** Team member’s full name<br>
**Sprint:** Sprint number<br>
**Date completed:** Month DD, YYYY<br>
**Status:** In progress / Awaiting review / Completed and merged<br>
**Related ticket:** SCRUM-XX<br>
**Branch:** `feature/SCRUM-XX-short-description`<br>
**Pull request:** Add the pull-request link<br>
**Target branch:** `develop`

## Task objective

Explain what the task was intended to achieve.

Describe the expected result from the user or business perspective. Mention the main feature, problem, or workflow covered by the ticket.

## Why this task was needed

Explain the problem that existed before the implementation.

Include:

- What was missing or incorrect
- Who was affected
- Why the change was important
- What risks or limitations the task addressed

## Requirements

List the main task requirements:

- Requirement one
- Requirement two
- Requirement three
- Required validation or security behavior
- Required user-facing behavior

## Implementation

Explain the main technical changes.

### Models and database

Describe any:

- New models
- New or modified fields
- Relationships
- Constraints
- Validation rules
- Database migrations

If the task did not change the database, state:

> No model changes or database migrations were required.

### Business logic

Explain any important services, calculations, transactions, or workflow rules.

Mention why the chosen approach was used when the reason is important.

### Forms and validation

Describe:

- Forms added or changed
- Fields accepted
- Validation rules
- Error messages
- Protection against invalid or unauthorized data

Remove this section if the task does not use forms.

### Views and URLs

Describe:

- Views added or changed
- Routes added
- Authentication requirements
- Ownership or role checks
- Redirect behavior
- Relevant HTTP method restrictions

### Templates and styling

List any templates and stylesheets created or updated.

Describe the main interface behavior, such as:

- Forms
- Tables
- Buttons
- Empty states
- Validation messages
- Responsive layouts
- Hover and focus effects

Remove this section if the task has no user-interface changes.

## Security and data isolation

Explain how the implementation protects data.

Examples include:

- Authentication requirements
- Role authorization
- Shop ownership checks
- Cross-shop access restrictions
- POST-only destructive operations
- CSRF protection
- Input validation
- Safe database transactions

If security behavior was not relevant, remove this section.

## Automated testing

Describe the tests added or updated.

The tests verify that:

- Successful behavior works correctly.
- Invalid input is rejected.
- Unauthorized access is blocked.
- Ownership or role isolation is enforced.
- Important edge cases are handled.
- Existing behavior is not broken.

Include the final number of tests when known.

## Manual verification

Describe any browser or manual testing completed.

Examples:

- Opened the new page successfully.
- Submitted valid and invalid forms.
- Confirmed navigation links.
- Verified responsive behavior.
- Confirmed success and validation messages.
- Tested the workflow with different user roles.

Remove this section when no manual verification was needed.

## Verification results

List the commands that were executed:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test app_name
python manage.py test
git diff --check
git status
```

Remove commands that were not used and add any other relevant checks.

Record the actual results:

- Application tests passed: add test count.
- Complete test suite passed: add test count.
- No missing migrations were detected.
- Django’s system check identified no issues.
- No whitespace errors were found.
- Manual browser verification was successful.

Do not write that a check passed unless it was actually executed successfully.

## Files changed

List the main files created or modified:

- `path/to/file.py`
- `path/to/template.html`
- `path/to/stylesheet.css`
- `path/to/migration.py`

## Dependencies

List any tickets, features, models, or team members that this task depended on.

Examples:

- Depends on SCRUM-XX.
- Requires the Product and Product Variant models.
- Uses the shared Ordira base template.
- No external task dependency.

## Known limitations or follow-up work

Document anything intentionally left for another task.

Examples:

- Styling will be refined in SCRUM-XX.
- This task provides backend behavior only.
- A later ticket will add notifications.
- No known limitations remain.

Do not claim unfinished work is complete.

## Final result

Summarize what the completed task provides.

Explain:

- What now works
- Who can use it
- What problem it solves
- How it was verified

Keep this section short and focused on the final outcome.

---

## Documentation checklist

Before committing this document, confirm that:

- The Jira ticket number and title are correct.
- The owner and Sprint are included.
- The status reflects the real task status.
- The branch and pull-request information are correct.
- Technical statements match the implemented code.
- Test counts match the actual command output.
- Every listed file was genuinely changed.
- Secrets, passwords, and private `.env` values are excluded.
- Placeholder text and unused sections are removed.
- The document is linked from `docs/README.md`.