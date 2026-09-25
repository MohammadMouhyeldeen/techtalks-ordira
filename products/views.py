from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from shops.models import Shop

from .forms import (
    CategoryForm,
    ProductForm,
    ProductVariantForm,
    StockAdjustmentForm,
)
from .models import Category, Product, ProductVariant
from .services import adjust_variant_stock


def get_owner_shop(request, shop_pk):
    return get_object_or_404(
        Shop,
        pk=shop_pk,
        owner=request.user,
    )


@login_required
def category_list(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    categories = Category.objects.filter(
        shop=shop,
        is_active=True,
    )

    return render(
        request,
        "products/category_list.html",
        {
            "shop": shop,
            "categories": categories,
        },
    )


@login_required
def category_create(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    form = CategoryForm(
        request.POST or None,
        shop=shop,
    )

    if request.method == "POST" and form.is_valid():
        category = form.save(commit=False)
        category.shop = shop
        category.save()

        messages.success(request, "Category created successfully.")

        return redirect(
            "products:category-list",
            shop_pk=shop.pk,
        )

    return render(
        request,
        "products/category_form.html",
        {
            "shop": shop,
            "form": form,
            "page_title": "Create category",
        },
    )


@login_required
def category_edit(request, shop_pk, category_pk):
    shop = get_owner_shop(request, shop_pk)

    category = get_object_or_404(
        Category,
        pk=category_pk,
        shop=shop,
    )

    form = CategoryForm(
        request.POST or None,
        instance=category,
        shop=shop,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category updated successfully.")

        return redirect(
            "products:category-list",
            shop_pk=shop.pk,
        )

    return render(
        request,
        "products/category_form.html",
        {
            "shop": shop,
            "category": category,
            "form": form,
            "page_title": "Edit category",
        },
    )


@login_required
@require_POST
def category_archive(request, shop_pk, category_pk):
    shop = get_owner_shop(request, shop_pk)

    category = get_object_or_404(
        Category,
        pk=category_pk,
        shop=shop,
        is_active=True,
    )

    category.is_active = False
    category.save(update_fields=["is_active"])

    messages.success(request, "Category archived successfully.")

    return redirect(
        "products:category-list",
        shop_pk=shop.pk,
    )

@login_required
def owner_product_list(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    products = (
        Product.objects
        .filter(shop=shop, is_active=True)
        .select_related("category")
    )

    return render(
        request,
        "products/product_list.html",
        {
            "shop": shop,
            "products": products,
        },
    )


@login_required
def owner_product_detail(request, shop_pk, product_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product.objects.select_related("category"),
        pk=product_pk,
        shop=shop,
    )

    variants = ProductVariant.objects.filter(
        product=product,
        is_active=True,
    )

    return render(
        request,
        "products/product_detail.html",
        {
            "shop": shop,
            "product": product,
            "variants": variants,
        },
    )


@login_required
def owner_product_create(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    product_instance = Product(shop=shop)

    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product_instance,
        shop=shop,
    )

    if form.is_valid():
        product = form.save()
        messages.success(request, "Product created successfully.")

        return redirect(
            "products:product-detail",
            shop_pk=shop.pk,
            product_pk=product.pk,
        )

    return render(
        request,
        "products/product_form.html",
        {
            "shop": shop,
            "form": form,
            "page_title": "Create product",
        },
    )


@login_required
def owner_product_edit(request, shop_pk, product_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product,
        shop=shop,
    )

    if form.is_valid():
        product = form.save()
        messages.success(request, "Product updated successfully.")

        return redirect(
            "products:product-detail",
            shop_pk=shop.pk,
            product_pk=product.pk,
        )

    return render(
        request,
        "products/product_form.html",
        {
            "shop": shop,
            "product": product,
            "form": form,
            "page_title": "Edit product",
        },
    )


@login_required
@require_POST
def owner_product_archive(request, shop_pk, product_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    product.is_active = False
    product.save(update_fields=["is_active"])

    messages.success(request, "Product archived successfully.")

    return redirect(
        "products:product-list",
        shop_pk=shop.pk,
    )

@login_required
def owner_variant_detail(request, shop_pk, product_pk, variant_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    variant = get_object_or_404(
        ProductVariant,
        pk=variant_pk,
        product=product,
        is_active=True,
    )

    return render(
        request,
        "products/variant_detail.html",
        {
            "shop": shop,
            "product": product,
            "variant": variant,
        },
    )


@login_required
def owner_variant_create(request, shop_pk, product_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    variant_instance = ProductVariant(product=product)

    form = ProductVariantForm(
        request.POST or None,
        instance=variant_instance,
        product=product,
    )

    if form.is_valid():
        variant = form.save()

        messages.success(
            request,
            "Product variant created successfully.",
        )

        return redirect(
            "products:variant-detail",
            shop_pk=shop.pk,
            product_pk=product.pk,
            variant_pk=variant.pk,
        )

    return render(
        request,
        "products/variant_form.html",
        {
            "shop": shop,
            "product": product,
            "form": form,
            "page_title": "Create product variant",
        },
    )


@login_required
def owner_variant_edit(request, shop_pk, product_pk, variant_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    variant = get_object_or_404(
        ProductVariant,
        pk=variant_pk,
        product=product,
        is_active=True,
    )

    form = ProductVariantForm(
        request.POST or None,
        instance=variant,
        product=product,
    )

    if form.is_valid():
        variant = form.save()

        messages.success(
            request,
            "Product variant updated successfully.",
        )

        return redirect(
            "products:variant-detail",
            shop_pk=shop.pk,
            product_pk=product.pk,
            variant_pk=variant.pk,
        )

    return render(
        request,
        "products/variant_form.html",
        {
            "shop": shop,
            "product": product,
            "variant": variant,
            "form": form,
            "page_title": "Edit product variant",
        },
    )


@login_required
@require_POST
def owner_variant_delete(request, shop_pk, product_pk, variant_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    variant = get_object_or_404(
        ProductVariant,
        pk=variant_pk,
        product=product,
        is_active=True,
    )

    if variant.stock_movements.exists():
        variant.is_active = False
        variant.save(update_fields=["is_active"])

        messages.success(
            request,
            "Product variant archived successfully.",
        )
    else:
        try:
            variant.delete()

            messages.success(
                request,
                "Product variant deleted successfully.",
            )
        except ProtectedError:
            variant.is_active = False
            variant.save(update_fields=["is_active"])

            messages.success(
                request,
                "Product variant archived successfully.",
            )

    return redirect(
        "products:product-detail",
        shop_pk=shop.pk,
        product_pk=product.pk,
    )

@login_required
def owner_variant_stock_adjust(
    request,
    shop_pk,
    product_pk,
    variant_pk,
):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
        is_active=True,
    )

    variant = get_object_or_404(
        ProductVariant,
        pk=variant_pk,
        product=product,
        is_active=True,
    )

    form = StockAdjustmentForm(
        request.POST or None,
        variant=variant,
    )

    if request.method == "POST" and form.is_valid():
        try:
            adjust_variant_stock(
                variant=variant,
                change_qty=form.cleaned_data["change_qty"],
                reason=form.cleaned_data["reason"],
                created_by=request.user,
            )
        except ValidationError as error:
            form.add_error(
                "change_qty",
                error.messages[0],
            )
        else:
            messages.success(
                request,
                "Stock adjusted successfully.",
            )

            return redirect(
                "products:product-detail",
                shop_pk=shop.pk,
                product_pk=product.pk,
            )

    return render(
        request,
        "products/stock_adjustment_form.html",
        {
            "shop": shop,
            "product": product,
            "variant": variant,
            "form": form,
            "page_title": "Adjust stock",
        },
    )

@login_required
def owner_variant_stock_history(
    request,
    shop_pk,
    product_pk,
    variant_pk,
):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
        is_active=True,
    )

    variant = get_object_or_404(
        ProductVariant,
        pk=variant_pk,
        product=product,
        is_active=True,
    )

    movements = (
        variant.stock_movements
        .select_related("created_by")
        .order_by("-created_at")
    )

    return render(
        request,
        "products/stock_movement_history.html",
        {
            "shop": shop,
            "product": product,
            "variant": variant,
            "movements": movements,
        },
    )