from hdwallet import HDWallet, cryptocurrencies
from hdwallet.entropies import BIP39Entropy
from hdwallet.mnemonics import BIP39Mnemonic, BIP39_MNEMONIC_LANGUAGES as LANGUAGES
from hdwallet.derivations import BIP44Derivation, CHANGES


class Wallet:
    def __init__(self, entropy, passphrase='', language=LANGUAGES.ENGLISH):
        self.account = 0
        self.entropy = entropy
        self.language = language
        self.passphrase = passphrase
        
    def get_mnemonic(self): return BIP39Mnemonic.from_entropy(BIP39Entropy(self.entropy), self.language)
    def get_wallet(self): return HDWallet(cryptocurrencies.Evrmore, passphrase=self.passphrase).from_mnemonic(BIP39Mnemonic(self.get_mnemonic()))
    def get_addresses(self, count=10): yield [self.get_wallet().from_derivation(BIP44Derivation(cryptocurrencies.Evrmore.COIN_TYPE, self.account, CHANGES.EXTERNAL_CHAIN, i)).address() for i in range(count)]
    