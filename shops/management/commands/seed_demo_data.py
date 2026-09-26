from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from products.models import Category, Product, ProductVariant
from shops.models import Shop, Subscription


class Command(BaseCommand):
    help = "Create demo data for Sprint 3."

    DEMO_PASSWORD = "DemoPass123!"

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()

        # ---------------------------------------------------------
        # Users
        # ---------------------------------------------------------

        admin = self._get_or_create_user(
            email="admin@ordira.test",
            full_name="Ordira Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )

        active_owner = self._get_or_create_user(
            email="active.owner@ordira.test",
            full_name="Active Shop Owner",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )

        no_subscription_owner = self._get_or_create_user(
            email="no.subscription.owner@ordira.test",
            full_name="No Subscription Owner",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )

        pending_owner = self._get_or_create_user(
            email="pending.owner@ordira.test",
            full_name="Pending Shop Owner",
            role=User.Role.SHOP_OWNER,
            status=User.Status.PENDING,
        )

        suspended_owner = self._get_or_create_user(
            email="suspended.owner@ordira.test",
            full_name="Suspended Shop Owner",
            role=User.Role.SHOP_OWNER,
            status=User.Status.SUSPENDED,
        )

        # ---------------------------------------------------------
        # Shop with active subscription + products
        # ---------------------------------------------------------

        active_shop, _ = Shop.objects.get_or_create(
            slug="demo-fashion",
            defaults={
                "owner": active_owner,
                "name": "Demo Fashion",
                "whatsapp": "+96170123456",
                "instagram": "@demo_fashion",
                "pickup_available": True,
                "exchange_rate_lbp_per_usd": "89500.00",
            },
        )

        Subscription.objects.get_or_create(
            shop=active_shop,
            status=Subscription.Status.ACTIVE,
            defaults={
                "plan": Subscription.Plan.BASIC,
                "starts_on": today,
                "ends_on": None,
            },
        )

        clothing, _ = Category.objects.get_or_create(
            shop=active_shop,
            name="Clothing",
            defaults={
                "is_active": True,
            },
        )

        accessories, _ = Category.objects.get_or_create(
            shop=active_shop,
            name="Accessories",
            defaults={
                "is_active": True,
            },
        )

        linen_shirt, _ = Product.objects.get_or_create(
            shop=active_shop,
            category=clothing,
            name="Linen Shirt",
            defaults={
                "description": "Breathable linen shirt for everyday wear.",
                "is_active": True,
            },
        )

        ProductVariant.objects.get_or_create(
            product=linen_shirt,
            color="Sand",
            size="M",
            defaults={
                "unit_price": "28.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 12,
                "low_stock_threshold": 5,
            },
        )

        ProductVariant.objects.get_or_create(
            product=linen_shirt,
            color="Black",
            size="M",
            defaults={
                "unit_price": "28.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 2,
                "low_stock_threshold": 5,
            },
        )

        denim_jacket, _ = Product.objects.get_or_create(
            shop=active_shop,
            category=clothing,
            name="Denim Jacket",
            defaults={
                "description": "Classic denim jacket.",
                "is_active": True,
            },
        )

        ProductVariant.objects.get_or_create(
            product=denim_jacket,
            color="Blue",
            size="M",
            defaults={
                "unit_price": "45.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 10,
                "low_stock_threshold": 5,
            },
        )

        tote_bag, _ = Product.objects.get_or_create(
            shop=active_shop,
            category=accessories,
            name="Canvas Tote Bag",
            defaults={
                "description": "Durable everyday canvas tote bag.",
                "is_active": True,
            },
        )

        ProductVariant.objects.get_or_create(
            product=tote_bag,
            color="Natural",
            size="One Size",
            defaults={
                "unit_price": "18.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 15,
                "low_stock_threshold": 5,
            },
        )

        # ---------------------------------------------------------
        # Shop with no subscription
        # ---------------------------------------------------------

        Shop.objects.get_or_create(
            slug="no-subscription-shop",
            defaults={
                "owner": no_subscription_owner,
                "name": "No Subscription Shop",
                "whatsapp": "+96171111222",
                "instagram": "@no_subscription_shop",
                "pickup_available": False,
                "exchange_rate_lbp_per_usd": "89500.00",
            },
        )

        # ---------------------------------------------------------
        # Output
        # ---------------------------------------------------------

        self.stdout.write(
            self.style.SUCCESS(
                "Sprint 3 demo data created successfully."
            )
        )

        self.stdout.write("")
        self.stdout.write("Demo accounts:")
        self.stdout.write(f"  Admin: {admin.email}")
        self.stdout.write(f"  Active owner: {active_owner.email}")
        self.stdout.write(
            f"  No-subscription owner: "
            f"{no_subscription_owner.email}"
        )
        self.stdout.write(f"  Pending owner: {pending_owner.email}")
        self.stdout.write(
            f"  Suspended owner: {suspended_owner.email}"
        )
        self.stdout.write(f"  Password: {self.DEMO_PASSWORD}")

        self.stdout.write("")
        self.stdout.write("Demo shops:")
        self.stdout.write(
            f"  Active subscription: {active_shop.name}"
        )

        no_subscription_shop = Shop.objects.get(
            slug="no-subscription-shop"
        )
        self.stdout.write(
            f"  No subscription: {no_subscription_shop.name}"
        )

    def _get_or_create_user(
        self,
        *,
        email,
        full_name,
        role,
        status,
        is_staff=False,
    ):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "role": role,
                "status": status,
                "is_staff": is_staff,
                "is_active": True,
            },
        )

        if created:
            user.set_password(self.DEMO_PASSWORD)
            user.save(update_fields=["password"])

        return user
