from django.db import migrations, models


def remap_legacy_asset_types(apps, schema_editor):
    TrackedAsset = apps.get_model('Wallet', 'TrackedAsset')

    for asset in TrackedAsset.objects.filter(asset_type__in=['nft', 'vault']).only('id', 'symbol', 'asset_type'):
        symbol = str(asset.symbol or '').strip()

        if symbol.endswith('!'):
            mapped = 'administrator'
        elif symbol.startswith('$'):
            mapped = 'restricted'
        elif symbol.startswith('#') and '/' in symbol:
            mapped = 'sub_qualifier'
        elif symbol.startswith('#'):
            mapped = 'qualifier'
        elif '~' in symbol:
            mapped = 'messaging_channel'
        elif '#' in symbol:
            mapped = 'unique'
        elif '/' in symbol:
            mapped = 'sub'
        else:
            mapped = 'main'

        asset.asset_type = mapped
        asset.save(update_fields=['asset_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('Wallet', '0013_trackedasset_network_mode'),
    ]

    operations = [
        migrations.RunPython(remap_legacy_asset_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='trackedasset',
            name='asset_type',
            field=models.CharField(
                choices=[
                    ('main', 'Main'),
                    ('sub', 'Sub'),
                    ('unique', 'Unique'),
                    ('messaging_channel', 'Messaging Channel'),
                    ('qualifier', 'Qualifier'),
                    ('sub_qualifier', 'Sub Qualifier'),
                    ('restricted', 'Restricted'),
                    ('administrator', 'Administrator'),
                ],
                default='main',
                max_length=32,
            ),
        ),
    ]
