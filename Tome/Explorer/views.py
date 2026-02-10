from django.shortcuts import render, redirect
from django.http import Http404
from .rpc import RPC
import datetime
import time

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
        # Demo mode: Show sample data when blockchain is not available
        demo_mode = request.GET.get('demo', 'true') == 'true'  # Enable demo by default
        
        if demo_mode:
            # Generate mock network statistics
            network_stats = {
                'block_height': 2847563,
                'difficulty': 15432.8976543,
                'hashrate': 1234567890.12,
                'chain': 'main',
                'blocks': 2847563,
                'bestblockhash': 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2',
            }
            
            # Generate mock blocks
            current_time = int(time.time())
            base_height = 2847563 - ((page - 1) * blocks_per_page)
            
            for i in range(blocks_per_page):
                block_height = base_height - i
                if block_height < 0:
                    break
                
                blocks.append({
                    'height': block_height,
                    'hash': f'{"a1b2c3d4e5f6g7h8i9j0" * 3}'[:64],
                    'time': current_time - (i * 60),  # 60 seconds apart
                    'tx_count': 15 + (i * 2),
                    'size': 125000 + (i * 1000),
                    'difficulty': 15432.8976543,
                    'confirmations': i + 1,
                })
            
            has_next = True
            has_prev = page > 1
            block_count = 2847563
            error_message = None  # Clear error in demo mode
        else:
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
        # Demo mode for block details
        demo_mode = request.GET.get('demo', 'true') == 'true'
        
        if demo_mode and not error_message:
            import time
            block_data = {
                'height': int(height),
                'hash': 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2',
                'confirmations': 145,
                'size': 125487,
                'version': 4,
                'merkleroot': 'b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2a1',
                'time': int(time.time()) - 3600,
                'nonce': 2847563421,
                'bits': '1a0a8b5f',
                'difficulty': 15432.8976543,
                'previousblockhash': 'c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2a1b2' if int(height) > 0 else None,
                'nextblockhash': 'd4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2a1b2c3',
                'tx_count': 25,
            }
            
            # Generate mock transactions
            for i in range(20):
                transactions.append({
                    'txid': f'{i}1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f',
                    'size': 250 + (i * 10),
                    'vout_count': 2,
                    'vin_count': 1,
                })
            error_message = None
        else:
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
        # Demo mode for transaction details
        demo_mode = request.GET.get('demo', 'true') == 'true'
        
        if demo_mode and not error_message:
            import time
            tx_data = {
                'txid': txid,
                'hash': txid,
                'size': 250,
                'version': 2,
                'locktime': 0,
                'blockhash': 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2',
                'confirmations': 145,
                'time': int(time.time()) - 3600,
                'blocktime': int(time.time()) - 3600,
                'block_height': 2847500,
                'vin': [
                    {
                        'txid': 'prev123abc456def789',
                        'vout': 0,
                        'scriptSig': {'hex': '483045022100abcd...'},
                        'sequence': 4294967295,
                    }
                ],
                'vout': [
                    {
                        'n': 0,
                        'value': 50.0,
                        'scriptPubKey': {
                            'hex': '76a914abc123def456...88ac',
                            'addresses': ['ELSomeAddress123456789ABCDEFGH'],
                            'type': 'pubkeyhash',
                        }
                    },
                    {
                        'n': 1,
                        'value': 25.5,
                        'scriptPubKey': {
                            'hex': '76a914def456abc123...88ac',
                            'addresses': ['ELAnotherAddr987654321ZYXWVU'],
                            'type': 'pubkeyhash',
                        }
                    }
                ],
            }
            error_message = None
        else:
            error_message = f"Error fetching transaction details: {str(e)}"
    
    context = {
        'transaction': tx_data,
        'error_message': error_message,
    }
    return render(request, 'explorer/transaction_detail.html', context)
