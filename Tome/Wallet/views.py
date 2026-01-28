from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import UserWallet
from .wallet import Wallet
from hdwallet.entropies import BIP39Entropy



# Create your views here.
@login_required
def portfolio(request):
    """Display user's wallet portfolio"""
    # Get the user's wallet if it exists using the OneToOne relationship
    user_wallet = getattr(request.user, 'user_wallet', None)
    # Create wallet on first access
    if request.method == 'POST':
        # Create wallet if it doesn't exist
        if not user_wallet:
            # Start by generating new entropy
            entropy = BIP39Entropy.generate(128)
            # Initialize and create wallet object
            wallet = Wallet(entropy)
            hdwallet = wallet.get_wallet()
            # Get the first address
            address = hdwallet.address()
            # Save the new wallet to the database
            user_wallet = UserWallet.objects.create(
                user=request.user,
                entropy=entropy,
                passphrase=''  # Empty passphrase for now
            )
    context = {
        'user_wallet': user_wallet,
    }
    return render(request, 'portfolio/index.html', context)
