from datetime import date
from decimal import Decimal

from django.test import TestCase

from .forms import EggProductionForm, SaleForm
from .models import EggProduction, Sale


class EggProductionValidationTests(TestCase):
    def test_damaged_trays_cannot_exceed_collected_trays(self):
        form = EggProductionForm(
            data={
                "production_date": date(2026, 7, 13),
                "total_eggs": 10,
                "broken_eggs": 11,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("broken_eggs", form.errors)

    def test_sale_quantity_cannot_exceed_available_trays(self):
        EggProduction.objects.create(production_date=date(2026, 7, 13), total_eggs=10, broken_eggs=2)

        form = SaleForm(
            data={
                "sale_date": date(2026, 7, 13),
                "quantity": Decimal("9.00"),
                "unit_price": Decimal("1000.00"),
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_sale_quantity_allows_available_trays(self):
        EggProduction.objects.create(production_date=date(2026, 7, 13), total_eggs=10, broken_eggs=2)

        form = SaleForm(
            data={
                "sale_date": date(2026, 7, 13),
                "quantity": Decimal("8.00"),
                "unit_price": Decimal("1000.00"),
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_production_edit_cannot_reduce_stock_below_sales(self):
        production = EggProduction.objects.create(production_date=date(2026, 7, 13), total_eggs=10, broken_eggs=2)
        Sale.objects.create(sale_date=date(2026, 7, 13), quantity=Decimal("8.00"), unit_price=Decimal("1000.00"))

        form = EggProductionForm(
            data={
                "production_date": date(2026, 7, 13),
                "total_eggs": 7,
                "broken_eggs": 0,
            },
            instance=production,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("total_eggs", form.errors)

