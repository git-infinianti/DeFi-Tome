from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal
from .models import TestnetConfig, LiquidityPool, LiquidityPosition, SwapTransaction

# Create your views here.

def testnet_home(request):
    """Display testnet home page with overview"""
    testnet_config = TestnetConfig.objects.first()
    if not testnet_config:
        testnet_config = TestnetConfig.objects.create()
    
    pools = LiquidityPool.objects.all()
    
    context = {
        'testnet_config': testnet_config,
        'pools': pools,
    }
    return render(request, 'testnet/home.html', context)

@login_required
def swap(request):
    """Handle token swaps on testnet"""
    pools = LiquidityPool.objects.all()
    
    if request.method == 'POST':
        pool_id = request.POST.get('pool_id')
        from_token = request.POST.get('from_token', '').strip()
        to_token = request.POST.get('to_token', '').strip()
        amount = request.POST.get('amount', '').strip()
        
        # Validate inputs
        if not pool_id or not from_token or not to_token or not amount:
            messages.error(request, 'All fields are required.')
            return redirect('swap')
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, Exception):
            messages.error(request, 'Invalid amount specified.')
            return redirect('swap')
        
        try:
            pool = LiquidityPool.objects.get(id=pool_id)
            
            # Calculate swap amount using constant product formula (x * y = k)
            if from_token == pool.token_a_symbol:
                reserve_in = pool.token_a_reserve
                reserve_out = pool.token_b_reserve
            elif from_token == pool.token_b_symbol:
                reserve_in = pool.token_b_reserve
                reserve_out = pool.token_a_reserve
            else:
                messages.error(request, 'Invalid token for this pool.')
                return redirect('swap')
            
            # Calculate output amount with fee
            fee = amount * pool.fee_percentage / Decimal('100')
            amount_with_fee = amount - fee
            
            # Constant product formula: (x + Δx) * (y - Δy) = x * y
            # Δy = (y * Δx) / (x + Δx)
            output_amount = (reserve_out * amount_with_fee) / (reserve_in + amount_with_fee)
            
            # Update pool reserves
            if from_token == pool.token_a_symbol:
                pool.token_a_reserve += amount
                pool.token_b_reserve -= output_amount
            else:
                pool.token_b_reserve += amount
                pool.token_a_reserve -= output_amount
            
            pool.save()
            
            # Record transaction
            SwapTransaction.objects.create(
                user=request.user,
                pool=pool,
                from_token=from_token,
                to_token=to_token,
                from_amount=amount,
                to_amount=output_amount,
                fee_amount=fee,
                tx_hash=f'testnet-{pool.id}-{SwapTransaction.objects.count() + 1}'
            )
            
            messages.success(request, f'Successfully swapped {amount} {from_token} for {output_amount:.8f} {to_token}!')
            
        except LiquidityPool.DoesNotExist:
            messages.error(request, 'Pool not found.')
        except Exception as e:
            messages.error(request, f'Error executing swap: {str(e)}')
        
        return redirect('swap')
    
    context = {
        'pools': pools,
    }
    return render(request, 'testnet/swap.html', context)

@login_required
def liquidity(request):
    """Manage liquidity pools on testnet"""
    pools = LiquidityPool.objects.all()
    user_positions = LiquidityPosition.objects.filter(user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        pool_id = request.POST.get('pool_id')
        
        if action == 'add':
            token_a_amount = request.POST.get('token_a_amount', '').strip()
            token_b_amount = request.POST.get('token_b_amount', '').strip()
            
            # Validate inputs
            if not pool_id or not token_a_amount or not token_b_amount:
                messages.error(request, 'All fields are required.')
                return redirect('liquidity')
            
            try:
                token_a_amount = Decimal(token_a_amount)
                token_b_amount = Decimal(token_b_amount)
                
                if token_a_amount <= 0 or token_b_amount <= 0:
                    raise ValueError
                
                pool = LiquidityPool.objects.get(id=pool_id)
                
                # Calculate liquidity tokens to mint
                if pool.total_liquidity_tokens == 0:
                    # First liquidity provider
                    liquidity_tokens = (token_a_amount * token_b_amount) ** Decimal('0.5')
                else:
                    # Proportional to existing liquidity
                    liquidity_tokens = min(
                        (token_a_amount * pool.total_liquidity_tokens) / pool.token_a_reserve,
                        (token_b_amount * pool.total_liquidity_tokens) / pool.token_b_reserve
                    )
                
                # Update pool reserves
                pool.token_a_reserve += token_a_amount
                pool.token_b_reserve += token_b_amount
                pool.total_liquidity_tokens += liquidity_tokens
                pool.save()
                
                # Update or create user position
                position, created = LiquidityPosition.objects.get_or_create(
                    user=request.user,
                    pool=pool,
                    defaults={'liquidity_tokens': liquidity_tokens}
                )
                
                if not created:
                    position.liquidity_tokens += liquidity_tokens
                    position.save()
                
                messages.success(request, f'Successfully added liquidity! Received {liquidity_tokens:.8f} liquidity tokens.')
                
            except LiquidityPool.DoesNotExist:
                messages.error(request, 'Pool not found.')
            except Exception as e:
                messages.error(request, f'Error adding liquidity: {str(e)}')
        
        elif action == 'remove':
            liquidity_tokens = request.POST.get('liquidity_tokens', '').strip()
            
            if not pool_id or not liquidity_tokens:
                messages.error(request, 'All fields are required.')
                return redirect('liquidity')
            
            try:
                liquidity_tokens = Decimal(liquidity_tokens)
                
                if liquidity_tokens <= 0:
                    raise ValueError
                
                pool = LiquidityPool.objects.get(id=pool_id)
                position = LiquidityPosition.objects.get(user=request.user, pool=pool)
                
                if liquidity_tokens > position.liquidity_tokens:
                    messages.error(request, 'Insufficient liquidity tokens.')
                    return redirect('liquidity')
                
                # Calculate tokens to return
                share = liquidity_tokens / pool.total_liquidity_tokens
                token_a_amount = pool.token_a_reserve * share
                token_b_amount = pool.token_b_reserve * share
                
                # Update pool reserves
                pool.token_a_reserve -= token_a_amount
                pool.token_b_reserve -= token_b_amount
                pool.total_liquidity_tokens -= liquidity_tokens
                pool.save()
                
                # Update user position
                position.liquidity_tokens -= liquidity_tokens
                if position.liquidity_tokens == 0:
                    position.delete()
                else:
                    position.save()
                
                messages.success(request, f'Successfully removed liquidity! Received {token_a_amount:.8f} {pool.token_a_symbol} and {token_b_amount:.8f} {pool.token_b_symbol}.')
                
            except LiquidityPool.DoesNotExist:
                messages.error(request, 'Pool not found.')
            except LiquidityPosition.DoesNotExist:
                messages.error(request, 'No liquidity position found.')
            except Exception as e:
                messages.error(request, f'Error removing liquidity: {str(e)}')
        
        return redirect('liquidity')
    
    context = {
        'pools': pools,
        'user_positions': user_positions,
    }
    return render(request, 'testnet/liquidity.html', context)

@login_required
def transactions(request):
    """Display user's swap transaction history"""
    user_swaps = SwapTransaction.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'transactions': user_swaps,
    }
    return render(request, 'testnet/transactions.html', context)
