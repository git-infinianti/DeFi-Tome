from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Wallet', '0012_walletprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='trackedasset',
            name='network_mode',
            field=models.CharField(
                choices=[('mainnet', 'Mainnet'), ('testnet', 'Testnet')],
                default='mainnet',
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='trackedasset',
            name='symbol',
            field=models.CharField(max_length=255),
        ),
        migrations.AddConstraint(
            model_name='trackedasset',
            constraint=models.UniqueConstraint(
                fields=('symbol', 'network_mode'),
                name='tracked_asset_symbol_network_unique',
            ),
        ),
    ]
