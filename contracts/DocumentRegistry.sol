// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title DocumentRegistry
 * @notice TradeFlow AI — Immutable document hash registry on Polygon Amoy (T-048)
 * @dev Stores SHA-256 hash of PIB payloads for non-repudiation and audit trail.
 *      Deployed to Polygon Amoy testnet. Uses CREATE2 for deterministic address.
 *
 * Events:
 *   DocumentAnchored(batchId, docHash, ipfsCid, timestamp, company)
 *
 * View functions:
 *   getDocument(batchId) → DocumentRecord
 *   verifyDocument(batchId, hash) → bool
 *   getDocumentCount() → uint256
 */

contract DocumentRegistry {
    // ─────────────────────────────────────────────────────────
    // State
    // ─────────────────────────────────────────────────────────

    struct DocumentRecord {
        bytes32 docHash;        // SHA-256 of the PIB JSON payload
        string  ipfsCid;        // IPFS CID of the encrypted full payload
        uint256 timestamp;      // block.timestamp at anchoring
        address anchorer;       // operator wallet address
        string  company;        // company identifier (not PII)
        string  ajuNumber;      // CEISA AJU number (post-submission)
        bool    exists;
    }

    mapping(string => DocumentRecord) private _records;  // batchId → record
    mapping(address => bool) public authorizedOperators;

    address public owner;
    uint256 public documentCount;

    // ─────────────────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────────────────

    event DocumentAnchored(
        string indexed batchId,
        bytes32 docHash,
        string  ipfsCid,
        uint256 timestamp,
        string  company,
        string  ajuNumber
    );

    event OperatorAuthorized(address indexed operator);
    event OperatorRevoked(address indexed operator);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // ─────────────────────────────────────────────────────────
    // Modifiers
    // ─────────────────────────────────────────────────────────

    modifier onlyOwner() {
        require(msg.sender == owner, "DocumentRegistry: not owner");
        _;
    }

    modifier onlyAuthorized() {
        require(
            authorizedOperators[msg.sender] || msg.sender == owner,
            "DocumentRegistry: not authorized"
        );
        _;
    }

    // ─────────────────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────────────────

    constructor() {
        owner = msg.sender;
        authorizedOperators[msg.sender] = true;
        emit OperatorAuthorized(msg.sender);
    }

    // ─────────────────────────────────────────────────────────
    // Core functions
    // ─────────────────────────────────────────────────────────

    /**
     * @notice Anchor a document hash on-chain.
     * @param batchId Unique batch identifier from TradeFlow AI
     * @param docHash SHA-256 hash of the PIB JSON payload (bytes32)
     * @param ipfsCid IPFS CID of the Pinata-pinned encrypted payload
     * @param company Anonymized company identifier
     * @param ajuNumber CEISA AJU number (can be empty string before submission)
     */
    function anchorDocument(
        string calldata batchId,
        bytes32 docHash,
        string calldata ipfsCid,
        string calldata company,
        string calldata ajuNumber
    ) external onlyAuthorized {
        require(bytes(batchId).length > 0, "DocumentRegistry: empty batchId");
        require(docHash != bytes32(0), "DocumentRegistry: empty hash");
        require(!_records[batchId].exists, "DocumentRegistry: already anchored");

        _records[batchId] = DocumentRecord({
            docHash:   docHash,
            ipfsCid:   ipfsCid,
            timestamp: block.timestamp,
            anchorer:  msg.sender,
            company:   company,
            ajuNumber: ajuNumber,
            exists:    true
        });

        documentCount++;

        emit DocumentAnchored(
            batchId, docHash, ipfsCid,
            block.timestamp, company, ajuNumber
        );
    }

    /**
     * @notice Update AJU number after CEISA submission (idempotent).
     * @dev Only the original anchorer or owner can update.
     */
    function updateAjuNumber(
        string calldata batchId,
        string calldata ajuNumber
    ) external onlyAuthorized {
        require(_records[batchId].exists, "DocumentRegistry: not found");
        _records[batchId].ajuNumber = ajuNumber;
    }

    // ─────────────────────────────────────────────────────────
    // View functions
    // ─────────────────────────────────────────────────────────

    function getDocument(string calldata batchId)
        external view
        returns (DocumentRecord memory)
    {
        require(_records[batchId].exists, "DocumentRegistry: not found");
        return _records[batchId];
    }

    function verifyDocument(string calldata batchId, bytes32 docHash)
        external view
        returns (bool)
    {
        if (!_records[batchId].exists) return false;
        return _records[batchId].docHash == docHash;
    }

    function getDocumentCount() external view returns (uint256) {
        return documentCount;
    }

    // ─────────────────────────────────────────────────────────
    // Admin
    // ─────────────────────────────────────────────────────────

    function authorizeOperator(address operator) external onlyOwner {
        authorizedOperators[operator] = true;
        emit OperatorAuthorized(operator);
    }

    function revokeOperator(address operator) external onlyOwner {
        require(operator != owner, "DocumentRegistry: cannot revoke owner");
        authorizedOperators[operator] = false;
        emit OperatorRevoked(operator);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "DocumentRegistry: zero address");
        emit OwnershipTransferred(owner, newOwner);
        authorizedOperators[newOwner] = true;
        owner = newOwner;
    }
}
