from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('Wallet', '0011_userwallet_evr_liquidity_mainnet_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='WalletProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('network_mode', models.CharField(choices=[('mainnet', 'Mainnet'), ('testnet', 'Testnet')], default='mainnet', max_length=10)),
                ('name', models.CharField(max_length=100)),
                ('is_main', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('address', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet_profile', to='Wallet.walletaddress')),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profiles', to='Wallet.userwallet')),
            ],
        ),
        migrations.AddConstraint(
            model_name='walletprofile',
            constraint=models.UniqueConstraint(condition=Q(('is_main', True)), fields=('wallet', 'network_mode'), name='wallet_one_main_profile_per_network'),
        ),
        migrations.AddConstraint(
            model_name='walletprofile',
            constraint=models.UniqueConstraint(fields=('wallet', 'network_mode', 'name'), name='wallet_profile_name_unique_per_network'),
        ),
    ]