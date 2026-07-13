from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import EggProductionForm, FeedConsumptionForm, FeedMixForm, PasswordResetWithOldPasswordForm, PurchaseForm, SaleForm
from .models import EggProduction, FeedConsumption, FeedMix, Purchase, Sale, get_stock_balance_for_item, get_unit_price_per_mixed_kg


def password_reset_with_old_password(request):
    if request.method == "POST":
        form = PasswordResetWithOldPasswordForm(request.POST)
        if form.is_valid():
            user = form.save()
            if request.user.is_authenticated and request.user.pk == user.pk:
                update_session_auth_hash(request, user)
            return redirect("password_reset_done")
    else:
        form = PasswordResetWithOldPasswordForm()

    return render(request, "registration/password_reset_with_old_password_form.html", {"form": form})


MODEL_CONFIG = {
    "purchases": {
        "title": "Purchases",
        "singular": "Purchase",
        "model": Purchase,
        "form": PurchaseForm,
        "fields": ["id", "purchase_date", "item_name", "quantity", "unit_price", "stock", "total_amount"],
        "accent": "blue",
    },
    "feed-mixes": {
        "title": "Feed Mixes",
        "singular": "Feed Mix",
        "model": FeedMix,
        "form": FeedMixForm,
        "fields": ["id", "mixed_date", "item_name", "quantity_kg", "total_amount"],
        "accent": "green",
    },
    "feed-consumption": {
        "title": "Feed Consumption",
        "singular": "Feed Consumption",
        "model": FeedConsumption,
        "form": FeedConsumptionForm,
        "fields": ["id", "consumption_date", "item_name", "number_of_birds", "quantity_kg", "expense_per_bird", "total_expense", "issued_by"],
        "accent": "amber",
    },
    "egg-production": {
        "title": "Egg Production",
        "singular": "Egg Production",
        "model": EggProduction,
        "form": EggProductionForm,
        "fields": ["id", "production_date", "total_eggs", "broken_eggs", "trays_for_sale", "trays_carried_forward"],
        "accent": "rose",
    },
    "sales": {
        "title": "Sales",
        "singular": "Sale",
        "model": Sale,
        "form": SaleForm,
        "fields": ["id", "sale_date", "available_trays_for_sale", "quantity", "unit_price", "total_amount", "net_profit"],
        "accent": "purple",
    },
}


def get_record_config(record_type):
    try:
        return MODEL_CONFIG[record_type]
    except KeyError as exc:
        raise Http404("Record type not found") from exc


def whole_number(value):
    return f"{value:,.0f}"


def money(value):
    return f"{whole_number(value)} UGX"


def get_field_label(field):
    labels = {
        "id": "Purchase Id",
        "mixed_date": "Mix Date",
        "item_name": "Item Name",
        "quantity_kg": "Quantity",
        "unit_price": "Unit Price",
        "total_amount": "Total Amount",
    }
    return labels.get(field, field.replace("_", " ").title())


def get_record_label(record_type, field):
    if record_type == "feed-mixes" and field == "id":
        return "Mix Id"
    if record_type == "egg-production":
        labels = {
            "id": "Production Id",
            "production_date": "Production Date",
            "total_eggs": "No. Trays Collected",
            "broken_eggs": "No. Of Trays Damaged",
            "trays_for_sale": "Produced For Sale",
            "trays_carried_forward": "Trays Carried Forward",
        }
        if field in labels:
            return labels[field]
    if record_type == "sales":
        labels = {
            "id": "Sales ID",
            "sale_date": "Sale Date",
            "available_trays_for_sale": "Available Trays For Sale",
            "quantity": "No. Of Trays Sold",
            "unit_price": "Unit Price",
            "total_amount": "Total Sales",
            "net_profit": "Net Profit/Loss",
        }
        if field in labels:
            return labels[field]
    if record_type == "feed-consumption":
        labels = {
            "id": "Consumption Id",
            "consumption_date": "Consumption Date",
            "item_name": "Item Name",
            "number_of_birds": "Number Of Birds",
            "quantity_kg": "Kgs Consumed",
            "expense_per_bird": "Expense Per Bird",
            "total_expense": "Total Expense",
            "issued_by": "Issued By",
        }
        if field in labels:
            return labels[field]
    return get_field_label(field)


def format_record_value(record_type, field, value, record):
    money_fields = {"unit_price", "total_amount", "expense_per_bird", "total_expense", "net_profit"}
    if record_type == "feed-consumption" and field == "item_name":
        return record.feed_mix.item_name if record.feed_mix else "-"
    if field == "quantity_kg":
        return f"{whole_number(value)}kg"
    if record_type == "purchases" and field in {"quantity", "stock"}:
        return f"{whole_number(value)}kg"
    if record_type == "egg-production" and field in {"total_eggs", "broken_eggs", "trays_for_sale", "trays_carried_forward"}:
        return f"{whole_number(value)} trays"
    if record_type == "sales" and field == "available_trays_for_sale":
        return f"{whole_number(value)} trays"
    if record_type == "sales" and field == "quantity":
        return f"{whole_number(value)} trays"
    if field in money_fields:
        return money(value)
    return value


def get_table_footer(record_type, records):
    if record_type == "purchases":
        total_quantity = sum((record.quantity for record in records), Decimal("0.00"))
        total_amount = sum((record.total_amount for record in records), Decimal("0.00"))
        return {
            "cells": [
                "Total",
                "",
                "",
                f"{whole_number(total_quantity)}kg",
                "",
                f"{whole_number(get_total_purchase_stock())}kg",
                money(total_amount),
            ]
        }

    if record_type == "feed-mixes":
        total_mixed_quantity = sum((record.quantity_kg for record in records), Decimal("0.00"))
        total_mixed_amount = sum((record.total_amount for record in records), Decimal("0.00"))
        total_consumed_quantity = sum(FeedConsumption.objects.values_list("quantity_kg", flat=True), Decimal("0.00"))
        available_quantity = total_mixed_quantity - total_consumed_quantity
        unit_price_per_mixed_kg = total_mixed_amount / total_mixed_quantity if total_mixed_quantity else Decimal("0.00")
        available_amount = available_quantity * unit_price_per_mixed_kg
        return {
            "cells": [
                "Total",
                "",
                f"Unit Price Per Mixed Kg: {money(unit_price_per_mixed_kg)}",
                f"{whole_number(available_quantity)}kg",
                money(available_amount),
            ]
        }


    if record_type == "feed-consumption":
        total_birds = sum((record.number_of_birds for record in records), 0)
        total_quantity = sum((record.quantity_kg for record in records), Decimal("0.00"))
        total_expense = sum((record.total_expense for record in records), Decimal("0.00"))
        average_expense_per_bird = total_expense / total_birds if total_birds else Decimal("0.00")
        return {
            "cells": [
                "Total",
                "",
                "",
                total_birds,
                f"{whole_number(total_quantity)}kg",
                money(average_expense_per_bird),
                money(total_expense),
                "",
            ]
        }

    if record_type == "egg-production":
        total_collected = sum((record.total_eggs for record in records), 0)
        total_damaged = sum((record.broken_eggs for record in records), 0)
        total_for_sale = sum((record.trays_for_sale for record in records), 0)
        carried_forward = records[-1].trays_carried_forward if records else Decimal("0.00")
        return {
            "cells": [
                "Total",
                "",
                f"{whole_number(total_collected)} trays",
                f"{whole_number(total_damaged)} trays",
                f"{whole_number(total_for_sale)} trays",
                f"{whole_number(carried_forward)} trays",
            ]
        }

    if record_type == "sales":
        total_sales_value = sum((record.total_amount for record in records), Decimal("0.00"))
        total_quantity = sum((record.quantity for record in records), Decimal("0.00"))
        total_feed_consumed = sum(FeedConsumption.objects.values_list("quantity_kg", flat=True), Decimal("0.00"))
        net_profit = total_sales_value - (total_feed_consumed * get_unit_price_per_mixed_kg())
        available_trays = records[-1].available_trays_for_sale if records else Decimal("0.00")
        return {
            "cells": [
                "Total",
                "",
                f"{whole_number(available_trays)} trays",
                f"{whole_number(total_quantity)} trays",
                "",
                money(total_sales_value),
                money(net_profit),
            ]
        }

    return None


def get_total_purchase_stock():
    return sum((get_stock_balance_for_item(item_name) for item_name, _label in Purchase.ITEM_CHOICES), start=0)

def get_module_balances():
    total_purchase_stock = get_total_purchase_stock()
    total_feed_mixed = sum((feed_mix.quantity_kg for feed_mix in FeedMix.objects.all()), start=0)
    total_feed_consumed = sum((item.quantity_kg for item in FeedConsumption.objects.all()), start=0)
    feed_balance = total_feed_mixed - total_feed_consumed
    saleable_eggs = sum((item.saleable_eggs for item in EggProduction.objects.all()), start=0)
    sold_eggs = sum((sale.quantity for sale in Sale.objects.filter(product="eggs")), start=0)
    egg_balance = saleable_eggs - sold_eggs
    total_sales_quantity = sum((sale.quantity for sale in Sale.objects.all()), start=0)

    return {
        "purchases": f"{whole_number(total_purchase_stock)}kg",
        "feed-mixes": f"{whole_number(feed_balance)}kg",
        "feed-consumption": f"{whole_number(total_feed_consumed)}kg",
        "egg-production": f"{whole_number(egg_balance)} trays",
        "sales": whole_number(total_sales_quantity),
    }


def get_navigation_cards(active_record_type=None):
    balances = get_module_balances()
    return [
        {
            "slug": slug,
            "title": item["title"],
            "balance": balances.get(slug, "0"),
            "active": slug == active_record_type,
        }
        for slug, item in MODEL_CONFIG.items()
    ]

@login_required
def dashboard(request):
    report_period = request.GET.get("report_period", "daily")
    if report_period not in REPORT_PERIODS:
        report_period = "daily"
    report_type = request.GET.get("report_type", "sales")
    if report_type not in REPORT_TYPES:
        report_type = "sales"
    try:
        report_date = date.fromisoformat(request.GET.get("report_date", ""))
    except ValueError:
        report_date = date.today()
    report = report_summary(report_period, report_date, report_type)

    total_purchase_value = sum(purchase.total_amount for purchase in Purchase.objects.all())
    total_sales_value = sum(sale.total_amount for sale in Sale.objects.all())
    total_feed_consumed = sum(item.quantity_kg for item in FeedConsumption.objects.all())
    total_expenses = total_feed_consumed * get_unit_price_per_mixed_kg()
    net_profit = total_sales_value - total_expenses
    total_eggs = sum(item.total_eggs for item in EggProduction.objects.all())
    saleable_eggs = sum(item.saleable_eggs for item in EggProduction.objects.all())

    cards = []
    for slug, config in MODEL_CONFIG.items():
        cards.append({
            "slug": slug,
            "title": config["title"],
            "singular": config["singular"],
            "count": config["model"].objects.count(),
            "accent": config["accent"],
        })

    total_purchased_quantity = sum(purchase.quantity for purchase in Purchase.objects.all())
    total_purchase_stock = get_total_purchase_stock()
    total_feed_mixed = sum(feed_mix.quantity_kg for feed_mix in FeedMix.objects.all())
    total_sales_quantity = sum(sale.quantity for sale in Sale.objects.all())

    quantity_cards = [
        {"label": "Purchased Quantity", "value": f"{whole_number(total_purchased_quantity)}kg", "url": "purchases", "tone": "blue"},
        {"label": "Stock Quantity", "value": f"{whole_number(total_purchase_stock)}kg", "url": "purchases", "tone": "green"},
        {"label": "Feed Mixed", "value": f"{whole_number(total_feed_mixed)}kg", "url": "feed-mixes", "tone": "amber"},
        {"label": "Feed Consumed", "value": f"{whole_number(total_feed_consumed)}kg", "url": "feed-consumption", "tone": "green"},
        {"label": "No. Trays Collected", "value": f"{total_eggs:,} trays", "url": "egg-production", "tone": "rose"},
        {"label": "No. Of Trays Sold", "value": whole_number(total_sales_quantity), "url": "sales", "tone": "purple"},
    ]

    metrics = [
        {"label": "Purchase Value", "value": money(total_purchase_value), "detail": "Total farm spending", "tone": "blue"},
        {"label": "Trays Produced", "value": f"{total_eggs:,}", "detail": f"{saleable_eggs:,} trays for sale", "tone": "rose"},
        {"label": "Feed Consumed", "value": f"{whole_number(total_feed_consumed)}kg", "detail": "Total feed usage", "tone": "green"},
        {"label": "Sales", "value": money(total_sales_value), "detail": "Total sales recorded", "tone": "purple"},
        {"label": "Expenses", "value": money(total_expenses), "detail": "Feed consumed cost", "tone": "amber"},
        {"label": "Net Profit", "value": money(net_profit), "detail": "Sales minus expenses", "tone": "green"},
    ]

    return render(
        request,
        "FarmApplication/dashboard.html",
        {
            "cards": cards,
            "metrics": metrics,
            "quantity_cards": quantity_cards,
            "report": report,
            "report_periods": REPORT_PERIODS,
            "report_types": REPORT_TYPES,
            "selected_report_period": report_period,
            "selected_report_type": report_type,
            "selected_report_date": report_date,
        },
    )



REPORT_PERIODS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
}


REPORT_TYPES = {
    "sales": "Sales",
    "egg-production": "Egg Production",
    "feed-consumption": "Feed Consumption",
    "feed-mixes": "Feed Mixes",
    "purchases": "Purchases",
}


def get_report_range(period, reference_date=None):
    selected_date = reference_date or date.today()
    if period == "daily":
        start = selected_date
        end = selected_date
    elif period == "weekly":
        start = selected_date - timedelta(days=selected_date.weekday())
        end = start + timedelta(days=6)
    elif period == "monthly":
        start = selected_date.replace(day=1)
        next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        end = next_month - timedelta(days=1)
    elif period == "yearly":
        start = selected_date.replace(month=1, day=1)
        end = selected_date.replace(month=12, day=31)
    else:
        raise Http404("Report period not found")
    return start, end


def in_range(queryset, field_name, start, end):
    return queryset.filter(**{f"{field_name}__gte": start, f"{field_name}__lte": end})



def summarize_day(day, value, unit=""):
    suffix = f" {unit}" if unit else ""
    return f"{day.strftime('%A, %Y-%m-%d')} - {whole_number(value)}{suffix}"


def best_worst_by_day(records, date_field, value_func, unit=""):
    daily_totals = {}
    for record in records:
        day = getattr(record, date_field)
        daily_totals[day] = daily_totals.get(day, Decimal("0.00")) + value_func(record)

    if not daily_totals:
        return "No data", "No data"

    best_day, best_value = max(daily_totals.items(), key=lambda item: (item[1], item[0]))
    worst_day, worst_value = min(daily_totals.items(), key=lambda item: (item[1], item[0]))
    return summarize_day(best_day, best_value, unit), summarize_day(worst_day, worst_value, unit)


def sales_breakdown_by_day(sales, expenses):
    daily_sales = {}
    total_quantity = Decimal("0.00")

    for sale in sales:
        sale_day = sale.sale_date
        if sale_day not in daily_sales:
            daily_sales[sale_day] = {
                "date": sale_day,
                "quantity": Decimal("0.00"),
                "amount": Decimal("0.00"),
            }
        daily_sales[sale_day]["quantity"] += sale.quantity
        daily_sales[sale_day]["amount"] += sale.total_amount
        total_quantity += sale.quantity

    rows = []
    for sale_day, values in sorted(daily_sales.items()):
        expense = Decimal("0.00")
        if total_quantity > 0:
            expense = expenses * (values["quantity"] / total_quantity)

        result = values["amount"] - expense
        rows.append({
            "date": sale_day,
            "quantity": f"{whole_number(values['quantity'])} trays",
            "amount": money(values["amount"]),
            "expense": money(expense),
            "profit": money(result) if result >= 0 else money(Decimal("0.00")),
            "loss": money(abs(result)) if result < 0 else money(Decimal("0.00")),
        })

    return rows


def build_detail_report(report_type, purchases, feed_mixes, feed_consumption, egg_production, sales, expenses):
    if report_type == "purchases":
        rows = []
        total_quantity = Decimal("0.00")
        total_amount = Decimal("0.00")
        for purchase in purchases.order_by("purchase_date", "id"):
            total_quantity += purchase.quantity
            total_amount += purchase.total_amount
            rows.append({"cells": [
                purchase.purchase_date,
                purchase.get_item_name_display(),
                f"{whole_number(purchase.quantity)}kg",
                money(purchase.unit_price),
                money(purchase.total_amount),
            ]})
        return {
            "title": "Purchase Details",
            "columns": ["Purchase Date", "Item", "Quantity", "Unit Price", "Amount"],
            "rows": rows,
            "footer": ["Total", "", f"{whole_number(total_quantity)}kg", "", money(total_amount)],
            "empty_message": "No purchases recorded for this period",
        }

    if report_type == "feed-mixes":
        rows = []
        total_quantity = Decimal("0.00")
        total_amount = Decimal("0.00")
        for feed_mix in feed_mixes.order_by("mixed_date", "id"):
            total_quantity += feed_mix.quantity_kg
            total_amount += feed_mix.total_amount
            rows.append({"cells": [
                feed_mix.mixed_date,
                feed_mix.item_name,
                f"{whole_number(feed_mix.quantity_kg)}kg",
                money(feed_mix.total_amount),
            ]})
        return {
            "title": "Feed Mix Details",
            "columns": ["Mix Date", "Item", "Quantity Mixed", "Amount"],
            "rows": rows,
            "footer": ["Total", "", f"{whole_number(total_quantity)}kg", money(total_amount)],
            "empty_message": "No feed mixes recorded for this period",
        }

    if report_type == "feed-consumption":
        unit_price = get_unit_price_per_mixed_kg()
        rows = []
        total_birds = 0
        total_quantity = Decimal("0.00")
        total_expense = Decimal("0.00")
        for item in feed_consumption.order_by("consumption_date", "id"):
            item_expense = item.quantity_kg * unit_price
            total_birds += item.number_of_birds
            total_quantity += item.quantity_kg
            total_expense += item_expense
            issued_by = item.issued_by.get_username() if item.issued_by else "-"
            rows.append({"cells": [
                item.consumption_date,
                item.number_of_birds,
                f"{whole_number(item.quantity_kg)}kg",
                money(item_expense),
                money(item.expense_per_bird),
                issued_by,
            ]})
        average_expense_per_bird = total_expense / total_birds if total_birds else Decimal("0.00")
        return {
            "title": "Feed Consumption Details",
            "columns": ["Consumption Date", "Birds", "Quantity", "Expense", "Expense Per Bird", "Issued By"],
            "rows": rows,
            "footer": ["Total", total_birds, f"{whole_number(total_quantity)}kg", money(total_expense), money(average_expense_per_bird), ""],
            "empty_message": "No feed consumption recorded for this period",
        }

    if report_type == "egg-production":
        rows = []
        total_collected = 0
        total_damaged = 0
        total_produced_for_sale = Decimal("0.00")
        total_sold = Decimal("0.00")
        ordered_production = egg_production.order_by("production_date", "id")
        first_production = ordered_production.first()
        previous_carried_forward = Decimal("0.00")
        if first_production:
            previous_day = first_production.production_date - timedelta(days=1)
            previous_trays_for_sale = sum(
                (item.trays_for_sale for item in EggProduction.objects.filter(production_date__lte=previous_day)),
                0,
            )
            previous_trays_sold = sum(
                Sale.objects.filter(product="eggs", sale_date__lte=previous_day).values_list("quantity", flat=True),
                Decimal("0.00"),
            )
            previous_carried_forward = Decimal(previous_trays_for_sale) - previous_trays_sold

        for item in ordered_production:
            trays_sold = sum(
                sales.filter(product="eggs", sale_date=item.production_date).values_list("quantity", flat=True),
                Decimal("0.00"),
            )
            opening_balance = previous_carried_forward
            produced_for_sale = Decimal(item.trays_for_sale)
            available_for_sale = produced_for_sale + opening_balance
            trays_carried_forward = available_for_sale - trays_sold
            total_collected += item.total_eggs
            total_damaged += item.broken_eggs
            total_produced_for_sale += produced_for_sale
            total_sold += trays_sold
            rows.append({"cells": [
                item.production_date,
                f"{whole_number(item.total_eggs)} trays",
                f"{whole_number(item.broken_eggs)} trays",
                f"{whole_number(produced_for_sale)} trays",
                f"{whole_number(opening_balance)} trays",
                f"{whole_number(available_for_sale)} trays",
                f"{whole_number(trays_sold)} trays",
                f"{whole_number(trays_carried_forward)} trays",
            ]})
            previous_carried_forward = trays_carried_forward
        return {
            "title": "Egg Production Details",
            "columns": ["Production Date", "Collected", "Damaged", "Produced For Sale", "Opening Balance", "Available For Sale", "No. Trays Sold", "Carried Forward"],
            "rows": rows,
            "footer": ["Total", f"{whole_number(total_collected)} trays", f"{whole_number(total_damaged)} trays", f"{whole_number(total_produced_for_sale)} trays", "", "", f"{whole_number(total_sold)} trays", f"{whole_number(previous_carried_forward)} trays"],
            "empty_message": "No egg production recorded for this period",
        }

    sales_rows = []
    total_quantity = Decimal("0.00")
    total_amount = Decimal("0.00")
    total_expense = Decimal("0.00")
    total_profit = Decimal("0.00")
    total_loss = Decimal("0.00")
    for row in sales_breakdown_by_day(sales, expenses):
        quantity = Decimal(row["quantity"].split()[0].replace(",", ""))
        amount = Decimal(row["amount"].split()[0].replace(",", ""))
        expense = Decimal(row["expense"].split()[0].replace(",", ""))
        profit = Decimal(row["profit"].split()[0].replace(",", ""))
        loss = Decimal(row["loss"].split()[0].replace(",", ""))
        total_quantity += quantity
        total_amount += amount
        total_expense += expense
        total_profit += profit
        total_loss += loss
        sales_rows.append({"cells": [
            row["date"],
            row["quantity"],
            row["amount"],
            row["expense"],
            row["profit"],
            row["loss"],
        ]})
    return {
        "title": "Sales Details",
        "columns": ["Sales Date", "Quantity Sold", "Amount Sold", "Expense", "Profit", "Loss"],
        "rows": sales_rows,
        "footer": ["Total", f"{whole_number(total_quantity)} trays", money(total_amount), money(total_expense), money(total_profit), money(total_loss)],
        "empty_message": "No sales recorded for this period",
    }


def report_summary(period, reference_date=None, report_type="sales"):
    if report_type not in REPORT_TYPES:
        report_type = "sales"
    start, end = get_report_range(period, reference_date)
    purchases = in_range(Purchase.objects.all(), "purchase_date", start, end)
    feed_mixes = in_range(FeedMix.objects.all(), "mixed_date", start, end)
    feed_consumption = in_range(FeedConsumption.objects.all(), "consumption_date", start, end)
    egg_production = in_range(EggProduction.objects.all(), "production_date", start, end)
    sales = in_range(Sale.objects.all(), "sale_date", start, end)

    purchased_quantity = sum((purchase.quantity for purchase in purchases), Decimal("0.00"))
    purchase_value = sum((purchase.total_amount for purchase in purchases), Decimal("0.00"))
    feed_mixed_quantity = sum((feed_mix.quantity_kg for feed_mix in feed_mixes), Decimal("0.00"))
    feed_mixed_value = sum((feed_mix.total_amount for feed_mix in feed_mixes), Decimal("0.00"))
    feed_consumed_quantity = sum(feed_consumption.values_list("quantity_kg", flat=True), Decimal("0.00"))
    expenses = feed_consumed_quantity * get_unit_price_per_mixed_kg()
    trays_collected = sum((item.total_eggs for item in egg_production), 0)
    trays_damaged = sum((item.broken_eggs for item in egg_production), 0)
    trays_for_sale = sum((item.trays_for_sale for item in egg_production), 0)
    trays_sold = sum(sales.filter(product="eggs").values_list("quantity", flat=True), Decimal("0.00"))
    sales_value = sum((sale.total_amount for sale in sales), Decimal("0.00"))
    net_profit = sales_value - expenses
    profit = net_profit if net_profit >= 0 else Decimal("0.00")
    loss = abs(net_profit) if net_profit < 0 else Decimal("0.00")
    detail_report = build_detail_report(report_type, purchases, feed_mixes, feed_consumption, egg_production, sales, expenses)
    best_sales_day, worst_sales_day = best_worst_by_day(sales, "sale_date", lambda sale: sale.total_amount, "UGX")
    best_egg_day, worst_egg_day = best_worst_by_day(egg_production, "production_date", lambda item: Decimal(item.trays_for_sale), "trays")

    return {
        "period": period,
        "period_label": REPORT_PERIODS[period],
        "report_type": report_type,
        "report_type_label": REPORT_TYPES[report_type],
        "start": start,
        "end": end,
        "metrics": [
            {"label": "Sales", "value": money(sales_value), "tone": "purple"},
            {"label": "Expenses", "value": money(expenses), "tone": "amber"},
            {"label": "Net Profit", "value": money(net_profit), "tone": "green"},
            {"label": "Purchases", "value": money(purchase_value), "tone": "blue"},
        ],
        "rows": [
            {"label": "Purchased Quantity", "value": f"{whole_number(purchased_quantity)}kg"},
            {"label": "Purchase Value", "value": money(purchase_value)},
            {"label": "Feed Mixed", "value": f"{whole_number(feed_mixed_quantity)}kg"},
            {"label": "Feed Mixed Value", "value": money(feed_mixed_value)},
            {"label": "Feed Consumed", "value": f"{whole_number(feed_consumed_quantity)}kg"},
            {"label": "Expenses", "value": money(expenses)},
            {"label": "No. Trays Collected", "value": f"{whole_number(trays_collected)} trays"},
            {"label": "No. Of Trays Damaged", "value": f"{whole_number(trays_damaged)} trays"},
            {"label": "Produced For Sale", "value": f"{whole_number(trays_for_sale)} trays"},
            {"label": "Trays Sold", "value": f"{whole_number(trays_sold)} trays"},
            {"label": "Total Sales", "value": money(sales_value)},
            {"label": "Net Profit", "value": money(net_profit)},
            {"label": "Profit", "value": money(profit)},
            {"label": "Loss", "value": money(loss)},
            {"label": "Best Sales Day", "value": best_sales_day},
            {"label": "Worst Sales Day", "value": worst_sales_day},
            {"label": "Best Egg Production Day", "value": best_egg_day},
            {"label": "Worst Egg Production Day", "value": worst_egg_day},
        ],
        "detail_report": detail_report,
    }


@login_required
def record_list(request, record_type):
    config = get_record_config(record_type)
    order_fields = ["id", "sale_date"] if record_type == "sales" else ["id"]
    records = list(config["model"].objects.all().order_by(*order_fields))
    fields = config["fields"]
    rows = []
    for record in records:
        rows.append({
            "record": record,
            "values": [format_record_value(record_type, field, getattr(record, field), record) for field in fields],
        })

    table_footer = get_table_footer(record_type, records)

    return render(
        request,
        "FarmApplication/record_list.html",
        {
            "record_type": record_type,
            "title": config["title"],
            "singular": config["singular"],
            "fields": fields,
            "field_labels": [get_record_label(record_type, field) for field in fields],
            "rows": rows,
            "table_footer": table_footer,
            "cards": get_navigation_cards(record_type),
        },
    )


@login_required
def record_create(request, record_type):
    config = get_record_config(record_type)
    form_class = config["form"]

    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            if record_type == "feed-consumption" and request.user.is_authenticated:
                record.issued_by = request.user
            record.save()
            return redirect("record_list", record_type=record_type)
    else:
        form = form_class()

    return render(
        request,
        "FarmApplication/record_form.html",
        {
            "form": form,
            "record_type": record_type,
            "title": f"Add {config['singular']}",
        },
    )


@login_required
def record_update(request, record_type, pk):
    config = get_record_config(record_type)
    model = config["model"]
    form_class = config["form"]
    record = get_object_or_404(model, pk=pk)

    if request.method == "POST":
        form = form_class(request.POST, instance=record)
        if form.is_valid():
            record = form.save(commit=False)
            if record_type == "feed-consumption" and request.user.is_authenticated:
                record.issued_by = request.user
            record.save()
            return redirect("record_list", record_type=record_type)
    else:
        form = form_class(instance=record)

    return render(
        request,
        "FarmApplication/record_form.html",
        {
            "form": form,
            "record_type": record_type,
            "title": f"Edit {config['singular']}",
        },
    )


@login_required
def record_delete(request, record_type, pk):
    config = get_record_config(record_type)
    record = get_object_or_404(config["model"], pk=pk)

    if request.method == "POST":
        record.delete()
        return redirect("record_list", record_type=record_type)

    return render(
        request,
        "FarmApplication/record_confirm_delete.html",
        {
            "record": record,
            "record_type": record_type,
            "title": f"Delete {config['singular']}",
        },
    )







































