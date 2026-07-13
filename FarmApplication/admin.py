from django.contrib import admin

from .models import EggProduction, FeedConsumption, FeedMix, Purchase, Sale


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "item_name",
        "quantity",
        "stock",
        "unit_price",
        "total_amount",
        "purchase_date",
    )
    list_filter = ("item_name", "purchase_date")
    search_fields = ("item_name",)
    readonly_fields = ("stock", "created_at", "updated_at")
    date_hierarchy = "purchase_date"


@admin.register(FeedMix)
class FeedMixAdmin(admin.ModelAdmin):
    list_display = ("id", "mixed_date", "item_name", "quantity_kg", "total_amount")
    list_filter = ("mixed_date", "purchase__item_name")
    search_fields = ("purchase__item_name",)
    readonly_fields = ("mixed_date", "created_at")


@admin.register(FeedConsumption)
class FeedConsumptionAdmin(admin.ModelAdmin):
    list_display = ("id", "consumption_date", "number_of_birds", "quantity_kg", "expense_per_bird", "issued_by")
    list_filter = ("consumption_date",)
    search_fields = ("feed_mix__purchase__item_name", "issued_by__username")


@admin.register(EggProduction)
class EggProductionAdmin(admin.ModelAdmin):
    list_display = ("id", "production_date", "total_eggs", "broken_eggs", "trays_for_sale", "trays_carried_forward")
    list_filter = ("production_date",)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("available_trays_for_sale", "quantity", "unit_price", "total_amount", "net_profit", "sale_date")
    list_filter = ("product", "sale_date")
    search_fields = ("customer", "product")








