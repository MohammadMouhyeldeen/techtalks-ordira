# SCRUM-45 — Product, Category, and Variant CRUD

**Owner:** Reem Saijary<br>
**Sprint:** Sprint 3<br>
**Status:** Completed and merged<br>
**Related ticket:** SCRUM-45<br>
**Target branch:** `develop`

## Task objective

The purpose of SCRUM-45 was to replace the static product markup with functional Django CRUD operations for:

- Categories
- Products
- Product variants

All owner-facing operations are scoped to a specific Shop. A Shop Owner can only view or modify catalog data belonging to one of their own shops.

## Main relationships

The catalog follows this relationship:

**Shop → Category → Product → Product Variant**

- A Shop contains categories and products.
- A Category groups related products.
- A Product stores general item information.
- A Product Variant represents the exact purchasable version of a product.

A Product Variant contains information such as:

- Color
- Size
- Unit price
- Currency
- Stock quantity
- Low-stock threshold

For example, “Classic T-shirt” is a Product, while “Black, Medium” and “White, Large” are separate Product Variants.

## Ownership and data isolation

The Shop acts as the ownership boundary.

Every owner-facing URL contains a `shop_pk`. Before accessing a resource, the application verifies that the selected Shop belongs to the authenticated user.

The ownership check is equivalent to:

```python
Shop.objects.get(
    pk=shop_pk,
    owner=request.user,
)
```

After confirming ownership of the Shop, the requested Category, Product, or Product Variant is retrieved through its parent relationships.

Accessing a Product Variant follows this chain:

**Authenticated User → Owned Shop → Product in Shop → Variant of Product**

If any part of the requested resource does not belong to the authenticated owner, Django returns a `404 Not Found` response.

Returning a 404 prevents one Shop Owner from discovering or modifying another shop’s resources.

## Model updates

### Category archive support

An `is_active` field was added to the `Category` model:

```python
is_active = models.BooleanField(default=True)
```

Categories are archived by setting `is_active=False` instead of deleting their database records.

This preserves existing relationships and prevents accidental loss of historical data.

The following migration was created:

```text
products/migrations/0002_category_is_active.py
```

### Product category validation

Model validation was added to ensure that a Product and its selected Category belong to the same Shop.

This prevents invalid relationships such as assigning a Product from Shop A to a Category owned by Shop B.

## Forms

The following ModelForms were added in `products/forms.py`:

- `CategoryForm`
- `ProductForm`
- `ProductVariantForm`

### Category form

`CategoryForm` validates that a category name is unique within the selected Shop.

Different shops can use the same category name, but one Shop cannot contain duplicate category names.

### Product form

`ProductForm` handles:

- Name
- Description
- Image
- Category
- Active status

The Category queryset is restricted to active categories belonging to the current Shop.

This prevents an owner from selecting another shop’s Category, including through a manually manipulated form submission.

### Product Variant form

`ProductVariantForm` handles the Product Variant’s identifying and pricing information.

The form rejects duplicate color-and-size combinations for the same Product.

For example, one Product cannot contain two variants with:

```text
Color: Black
Size: Medium
```

A different Product may still use the same combination.

## Category CRUD

The following owner-scoped Category operations were implemented:

- List active categories
- Create a category
- Edit a category
- Archive a category

Archive operations accept only POST requests.

Archived categories are excluded from the active owner-facing Category list.

## Product CRUD

The following owner-scoped Product operations were implemented:

- List active products
- Create a product
- View product details
- Edit a product
- Archive a product

Product creation and editing support image uploads through `request.FILES`.

Products are archived using:

```python
product.is_active = False
```

Product archive operations accept only POST requests.

## Product Variant CRUD

The following owner-scoped Product Variant operations were implemented:

- Create a variant
- View variant details
- Edit a variant
- Delete a variant

Before performing an operation, the application verifies that:

1. The Shop belongs to the authenticated user.
2. The Product belongs to that Shop.
3. The Product Variant belongs to that Product.

Variant deletion accepts only POST requests.

## Historical implementation note

SCRUM-45 established the initial Product Variant CRUD workflow.

At that stage:

- `stock_quantity` could be edited through the Product Variant form.
- Product Variants were permanently deleted.

SCRUM-49 later improved this behavior by:

- Removing direct stock editing from the regular Variant form.
- Introducing audited stock adjustments.
- Creating a `StockMovement` record for every adjustment.
- Archiving variants that have inventory history instead of deleting them.

This means SCRUM-45 provided the CRUD foundation, while SCRUM-49 introduced the current inventory and safe-archiving behavior.

## URL routing

Owner-facing Category, Product, and Product Variant routes were created in:

```text
products/urls.py
```

The Product application URLs were included in the project’s main URL configuration.

Named URL patterns are used so views and templates can generate routes using Django’s `reverse()` function and `{% url %}` tag instead of hard-coded paths.

## Separation of responsibilities

The implementation follows Django’s standard separation of responsibilities:

- `models.py` defines database fields, relationships, and model validation.
- `forms.py` validates owner-submitted data.
- `views.py` handles requests and CRUD operations.
- `urls.py` connects URL patterns to views.
- `tests.py` verifies the expected behavior.

The tests do not implement the feature. They simulate requests and confirm that the actual models, forms, and views behave correctly.

## Automated testing

A total of 28 tests were added to the `products` application.

### Form and validation tests

The tests verify that:

- Valid Category data is accepted.
- Duplicate Category names within the same Shop are rejected.
- Categories from another Shop cannot be assigned to a Product.
- Model validation rejects cross-shop Product and Category relationships.
- Valid Product Variant data is accepted.
- Duplicate color-and-size combinations are rejected.
- The same combination can be used by different Products.

### Category tests

The tests verify that:

- An owner can create a Category for their Shop.
- An owner can edit their Category.
- An owner can archive their Category.
- An owner cannot access another owner’s Category.
- Category archive operations reject GET requests.

### Product tests

The tests verify that:

- An owner can create a Product for their Shop.
- An owner can view and edit their Product.
- An owner can archive their Product.
- An owner cannot create or modify Products in another Shop.
- An owner cannot view another owner’s Product.
- Product archive operations reject GET requests.

### Product Variant tests

The tests verify that:

- An owner can create a Variant for their Product.
- An owner can view and edit their Variant.
- An owner can delete their Variant.
- An owner cannot create a Variant for another owner’s Product.
- An owner cannot view, edit, or delete another owner’s Variant.
- Variant deletion rejects GET requests.

## How Django testing works

When this command is executed:

```powershell
python manage.py test
```

Django:

1. Creates a temporary test database.
2. Discovers the project’s automated tests.
3. Creates temporary users, shops, categories, products, and variants.
4. Simulates URL visits and form submissions.
5. Compares actual behavior with expected results.
6. Deletes the temporary test database.

The real development database is not modified.

## Verification results

The following commands were completed successfully:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test products
python manage.py test
git diff --check
git status
```

Results:

- No missing migrations were detected.
- Django’s system check identified no issues.
- All 28 Product application tests passed.
- The complete project test suite passed with 183 tests.
- No whitespace errors were detected.
- The branch was pushed successfully.
- The working tree was clean after the final push.
- The pull request was reviewed and merged into `develop`.

## Files changed

- `config/urls.py`
- `products/models.py`
- `products/forms.py`
- `products/views.py`
- `products/urls.py`
- `products/tests.py`
- `products/migrations/0002_category_is_active.py`

## Git checkpoints

The implementation was divided into focused commits:

1. `SCRUM-45 add product validation and category archive field`
2. `SCRUM-45 add owner-scoped product forms and validation tests`
3. `SCRUM-45 add owner-scoped category CRUD`
4. `SCRUM-45 add owner-scoped product CRUD`
5. `SCRUM-45 add owner-scoped product variant CRUD`

Each commit represents a clear implementation stage, making the pull request easier to review.

## Final result

Ordira now has an owner-scoped CRUD foundation for Categories, Products, and Product Variants.

Shop Owners can manage their catalog data while cross-shop access is blocked at both the form and view levels. Automated tests confirm the CRUD operations, validation rules, request-method protection, and ownership isolation.

This implementation also provided the Product and Product Variant foundation later used by SCRUM-49 for audited inventory management.