// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title Anti-Tamper Vault custody log
///@author 0xSAROOP_KUMAR_SARKAR
/// @notice Stores hashes of off-chain vault events, plus the device's
///         reported time and GPS location in the clear. The rest of the
///         event (sensor readings, status, device id) lives off-chain;
///         only its keccak256 hash is anchored here so it can be verified
///         later. Owner-only writes stop anyone spoofing the chain.
contract Vault {
    struct Record {
        bytes32 dataHash;        // keccak256 of the off-chain event JSON
        uint256 deviceTimestamp; // timestamp reported by the hardware
        uint256 blockTimestamp;  // when it landed on-chain (block.timestamp)
        address submitter;
        int256 lat;              // degrees * 1e6, 0 if the device reported none
        int256 lng;              // degrees * 1e6, 0 if the device reported none
    }

    address public owner;
    Record[] private records;

    event EventLogged(
        uint256 indexed id,
        bytes32 dataHash,
        uint256 deviceTimestamp,
        uint256 blockTimestamp,
        int256 lat,
        int256 lng
    );
    event OwnerChanged(address indexed oldOwner, address indexed newOwner);

    error NotOwner();
    error ZeroHash();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Anchor one event hash plus its time and location. Called by
    ///         your backend's wallet only. lat/lng are fixed-point degrees
    ///         scaled by 1e6 (e.g. 37.774900 -> 37774900), matching the
    ///         6-decimal precision already used off-chain.
    /// @return id The index of the stored record.
    function logEvent(bytes32 dataHash, uint256 deviceTimestamp, int256 lat, int256 lng)
        external
        onlyOwner
        returns (uint256 id)
    {
        if (dataHash == bytes32(0)) revert ZeroHash();
        id = records.length;
        records.push(Record({
            dataHash: dataHash,
            deviceTimestamp: deviceTimestamp,
            blockTimestamp: block.timestamp,
            submitter: msg.sender,
            lat: lat,
            lng: lng
        }));
        emit EventLogged(id, dataHash, deviceTimestamp, block.timestamp, lat, lng);
    }

    function getRecord(uint256 id) external view returns (Record memory) {
        return records[id];
    }

    /// @notice Verify a hash matches what was stored at that id.
    function verify(uint256 id, bytes32 dataHash) external view returns (bool) {
        return records[id].dataHash == dataHash;
    }

    function totalRecords() external view returns (uint256) {
        return records.length;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        emit OwnerChanged(owner, newOwner);
        owner = newOwner;
    }
}