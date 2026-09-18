import { ethers } from "ethers";
import dotenv from "dotenv";
dotenv.config();

// Recursively sorts object keys so JSON.stringify is stable regardless of
// insertion order. Needed because Postgres JSONB re-orders object keys
// alphabetically on round-trip, which would otherwise change the hash.
function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    return Object.keys(value)
      .sort()
      .reduce((acc, key) => {
        acc[key] = sortKeys(value[key]);
        return acc;
      }, {});
  }
  return value;
}

// Canonical hash: sort keys, JSON stringify, keccak256 the UTF-8 bytes.
// This MUST match what the contract verifies against.
export function hashEvent(evt) {
  const canonical = JSON.stringify(
    sortKeys({
      device_id: evt.device_id,
      device_ts: evt.device_ts,
      status: evt.status,
      tamper: evt.tamper,
      sensor_data: evt.sensor_data ?? null,
      lat: evt.lat ?? null,
      lng: evt.lng ?? null,
    })
  );
  return ethers.keccak256(ethers.toUtf8Bytes(canonical));
}

const ABI = [
  "function logEvent(bytes32 dataHash, uint256 deviceTimestamp, int256 lat, int256 lng) returns (uint256)",
  "function verify(uint256 id, bytes32 dataHash) view returns (bool)",
  "function totalRecords() view returns (uint256)",
  "event EventLogged(uint256 indexed id, bytes32 dataHash, uint256 deviceTimestamp, uint256 blockTimestamp, int256 lat, int256 lng)",
];

// Fixed-point scale for on-chain lat/lng (Solidity has no floats).
// 1e6 matches the 6-decimal precision already used off-chain (see fake-sensor.js).
const GEO_SCALE = 1_000_000;
function toFixedPoint(coord) {
  if (coord === null || coord === undefined) return 0n;
  return BigInt(Math.round(coord * GEO_SCALE));
}

let contract = null;
function getContract() {
  if (!process.env.CONTRACT_ADDRESS) return null; // not deployed yet
  if (contract) return contract;
  const provider = new ethers.JsonRpcProvider(process.env.RPC_URL);
  const wallet = new ethers.Wallet(process.env.PRIVATE_KEY, provider);
  contract = new ethers.Contract(process.env.CONTRACT_ADDRESS, ABI, wallet);
  return contract;
}

// Anchors a hash + location on-chain. Returns { txHash, onchainId, contract } or null if no contract.
export async function anchorHash(dataHash, deviceTsSeconds, lat, lng) {
  const c = getContract();
  if (!c) return null;
  const tx = await c.logEvent(dataHash, deviceTsSeconds, toFixedPoint(lat), toFixedPoint(lng));
  const receipt = await tx.wait();
  // Read the id straight out of this transaction's own EventLogged log instead of
  // re-querying totalRecords() afterward -- the latter races when two anchors land
  // close together (a second tx can confirm in between, handing this one the wrong id).
  const parsed = receipt.logs
    .map((log) => { try { return c.interface.parseLog(log); } catch { return null; } })
    .find((e) => e && e.name === "EventLogged");
  const onchainId = Number(parsed.args.id);
  return { txHash: receipt.hash, onchainId, contract: process.env.CONTRACT_ADDRESS };
}

export async function verifyOnChain(onchainId, dataHash) {
  const c = getContract();
  if (!c) return null;
  return await c.verify(onchainId, dataHash);
}