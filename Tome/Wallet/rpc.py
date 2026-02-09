from decouple import config
from evrmore_rpc import EvrmoreClient

RPC = EvrmoreClient(datadir=config('RPC_DATADIR', default='/tmp/evrmore'))

# Create inputs and outputs for a raw transaction
def itxo(txid, vout):
    return {"txid": txid, "vout": vout}

def utxo(address, amount):
    return {address: amount}

def create_raw_transaction(inputs, outputs):
    """
    Create a raw transaction on the Evrmore network.
    
    Args:
        inputs (list): List of dicts with 'txid' and 'vout' keys
                       Example: [{"txid": "...", "vout": 0}]
        outputs (dict): Dict mapping addresses to amounts
                        Example: {"EVR_ADDRESS": 0.5}
    
    Returns:
        str: Raw transaction hex string
    
    Raises:
        Exception: If RPC call fails
    """
    try:
        raw_tx = RPC.createrawtransaction(inputs, outputs)
        return raw_tx
    except Exception as e:
        raise Exception(f"Failed to create raw transaction: {str(e)}")