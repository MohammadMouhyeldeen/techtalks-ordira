# SCRUM-52 — Shop-Scoped Public Catalog with Real Queries

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 3<br>
**Date completed:** September 25, 2026<br>
**Status:** Completed and merged<br>
**Related ticket:** SCRUM-52<br>
**Branch:** `feature/SCRUM-52-shop-catalog`<br>
**Pull request:** https://github.com/MohammadMouhyeldeen/techtalks-ordira/pull/24<br>
**Target branch:** `develop`

## Task objective

Convert the Sprint 2 storefront (SCRUM-46), which rendered the Public Catalog and Product Detail pages against hardcoded dummy data, into real, shop-scoped database queries at `/store/<shop-slug>/`, so each shop's actual products and variants render instead of the same fake catalog for every visitor — while cleanly handling an invalid shop slug or a shop that isn't currently accepting orders.

## Why this task was needed

SCRUM-46 deliberately used dummy data so the Sprint 2 wireframes could be implemented without waiting on real data wiring, and explicitly left "convert to real queries" as follow-up work. Before this task:

- Every shop's storefront page showed the same hardcoded products, regardless of which shop's link a customer actually followed.
- There was no handling at all for a shop slug that didn't exist, or for a shop without an active subscription — both would have hit whatever Django's default error handling produced, not a branded page.

## Requirements

- Real, shop-scoped queries replacing all dummy data on the public catalog and product detail pages.
- Clean, branded handling of an unknown shop slug and of a shop with no active subscription (not a raw 404/500).
- Full automated test coverage for the above.

## Implementation

### Models and database

No model changes or database migrations were required — this task only changed which queries populate the existing templates.

### Business logic

- **`products/storefront_views.py`** (new module) — `_catalog_products(shop)` is a shared helper returning the shop's active products with a starting-price annotation (`Min("variants__unit_price")`), excluding any product with no variants (and therefore no price) from the catalog. `public_catalog` lists all active categories that have at least one active product, alongside the catalog grid. `product_detail` looks up a single product scoped to `shop` + `is_active`, collects the distinct colors across its variants for the color-swatch picker, and queries up to 4 related products from the same category.
- The previous dummy-data versions of these two views were removed from `products/views.py` now that real versions exist in the dedicated `storefront_views.py` module.

### Views and URLs

- **`shops/decorators.py::public_shop_required`** (new) — resolves the `shop_slug` URL kwarg into a `Shop` before calling the wrapped view.
  - No `Shop` matches the slug → renders the shared `storefront/unavailable.html` template with `state="shop_not_found"` and a 404 status.
  - The shop exists but has no active subscription → renders the same template with `state="unavailable"` and a 200 status (a paused shop is a legitimate, bookmarkable page, not an error).
  - Otherwise calls the view with `shop` passed in place of `shop_slug`.
- **`config/urls.py`** — `public_catalog` and `product_detail` wired to the new `storefront_views` functions at `store/<slug:shop_slug>/` and `store/<slug:shop_slug>/products/<int:product_pk>/`.

### Templates and styling

- **`templates/storefront/unavailable.html`** (new) — one shared template covering the "shop not found," "shop unavailable," and "product not found" states, reused by both the decorator and `product_detail`'s own not-found case.
- **`templates/storefront/public_catalog.html`**, **`product_detail.html`** — swapped from dummy context variables to the real queried ones; no structural template changes were needed since the dummy data was already shaped to match the real model fields.
- **`templates/components/product_card.html`** — updated to read the real `Product` fields (category name via the real FK, the annotated starting price) instead of the dummy dict's keys.

## Security and data isolation

- Every storefront route is scoped by the `shop` resolved from the URL slug; both the catalog and product-detail queries filter explicitly on that shop, so one shop's products, categories, or related items never leak into another shop's storefront page.
- A shop with no active subscription renders the safe "unavailable" page instead of exposing its catalog.

## Automated testing

**`products/test_storefront.py`** (new, 18 tests):

- `PublicCatalogViewTests` (10) — real products render for an active shop; products belonging to other shops don't leak in; inactive products are hidden; a product with no variants (and therefore no price) is hidden; category filter chips reflect the shop's real categories; a category with no active products gets no chip; an unknown shop slug returns the branded 404 unavailable page; a shop with no subscription (or only an expired one) shows the unavailable state instead of its catalog; the empty-catalog state renders the correct copy.
- `ProductDetailViewTests` (8) — real product detail renders with correct stock data attributes; out-of-stock variant pills are disabled and in-stock ones are not; a product belonging to a different shop 404s; an inactive product 404s; related products are scoped to the same shop and category; no leftover dummy hex-color swatch data leaks into the response; a shop with no subscription shows the unavailable state before the product lookup even runs.

## Verification results

```powershell
python manage.py check
python manage.py test products.test_storefront
```

- Django's system check identified no issues.
- `products.test_storefront`: **18 tests passed.**

## Files changed

- `products/storefront_views.py` (new)
- `products/test_storefront.py` (new)
- `products/views.py` (dummy storefront views removed)
- `shops/decorators.py` (new)
- `config/urls.py`
- `templates/storefront/unavailable.html` (new)
- `templates/storefront/public_catalog.html`
- `templates/storefront/product_detail.html`
- `templates/components/product_card.html`
- `static/storefront/css/storefront.css`
- `templates/storefront/base_public.html`

## Dependencies

- Depends on SCRUM-46 (the storefront templates and dummy-data views this task replaced).
- Uses the `Shop`, `Subscription`, `Product`, `Category`, and `ProductVariant` models, already in place.

## Known limitations or follow-up work

- No known limitations remain for the catalog/product-detail query behavior itself; cart and checkout functionality were out of scope for this ticket and were built later (SCRUM-71).

## Final result

The public catalog and product detail pages now show each shop's real, active products and categories, scoped correctly so no cross-shop data leaks. An unknown shop link or a shop without an active subscription both land on a clean, branded page instead of a raw error. Verified by 18 passing automated tests covering the real-query behavior, shop isolation, and both unavailable states.
