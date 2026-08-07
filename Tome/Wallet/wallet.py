from hdwallet import HDWallet, cryptocurrencies
from hdwallet.entropies import BIP39Entropy
from hdwallet.mnemonics import BIP39Mnemonic, BIP39_MNEMONIC_LANGUAGES as LANGUAGES
from hdwallet.derivations import BIP44Derivation, CHANGES


class Wallet:
    def __init__(self, entropy, passphrase='', language=LANGUAGES.ENGLISH, network_mode='mainnet'):
        self.account = 0
        self.entropy = entropy
        self.language = language
        self.passphrase = passphrase
        self.network_mode = 'testnet' if str(network_mode).lower() == 'testnet' else 'mainnet'

    def get_mnemonic(self):
        return BIP39Mnemonic.from_entropy(BIP39Entropy(self.entropy), self.language)

    def get_wallet(self):
        return HDWallet(
            cryptocurrencies.Evrmore,
            passphrase=self.passphrase,
            network=self.network_mode,
        ).from_mnemonic(
            BIP39Mnemonic(self.get_mnemonic())
        )

    def _derive_wallet(self, index=0, is_change=False):
        change_chain = CHANGES.INTERNAL_CHAIN if is_change else CHANGES.EXTERNAL_CHAIN
        return self.get_wallet().from_derivation(
            BIP44Derivation(
                cryptocurrencies.Evrmore.COIN_TYPE,
                self.account,
                change_chain,
                index,
            )
        )

    def get_address(self, index=0):
        return self._derive_wallet(index=index, is_change=False).address()

    def get_addresses(self, count=10):
        yield [self.get_address(index=i) for i in range(count)]

    def get_private_key(self, index=0):
        return self._derive_wallet(index=index, is_change=False).private_key()

    def get_wif(self, index=0):
        return self._derive_wallet(index=index, is_change=False).wif()

    def get_change_address(self, index=0):
        return self._derive_wallet(index=index, is_change=True).address()

    def get_change_wif(self, index=0):
        return self._derive_wallet(index=index, is_change=True).wif()

    def get_wif_for_address(self, address, max_scan=200):
        target = str(address or '').strip()
        if not target:
            raise ValueError('Address is required.')

        for is_change in (False, True):
            for index in range(int(max_scan)):
                derived = self._derive_wallet(index=index, is_change=is_change)
                if derived.address() == target:
                    return derived.wif()

        raise ValueError(f'Address {target} not found in first {max_scan} derived addresses.')