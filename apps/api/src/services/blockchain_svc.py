"""
TradeFlow AI — Blockchain Anchoring Service (Phase 4, Step 4.2)

PRD §15 — Content hash anchoring on Polygon (Amoy testnet → PoS mainnet).
  1. Compute SHA-256 content hash of submission payload
  2. Build Merkle root from all document hashes
  3. Call smart contract anchor(bytes32 merkleRoot, bytes32 contentHash)
  4. Store tx_hash + IPFS CID to blockchain_records table
  5. Return PolygonScan URL

Contract: TradeFlowAudit.sol (deployed on Amoy / Polygon PoS)
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import structlog
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from ..config import settings

log = structlog.get_logger()

# ── TradeFlowAudit ABI (minimal — only anchor function) ──────────────────────
AUDIT_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
            {"internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
            {"internalType": "string",  "name": "ipfsCid",    "type": "string"},
        ],
        "name": "anchor",
        "outputs": [{"internalType": "uint256", "name": "recordId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "recordId",    "type": "uint256"},
            {"indexed": True,  "name": "contentHash", "type": "bytes32"},
            {"indexed": False, "name": "merkleRoot",  "type": "bytes32"},
            {"indexed": False, "name": "ipfsCid",     "type": "string"},
            {"indexed": False, "name": "timestamp",   "type": "uint256"},
        ],
        "name": "Anchored",
        "type": "event",
    },
]


def _sha256_bytes(data: str | bytes) -> bytes:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).digest()


def _compute_merkle_root(leaves: list[bytes]) -> bytes:
    """Simple binary Merkle tree implementation."""
    if not leaves:
        return b"\x00" * 32
    if len(leaves) == 1:
        return leaves[0]
    # Pad to even number
    if len(leaves) % 2 == 1:
        leaves.append(leaves[-1])
    parents = [
        _sha256_bytes(leaves[i] + leaves[i + 1])
        for i in range(0, len(leaves), 2)
    ]
    return _compute_merkle_root(parents)


async def _upload_to_ipfs(content: dict) -> str:
    """Upload JSON metadata to IPFS via Pinata."""
    import httpx

    if not settings.PINATA_API_KEY:
        log.warning("Pinata not configured — skipping IPFS upload")
        return ""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.pinata.cloud/pinning/pinJSONToIPFS",
            json={"pinataContent": content, "pinataMetadata": {"name": "tradeflow-audit"}},
            headers={
                "pinata_api_key": settings.PINATA_API_KEY,
                "pinata_secret_api_key": settings.PINATA_SECRET_KEY,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        cid = resp.json()["IpfsHash"]
        log.info("IPFS upload successful", cid=cid)
        return cid


class BlockchainService:
    """Anchors submission hashes to Polygon via TradeFlowAudit smart contract."""

    def __init__(self) -> None:
        self._w3: Web3 | None = None

    def _get_web3(self) -> Web3:
        if self._w3 is not None:
            return self._w3

        rpc_url = (
            settings.POLYGON_AMOY_RPC_URL
            if settings.ENVIRONMENT != "production"
            else settings.POLYGON_POS_RPC_URL
        )
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        # PoA middleware required for Polygon Amoy
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not w3.is_connected():
            raise ConnectionError(f"Cannot connect to Polygon RPC: {rpc_url}")

        self._w3 = w3
        return w3

    async def anchor(
        self,
        batch_id: str,
        payload: dict,
        document_hashes: list[str],
    ) -> dict[str, Any]:
        """
        Anchor a submission to Polygon.
        Returns: {tx_hash, block_number, content_hash, merkle_root, ipfs_cid, polygonscan_url}
        """
        if not settings.ENABLE_BLOCKCHAIN:
            log.info("Blockchain disabled — skipping anchor", batch_id=batch_id)
            return {"tx_hash": None, "block_number": None, "ipfs_cid": None}

        if not settings.CONTRACT_ADDRESS or not settings.BLOCKCHAIN_PRIVATE_KEY:
            log.warning("Blockchain not configured — skipping", batch_id=batch_id)
            return {"tx_hash": None, "block_number": None, "ipfs_cid": None}

        log.info("Anchoring to blockchain", batch_id=batch_id)

        # ── Hashes ─────────────────────────────────────────────────
        content_hash_bytes = _sha256_bytes(json.dumps(payload, sort_keys=True))
        leaf_bytes = [bytes.fromhex(h) if len(h) == 64 else _sha256_bytes(h) for h in document_hashes]
        merkle_root_bytes = _compute_merkle_root(leaf_bytes)

        # ── IPFS upload ────────────────────────────────────────────
        ipfs_cid = await _upload_to_ipfs({
            "batch_id": batch_id,
            "content_hash": content_hash_bytes.hex(),
            "merkle_root": merkle_root_bytes.hex(),
            "timestamp": int(time.time()),
        })

        # ── Contract call ──────────────────────────────────────────
        try:
            w3 = self._get_web3()
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(settings.CONTRACT_ADDRESS),
                abi=AUDIT_ABI,
            )
            account = w3.eth.account.from_key(settings.BLOCKCHAIN_PRIVATE_KEY)
            nonce = w3.eth.get_transaction_count(account.address)

            tx = contract.functions.anchor(
                merkle_root_bytes,
                content_hash_bytes,
                ipfs_cid,
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 200_000,
                "maxFeePerGas": w3.to_wei("30", "gwei"),
                "maxPriorityFeePerGas": w3.to_wei("2", "gwei"),
            })

            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            block_num = receipt["blockNumber"]
            explorer_base = (
                "https://amoy.polygonscan.com"
                if settings.ENVIRONMENT != "production"
                else "https://polygonscan.com"
            )
            polygonscan_url = f"{explorer_base}/tx/{tx_hash.hex()}"

            log.info(
                "Blockchain anchor successful",
                batch_id=batch_id,
                tx_hash=tx_hash.hex(),
                block=block_num,
            )

            return {
                "tx_hash": tx_hash.hex(),
                "block_number": block_num,
                "content_hash": content_hash_bytes.hex(),
                "merkle_root": merkle_root_bytes.hex(),
                "ipfs_cid": ipfs_cid,
                "polygonscan_url": polygonscan_url,
            }

        except Exception as exc:
            log.error("Blockchain anchor failed", error=str(exc), batch_id=batch_id)
            raise


# ── Singleton ────────────────────────────────────────────────────────────────
blockchain_service = BlockchainService()
