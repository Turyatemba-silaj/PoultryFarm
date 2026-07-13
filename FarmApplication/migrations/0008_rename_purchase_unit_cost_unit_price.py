# Generated manually for purchase unit cost rename

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('FarmApplication', '0007_remove_purchase_invoice_number'),
    ]

    operations = [
        migrations.RenameField(
            model_name='purchase',
            old_name='unit_cost',
            new_name='unit_price',
        ),
    ]
