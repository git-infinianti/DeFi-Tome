from django.shortcuts import render
from .rpc import RPC

def explorer(request):
    """Display 4 blocks per page from the blockchain with pagination"""
    blocks = []
    error_message = None
    blocks_per_page = 4
    
    # Get the page number from query parameter (default to 1)
    try:
        page = int(request.GET.get('page', 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1
    
    try:
        # Get the current block count (height)
        block_count = RPC.execute_command_sync('getblockcount')
        
        # Calculate starting block for this page
        # Page 1 shows blocks: block_count, block_count-1, block_count-2, block_count-3
        # Page 2 shows blocks: block_count-4, block_count-5, block_count-6, block_count-7
        start_offset = (page - 1) * blocks_per_page
        
        # Get 4 blocks for the current page
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
            })
        
        # Calculate if there are more blocks to show
        has_next = (block_count - start_offset - blocks_per_page) >= 0
        has_prev = page > 1
        
    except Exception as e:
        error_message = f"Error connecting to blockchain: {str(e)}"
        has_next = False
        has_prev = False
    
    context = {
        'blocks': blocks,
        'error_message': error_message,
        'page': page,
        'has_next': has_next,
        'has_prev': has_prev,
    }
    return render(request, 'explorer/index.html', context)
