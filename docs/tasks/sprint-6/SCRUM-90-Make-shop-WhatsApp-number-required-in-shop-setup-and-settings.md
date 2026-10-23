# Shop WhatsApp Number Required in Setup and Settings

**Owner:** Jinan

**Sprint:** Sprint 5

**Status:** Implementation complete; automated tests passing; final review and PR pending

**Related epic:** SCRUM-31

**Branch:** `feature/shop-whatsapp-required`

**Target branch:** `develop`

## Objective

Require a WhatsApp number when a shop is created through setup or when its settings are saved. This ensures new and updated shop profiles contain a customer contact number while allowing existing shops with an empty number to remain accessible.

## Form validation

The shared `ShopContactLogoCleanMixin` makes the WhatsApp field required in both `ShopSetupForm` and `ShopSettingsForm`.

The existing format validation remains unchanged:

* Accept 10–15 ASCII digits, including the country code.
* Allow the existing supported formatting characters and an optional leading plus sign.
* Reject numbers that begin with a local `0`.
* Continue to display a form validation error for invalid input rather than allowing an invalid submission to be saved.

No database migration is required. The `Shop.whatsapp` model field remains optional at the database/model level so existing records with an empty number can still be loaded.

## Dashboard notice for existing shops

When a shop exists but its WhatsApp number is empty, the dashboard displays this notice:

> Add your WhatsApp number so customers can reach you

The notice includes a link to Shop Settings.

The notice is conditional: it appears only when the shop’s WhatsApp number is empty. Existing shops with an empty number must continue to load the dashboard normally.

## Settings behavior

Submitting Shop Settings without a WhatsApp number must:

* Keep the user on the settings page.
* Show a field validation error.
* Avoid saving the submitted changes.
* Avoid raising a server error.

Submitting a valid number must save the settings successfully and preserve the existing normalization and format-validation behavior.

## Test fixtures and seed data

Existing test submissions that successfully create or update shops now provide a valid WhatsApp number. The owner-isolation settings test also supplies a valid number so the test can continue verifying that an owner can update their own shop without modifying another owner's shop.

Tests that intentionally create legacy shops with an empty number remain unchanged, because empty stored values must continue to be supported.

**Seed-data review:** The repository search performed during implementation did not identify a dedicated seed-data script or fixture that sets WhatsApp. No separate seed-data file change has been confirmed. Any applicable seed-data creation path should be checked before merging.

## Testing

Automated tests cover:

* Setup submission without a WhatsApp number being rejected.
* Settings submission without a WhatsApp number being rejected.
* A valid WhatsApp number being saved and normalized.
* The dashboard notice appearing when the number is empty.
* The dashboard notice being hidden when a number exists.
* Existing shop setup and settings behavior.
* Shop settings owner isolation.

The full test suite passed **483 tests with no failures**.
