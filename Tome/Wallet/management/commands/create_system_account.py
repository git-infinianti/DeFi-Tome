from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Wallet.models import UserWallet, WalletAddress
from Wallet.wallet import Wallet
from hdwallet.entropies import BIP39Entropy
import os


class Command(BaseCommand):
    help = 'Create a system account with a wallet'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='system',
            help='Username for the system account (default: system)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='system@defihome.com',
            help='Email for the system account (default: system@defihome.com)'
        )
        parser.add_argument(
            '--wallet-name',
            type=str,
            default='System Wallet',
            help='Name for the wallet (default: System Wallet)'
        )
        parser.add_argument(
            '--passphrase',
            type=str,
            default='',
            help='Passphrase for the wallet (default: empty string)'
        )
        parser.add_argument(
            '--addresses',
            type=int,
            default=10,
            help='Number of addresses to generate (default: 10)'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        wallet_name = options['wallet_name']
        passphrase = options['passphrase']
        num_addresses = options['addresses']

        self.stdout.write(f'Creating system account: {username}...')

        # Create or get the user
        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': False,
            }
        )

        if user_created:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created user: {username}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'User already exists: {username}')
            )

        # Create or get the wallet
        if hasattr(user, 'user_wallet'):
            self.stdout.write(
                self.style.WARNING(f'Wallet already exists for user: {username}')
            )
            user_wallet = user.user_wallet
        else:
            # Generate entropy for the wallet
            entropy = BIP39Entropy(os.urandom(16)).entropy()
            
            # Create the wallet
            user_wallet = UserWallet.objects.create(
                user=user,
                name=wallet_name,
                entropy=entropy,
                passphrase=passphrase,
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created wallet: {wallet_name}')
            )
            self.stdout.write(
                self.style.WARNING(f'Entropy: {entropy}')
            )

        # Generate addresses
        wallet = Wallet(user_wallet.entropy, user_wallet.passphrase)
        addresses_list = list(wallet.get_addresses(num_addresses))[0]

        for idx, address_str in enumerate(addresses_list):
            wallet_obj = wallet.get_wallet().from_derivation(
                __import__('hdwallet.derivations', fromlist=['BIP44Derivation']).BIP44Derivation(
                    __import__('hdwallet', fromlist=['cryptocurrencies']).cryptocurrencies.Evrmore.COIN_TYPE,
                    user_wallet.id or 0,
                    __import__('hdwallet.derivations', fromlist=['CHANGES']).CHANGES.EXTERNAL_CHAIN,
                    idx
                )
            )
            
            WalletAddress.objects.get_or_create(
                wallet=user_wallet,
                index=idx,
                defaults={
                    'address': address_str,
                    'wif': wallet_obj.private_key(),
                    'account': user_wallet.id or 0,
                    'is_change': False,
                }
            )

        self.stdout.write(
            self.style.SUCCESS(f'✓ Generated {num_addresses} wallet addresses')
        )

        self.stdout.write(
            self.style.SUCCESS('\n✓ System account setup completed successfully!')
        )
        self.stdout.write(f'  Username: {username}')
        self.stdout.write(f'  Email: {email}')
        self.stdout.write(f'  Wallet: {wallet_name}')
        self.stdout.write(f'  Addresses: {num_addresses}')
