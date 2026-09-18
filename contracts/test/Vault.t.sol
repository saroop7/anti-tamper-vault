// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";

contract VaultTest is Test {
    Vault vault;
    address backend = address(0xBEEF);
    address stranger = address(0xBAD);

    function setUp() public {
        vm.prank(backend);
        vault = new Vault();   // backend deploys, so backend is owner
    }

    function test_OwnerIsDeployer() public view {
        assertEq(vault.owner(), backend);
    }

    function test_LogEvent_StoresAndEmits() public {
        bytes32 h = keccak256("event-json-1");
        vm.prank(backend);
        uint256 id = vault.logEvent(h, 1_725_000_000, 37_774_900, -122_419_400);

        assertEq(id, 0);
        assertEq(vault.totalRecords(), 1);

        Vault.Record memory r = vault.getRecord(id);
        assertEq(r.dataHash, h);
        assertEq(r.deviceTimestamp, 1_725_000_000);
        assertEq(r.submitter, backend);
        assertEq(r.lat, 37_774_900);
        assertEq(r.lng, -122_419_400);
    }

    function test_Verify_MatchAndMismatch() public {
        bytes32 h = keccak256("event-json-1");
        vm.prank(backend);
        uint256 id = vault.logEvent(h, 1, 0, 0);

        assertTrue(vault.verify(id, h));
        assertFalse(vault.verify(id, keccak256("tampered")));
    }

    function test_RevertWhen_StrangerLogs() public {
        vm.prank(stranger);
        vm.expectRevert(Vault.NotOwner.selector);
        vault.logEvent(keccak256("x"), 1, 0, 0);
    }

    function test_RevertWhen_ZeroHash() public {
        vm.prank(backend);
        vm.expectRevert(Vault.ZeroHash.selector);
        vault.logEvent(bytes32(0), 1, 0, 0);
    }

    function test_MultipleEvents_Indexed() public {
        vm.startPrank(backend);
        vault.logEvent(keccak256("a"), 1, 0, 0);
        vault.logEvent(keccak256("b"), 2, 10_000_000, 20_000_000);
        vm.stopPrank();

        assertEq(vault.totalRecords(), 2);
        assertEq(vault.getRecord(1).dataHash, keccak256("b"));
        assertEq(vault.getRecord(1).lat, 10_000_000);
        assertEq(vault.getRecord(1).lng, 20_000_000);
    }
}