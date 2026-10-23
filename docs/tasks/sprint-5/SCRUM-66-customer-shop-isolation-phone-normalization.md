# SCRUM-66 — Customer Shop Isolation and Lebanese Phone Normalization

**Owner:** Jinan
**Sprint:** Sprint 5 — carried from Sprint 4
**Status:** Implementation complete; fresh-database browser verification pending
**Related ticket:** SCRUM-66
**Branch:** `feature/customer-model-shop-isolation`
**Target branch:** `develop`
**Reviewer:** Mohammad
**Tester:** Hadi

## Objective

Normalize Lebanese customer phone numbers consistently during checkout and enforce customer isolation by shop. The normalization is performed inside `create_order()` so every caller uses the same canonical phone value when locating or creating a customer.

## Phone normalization

The `normalize_phone_number()` function accepts Lebanese local and international formats and converts them into a canonical digits-only representation.

The implemented rules are:

* Remove spaces, dashes, parentheses, and plus signs.
* Remove a leading `00` international dialing prefix.
* Convert a leading local `0` to country code `961`.
* Add `961` to bare 7–8 digit numbers.
* Validate Lebanese results as 10–11 digits, and other numbers as 10–15 digits.

For example, `70 123 456`, `70123456`, `+961 70 123 456`, and `0070123456` normalize to `96170123456`.

Normalization occurs in `create_order()` before `Customer.objects.get_or_create()`. The normalized number is also recorded in `Order.customer_phone_snapshot`.

The customer model continues to normalize values on save as a safeguard. The shop setup form is unchanged.

## Shop isolation and duplicate handling

Customer uniqueness remains defined by `(shop, normalized phone number)`.

* Repeated orders using different formats of the same number in one shop reuse the same customer.
* The same normalized number in different shops creates separate customer records.
* Invalid phone numbers raise `ValidationError` before the order is created and are displayed on the checkout page.

## Existing-data migration

The migration `0002_normalize_existing_customer_phones` normalizes existing customer records.

When multiple records in the same shop normalize to the same number, the customer with the lowest primary key is retained. Orders belonging to duplicate customer records are reassigned to the retained customer before the redundant customer records are deleted.

Historical order snapshots are preserved. Invalid legacy phone values cause the migration to stop with an error identifying the affected customer, rather than silently discarding or rewriting invalid data.

## Testing

The following behaviors are covered by automated tests:

* Accepted Lebanese local and international phone formats.
* Equivalent formats resolving to one customer.
* Repeated orders not producing duplicate-key errors.
* Separate customers for the same number in different shops.
* Invalid phone rejection without order creation.
* Invalid-phone feedback on the checkout page.
* Customer model normalization and per-shop uniqueness.
* Migration consolidation of duplicate customers while preserving order references and historical snapshots.

The focused customer and checkout tests passed. The latest full-suite run passed **462 tests**.
