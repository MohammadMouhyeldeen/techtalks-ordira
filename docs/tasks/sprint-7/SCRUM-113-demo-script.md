# SCRUM-113 — Demo Script (Full Flow)

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 7 (final week)<br>
**Related ticket:** SCRUM-113<br>
**Status:** Script written and fully verified end-to-end on `develop` (every scene driven through automatically, all steps and on-screen text confirmed accurate) — your own recording + timed rehearsal still to do

## What this document is

The rehearsed script for the live demo, and the shot list for the no-cuts fallback recording. Every step below is verified against `develop` as it stands today (Oct 22, 2026) — nothing here depends on a branch that isn't merged.

## Before you start

```powershell
git checkout develop
git pull origin develop
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

**If `runserver` fails with `RuntimeError: The SECRET_KEY environment variable must be configured`:** the recent security-settings merge (SCRUM-110) now requires `SECRET_KEY` and `DEBUG` in your local `.env`, and an older `.env` (DB vars only, no `SECRET_KEY`) will hit this. Add both lines to `.env` (not `.env.example`):

```
SECRET_KEY=<any long random string>
DEBUG=True
```

This isn't code — it's a one-time local setup gap every teammate pulling this merge for the first time will hit, not something this ticket needs to fix.

Open **two browser windows side by side** (or two tabs you can flip between): one for the guest/customer, one for the merchant/admin. Use an **incognito/private window for the guest side** so its cart/session never mixes with your logged-in merchant session.

**Demo accounts** (all password `DemoPass123!`), straight from the seed script:

| Role | Email | Used in |
|---|---|---|
| Shop owner (active) | `active.owner@ordira.test` | Scenes 2–6 |
| Platform admin | `admin@ordira.test` | Scenes 7–9 |
| Pending owner | `pending.owner@ordira.test` | Scene 7 (approve) |
| Suspended owner | `suspended.owner@ordira.test` | Scene 9 (reactivate) |

Demo shop: **Demo Fashion** — public catalog at `/store/demo-fashion/`.

**One thing to get right before you hit record:** on checkout, always choose **Delivery**, never Pickup. Pickup is a known, currently-unfixed bug (SCRUM-106 finding) — picking it always fails with "Pickup orders cannot have a delivery zone." This isn't a feature-not-merged issue, it's a live landmine: route around it.

---

## Scene 1 — Guest places an order (guest window)

| Step | What you do | What the audience should see |
|---|---|---|
| 1.1 | Go to `http://127.0.0.1:8000/store/demo-fashion/` | The public catalog: shop name, tagline, search box, category chips, and the product grid (Linen Shirt, Denim Jacket, Canvas Tote Bag). |
| 1.2 | Click **Canvas Tote Bag** | Product detail page: image, price, color/size pills, quantity stepper, "X available" stock count. |
| 1.3 | Click **Add to Cart** | A toast confirms the item was added; the cart icon top-right now shows a count badge. |
| 1.4 | Click the cart icon → **Proceed to Checkout** | The cart page, then the checkout form: contact details, fulfillment (Delivery/Pickup), payment method, currency, and a live order summary on the right. |
| 1.5 | Fill in **Full name**, **Phone number**; select **Delivery**, pick a delivery area (e.g. Beirut), type a delivery address; pick **Cash** as payment method | Delivery fee appears once the area is chosen. |
| 1.6 | Click **Place Order** | Order-success page: large order number, status "New Order", fulfillment/customer/items/total, a green **"Contact the seller on WhatsApp to arrange payment"** button, and a **Track your order** link. |
| 1.7 | (Optional, quick) Click **Track your order** | The same order info on its own persistent page — this is the link a real customer would bookmark. |

**Say while doing this:** "No account, no app — just the catalog link. The order is saved the moment Place Order is clicked, before the customer ever touches WhatsApp."

---

## Scene 2 — The order arrives on the merchant dashboard (merchant window)

| Step | What you do | What the audience should see |
|---|---|---|
| 2.1 | Log in as `active.owner@ordira.test` at `/accounts/login/` | Merchant dashboard: shop stats (products, variants, low stock). |
| 2.2 | Click **Orders** in the sidebar | The order list, the one just placed at the top, status **New Order** — no refresh trick, it's just there. |
| 2.3 | Click into that order | Order detail page: order number, **Download invoice** button and status pill in the header, customer info, fulfillment, items, total — and a **Record payment** panel at the bottom showing the expected amount. |

**Say while doing this:** "Same order, same number, on the merchant's side — nothing to sync manually."

---

## Scene 3 — Merchant moves the order through its statuses

| Step | What you do | What the audience should see |
|---|---|---|
| 3.1 | On the order detail page, click **Mark as Preparing** | Status pill updates to "Preparing", a success message confirms it. |
| 3.2 | Click **Hand to Delivery** | Status pill updates to "Handed to Delivery". |
| 3.3 | (Skip "Mark as Completed" for now — payment comes first, see Scene 4) | — |

**Say while doing this:** "Each status is a deliberate step forward — there's no skipping ahead, and a cancelled or completed order can't be moved again."

---

## Scene 4 — Record a payment

| Step | What you do | What the audience should see |
|---|---|---|
| 4.1 | Scroll to **Record payment** | A panel showing order total, the payment method the customer picked at checkout, and the expected amount — already pre-filled into the form (this is SCRUM-96). |
| 4.2 | Leave the pre-filled amount/currency as-is, click **Record payment** | Payment status flips to "Paid", with a received-on timestamp. |
| 4.3 | Click **Mark as Completed** | Status pill updates to "Completed" — the order is now in its terminal state. |

**Say while doing this:** "The merchant doesn't retype anything — the expected amount is already there from the order itself."

---

## Scene 5 — Customer balance

| Step | What you do | What the audience should see |
|---|---|---|
| 5.1 | Click **Customers** in the sidebar | The customer list: name, phone, order count, last order date, and an **Outstanding balance** column. |
| 5.2 | Click into the customer from Scene 1 | Customer detail page: an **Outstanding balance** card (should read **0.00** — nothing outstanding, since the order was just paid), and that customer's order history below with an "Outstanding" badge logic (none shown now, since it's paid). |

**Say while doing this:** "Partial payments are out of scope for the MVP — this is a straight sum of what's unpaid and not cancelled, per currency, never mixed USD and LBP in one number."

*(If you want the audience to see a non-zero balance, place a second, smaller guest order first and record payment on it later — or just leave this one order's balance at 0.00 and explain verbally that it is the sum of exactly this kind of unpaid order.)*

---

## Scene 6 — Invoice PDF

| Step | What you do | What the audience should see |
|---|---|---|
| 6.1 | Go back to the order detail page, click **Download invoice** | A PDF downloads/opens: invoice number, the order's line items, subtotal, delivery fee, total, currency. |

---

## Scene 7 — Admin: approve a pending registration

| Step | What you do | What the audience should see |
|---|---|---|
| 7.1 | Log out, log in as `admin@ordira.test` | Admin dashboard, "Pending Registrations" section listing `pending.owner@ordira.test`. |
| 7.2 | Click **Approve**, confirm the prompt | The user disappears from the pending list; a success message confirms the approval. |

---

## Scene 8 — Admin: order monitoring

| Step | What you do | What the audience should see |
|---|---|---|
| 8.1 | From the admin dashboard, click **Order Monitoring** | A read-only list of the latest orders **across every shop**, filterable by shop and status — including the order from Scene 1, now "Completed". |

**Say while doing this:** "This is read-only by design — the admin can see everything, but order actions stay with the merchant who owns the shop."

---

## Scene 9 — Admin: suspend and reactivate

| Step | What you do | What the audience should see |
|---|---|---|
| 9.1 | Back on the admin dashboard, find `active.owner@ordira.test` under "Active Accounts", click **Suspend** | That account moves to the "Suspended Shop Owners" section. |
| 9.2 | Find `suspended.owner@ordira.test` under "Suspended Shop Owners", click **Reactivate** | That account moves back to "Active Accounts". |

**Say while doing this, if asked:** "This is the same switch either direction — suspending `active.owner` here is just to show the action; reactivating `suspended.owner` shows the opposite one so we don't lock ourselves out of the account we've been demoing with."

**Important:** do Scene 9 **last**, and reactivate `active.owner@ordira.test` again before you stop recording if you suspended it, so the account is left in a normal state afterward.

**Gotcha found while verifying this script:** `python manage.py seed_demo_data` uses `get_or_create` by email — if a rehearsal run approves `pending.owner` or suspends `active.owner`, re-running the seed command does **not** reset those statuses back. If you rehearse more than once, either reset the affected accounts manually (Django admin or shell) before the real take, or just account for it: after one rehearsal, `pending.owner` will already be ACTIVE and there's nothing left to approve in Scene 7.

---

## Timing (for the rehearsal)

| Scene | Rough time |
|---|---|
| 1 — Guest order | 2.5 min |
| 2 — Order arrives | 1 min |
| 3 — Status transitions | 1 min |
| 4 — Record payment | 1 min |
| 5 — Customer balance | 1 min |
| 6 — Invoice PDF | 0.5 min |
| 7 — Admin approve | 1 min |
| 8 — Order monitoring | 1 min |
| 9 — Suspend/reactivate | 1.5 min |
| **Total** | **~11 minutes** |

Run it once, fully, start to finish, with a timer — that's the "one timed rehearsal" the ticket asks for. Note the actual elapsed time and anything that felt slow or confusing here before recording.

## Known issues to route around (not fixed, not this ticket's job to fix)

- **Pickup checkout is broken** (SCRUM-106 finding #1, rating A) — always use Delivery.
- **Catalog "No products match your search" shows even with real results** (SCRUM-106 finding #2, rating B) — cosmetic, ignorable, but don't let it throw you off mid-demo if you linger on the catalog page.

## Recording requirements (acceptance criteria)

- [ ] Record the **entire** flow above in **one continuous take, no cuts**.
- [ ] Save the video file **outside this git repo** (e.g. shared drive) — do not commit it.
- [ ] Confirm the recording actually shows every scene working end to end before calling this done.
