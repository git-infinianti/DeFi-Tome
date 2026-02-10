from django.shortcuts import render, redirect
from django.http import Http404
from .rpc import RPC
import datetime

def explorer(request):
    """Display recent blocks with network statistics and search"""
    blocks = []
    error_message = None
    network_stats = {}
    recent_blocks = []
    blocks_per_page = 10
    
    # Handle search
    search_query = request.GET.get('search', '').strip()
    if search_query:
        return handle_search(request, search_query)
    
    # Get the page number from query parameter (default to 1)
    try:
        page = int(request.GET.get('page', 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1
    
    try:
        # Get network statistics
        block_count = RPC.execute_command_sync('getblockcount')
        blockchain_info = RPC.execute_command_sync('getblockchaininfo')
        mining_info = RPC.execute_command_sync('getmininginfo')
        
        network_stats = {
            'block_height': block_count,
            'difficulty': mining_info.get('difficulty', 0),
            'hashrate': mining_info.get('networkhashps', 0),
            'chain': blockchain_info.get('chain', 'unknown'),
            'blocks': blockchain_info.get('blocks', 0),
            'bestblockhash': blockchain_info.get('bestblockhash', ''),
        }
        
        # Calculate maximum valid page number
        max_page = (block_count // blocks_per_page) + 1
        if page > max_page:
            page = max_page
        
        # Calculate starting block for this page
        start_offset = (page - 1) * blocks_per_page
        
        # Get blocks for the current page
        for i in range(blocks_per_page):
            block_height = block_count - start_offset - i
            if block_height < 0:
                break
            
            # Get block hash for this height
            block_hash = RPC.execute_command_sync('getblockhash', block_height)
            
            # Get block details
            block = RPC.execute_command_sync('getblock', block_hash)
            
            blocks.append({
                'height': block_height,
                'hash': block_hash,
                'time': block.get('time'),
                'tx_count': len(block.get('tx', [])),
                'size': block.get('size'),
                'difficulty': block.get('difficulty'),
                'confirmations': block.get('confirmations', 0),
            })
        
        # Calculate if there are more blocks to show
        has_next = (block_count - start_offset - blocks_per_page) >= 0
        has_prev = page > 1
        
    except Exception as e:
        error_message = f"Error connecting to blockchain: {str(e)}"
        has_next = False
        has_prev = False
        block_count = 0
    
    context = {
        'blocks': blocks,
        'error_message': error_message,
        'page': page,
        'has_next': has_next,
        'has_prev': has_prev,
        'network_stats': network_stats,
        'total_blocks': block_count,
    }
    return render(request, 'explorer/index.html', context)


def handle_search(request, query):
    """Handle search for blocks, transactions, or addresses"""
    try:
        # Try as block height (integer)
        if query.isdigit():
            block_height = int(query)
            return redirect('block_detail', height=block_height)
        
        # Try as block hash or transaction hash (64 character hex)
        if len(query) == 64 and all(c in '0123456789abcdefABCDEF' for c in query):
            # Try block hash first
            try:
                block = RPC.execute_command_sync('getblock', query)
                return redirect('block_detail', height=block.get('height'))
            except:
                pass
            
            # Try transaction hash
            try:
                tx = RPC.execute_command_sync('getrawtransaction', query, True)
                return redirect('transaction_detail', txid=query)
            except:
                pass
        
        # If nothing found, return to explorer with error
        return redirect('explorer')
        
    except Exception as e:
        return redirect('explorer')


def block_detail(request, height):
    """Display detailed information about a specific block"""
    error_message = None
    block_data = None
    transactions = []
    
    try:
        # Get block hash for this height
        block_hash = RPC.execute_command_sync('getblockhash', int(height))
        
        # Get block details with full transaction data
        block = RPC.execute_command_sync('getblock', block_hash, 2)
        
        block_data = {
            'height': block.get('height'),
            'hash': block.get('hash'),
            'confirmations': block.get('confirmations'),
            'size': block.get('size'),
            'version': block.get('version'),
            'merkleroot': block.get('merkleroot'),
            'time': block.get('time'),
            'nonce': block.get('nonce'),
            'bits': block.get('bits'),
            'difficulty': block.get('difficulty'),
            'previousblockhash': block.get('previousblockhash'),
            'nextblockhash': block.get('nextblockhash'),
            'tx_count': len(block.get('tx', [])),
        }
        
        # Get transaction details
        for tx in block.get('tx', [])[:20]:  # Limit to first 20 transactions
            if isinstance(tx, dict):
                transactions.append({
                    'txid': tx.get('txid'),
                    'size': tx.get('size'),
                    'vout_count': len(tx.get('vout', [])),
                    'vin_count': len(tx.get('vin', [])),
                })
            else:
                # If tx is just a string (txid), fetch details
                transactions.append({
                    'txid': tx,
                })
        
    except Exception as e:
        error_message = f"Error fetching block details: {str(e)}"
    
    context = {
        'block': block_data,
        'transactions': transactions,
        'error_message': error_message,
    }
    return render(request, 'explorer/block_detail.html', context)


def transaction_detail(request, txid):
    """Display detailed information about a specific transaction"""
    error_message = None
    tx_data = None
    
    try:
        # Get transaction details
        tx = RPC.execute_command_sync('getrawtransaction', txid, True)
        
        tx_data = {
            'txid': tx.get('txid'),
            'hash': tx.get('hash'),
            'size': tx.get('size'),
            'version': tx.get('version'),
            'locktime': tx.get('locktime'),
            'blockhash': tx.get('blockhash'),
            'confirmations': tx.get('confirmations', 0),
            'time': tx.get('time'),
            'blocktime': tx.get('blocktime'),
            'vin': tx.get('vin', []),
            'vout': tx.get('vout', []),
        }
        
        # Get block height if transaction is in a block
        if tx_data['blockhash']:
            try:
                block = RPC.execute_command_sync('getblock', tx_data['blockhash'])
                tx_data['block_height'] = block.get('height')
            except:
                tx_data['block_height'] = None
        
    except Exception as e:
        error_message = f"Error fetching transaction details: {str(e)}"
    
    context = {
        'transaction': tx_data,
        'error_message': error_message,
    }
    return render(request, 'explorer/transaction_detail.html', context)
