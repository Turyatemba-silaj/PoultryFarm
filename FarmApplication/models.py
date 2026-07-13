from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


class Purchase(models.Model):
    ITEM_CHOICES = [
        ("soya", "Soya"),
        ("sunflower", "Sunflower"),
        ("maize_bran", "Maize Bran"),
        ("shells", "Shells"),
        ("dpc", "DPC"),
        
    ]
    item_name = models.CharField(max_length=100, choices=ITEM_CHOICES, default="soya")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-purchase_date", "-created_at"]
        indexes = [
            models.Index(fields=["item_name", "purchase_date"]),
        ]

    @property
    def total_amount(self):
        return self.quantity * self.unit_price

    @property
    def is_low_stock(self):
        return self.stock <= 0

    def __str__(self):
        return f"{self.get_item_name_display()} - {self.purchase_date}"


class FeedMix(models.Model):
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feed_mixes",
    )
    quantity_kg = models.DecimalField(max_digits=10, decimal_places=2)
    mixed_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-mixed_date", "-created_at"]

    @property
    def item_name(self):
        if not self.purchase:
            return ""
        return self.purchase.get_item_name_display()

    @property
    def ingredient(self):
        return self.item_name

    @property
    def unit_price(self):
        if not self.purchase:
            return Decimal("0.00")
        return self.purchase.unit_price

    @property
    def total_amount(self):
        return self.quantity_kg * self.unit_price

    def clean(self):
        if not self.purchase:
            raise ValidationError({"purchase": "Select a purchase item."})

        current_quantity = Decimal("0.00")
        if self.pk:
            current_quantity = FeedMix.objects.filter(pk=self.pk).values_list("quantity_kg", flat=True).first() or Decimal("0.00")

        available_stock = get_stock_balance_for_item(self.purchase.item_name) + current_quantity
        if self.quantity_kg > available_stock:
            raise ValidationError({"quantity_kg": f"Only {available_stock:.0f}kg available in stock."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name} - {self.quantity_kg:.0f}kg"


def get_stock_balance_for_item(item_name):
    purchased_quantity = sum(
        Purchase.objects.filter(item_name=item_name).values_list("quantity", flat=True),
        Decimal("0.00"),
    )
    mixed_quantity = sum(
        FeedMix.objects.filter(purchase__item_name=item_name).values_list("quantity_kg", flat=True),
        Decimal("0.00"),
    )
    return purchased_quantity - mixed_quantity


def recalculate_purchase_stock():
    for item_name, _label in Purchase.ITEM_CHOICES:
        stock = get_stock_balance_for_item(item_name)
        Purchase.objects.filter(item_name=item_name).update(stock=stock)


@receiver(post_save, sender=Purchase)
def update_stock_after_purchase_save(sender, instance, **kwargs):
    recalculate_purchase_stock()


@receiver(post_delete, sender=Purchase)
def update_stock_after_purchase_delete(sender, instance, **kwargs):
    recalculate_purchase_stock()


@receiver(post_save, sender=FeedMix)
def update_stock_after_feed_mix_save(sender, instance, **kwargs):
    recalculate_purchase_stock()


@receiver(post_delete, sender=FeedMix)
def update_stock_after_feed_mix_delete(sender, instance, **kwargs):
    recalculate_purchase_stock()


class FeedConsumption(models.Model):
    feed_mix = models.ForeignKey(
        FeedMix,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consumptions",
    )
    number_of_birds = models.PositiveIntegerField(default=0)
    quantity_kg = models.DecimalField(max_digits=10, decimal_places=2)
    consumption_date = models.DateField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feed_consumptions_issued",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def item_name(self):
        if not self.feed_mix:
            return "-"
        return self.feed_mix.item_name


    @property
    def expense_per_bird(self):
        if self.number_of_birds <= 0:
            return Decimal("0.00")
        total_expense = self.quantity_kg * get_unit_price_per_mixed_kg()
        return total_expense / self.number_of_birds

    @property
    def total_expense(self):
        return self.number_of_birds * self.expense_per_bird

    def __str__(self):
        return f"{self.quantity_kg:.0f}kg consumed on {self.consumption_date}"


def get_total_feed_mixed_quantity():
    return sum(
        FeedMix.objects.values_list("quantity_kg", flat=True),
        Decimal("0.00"),
    )


def get_total_feed_consumed_quantity(exclude_consumption_id=None):
    queryset = FeedConsumption.objects.all()
    if exclude_consumption_id:
        queryset = queryset.exclude(pk=exclude_consumption_id)
    return sum(queryset.values_list("quantity_kg", flat=True), Decimal("0.00"))


def get_feed_block_balance(exclude_consumption_id=None):
    return get_total_feed_mixed_quantity() - get_total_feed_consumed_quantity(exclude_consumption_id)


def get_unit_price_per_mixed_kg():
    total_quantity = get_total_feed_mixed_quantity()
    if total_quantity <= 0:
        return Decimal("0.00")
    total_amount = sum((feed_mix.total_amount for feed_mix in FeedMix.objects.all()), Decimal("0.00"))
    return total_amount / total_quantity

class EggProduction(models.Model):
    production_date = models.DateField()
    total_eggs = models.PositiveIntegerField()
    broken_eggs = models.PositiveIntegerField(default=0)
    tray_count = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def trays_for_sale(self):
        return self.total_eggs - self.broken_eggs

    @property
    def saleable_eggs(self):
        return self.trays_for_sale

    @property
    def trays_carried_forward(self):
        productions = EggProduction.objects.filter(production_date__lte=self.production_date)
        if self.pk:
            productions = productions.exclude(production_date=self.production_date, pk__gt=self.pk)

        total_trays_for_sale = sum((item.trays_for_sale for item in productions), 0)
        sold_trays = sum(
            Sale.objects.filter(product="eggs", sale_date__lte=self.production_date).values_list("quantity", flat=True),
            Decimal("0.00"),
        )
        return Decimal(total_trays_for_sale) - sold_trays

    def __str__(self):
        return f"{self.total_eggs} trays - {self.production_date}"


class Sale(models.Model):
    PRODUCT_CHOICES = [
        ("eggs", "Eggs"),
        ("birds", "Birds"),
        ("manure", "Manure"),
        ("other", "Other"),
    ]

    product = models.CharField(max_length=20, choices=PRODUCT_CHOICES, default="eggs")
    customer = models.CharField(max_length=100, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=30, default="tray")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_amount(self):
        return self.quantity * self.unit_price

    @property
    def available_trays_for_sale(self):
        total_trays_for_sale = sum(
            (item.trays_for_sale for item in EggProduction.objects.filter(production_date__lte=self.sale_date)),
            0,
        )
        previous_sales = Sale.objects.filter(product="eggs", sale_date__lt=self.sale_date)
        if self.pk:
            same_day_previous_sales = Sale.objects.filter(product="eggs", sale_date=self.sale_date, pk__lt=self.pk)
            previous_sales = previous_sales | same_day_previous_sales

        sold_trays = sum(previous_sales.values_list("quantity", flat=True), Decimal("0.00"))
        return Decimal(total_trays_for_sale) - sold_trays

    @property
    def net_profit(self):
        total_sales = sum((sale.total_amount for sale in Sale.objects.all()), Decimal("0.00"))
        total_kgs_consumed = sum(
            FeedConsumption.objects.values_list("quantity_kg", flat=True),
            Decimal("0.00"),
        )
        expenses = total_kgs_consumed * get_unit_price_per_mixed_kg()
        return total_sales - expenses

    def __str__(self):
        return f"{self.product} sale - {self.sale_date}"











