# Google OAuth Callback Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the django-allauth authentication backend path so a completed Google OAuth callback can create a Django session.

**Architecture:** Keep the existing Django session and django-allauth Google provider. Correct only the configured backend import path, then exercise Django's own `get_backends()` loading boundary in a regression test. No OAuth browser flow, credential, data-model, or API change is part of this plan.

**Tech Stack:** Python 3.12, Django 5.2, django-allauth 65.19.6, Django test runner, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-12-google-oauth-callback-backend-design.md`

## Global Constraints

- Work only on `codex/oauth`; do not push, create a PR, or merge.
- Never read, print, change, or commit `.env`, OAuth Client ID, OAuth Client Secret, OAuth code, OAuth state, or KRX credentials.
- Keep all account, ledger, order, portfolio, next-trading-day-open, and virtual-money behavior unchanged.
- Do not add dependencies, migrations, external requests, UI changes, or a custom authentication backend.
- Rebuild `web` after code changes because Compose copies source into the image rather than bind-mounting it.

## Review Focus

- A misspelled import path must fail a test before a user reaches Google login; Task 1 loads the configured backends.
- The standard Django `ModelBackend` must remain alongside allauth; Task 1 asserts both configured paths load.
- Tests must not need OAuth values or network access; Task 1 runs with ordinary test settings only.
- The rebuilt Docker image, not a stale web container, must run the final checks; Task 3 rebuilds before verification.
- No scope expansion into credentials, DB, or actual trading is allowed; Task 3 checks the changed-file set and diff.

---

### Task 1: Authentication backend loading regression test

**Files:**
- Modify: `backend/trading/test_auth.py`

**Interfaces:**
- Consumes: `django.conf.settings.AUTHENTICATION_BACKENDS`, `django.contrib.auth.get_backends()`.
- Produces: `AuthenticationBackendConfigurationTests.test_all_configured_authentication_backends_load`.

- [ ] **Step 1: Write the failing test**

Add a `SimpleTestCase` that imports `AuthenticationBackend` from `allauth.account.auth_backends`, calls `get_backends()`, and asserts that the returned instances include both Django `ModelBackend` and allauth `AuthenticationBackend`.

- [ ] **Step 2: Run the targeted test before the fix**

Run `docker compose exec web python manage.py test trading.test_auth.AuthenticationBackendConfigurationTests`. Expected: FAIL with the current `ModuleNotFoundError` for `allauth.account.auth`.

- [ ] **Step 3: Keep the test independent of real OAuth**

Do not put Client ID, Client Secret, email, OAuth code, state, redirect URI, or browser requests in the test. The test proves only Django's configuration import boundary.

### Task 2: Correct the allauth backend configuration

**Files:**
- Modify: `backend/jumong/settings.py:68-71`

**Interfaces:**
- Consumes: the class installed by `django-allauth==65.19.6`.
- Produces: `AUTHENTICATION_BACKENDS` containing `allauth.account.auth_backends.AuthenticationBackend`.

- [ ] **Step 1: Make the one-line configuration correction**

Replace only `allauth.account.auth.backends.AuthenticationBackend` with `allauth.account.auth_backends.AuthenticationBackend`. Preserve Django `ModelBackend` and all surrounding settings.

- [ ] **Step 2: Rebuild web and rerun the targeted test**

Run `docker compose up -d --build web`, then `docker compose exec web python manage.py test trading.test_auth.AuthenticationBackendConfigurationTests`. Expected: targeted test passes without OAuth network access.

- [ ] **Step 3: Commit the implementation and regression test**

Stage only `backend/jumong/settings.py` and `backend/trading/test_auth.py`, then commit with message `fix: load allauth authentication backend`.

### Task 3: Full regression verification and handoff

**Files:**
- Create: `docs/handoffs/T-010-P1-claude-handoff.md`

**Interfaces:**
- Consumes: Tasks 1 and 2 plus `docs/handoffs/CLAUDE_HANDOFF_TEMPLATE.md`.
- Produces: reproducible implementation evidence for Codex review.

- [ ] **Step 1: Run final automated checks on the rebuilt image**

Run `docker compose exec web python manage.py test trading`, `docker compose exec web python manage.py check`, and `docker compose exec web python manage.py makemigrations --check --dry-run`. Expected: all tests pass, system check has no issues, and migration dry-run reports no changes.

- [ ] **Step 2: Check scope before handoff**

Run `git diff --check origin/dev...HEAD` and inspect the changed-file list. Confirm no `.env`, migration, dependency, database-data, secret, or out-of-scope UI change is included.

- [ ] **Step 3: Write the handoff and commit it**

Record the observed callback failure without OAuth query parameters, the exact corrected module path, changed files, test commands/results, and the separate user-only manual Google login verification. Do not record values or masked values. Commit the handoff; do not push or merge.

## Self-review

- Spec coverage: Tasks 1–3 cover the one setting correction, the pre-fix failure, regression protection, image rebuild, full checks, and secret-free handoff.
- Type consistency: the test imports the same `AuthenticationBackend` class path that Task 2 configures.
- Proportion: the plan has one code setting change and one focused regression test; it intentionally excludes unrelated OAuth or trading changes.
