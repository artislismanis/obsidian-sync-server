# Test Scenarios

Step-by-step test drive checklist organized by feature. Each scenario is self-contained with exact commands you can copy-paste.

## Prerequisites

Start the server in debug mode (enables API docs):

```bash
cd server && source .venv/bin/activate
OSS_DEBUG=true uvicorn obsidian_sync.main:app --reload --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/api/v1/health
# {"status":"healthy","version":"0.1.0","mode":"self_hosted"}
```

API docs available at http://localhost:8000/api/docs

---

## Scenario 1: First-Run Setup

```bash
# 1. Create admin account (only works once)
curl -s -X POST http://localhost:8000/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "testpass1234", "email": "admin@test.com"}' | python3 -m json.tool

# Expected: 201 with access_token + refresh_token
# Save the access_token:
export TOKEN="<paste access_token here>"

# 2. Try setup again — should fail
curl -s -X POST http://localhost:8000/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username": "admin2", "password": "testpass1234"}' | python3 -m json.tool
# Expected: 409 "Setup already completed"

# 3. Login with credentials
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "testpass1234"}' | python3 -m json.tool
# Expected: 200 with fresh tokens
```

**Pass criteria**: Setup returns 201 once, 409 on retry. Login returns 200 with tokens.

---

## Scenario 2: Vault CRUD

```bash
# 1. Create a vault
curl -s -X POST http://localhost:8000/api/v1/vaults \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Vault"}' | python3 -m json.tool

# Save the vault ID:
export VAULT_ID="<paste id here>"

# 2. List vaults
curl -s http://localhost:8000/api/v1/vaults \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: total=1, vault name="Test Vault"

# 3. Get vault details
curl -s http://localhost:8000/api/v1/vaults/$VAULT_ID \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 4. Update vault
curl -s -X PATCH http://localhost:8000/api/v1/vaults/$VAULT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Renamed Vault", "sync_mode": "both"}' | python3 -m json.tool
# Expected: name changed, sync_mode="both"

# 5. Delete vault
curl -s -X DELETE http://localhost:8000/api/v1/vaults/$VAULT_ID \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 204
```

**Pass criteria**: Full CRUD lifecycle works. Deleted vault no longer appears in list.

---

## Scenario 3: File Sync via API

```bash
# Create a fresh vault for file testing
export VAULT_ID=$(curl -s -X POST http://localhost:8000/api/v1/vaults \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "File Test Vault"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 1. Upload a file (content is base64-encoded)
CONTENT=$(echo -n "# Hello World\nThis is a test note." | base64)
HASH=$(echo -n "# Hello World\nThis is a test note." | sha256sum | cut -d' ' -f1)

curl -s -X PUT "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/notes/hello.md" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"notes/hello.md\", \"content\": \"$CONTENT\", \"version\": 0, \"content_hash\": \"$HASH\"}" | python3 -m json.tool
# Expected: version=1

# 2. Download the file
curl -s "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/notes/hello.md" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json,base64; d=json.load(sys.stdin); print(base64.b64decode(d['content']).decode())"
# Expected: "# Hello World\nThis is a test note."

# 3. Upload new version
CONTENT2=$(echo -n "# Hello World\nUpdated content." | base64)
HASH2=$(echo -n "# Hello World\nUpdated content." | sha256sum | cut -d' ' -f1)

curl -s -X PUT "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/notes/hello.md" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"notes/hello.md\", \"content\": \"$CONTENT2\", \"version\": 1, \"content_hash\": \"$HASH2\"}" | python3 -m json.tool
# Expected: version=2

# 4. List files
curl -s "http://localhost:8000/api/v1/vaults/$VAULT_ID/files" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: 1 file, version=2

# 5. Conflict detection — send stale version
curl -s -X PUT "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/notes/hello.md" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"notes/hello.md\", \"content\": \"$CONTENT\", \"version\": 1, \"content_hash\": \"$HASH\"}" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 409 "Conflict: server has a newer version"

# 6. Delete file
curl -s -X DELETE "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/notes/hello.md" \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 204
```

**Pass criteria**: Upload, download, versioning, conflict detection (409), and delete all work.

---

## Scenario 4: User Management

```bash
# 1. Create a regular user (admin only)
curl -s -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "alicepass1234", "email": "alice@test.com"}' | python3 -m json.tool
# Expected: 201, is_superadmin=false

export ALICE_ID="<paste id>"

# 2. List users
curl -s http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: 2 users (admin + alice)

# 3. Login as alice
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "alicepass1234"}' | python3 -m json.tool
export ALICE_TOKEN="<paste access_token>"

# 4. Alice cannot list users (not admin)
curl -s http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $ALICE_TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 403

# 5. Reset alice's password
curl -s -X PATCH "http://localhost:8000/api/v1/users/$ALICE_ID/password" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "newpass12345"}' -w "\nHTTP %{http_code}\n"
# Expected: HTTP 204

# 6. Alice can login with new password
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "newpass12345"}' -w "\nHTTP %{http_code}\n"
# Expected: HTTP 200
```

**Pass criteria**: Admin can CRUD users. Non-admin gets 403. Password reset works.

---

## Scenario 5: Vault Sharing & ACL

```bash
# Setup: admin creates a vault and uploads a file
export VAULT_ID=$(curl -s -X POST http://localhost:8000/api/v1/vaults \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Shared Vault"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

CONTENT=$(echo -n "shared content" | base64)
curl -s -X PUT "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/shared.md" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"shared.md\", \"content\": \"$CONTENT\", \"version\": 0, \"content_hash\": \"x\"}" > /dev/null

# 1. Alice cannot access the vault (no sharing yet)
curl -s "http://localhost:8000/api/v1/vaults/$VAULT_ID" \
  -H "Authorization: Bearer $ALICE_TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 403

# 2. Share with alice as "read"
curl -s -X POST "http://localhost:8000/api/v1/vaults/$VAULT_ID/sharing" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$ALICE_ID\", \"role\": \"read\"}" | python3 -m json.tool
# Expected: 201

# 3. Alice can now read files
curl -s "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/shared.md" \
  -H "Authorization: Bearer $ALICE_TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 200

# 4. Alice cannot upload (read-only)
curl -s -X PUT "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/new.md" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "new.md", "content": "dGVzdA==", "version": 0, "content_hash": "x"}' -w "\nHTTP %{http_code}\n"
# Expected: HTTP 403

# 5. Upgrade alice to "write"
curl -s -X PATCH "http://localhost:8000/api/v1/vaults/$VAULT_ID/sharing/$ALICE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "write"}' | python3 -m json.tool

# 6. Alice can now upload
curl -s -X PUT "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/alice-note.md" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "alice-note.md", "content": "dGVzdA==", "version": 0, "content_hash": "x"}' -w "\nHTTP %{http_code}\n"
# Expected: HTTP 200

# 7. Revoke access
curl -s -X DELETE "http://localhost:8000/api/v1/vaults/$VAULT_ID/sharing/$ALICE_ID" \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 204

# 8. Alice blocked again
curl -s "http://localhost:8000/api/v1/vaults/$VAULT_ID" \
  -H "Authorization: Bearer $ALICE_TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 403
```

**Pass criteria**: Read user can GET but not PUT. Write user can do both. Revoke takes effect immediately.

---

## Scenario 6: Share Links

```bash
# 1. Create a share link (24h expiry)
curl -s -X POST "http://localhost:8000/api/v1/vaults/$VAULT_ID/share-links" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "shared.md", "permissions": "download", "expires_in_hours": 24}' | python3 -m json.tool

export SHARE_TOKEN="<paste token>"

# 2. Access share link (no auth needed)
curl -s "http://localhost:8000/api/v1/share/$SHARE_TOKEN" | python3 -m json.tool
# Expected: file content returned

# 3. Invalid token
curl -s "http://localhost:8000/api/v1/share/invalid-token" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 404

# 4. Create password-protected link
curl -s -X POST "http://localhost:8000/api/v1/vaults/$VAULT_ID/share-links" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "shared.md", "permissions": "view", "password": "secret12345"}' | python3 -m json.tool

export PW_TOKEN="<paste token>"

# 5. Access without password — fails
curl -s "http://localhost:8000/api/v1/share/$PW_TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 401 "Password required"

# 6. Access with password — works
curl -s "http://localhost:8000/api/v1/share/$PW_TOKEN?password=secret12345" | python3 -m json.tool
# Expected: 200

# 7. Revoke the link
LINK_ID="<paste link id from step 1>"
curl -s -X DELETE "http://localhost:8000/api/v1/vaults/$VAULT_ID/share-links/$LINK_ID" \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 204
```

**Pass criteria**: Share links work without auth. Password protection enforced. Revocation works.

---

## Scenario 7: Admin & Server Stats

```bash
# 1. Server stats
curl -s http://localhost:8000/api/v1/admin/stats \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: users, vaults, files, storage_bytes, connected_clients

# 2. Audit log
curl -s http://localhost:8000/api/v1/admin/audit-log \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: entries array with actions from previous tests

# 3. Server config
curl -s http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: deployment_mode, storage_backend, oauth/stripe status
```

**Pass criteria**: Stats show correct counts. Audit log has entries. Config is readable.

---

## Scenario 8: GDPR Compliance

```bash
# 1. Export personal data
curl -s http://localhost:8000/api/v1/account/export \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: user info + vault list with files

# 2. Request account deletion
curl -s -X DELETE http://localhost:8000/api/v1/account/delete \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: status="deletion_requested"

# 3. Cancel deletion
curl -s -X POST http://localhost:8000/api/v1/account/cancel-deletion \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: status="cancelled"

# 4. Record consent
curl -s -X POST http://localhost:8000/api/v1/account/consent \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: gdpr_consent_at timestamp
```

**Pass criteria**: Export returns data. Deletion is requestable and cancellable. Consent records timestamp.

---

## Scenario 9: Rate Limiting

```bash
# 1. Hit login 6 times rapidly
for i in {1..6}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "wrong"}')
  echo "Attempt $i: HTTP $CODE"
done
# Expected: first 5 return 401, 6th returns 429

# 2. Check rate limit headers on any response
curl -s -D - http://localhost:8000/api/v1/health 2>&1 | grep -i "x-ratelimit"
# Expected: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset headers
```

**Pass criteria**: 6th login attempt returns 429. Rate limit headers present on all responses.

---

## Scenario 10: Security Checks

```bash
# 1. No auth → 401
curl -s http://localhost:8000/api/v1/vaults -w "\nHTTP %{http_code}\n"
# Expected: HTTP 401

# 2. Invalid JWT → 401
curl -s http://localhost:8000/api/v1/vaults \
  -H "Authorization: Bearer invalid.jwt.token" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 401

# 3. Path traversal blocked
curl -s -X PUT "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/../../etc/passwd" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "../../etc/passwd", "content": "dGVzdA==", "version": 0, "content_hash": "x"}' -w "\nHTTP %{http_code}\n"
# Expected: HTTP 400 or 500 (path traversal rejected)

# 4. Short share link password rejected
curl -s -X POST "http://localhost:8000/api/v1/vaults/$VAULT_ID/share-links" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"permissions": "view", "password": "short"}' -w "\nHTTP %{http_code}\n"
# Expected: HTTP 422 (validation error, min 8 chars)

# 5. API key auth
API_KEY=$(curl -s -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-key"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])")

curl -s http://localhost:8000/api/v1/vaults \
  -H "X-API-Key: $API_KEY" -w "\nHTTP %{http_code}\n"
# Expected: HTTP 200
```

**Pass criteria**: All security boundaries enforced. API key auth works as alternative to JWT.

---

## Scenario 11: CLI Client

```bash
cd cli && source .venv/bin/activate

# 1. Login
oss login http://localhost:8000
# Enter: admin / testpass1234
# Expected: "Logged in to http://localhost:8000"

# 2. Check status
oss status
# Expected: table showing vaults

# 3. Sync a directory
mkdir -p /tmp/test-vault
echo "# CLI Test" > /tmp/test-vault/cli-note.md
oss sync /tmp/test-vault --vault $VAULT_ID
# Expected: "Pulled X files" then "Pushed 1 changed files" then "Sync complete"

# 4. Verify file is on server
curl -s "http://localhost:8000/api/v1/vaults/$VAULT_ID/files" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: cli-note.md in file list

# 5. Pull
echo "# Server File" | base64 | xargs -I{} curl -s -X PUT \
  "http://localhost:8000/api/v1/vaults/$VAULT_ID/files/server-note.md" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"server-note.md\", \"content\": \"{}\", \"version\": 0, \"content_hash\": \"x\"}" > /dev/null

oss pull --vault $VAULT_ID
cat /tmp/test-vault/server-note.md
# Expected: file pulled from server
```

**Pass criteria**: Login, sync, pull, push all work. Files round-trip correctly.

---

## Scenario 12: Portal UI

Start the portal dev server: `cd portal && npm run dev`

Open http://localhost:5173 in a browser.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Login page loads | Username + password fields visible |
| 2 | Enter wrong password | Error message shown |
| 3 | Enter correct credentials | Dashboard loads with vault cards |
| 4 | Click a vault card | File tree + content pane appear |
| 5 | Click a .md file | Markdown renders (headers, bold, links) |
| 6 | Click "Admin" | Server stats table shows |
| 7 | Click "Billing" | "Self-hosted mode" message (no Stripe configured) |
| 8 | Click "Logout" | Returns to login page |
| 9 | Refresh page | Stays logged in (token in localStorage) |
| 10 | Resize to mobile width | Layout stacks, nav collapses |

**Pass criteria**: All 10 steps work. No console errors.

---

## Scenario 13: Docker Deployment

```bash
cd docker
cp .env.example .env
# Edit .env: set OSS_SECRET_KEY=test-secret-key-at-least-32-chars

docker compose up -d --build

# 1. Containers running
docker compose ps
# Expected: server + caddy both "Up"

# 2. Health check via Caddy
curl -k https://localhost/api/v1/health
# Expected: {"status":"healthy"}

# 3. Setup via Caddy
curl -k -X POST https://localhost/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "dockertest1234"}'
# Expected: 201 with tokens

# 4. Data persists across restart
docker compose down
docker compose up -d
curl -k -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "dockertest1234"}'
# Expected: 200 (login works with existing data)

# Cleanup
docker compose down -v
```

**Pass criteria**: Docker builds, Caddy proxies correctly, data survives restart.
