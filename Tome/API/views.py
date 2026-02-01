from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
import json

from .models import SolidityContract, ContractInteraction, ContractAsset
from .rpc import evrmore_rpc
from .authentication import api_key_required


# ============================================================
# DOCUMENTATION & INFO VIEWS
# ============================================================

def docs(request):
    """API Documentation page with DeFi-related commands"""
    # Check if user is authenticated
    user_has_api_key = False
    if request.user.is_authenticated:
        from .models import APIKey
        user_has_api_key = APIKey.objects.filter(user=request.user, is_active=True).exists()
    
    context = {
        'user_has_api_key': user_has_api_key,
    }
    return render(request, 'api/docs.html', context)


@require_http_methods(["GET"])
def api_info(request):
    """
    Get general API information and available endpoints.
    
    Returns:
        JSON response with API version, available endpoints, and blockchain info
    """
    try:
        blockchain_info = evrmore_rpc.get_blockchain_info()
        
        return JsonResponse({
            'success': True,
            'api_version': '1.0.0',
            'blockchain': {
                'chain': blockchain_info.get('chain', 'unknown'),
                'blocks': blockchain_info.get('blocks', 0),
                'difficulty': blockchain_info.get('difficulty', 0),
            },
            'endpoints': {
                'contracts': '/api/v1/contracts/',
                'assets': '/api/v1/assets/',
                'blockchain': '/api/v1/blockchain/',
                'messages': '/api/v1/messages/',
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================
# CONTRACT MANAGEMENT VIEWS
# ============================================================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def contracts_list(request):
    """
    List all contracts or deploy a new contract.
    
    GET: List all deployed contracts
    POST: Deploy a new contract (requires API key)
    """
    if request.method == 'GET':
        # List contracts
        page = request.GET.get('page', 1)
        per_page = request.GET.get('per_page', 20)
        
        contracts = SolidityContract.objects.filter(is_active=True)
        
        # Filter by deployer if specified
        deployer_id = request.GET.get('deployer')
        if deployer_id:
            contracts = contracts.filter(deployer_id=deployer_id)
        
        paginator = Paginator(contracts, per_page)
        page_obj = paginator.get_page(page)
        
        contracts_data = []
        for contract in page_obj:
            contracts_data.append({
                'id': contract.id,
                'name': contract.name,
                'contract_address': contract.contract_address,
                'deployer': contract.deployer.username,
                'deployment_tx': contract.deployment_tx,
                'deployment_block': contract.deployment_block,
                'description': contract.description,
                'ipfs_hash': contract.ipfs_hash,
                'created_at': contract.created_at.isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'contracts': contracts_data,
            'pagination': {
                'page': page_obj.number,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'total_contracts': paginator.count,
            }
        })
    
    elif request.method == 'POST':
        # Deploy endpoint moved to separate function with API key auth
        return contracts_deploy(request)


@csrf_exempt
@api_key_required
@require_http_methods(["POST"])
def contracts_deploy(request):
    """
    Deploy a new contract. Requires API key authentication.
    """
    try:
        data = json.loads(request.body)
        
        # Required fields
        name = data.get('name')
        contract_address = data.get('contract_address')  # Asset name or identifier
        
        if not name or not contract_address:
            return JsonResponse({
                'success': False,
                'error': 'Name and contract_address are required'
            }, status=400)
        
        # Create contract record
        contract = SolidityContract.objects.create(
            name=name,
            contract_address=contract_address,
            source_code=data.get('source_code', ''),
            bytecode=data.get('bytecode', ''),
            abi=data.get('abi', []),
            deployer=request.user,
            deployment_tx=data.get('deployment_tx', ''),
            deployment_block=data.get('deployment_block'),
            description=data.get('description', ''),
            ipfs_hash=data.get('ipfs_hash', ''),
        )
        
        return JsonResponse({
            'success': True,
            'contract': {
                'id': contract.id,
                'name': contract.name,
                'contract_address': contract.contract_address,
                'created_at': contract.created_at.isoformat(),
            }
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



@require_http_methods(["GET"])
def contract_detail(request, contract_id):
    """
    Get details of a specific contract.
    
    Args:
        contract_id: ID of the contract
        
    Returns:
        JSON response with contract details
    """
    try:
        contract = SolidityContract.objects.get(id=contract_id, is_active=True)
        
        # Get related assets
        assets = contract.assets.all()
        assets_data = []
        for asset in assets:
            assets_data.append({
                'asset_name': asset.asset_name,
                'quantity': str(asset.quantity),
                'units': asset.units,
                'reissuable': asset.reissuable,
                'has_ipfs': asset.has_ipfs,
                'ipfs_hash': asset.ipfs_hash,
            })
        
        # Get recent interactions
        interactions = contract.interactions.all()[:10]
        interactions_data = []
        for interaction in interactions:
            interactions_data.append({
                'function_name': interaction.function_name,
                'user': interaction.user.username,
                'tx_hash': interaction.tx_hash,
                'success': interaction.success,
                'created_at': interaction.created_at.isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'contract': {
                'id': contract.id,
                'name': contract.name,
                'contract_address': contract.contract_address,
                'source_code': contract.source_code,
                'bytecode': contract.bytecode,
                'abi': contract.abi,
                'deployer': contract.deployer.username,
                'deployment_tx': contract.deployment_tx,
                'deployment_block': contract.deployment_block,
                'description': contract.description,
                'ipfs_hash': contract.ipfs_hash,
                'created_at': contract.created_at.isoformat(),
                'updated_at': contract.updated_at.isoformat(),
                'assets': assets_data,
                'recent_interactions': interactions_data,
            }
        })
    except SolidityContract.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Contract not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@api_key_required
@require_http_methods(["POST"])
def contract_interact(request, contract_id):
    """
    Interact with a contract by calling a function. Requires API key authentication.
    
    Args:
        contract_id: ID of the contract
        
    Body:
        function_name: Name of function to call
        parameters: Function parameters (dict)
        
    Returns:
        JSON response with interaction result
    """
    
    try:
        contract = SolidityContract.objects.get(id=contract_id, is_active=True)
        data = json.loads(request.body)
        
        function_name = data.get('function_name')
        parameters = data.get('parameters', {})
        
        if not function_name:
            return JsonResponse({
                'success': False,
                'error': 'function_name is required'
            }, status=400)
        
        # Create interaction record
        interaction = ContractInteraction.objects.create(
            contract=contract,
            user=request.user,
            function_name=function_name,
            parameters=parameters,
            success=False,
        )
        
        # Here you would implement actual contract interaction
        # For MVP, we'll just record the interaction
        # In production, this would call the contract via RPC
        
        interaction.success = True
        interaction.result = {'status': 'pending', 'message': 'Contract interaction queued'}
        interaction.save()
        
        return JsonResponse({
            'success': True,
            'interaction': {
                'id': interaction.id,
                'function_name': interaction.function_name,
                'parameters': interaction.parameters,
                'created_at': interaction.created_at.isoformat(),
            }
        })
        
    except SolidityContract.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Contract not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================
# ASSET MANAGEMENT VIEWS
# ============================================================

@require_http_methods(["GET"])
def assets_list(request):
    """
    List all assets on the Evrmore blockchain.
    
    Query params:
        asset: Asset name filter (default: "*" for all)
        verbose: Include detailed info (default: false)
        count: Results per page (default: 50)
        start: Starting index (default: 0)
    """
    try:
        asset = request.GET.get('asset', '*')
        verbose = request.GET.get('verbose', 'false').lower() == 'true'
        count = int(request.GET.get('count', 50))
        start = int(request.GET.get('start', 0))
        
        assets = evrmore_rpc.list_assets(asset, verbose, count, start)
        
        return JsonResponse({
            'success': True,
            'assets': assets,
            'pagination': {
                'count': count,
                'start': start,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def asset_detail(request, asset_name):
    """
    Get detailed information about a specific asset.
    
    Args:
        asset_name: Name of the asset
        
    Returns:
        JSON response with asset data
    """
    try:
        asset_data = evrmore_rpc.get_asset_data(asset_name)
        
        return JsonResponse({
            'success': True,
            'asset': asset_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@api_key_required
@require_http_methods(["POST"])
def asset_issue(request):
    """
    Issue a new asset on the Evrmore blockchain. Requires API key authentication.
    
    Body:
        asset_name: Name of the asset
        qty: Quantity to issue
        to_address: Recipient address (optional)
        change_address: Change address (optional)
        units: Divisibility 0-8 (default: 0)
        reissuable: Can be reissued (default: true)
        has_ipfs: Has IPFS metadata (default: false)
        ipfs_hash: IPFS hash (optional)
    """
    
    try:
        data = json.loads(request.body)
        
        asset_name = data.get('asset_name')
        qty = data.get('qty')
        
        if not asset_name or not qty:
            return JsonResponse({
                'success': False,
                'error': 'asset_name and qty are required'
            }, status=400)
        
        result = evrmore_rpc.issue_asset(
            asset_name=asset_name,
            qty=qty,
            to_address=data.get('to_address', ''),
            change_address=data.get('change_address', ''),
            units=data.get('units', 0),
            reissuable=data.get('reissuable', True),
            has_ipfs=data.get('has_ipfs', False),
            ipfs_hash=data.get('ipfs_hash', ''),
        )
        
        return JsonResponse({
            'success': True,
            'result': result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@api_key_required
@require_http_methods(["POST"])
def asset_transfer(request):
    """
    Transfer an asset to another address. Requires API key authentication.
    
    Body:
        asset_name: Name of the asset
        qty: Quantity to transfer
        to_address: Recipient address
        message: Optional message
        expire_time: Expiration time (default: 0)
        change_address: Change address (optional)
        asset_change_address: Asset change address (optional)
    """
    
    try:
        data = json.loads(request.body)
        
        asset_name = data.get('asset_name')
        qty = data.get('qty')
        to_address = data.get('to_address')
        
        if not asset_name or not qty or not to_address:
            return JsonResponse({
                'success': False,
                'error': 'asset_name, qty, and to_address are required'
            }, status=400)
        
        result = evrmore_rpc.transfer_asset(
            asset_name=asset_name,
            qty=qty,
            to_address=to_address,
            message=data.get('message', ''),
            expire_time=data.get('expire_time', 0),
            change_address=data.get('change_address', ''),
            asset_change_address=data.get('asset_change_address', ''),
        )
        
        return JsonResponse({
            'success': True,
            'tx_hash': result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================
# BLOCKCHAIN QUERY VIEWS
# ============================================================

@require_http_methods(["GET"])
def blockchain_info(request):
    """Get general blockchain information"""
    try:
        info = evrmore_rpc.get_blockchain_info()
        return JsonResponse({
            'success': True,
            'blockchain': info
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def block_info(request, block_hash):
    """
    Get information about a specific block.
    
    Args:
        block_hash: Hash of the block
        
    Query params:
        verbosity: Level of detail (default: 1)
    """
    try:
        verbosity = int(request.GET.get('verbosity', 1))
        block = evrmore_rpc.get_block(block_hash, verbosity)
        
        return JsonResponse({
            'success': True,
            'block': block
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def address_balance(request, address):
    """
    Get balance for a specific address.
    
    Args:
        address: Evrmore address
    """
    try:
        balance = evrmore_rpc.get_address_balance(address)
        
        return JsonResponse({
            'success': True,
            'address': address,
            'balance': balance
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def address_transactions(request, address):
    """
    Get transaction IDs for a specific address.
    
    Args:
        address: Evrmore address
        
    Query params:
        start: Start block height (optional)
        end: End block height (optional)
    """
    try:
        start = request.GET.get('start')
        end = request.GET.get('end')
        
        if start:
            start = int(start)
        if end:
            end = int(end)
        
        txids = evrmore_rpc.get_address_txids([address], start, end)
        
        return JsonResponse({
            'success': True,
            'address': address,
            'transactions': txids
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def address_utxos(request, address):
    """
    Get unspent transaction outputs for an address.
    
    Args:
        address: Evrmore address
    """
    try:
        utxos = evrmore_rpc.get_address_utxos([address])
        
        return JsonResponse({
            'success': True,
            'address': address,
            'utxos': utxos
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================
# MESSAGING VIEWS
# ============================================================

@csrf_exempt
@api_key_required
@require_http_methods(["POST"])
def send_message(request):
    """
    Send a message to a channel. Requires API key authentication.
    
    Body:
        channel_name: Name of the channel
        ipfs_hash: IPFS hash of the message
        expire_time: Expiration time (default: 0)
    """
    
    try:
        data = json.loads(request.body)
        
        channel_name = data.get('channel_name')
        ipfs_hash = data.get('ipfs_hash')
        
        if not channel_name or not ipfs_hash:
            return JsonResponse({
                'success': False,
                'error': 'channel_name and ipfs_hash are required'
            }, status=400)
        
        result = evrmore_rpc.send_message(
            channel_name=channel_name,
            ipfs_hash=ipfs_hash,
            expire_time=data.get('expire_time', 0),
        )
        
        return JsonResponse({
            'success': True,
            'result': result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def view_messages(request):
    """View all messages"""
    try:
        messages = evrmore_rpc.view_all_messages()
        
        return JsonResponse({
            'success': True,
            'messages': messages
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def view_channels(request):
    """View all message channels"""
    try:
        channels = evrmore_rpc.view_all_message_channels()
        
        return JsonResponse({
            'success': True,
            'channels': channels
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

