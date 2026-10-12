# SCRUM-83 — Copy Catalog Link

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 5<br>
**Date completed:** October 6, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-83<br>
**Branch:** `feature/SCRUM-83-copy-catalog-link`<br>
**Pull request:** Add the pull-request link<br>
**Target branch:** `develop`

## Task objective

Give a shop owner a one-click way to copy their public catalog link from the merchant dashboard, so they can paste it into an Instagram bio or a WhatsApp message without having to construct the URL themselves.

## Why this task was needed

Sharing the catalog link on Instagram and WhatsApp is the core loop of the product — a shop only gets orders once customers can reach its `/store/<slug>/` page. Before this task there was no way for an owner to find or copy that link from the dashboard; they'd have to know the URL pattern and their own slug and type it out by hand.

## Requirements

- A "Your catalog link" card on the merchant dashboard showing the full `/store/<slug>/` URL with a Copy button and a confirmation toast.
- When the shop's subscription is not `ACTIVE`, the card explains the catalog isn't public yet and why, matching the existing subscription banner's wording exactly.
- Works at mobile widths.
- The card must only ever show the logged-in owner's own shop's link, never another shop's.

## Implementation

### Models and database

No model changes or database migrations were required.

### Business logic

No new business logic — the URL is built directly in the template from the already-available `shop` (from `shops.context_processors.current_shop`) and `request` (from Django's built-in request context processor), so no view changes were needed:
```
{{ request.scheme }}://{{ request.get_host }}{% url 'public_catalog' shop.slug %}
```
This produces a correct absolute URL in any environment (dev, staging, production) without hardcoding a domain.

### Forms and validation

Not applicable — no form on this card, just a read-only link and a copy action.

### Views and URLs

No new views or URLs. The card lives inside the existing `shops:dashboard` view/template.

### Templates and styling

- **`templates/components/subscription_reason.html`** (new) — extracted the subscription banner's three-way "why isn't this active" copy (EXPIRED / CANCELLED / waiting for activation) into its own include. It's now used by both the dashboard's top banner and the new catalog-link card, so the two can never drift out of sync — directly satisfying the "matches the existing banner" requirement rather than just copy-pasting similar-looking text.
- **`templates/shops/dashboard.html`** — new "Your catalog link" card (guarded by `{% if shop %}`), styled as a `.settings-section` card consistent with the rest of the dashboard. Shows the real link + Copy button when the subscription is active, or the shared "why not" copy when it isn't. A fixed-position confirmation toast (`#catalogLinkToast`) is shown on copy.
- **`templates/base.html`** — added an `i-copy` icon to the shared sprite.
- **`static/shops/css/dashboard.css`** — `.catalog-link-row` (flex row that wraps/stacks to a single column under 600px), `.catalog-link-unavailable`, and `.copy-toast` (a small fixed-position pill, matching the storefront's existing toast pattern but themed for the merchant shell).
- Copy itself uses `navigator.clipboard.writeText`, with a `document.execCommand("copy")` fallback (temporarily lifting `readonly` so `.select()` works) for browsers/contexts where the Clipboard API isn't available.

## Security and data isolation

- The link is built from `shop`, which the existing `current_shop` context processor already scopes to `request.user.shops.first()` — there is no shop-id parameter anywhere on this page for another owner's shop to be substituted in, so the card can only ever show the logged-in owner's own link.

## Automated testing

**`shops/test_settings.py::CatalogLinkCardTests`** (new, 4 tests):
- An active subscription shows the real `/store/<slug>/` link and the Copy button.
- No active subscription shows the "Waiting for activation" copy instead of the link, and the Copy button is absent.
- An expired subscription shows "Subscription expired," and the exact sentence appears twice on the page (once in the banner, once in the card) — confirming the shared-include approach actually keeps them in sync rather than just asserting the text exists somewhere.
- A second shop's slug never appears on the first owner's dashboard, even when both have active subscriptions.

## Manual verification

- Logged in as the seeded `demo-fashion` owner (active subscription) and confirmed the card shows `http://127.0.0.1:8000/store/demo-fashion/` with a working Copy button and toast.
- Logged in as the seeded no-subscription owner and confirmed the card shows the "Waiting for activation" copy with no Copy button, matching the top banner's wording exactly.
- Confirmed the row stacks to a single column under 600px via the media query (same flex-wrap/stack pattern already used elsewhere in the dashboard).

## Verification results

```powershell
python manage.py check
python manage.py test shops.test_settings
python manage.py test
```

- Django's system check identified no issues.
- `shops.test_settings`: **18 tests passed** (14 existing + 4 new).
- Complete test suite: **392 tests passed.**

## Files changed

- `templates/components/subscription_reason.html` (new)
- `templates/shops/dashboard.html`
- `templates/base.html`
- `static/shops/css/dashboard.css`
- `shops/test_settings.py`

## Dependencies

- Uses the `Shop` and `Subscription` models, and the existing `shops.context_processors.current_shop` context processor — all already in place.
- No dependency on SCRUM-81/SCRUM-82 — this card is independent of the order/checkout flow.

## Known limitations or follow-up work

- No known limitations remain for this card.

## Final result

Shop owners can now see and copy their real, shareable catalog link directly from the dashboard, with a clear explanation shown instead whenever their subscription isn't active yet — using the exact same wording as the existing subscription banner. Verified by 4 new passing tests plus the existing dashboard test suite, and a live walkthrough of both the active and inactive states.
