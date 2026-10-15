# SCRUM-87 — Invoice PDF Download

**Owner:** Reem Saijary
**Sprint:** Sprint 6
**Date completed:** October 15, 2026
**Status:** Ready for review
**Related ticket:** SCRUM-87
**Branch:** `feature/SCRUM-87-invoice-pdf`
**Pull request:** #66
**Target branch:** `develop`

## Task objective

The purpose of this task was to allow an authenticated Shop Owner to generate and download a PDF invoice for an Order.

The invoice provides a permanent and readable record of the Shop, customer, Order items, fulfillment information, totals, and payment details.

## Existing Invoice model

The project already contained an `Invoice` model connected to an Order through a one-to-one relationship.

The model stores:

- The Shop that owns the Invoice.
- The related Order.
- A unique invoice number.
- The issue date and time.
- A snapshot of the Order subtotal.
- A snapshot of the delivery fee.
- A snapshot of the final total.
- The Invoice currency.
- The Invoice status.

No changes to the Invoice model or database schema were required for this task.

## Implementation

### Invoice service

Created `payments/invoice_service.py`.

The service is responsible for creating the Invoice record and generating its PDF document.

When an Invoice is requested, the service:

1. Locks the Order during Invoice creation.
2. Retrieves the existing Invoice when one has already been created.
3. Creates a new Invoice when the Order does not yet have one.
4. Generates a unique invoice number.
5. Copies the Order totals and currency into the Invoice snapshot fields.
6. Marks the Invoice as issued.
7. Records the issue date and time.
8. Generates the PDF content in memory.

Reusing the existing Invoice ensures that repeatedly downloading the same Order’s Invoice does not create duplicate Invoice records or change its original invoice number.

### Invoice snapshots

The Invoice stores copies of the Order’s financial totals:

- Subtotal.
- Delivery fee.
- Final total.
- Currency.

These snapshots preserve the values used when the Invoice was issued.

### PDF generation

ReportLab is used to generate the PDF document.

The generated Invoice includes:

- Shop information.
- Invoice number.
- Invoice issue date.
- Order number.
- Order creation date.
- Customer name.
- Customer phone number.
- Fulfillment type.
- Delivery zone and address for delivery Orders.
- Product names.
- Product variant details.
- Quantities.
- Unit prices.
- Line totals.
- Order subtotal.
- Delivery fee.
- Final total.
- Currency.
- Selected payment method.
- Payment status when a Payment has been recorded.

The PDF is created in memory and returned directly in the HTTP response. It does not need to be saved permanently on the server.

### ReportLab dependency

Added ReportLab to `requirements.txt`:

```text
reportlab==5.0.1
```

ReportLab provides the tools used to build and return the PDF document.

### Merchant Invoice view

Added `merchant_order_invoice_pdf` to `orders/views.py`.

The view:

- Requires an authenticated user.
- Accepts GET requests only.
- Resolves the Shop through the authenticated Shop Owner.
- Retrieves the Order only when it belongs to that Shop.
- Returns `404 Not Found` when another user attempts to access the Shop or Order.
- Creates or retrieves the Order’s Invoice.
- Generates the PDF.
- Returns the result with the `application/pdf` content type.
- Uses the Invoice number as the downloaded filename.

Restricting the endpoint with `@require_GET` prevents Invoice generation through unsupported HTTP methods.

### Invoice URL

Added a new route to `orders/urls.py`.

The named URL is:

```text
orders:invoice-pdf
```

The route includes both the Shop ID and Order ID so ownership can be verified before the Invoice is generated.

### Download button

Updated `templates/orders/order_detail.html` with a **Download invoice** button.

The button appears in the Order detail header and links to the Invoice PDF endpoint for the displayed Order.

The existing Order status badge and Order action controls remain available.

## Security and access control

Invoice access follows the same Shop ownership protection used by the merchant Order pages.

An authenticated Shop Owner can download an Invoice only when:

- The requested Shop belongs to that user.
- The requested Order belongs to that Shop.

A different Shop Owner cannot access the Invoice by changing the Shop ID or Order ID in the URL.

Anonymous users are redirected to the login page.

## Automated testing

Created `payments/test_invoice_pdf.py` with six dedicated tests.

The tests verify the Invoice creation and download workflow, including:

- Creating an Invoice for an Order.
- Reusing the same Invoice on repeated requests.
- Returning a valid PDF response.
- Protecting Invoices from other Shop Owners.
- Requiring authentication.
- Rejecting unsupported HTTP methods.

## Manual verification

The feature was also tested through the merchant interface.

The verification confirmed that:

- The **Download invoice** button appears on the Order detail page.
- Existing Order action buttons remain visible.
- Clicking the button downloads a PDF.
- The downloaded file uses the Invoice number as its filename.
- The PDF opens successfully.
- The Invoice displays the Order and financial information.

## Verification results

The following commands were executed:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test payments.test_invoice_pdf
python manage.py test
git diff --check
```

Results:

- All 6 dedicated Invoice PDF tests passed.
- The complete project test suite passed: 502 tests.
- Django’s system check identified no issues.
- No model changes or new migrations were required.
- No whitespace errors remained.
- The PDF download was verified manually.

## Files changed

- `requirements.txt`
- `payments/invoice_service.py`
- `payments/test_invoice_pdf.py`
- `orders/urls.py`
- `orders/views.py`
- `templates/orders/order_detail.html`
- `docs/tasks/sprint-6/SCRUM-87-invoice-pdf.md`
- `docs/README.md`

## Dependencies

SCRUM-87 uses the existing:

- Order and Order Item snapshot data.
- Invoice model.
- Payment information.
- Merchant Order detail page.
- Shop ownership access-control pattern.

The task also introduces ReportLab as the project’s PDF-generation dependency.

## Final result

Ordira now allows an authenticated Shop Owner to securely download a PDF invoice for an Order.

The implementation generates an itemized and readable Invoice, preserves financial totals through snapshots, prevents duplicate Invoice creation, restricts access to the correct Shop Owner, and makes the Invoice available directly from the merchant Order detail page.
