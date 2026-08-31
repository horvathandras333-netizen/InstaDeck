# App Updates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users update all detected winget upgrades in one confirmed action, while retaining selective per-app updates.

**Architecture:** Reuse the existing installed-package scan and `WingetEngine` upgrade queue. The frontend derives upgradeable package IDs, starts the same preflight and queue workflow with an explicit `upgrade` operation, and adds no background service or duplicate state.

**Tech Stack:** Python 3.10, pywebview, winget, vanilla JavaScript, CSS, unittest.

---

### Task 1: Lock the update-all UI contract

**Files:**
- Modify: `tests/test_ui_contract.py`
- Modify: `web/index.html`
- Modify: `web/app.js`

**Step 1:** Add a failing source-contract test for a disabled bulk-update button, a derived upgrade-ID helper, confirmation, and the existing `upgrade` API route.

**Step 2:** Run `python -m unittest tests.test_ui_contract -v` and observe failure.

**Step 3:** Add the button and minimal frontend wiring.

**Step 4:** Re-run the test and observe success.

### Task 2: Share the existing queue start logic

**Files:**
- Modify: `web/app.js`
- Test: `tests/test_ui_contract.py`

**Step 1:** Extract the existing preflight/queue transition into a helper taking package IDs and `install` or `upgrade`.

**Step 2:** Make the regular selected action call it with the selected operation.

**Step 3:** Make bulk update call it with all upgradeable IDs after confirmation; show an up-to-date toast when the list is empty.

**Step 4:** Verify selected upgrades and bulk upgrades still use `api('upgrade', ...)`.

### Task 3: Verify and package

**Files:**
- Modify: `web/styles.css` only if layout needs spacing adjustment

**Step 1:** Run the unit/contract suite, Python compilation, JavaScript syntax check, and diff check.

**Step 2:** Build `dist\\InstaDeck.exe` with `build.bat`.

**Step 3:** Refresh `Desktop\\InstaDeck-Portable.zip` from the new executable and verify that it contains the current executable.
