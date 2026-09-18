// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {Vault} from "../src/Vault.sol";

contract Deploy is Script {
    function run() external returns (Vault vault) {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        vault = new Vault();
        vm.stopBroadcast();
    }
}