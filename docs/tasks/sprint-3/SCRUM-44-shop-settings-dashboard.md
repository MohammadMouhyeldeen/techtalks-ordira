# SCRUM-44 — Shop Settings Edit Form + Real Dashboard Counts

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 3<br>
**Date completed:** September 25, 2026<br>
**Status:** Completed and merged<br>
**Related ticket:** SCRUM-44<br>
**Branch:** `feature/SCRUM-44-shop-settings-dashboard`<br>
**Pull request:** https://github.com/MohammadMouhyeldeen/techtalks-ordira/pull/25<br>
**Target branch:** `develop`

## Task objective

Replace the merchant dashboard shell's placeholder markup with a real Shop Settings edit form and real dashboard statistics (total products, total variants, low-stock variant count), scoped strictly to the logged-in owner's own shop.

## Why this task was needed

Before this task, the merchant dashboard and shop settings pages were placeholder markup only — there was no way for a shop owner to actually edit their shop's name, WhatsApp number, Instagram handle, logo, or pickup availability after initial setup, and the dashboard showed no real numbers. Shop owners had no self-service way to keep their storefront's contact details current, and had no at-a-glance view of their own inventory health.

## Requirements

- A real, working Shop Settings edit form (name, WhatsApp, Instagram, logo, pickup availability).
- Real dashboard counts: total active products, total variants, and variants at or below their low-stock threshold.
- Owner isolation — a shop owner must only ever see and edit their own shop.
- Automated tests covering both the settings form and the dashboard counts.

## Implementation

### Models and database

No model changes or database migrations were required — this task reused the existing `Shop`, `Product`, and `ProductVariant` models.

### Business logic

- **`shops/helpers.py::get_dashboard_stats(shop)`** (new) — returns `total_products`, `total_variants`, and `low_stock_count` for a shop. Variant counts are scoped to `product__is_active=True` so an archived product doesn't permanently inflate the merchant's own "Total products" count. Low stock is computed as `stock_quantity <= low_stock_threshold` via an `F()` expression comparison at the database level.
- **`shops/templatetags/shop_extras.py::format_whatsapp`** (new template filter) — formats a stored WhatsApp number (digits only, e.g. `"96170123456"`) for display by dropping the Lebanese country code and grouping the local number as 2-3-3 (e.g. `"70 123 456"`). Falls back to the raw digits if the number doesn't match that shape.

### Forms and validation

- **`shops/forms.py::ShopSettingsForm`** (new `ModelForm`, sharing a `ShopContactLogoCleanMixin` with the existing `ShopSetupForm`) — editable fields: `name`, `whatsapp`, `instagram`, `logo`, `pickup_available`. `clean_whatsapp()` strips a leading `+`, removes spaces/dashes/parentheses, and requires 10–15 digits including the country code (rejecting a number typed without one). `clean_logo()` rejects a logo image over 2 MB.

### Views and URLs

- **`shops/views.py::shop_settings`** (`@login_required`) — resolves the current user's own shop (`request.user.shops.first()`); redirects to shop setup if the owner has no shop yet. On a valid POST, saves the form and redirects back to the settings page with a success message (POST → messages → redirect).
- **`shops/views.py::dashboard`** — now calls `get_dashboard_stats(shop)` and passes the real counts into the dashboard template, instead of the previous placeholder values.
- **`shops/context_processors.py::current_shop`** (new) — makes the logged-in owner's shop available as `shop` in every template rendered through the merchant shell, without every view needing to remember to pass it explicitly. Registered in `TEMPLATES["OPTIONS"]["context_processors"]`.

### Templates and styling

- **`templates/shops/settings.html`** (new) — a real settings form organized into sectioned cards (shop identity with a logo preview, contact details, preferences), replacing the previous placeholder page.
- **`templates/shops/dashboard.html`** — stat-tile widgets now render the real `total_products`/`total_variants`/`low_stock_count` values instead of placeholders, with a warning/success state on the low-stock tile depending on whether any variants are at or below threshold.
- **`templates/base.html`**, **`templates/components/navbar.html`**, **`templates/components/sidebar.html`** — shared icon sprite and merchant-shell navigation updated to support the new settings page and the real shop data now available via the context processor.
- **`static/shell/css/shell.css`** — the bulk of this task's styling work: real form-section card styling for the settings page, redesigned stat-tile widgets, and the supporting visual polish (icons, color variety, profile dropdown) carried out iteratively on this same branch before merge.

## Security and data isolation

- `shop_settings` resolves the shop from `request.user.shops.first()` — a shop owner can only ever load and submit their own shop's settings form; there is no shop-id parameter in the URL for another owner's shop to be substituted in.
- The dashboard's stat counts are computed from the same request-scoped `shop`, so one owner never sees another shop's product/variant counts.
- The settings form is `@login_required` and POST-only for mutation, with CSRF protection.

## Automated testing

**`shops/test_settings.py`** (new, 14 tests):

- `ShopSettingsViewTests` (9) — an unauthenticated user is redirected to login; an owner without a shop is redirected to shop setup; the form renders with the shop's current values; a valid POST updates the shop and redirects with a success message; invalid WhatsApp numbers (missing country code, non-digit characters, wrong length) are rejected with the expected validation errors; an oversized logo upload is rejected.
- `ShopSettingsOwnerIsolationTests` (2) — one owner's settings submission never affects another owner's shop; the rendered form only ever shows the logged-in owner's own shop data.
- `DashboardStatsTests` (3) — `get_dashboard_stats` returns the correct total product count, total variant count, and low-stock count for a shop, scoped to active products only.

## Verification results

```powershell
python manage.py check
python manage.py test shops.test_settings
```

- Django's system check identified no issues.
- `shops.test_settings`: **14 tests passed.**

## Files changed

- `shops/forms.py`
- `shops/helpers.py`
- `shops/views.py`
- `shops/urls.py`
- `shops/context_processors.py` (new)
- `shops/templatetags/shop_extras.py` (new)
- `shops/test_settings.py` (new)
- `config/settings.py`
- `templates/shops/settings.html` (new)
- `templates/shops/dashboard.html`
- `templates/base.html`
- `templates/components/navbar.html`
- `templates/components/sidebar.html`
- `templates/landing/landing.html`
- `static/shell/css/shell.css`

## Dependencies

- Uses the existing `Shop`, `Product`, and `ProductVariant` models.
- Builds on the shop-setup flow from earlier Sprint 1/2 work (an owner must already have a shop to reach the settings page).

## Known limitations or follow-up work

- No known limitations remain for the settings form or dashboard counts; subscription-status banner logic and admin subscription management were handled separately by other tickets.

## Final result

Shop owners can now edit their shop's name, WhatsApp number, Instagram handle, logo, and pickup availability through a real, validated settings form, and see accurate total-products/total-variants/low-stock counts on their dashboard — all scoped strictly to their own shop. Verified by 14 passing automated tests covering the form, owner isolation, and the dashboard statistics helper.
