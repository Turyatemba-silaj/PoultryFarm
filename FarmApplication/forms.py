from decimal import Decimal

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation

from .models import (
    EggProduction,
    FeedConsumption,
    FeedMix,
    Purchase,
    Sale,
)



def get_feed_item_balance(item_name, exclude_consumption_id=None):
    mixed_quantity = sum(
        FeedMix.objects.filter(purchase__item_name=item_name).values_list("quantity_kg", flat=True),
        Decimal("0.00"),
    )
    consumptions = FeedConsumption.objects.filter(feed_mix__purchase__item_name=item_name)
    if exclude_consumption_id:
        consumptions = consumptions.exclude(pk=exclude_consumption_id)
    consumed_quantity = sum(consumptions.values_list("quantity_kg", flat=True), Decimal("0.00"))
    return mixed_quantity - consumed_quantity


def get_available_egg_trays(sale_date, exclude_sale_id=None):
    produced_trays = sum(
        (item.trays_for_sale for item in EggProduction.objects.filter(production_date__lte=sale_date)),
        0,
    )
    egg_sales = Sale.objects.filter(product="eggs", sale_date__lte=sale_date)
    if exclude_sale_id:
        egg_sales = egg_sales.exclude(pk=exclude_sale_id)
    sold_trays = sum(egg_sales.values_list("quantity", flat=True), Decimal("0.00"))
    return Decimal(produced_trays) - sold_trays


def get_lowest_egg_balance_from(start_date, exclude_production_id=None):
    production_dates = EggProduction.objects.filter(production_date__gte=start_date).values_list(
        "production_date",
        flat=True,
    )
    sale_dates = Sale.objects.filter(product="eggs", sale_date__gte=start_date).values_list("sale_date", flat=True)
    dates = sorted(set(production_dates) | set(sale_dates))
    if not dates:
        dates = [start_date]

    lowest_balance = None
    for check_date in dates:
        productions = EggProduction.objects.filter(production_date__lte=check_date)
        if exclude_production_id:
            productions = productions.exclude(pk=exclude_production_id)
        produced_trays = sum((item.trays_for_sale for item in productions), 0)
        sold_trays = sum(
            Sale.objects.filter(product="eggs", sale_date__lte=check_date).values_list("quantity", flat=True),
            Decimal("0.00"),
        )
        balance = Decimal(produced_trays) - sold_trays
        if lowest_balance is None or balance < lowest_balance:
            lowest_balance = balance
    return lowest_balance or Decimal("0.00")


class FeedBlockChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, balances=None, **kwargs):
        self.balances = balances or {}
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        balance = self.balances.get(obj.purchase.item_name if obj.purchase else "", obj.quantity_kg)
        return f"{obj.item_name} - {balance:.0f}kg"


class BaseFarmForm(forms.ModelForm):
    date_fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in self.date_fields:
                field.widget.input_type = "date"

            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({"class": "form-control", "rows": 3})
            else:
                field.widget.attrs.update({"class": "form-control"})


class PasswordResetWithOldPasswordForm(forms.Form):
    username = forms.CharField(label="Username")
    old_password = forms.CharField(label="Old password", widget=forms.PasswordInput)
    new_password1 = forms.CharField(label="New password", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})
        self.user = None

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        old_password = cleaned_data.get("old_password")
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        if username and old_password:
            self.user = authenticate(username=username, password=old_password)
            if self.user is None:
                raise forms.ValidationError("Username or old password is incorrect.")

        if new_password1 and new_password2 and new_password1 != new_password2:
            self.add_error("new_password2", "The new passwords do not match.")

        if self.user and new_password1:
            password_validation.validate_password(new_password1, self.user)

        return cleaned_data

    def save(self):
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        self.user.save(update_fields=["password"])
        return self.user


class PurchaseForm(BaseFarmForm):
    date_fields = ("purchase_date",)

    class Meta:
        model = Purchase
        fields = [
            "item_name",
            "quantity",
            "unit_price",
            "purchase_date",
            "notes",
        ]


class FeedMixForm(BaseFarmForm):
    class Meta:
        model = FeedMix
        fields = [
            "purchase",
            "quantity_kg",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Purchase.objects.filter(stock__gt=0).order_by("item_name", "purchase_date")
        if self.instance and self.instance.pk and self.instance.purchase_id:
            queryset = Purchase.objects.filter(pk=self.instance.purchase_id) | queryset
        self.fields["purchase"].queryset = queryset.distinct()
        self.fields["purchase"].label = "Purchase Item"
        self.fields["quantity_kg"].label = "Quantity"


class FeedConsumptionForm(BaseFarmForm):
    date_fields = ("consumption_date",)

    class Meta:
        model = FeedConsumption
        fields = [
            "feed_mix",
            "number_of_birds",
            "quantity_kg",
            "consumption_date",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        exclude_id = self.instance.pk if self.instance and self.instance.pk else None
        balances = {}
        representative_ids = []
        seen_items = set()

        for feed_mix in FeedMix.objects.select_related("purchase").order_by("purchase__item_name", "id"):
            if not feed_mix.purchase or feed_mix.purchase.item_name in seen_items:
                continue
            balance = get_feed_item_balance(feed_mix.purchase.item_name, exclude_id)
            if balance <= 0 and feed_mix.pk != getattr(self.instance, "feed_mix_id", None):
                continue
            seen_items.add(feed_mix.purchase.item_name)
            balances[feed_mix.purchase.item_name] = balance
            representative_ids.append(feed_mix.pk)

        if self.instance and self.instance.pk and self.instance.feed_mix_id and self.instance.feed_mix_id not in representative_ids:
            representative_ids.append(self.instance.feed_mix_id)
            if self.instance.feed_mix and self.instance.feed_mix.purchase:
                item_name = self.instance.feed_mix.purchase.item_name
                balances[item_name] = get_feed_item_balance(item_name, exclude_id)

        queryset = FeedMix.objects.filter(pk__in=representative_ids).select_related("purchase").order_by("purchase__item_name", "id")
        has_feed_mixes = queryset.exists()

        self.fields["feed_mix"] = FeedBlockChoiceField(
            queryset=queryset,
            required=has_feed_mixes,
            balances=balances,
            label="Feed Mix",
            empty_label=None if has_feed_mixes else "No mixed feed available",
            widget=forms.Select(attrs={"class": "form-control"}),
        )

    def clean(self):
        cleaned_data = super().clean()
        feed_mix = cleaned_data.get("feed_mix")
        quantity_kg = cleaned_data.get("quantity_kg")
        if feed_mix and feed_mix.purchase and quantity_kg is not None:
            exclude_id = self.instance.pk if self.instance and self.instance.pk else None
            balance = get_feed_item_balance(feed_mix.purchase.item_name, exclude_id)
            if quantity_kg > balance:
                self.add_error("quantity_kg", f"Only {balance:.0f}kg available for {feed_mix.item_name}.")
        return cleaned_data


class EggProductionForm(BaseFarmForm):
    date_fields = ("production_date",)

    class Meta:
        model = EggProduction
        fields = [
            "production_date",
            "total_eggs",
            "broken_eggs",
            "notes",
        ]
        labels = {
            "total_eggs": "No. Trays Collected",
            "broken_eggs": "No. Of Trays Damaged",
        }

    def clean(self):
        cleaned_data = super().clean()
        production_date = cleaned_data.get("production_date")
        total_eggs = cleaned_data.get("total_eggs")
        broken_eggs = cleaned_data.get("broken_eggs")

        if total_eggs is not None and broken_eggs is not None and broken_eggs > total_eggs:
            self.add_error("broken_eggs", "Damaged trays cannot be greater than collected trays.")

        if production_date and total_eggs is not None and broken_eggs is not None:
            trays_for_sale = Decimal(total_eggs - broken_eggs)
            exclude_id = self.instance.pk if self.instance and self.instance.pk else None
            lowest_existing_balance = get_lowest_egg_balance_from(production_date, exclude_id)
            lowest_balance_after_save = lowest_existing_balance + trays_for_sale
            if lowest_balance_after_save < 0:
                shortage = abs(lowest_balance_after_save)
                self.add_error(
                    "total_eggs",
                    f"This production record would leave egg stock short by {shortage:.0f} trays.",
                )

        return cleaned_data


class SaleForm(BaseFarmForm):
    date_fields = ("sale_date",)

    class Meta:
        model = Sale
        fields = [
            "quantity",
            "unit_price",
            "sale_date",
        ]
        labels = {
            "quantity": "Quantity",
        }

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        sale_date = cleaned_data.get("sale_date")

        if quantity is not None and sale_date:
            exclude_id = self.instance.pk if self.instance and self.instance.pk else None
            available_trays = get_available_egg_trays(sale_date, exclude_id)
            if quantity > available_trays:
                self.add_error("quantity", f"Only {available_trays:.0f} trays available for sale on this date.")

        return cleaned_data



