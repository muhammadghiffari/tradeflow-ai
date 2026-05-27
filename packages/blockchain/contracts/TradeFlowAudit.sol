// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title TradeFlowAudit
 * @notice Immutable audit log for customs declaration content hashes.
 *         Deployed on Polygon Amoy (testnet) and Polygon PoS (mainnet).
 *
 * PRD §15 — Each accepted CEISA submission is anchored via:
 *   anchor(merkleRoot, contentHash, ipfsCid)
 *
 * The Merkle root covers all document hashes (B/L, Invoice, Packing List).
 * Content hash is SHA-256 of the encrypted CEISA payload.
 * IPFS CID points to the full audit metadata JSON.
 */
contract TradeFlowAudit {
    struct Record {
        bytes32 merkleRoot;
        bytes32 contentHash;
        string  ipfsCid;
        uint256 timestamp;
        address submitter;
    }

    // ── State ─────────────────────────────────────────────────────────────────
    uint256 public recordCount;
    mapping(uint256 => Record) public records;
    mapping(bytes32 => uint256) public hashToRecordId;  // contentHash → recordId

    // ── Events ────────────────────────────────────────────────────────────────
    event Anchored(
        uint256 indexed recordId,
        bytes32 indexed contentHash,
        bytes32          merkleRoot,
        string           ipfsCid,
        uint256          timestamp
    );

    // ── Access control ────────────────────────────────────────────────────────
    address public owner;
    mapping(address => bool) public authorizedSubmitters;

    modifier onlyOwner() {
        require(msg.sender == owner, "TradeFlowAudit: not owner");
        _;
    }

    modifier onlyAuthorized() {
        require(
            authorizedSubmitters[msg.sender] || msg.sender == owner,
            "TradeFlowAudit: not authorized"
        );
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedSubmitters[msg.sender] = true;
    }

    // ── Core function ─────────────────────────────────────────────────────────

    /**
     * @notice Anchor a submission's content hash and Merkle root.
     * @param merkleRoot  SHA-256 Merkle root of document hashes.
     * @param contentHash SHA-256 of the encrypted CEISA payload.
     * @param ipfsCid     IPFS CID of the full audit metadata.
     * @return recordId   The new immutable record ID.
     */
    function anchor(
        bytes32 merkleRoot,
        bytes32 contentHash,
        string calldata ipfsCid
    ) external onlyAuthorized returns (uint256 recordId) {
        require(contentHash != bytes32(0), "TradeFlowAudit: empty hash");
        require(
            hashToRecordId[contentHash] == 0,
            "TradeFlowAudit: already anchored"
        );

        recordCount++;
        recordId = recordCount;

        records[recordId] = Record({
            merkleRoot:  merkleRoot,
            contentHash: contentHash,
            ipfsCid:     ipfsCid,
            timestamp:   block.timestamp,
            submitter:   msg.sender
        });

        hashToRecordId[contentHash] = recordId;

        emit Anchored(recordId, contentHash, merkleRoot, ipfsCid, block.timestamp);
    }

    /**
     * @notice Verify that a contentHash is anchored on-chain.
     */
    function verify(bytes32 contentHash) external view returns (bool, uint256 timestamp) {
        uint256 rid = hashToRecordId[contentHash];
        if (rid == 0) return (false, 0);
        return (true, records[rid].timestamp);
    }

    // ── Admin ─────────────────────────────────────────────────────────────────

    function addSubmitter(address submitter) external onlyOwner {
        authorizedSubmitters[submitter] = true;
    }

    function removeSubmitter(address submitter) external onlyOwner {
        authorizedSubmitters[submitter] = false;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "TradeFlowAudit: zero address");
        owner = newOwner;
    }
}
