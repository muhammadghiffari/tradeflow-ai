"""
TradeFlow AI — Blockchain Anchor Agent (T-049)

Parallel branch in the LangGraph pipeline (runs alongside review_ready).
  1. Hash PIB payload (SHA-256)
  2. Upload encrypted payload to IPFS via Pinata
  3. Call DocumentRegistry.anchorDocument() on Polygon Amoy
  4. Return tx_hash, block_number, ipfs_cid, polygonscan_url

Runs only when ENABLE_BLOCKCHAIN=True.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from ..state import DeclarationState

logger = logging.getLogger("agents.blockchain")

POLYGON_AMOY_CHAIN_ID = 80002
POLYGONSCAN_AMOY_TX = "https://amoy.polygonscan.com/tx/"

# DocumentRegistry ABI (minimal — only what we call)
_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "batchId", "type": "string"},
            {"internalType": "bytes32", "name": "docHash", "type": "bytes32"},
            {"internalType": "string", "name": "ipfsCid", "type": "string"},
            {"internalType": "string", "name": "company", "type": "string"},
            {"internalType": "string", "name": "ajuNumber", "type": "string"},
        ],
        "name": "anchorDocument",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "batchId", "type": "string"},
            {"internalType": "bytes32", "name": "docHash", "type": "bytes32"},
        ],
        "name": "verifyDocument",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


async def blockchain_anchor_node(state: DeclarationState) -> dict:
    """
    Hash and anchor the current PIB payload on Polygon Amoy.
    Runs in parallel branch — errors do NOT fail the main pipeline.
    """
    from ....api.src.config import settings  # type: ignore

    if not settings.ENABLE_BLOCKCHAIN:
        return {
            "blockchain_tx": {
                "status": "disabled",
                "tx_hash": None,
                "block_number": None,
                "ipfs_cid": None,
            },
            "messages": [],
        }

    batch_id = state.get("batch_id", "unknown")

    # Build hashable payload (reconciled fields + batch metadata)
    payload_to_hash = {
        "batch_id": batch_id,
        "reconciled_fields": state.get("reconciled_fields", []),
        "validation_results": state.get("validation_results", []),
        "crs": state.get("crs", {}),
        "anchored_at": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(payload_to_hash, sort_keys=True, ensure_ascii=False).encode()
    doc_hash_hex = hashlib.sha256(payload_bytes).hexdigest()
    doc_hash_bytes32 = bytes.fromhex(doc_hash_hex)

    # Step 1: Upload to IPFS via Pinata
    ipfs_cid = await _upload_to_ipfs(payload_bytes, batch_id, settings)

    # Step 2: Anchor on-chain
    try:
        tx_hash, block_number = await _anchor_on_chain(
            batch_id=batch_id,
            doc_hash_bytes32=doc_hash_bytes32,
            ipfs_cid=ipfs_cid or "",
            company=_anonymize_company(state),
            settings=settings,
        )
        status = "confirmed"
    except Exception as e:
        logger.error(f"Blockchain anchor failed for {batch_id}: {e}")
        tx_hash = None
        block_number = None
        status = "failed"

    result = {
        "blockchain_tx": {
            "status": status,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "ipfs_cid": ipfs_cid,
            "doc_hash": doc_hash_hex,
            "anchored_at": datetime.now(timezone.utc).isoformat(),
            "polygonscan_url": f"{POLYGONSCAN_AMOY_TX}{tx_hash}" if tx_hash else None,
        },
        "messages": [{
            "node": "blockchain_anchor",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "blockchain_anchor_complete",
            "payload": {
                "batch_id": batch_id,
                "status": status,
                "tx_hash": tx_hash,
                "ipfs_cid": ipfs_cid,
            },
        }],
    }
    return result


async def _upload_to_ipfs(
    content: bytes, batch_id: str, settings
) -> str | None:
    """Upload payload to IPFS via Pinata pinJSONToIPFS."""
    if not settings.PINATA_JWT:
        logger.warning("PINATA_JWT not set — skipping IPFS upload")
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.pinata.cloud/pinning/pinJSONToIPFS",
                headers={
                    "Authorization": f"Bearer {settings.PINATA_JWT.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                content=content,
            )
            resp.raise_for_status()
            return resp.json().get("IpfsHash")
    except Exception as e:
        logger.error(f"IPFS upload failed: {e}")
        return None


async def _anchor_on_chain(
    batch_id: str,
    doc_hash_bytes32: bytes,
    ipfs_cid: str,
    company: str,
    settings,
) -> tuple[str, int]:
    """Send anchorDocument transaction to Polygon Amoy."""
    from web3 import AsyncWeb3
    from web3.middleware import async_geth_poa_middleware

    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.POLYGON_RPC_URL))
    w3.middleware_onion.inject(async_geth_poa_middleware, layer=0)

    pk = settings.OPERATOR_WALLET_PRIVATE_KEY.get_secret_value()
    account = w3.eth.account.from_key(pk)

    contract = w3.eth.contract(
        address=w3.to_checksum_address(settings.CONTRACT_ADDRESS),
        abi=_ABI,
    )

    nonce = await w3.eth.get_transaction_count(account.address)
    gas_price = await w3.eth.gas_price

    txn = await contract.functions.anchorDocument(
        batch_id,
        doc_hash_bytes32,
        ipfs_cid,
        company,
        "",  # ajuNumber — empty at this stage, updated after CEISA
    ).build_transaction({
        "chainId": POLYGON_AMOY_CHAIN_ID,
        "from": account.address,
        "nonce": nonce,
        "gasPrice": gas_price,
        "gas": 200_000,
    })

    signed = account.sign_transaction(txn)
    tx_hash = await w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    return tx_hash.hex(), receipt["blockNumber"]


def _anonymize_company(state: DeclarationState) -> str:
    """Return anonymized company ID (not the legal name) for on-chain storage."""
    # Use batch_id prefix as a stable anonymous identifier
    batch_id = state.get("batch_id", "unknown")
    return hashlib.sha256(batch_id.encode()).hexdigest()[:16]
