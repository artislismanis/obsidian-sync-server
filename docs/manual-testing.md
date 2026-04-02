# Manual Testing Guide

This document covers testing scenarios that require manual verification — integration tests across components, UI/UX validation, deployment verification, and real-device testing that automated tests cannot cover.

## Prerequisites

```bash
# Terminal 1: Start server
cd server && source .venv/bin/activate
OSS_DEBUG=true uvicorn obsidian_sync.main:app --reload --port 8000

# Terminal 2: Start portal dev server
cd portal && npm run dev

# Terminal 3: Build plugin
cd plugin && npm run build
```

The server API docs are available at `http://localhost:8000/api/docs` when `OSS_DEBUG=true`.

---

## 1. First-Run Setup Flow

**Goal**: Verify the complete first-time setup experience.

- [ ] Start server with fresh data directory (empty `data/` folder)
- [ ] Open `http://localhost:8000/api/docs` and verify API docs load
- [ ] `POST /api/v1/auth/setup` with `{"username": "admin", "password": "testpass123"}` — should return 201 with tokens
- [ ] Repeat the same setup call — should return 409 (already configured)
- [ ] `POST /api/v1/auth/login` with the same credentials — should return 200 with tokens
- [ ] Verify health endpoint returns `{"status": "healthy"}`

---

## 2. Plugin End-to-End Sync

**Goal**: Verify sync between Obsidian plugin and server.

### Setup
- [ ] Copy `plugin/main.js` and `plugin/manifest.json` to an Obsidian vault's `.obsidian/plugins/obsidian-sync/` directory
- [ ] Enable the plugin in Obsidian Settings → Community Plugins
- [ ] Open plugin settings, enter server URL (`http://localhost:8000`), login

### On-Save Sync
- [ ] Create a new note in Obsidian → verify it appears on the server (`GET /api/v1/vaults/{id}/files`)
- [ ] Edit the note and save → verify the version increments on the server
- [ ] Delete the note → verify it's removed from server
- [ ] Rename a note → verify old path gone, new path present on server

### Status Bar
- [ ] Verify status bar shows "Sync: Connected" when WebSocket is active
- [ ] Stop the server → verify status changes to "Sync: Offline (N pending)"
- [ ] Restart the server → verify status returns to "Sync: Connected" and pending changes sync

### Conflict Resolution
- [ ] Edit a file on two devices simultaneously while one is offline
- [ ] Reconnect the offline device → verify a `.conflict-<timestamp>.md` file is created
- [ ] Verify both versions are preserved (original file has server version, conflict file has local version)

---

## 3. Multi-Device Sync

**Goal**: Verify real-time sync between two connected clients.

- [ ] Connect two Obsidian instances (or one Obsidian + CLI) to the same vault
- [ ] Create a file on device A → verify it appears on device B within 2 seconds
- [ ] Edit a file on device A → verify the change appears on device B
- [ ] Delete a file on device B → verify it disappears from device A
- [ ] Rename a file on device A → verify the rename propagates to device B

---

## 4. CLI Client Testing

**Goal**: Verify headless sync via the CLI tool.

```bash
cd cli && source .venv/bin/activate
```

- [ ] `oss login http://localhost:8000` — enter credentials, verify "Logged in" message
- [ ] `oss status` — verify vault list displays
- [ ] Create a vault via API, then `oss sync /tmp/test-vault --vault <vault-id>` — verify files sync
- [ ] Add a file to `/tmp/test-vault/`, run `oss push` → verify file appears on server
- [ ] Add a file via API, run `oss pull` → verify file appears locally
- [ ] `oss watch --vault <vault-id>` — modify a file, verify it uploads automatically
- [ ] Press Ctrl+C → verify clean shutdown

---

## 5. Web Portal Testing

**Goal**: Verify the portal UI works correctly.

Open `http://localhost:5173` (Vite dev server).

### Authentication
- [ ] Login page renders with username/password fields
- [ ] Enter wrong credentials → error message displayed
- [ ] Enter correct credentials → redirected to dashboard
- [ ] Refresh the page → stays logged in (token persisted)
- [ ] Click Logout → returns to login page, token cleared

### Dashboard
- [ ] Vault cards display with name, storage type, encryption status
- [ ] Click a vault card → navigates to vault browser

### Vault Browser
- [ ] File tree renders with correct folder hierarchy
- [ ] Click a `.md` file → markdown renders in the content pane
- [ ] Click a non-markdown file → raw content displayed
- [ ] Click "Back" → returns to dashboard
- [ ] Folders expand/collapse on click

### Admin Panel
- [ ] Click "Admin" nav link → admin page loads
- [ ] Server health status displays (healthy/version/mode)

### Responsive Design
- [ ] Resize browser to mobile width (< 768px) → layout stacks vertically
- [ ] File tree and content pane are usable on narrow screens
- [ ] Nav links remain accessible

---

## 6. Vault Sharing & ACL

**Goal**: Verify multi-user access control works correctly.

### Setup
Create two users via the API:
```bash
# Create user2 (admin creates via API or setup a second account)
curl -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"username": "user2", "password": "testpass123"}'
```

### Role Testing
- [ ] **Owner**: Can create vaults, upload files, manage sharing, delete vault
- [ ] **Admin**: Can manage sharing, upload files. Cannot delete the vault (403)
- [ ] **Write**: Can upload and download files. Cannot manage sharing (403)
- [ ] **Read**: Can download files. Cannot upload (403) or manage sharing (403)
- [ ] **No access**: Gets 403 on all vault operations
- [ ] Revoke access → user immediately loses access (including active WebSocket)

---

## 7. Share Links

**Goal**: Verify signed share link functionality.

- [ ] Create a share link via API: `POST /api/v1/vaults/{id}/share-links` with `{"file_path": "note.md", "permissions": "download", "expires_in_hours": 24}`
- [ ] Access the link: `GET /api/v1/share/{token}` — should return file content
- [ ] Access with wrong token → 404
- [ ] Wait for expiry (or set `expires_in_hours: 0`) → link returns 404
- [ ] Revoke the link → returns 404
- [ ] Create a password-protected link (min 8 chars) → access without password returns 401
- [ ] Access with correct password → returns content

---

## 8. Per-Vault Encryption

**Goal**: Verify client-side encryption works end-to-end.

- [ ] Create an encrypted vault: `POST /api/v1/vaults` with `{"name": "Secret", "encrypted": true, "encryption_salt": "<random-hex>"}`
- [ ] Upload a file via plugin with encryption enabled → verify server stores ciphertext (base64 decode the content from `GET /files/{path}` — it should NOT be readable plaintext)
- [ ] Download the same file via plugin → verify it's decrypted correctly (matches original)
- [ ] Attempt to read the encrypted file directly via API → verify content is opaque ciphertext

---

## 9. Docker Deployment

**Goal**: Verify the Docker Compose deployment works on target hardware.

```bash
cd docker
cp .env.example .env
# Edit .env: set OSS_SECRET_KEY to a random 32+ char string
docker compose up -d
```

- [ ] Containers start without errors: `docker compose ps`
- [ ] Health check passes: `curl https://localhost/api/v1/health` (self-signed cert warning OK)
- [ ] Setup endpoint works through Caddy reverse proxy
- [ ] WebSocket sync works through Caddy (Caddy proxies WebSocket by default)
- [ ] Data persists after `docker compose down && docker compose up -d`
- [ ] Logs are accessible: `docker compose logs server`

### Synology NAS
- [ ] SSH into NAS, clone repo, run `docker compose up -d`
- [ ] Verify containers start on ARM64 architecture
- [ ] Verify sync works from Obsidian on the same LAN
- [ ] Verify portal accessible from LAN at `https://<nas-ip>`
- [ ] Monitor memory usage — should be < 256MB idle

---

## 10. Mobile Plugin Testing

**Goal**: Verify the plugin works on Obsidian mobile.

### iOS
- [ ] Install plugin on iOS Obsidian (copy files via iCloud or Obsidian Sync)
- [ ] Open plugin settings → server URL field is usable on mobile keyboard
- [ ] Login succeeds
- [ ] Create a note → syncs to server (verify 5s debounce, not 2s)
- [ ] Verify status bar is readable on mobile screen

### Android
- [ ] Same tests as iOS on Android Obsidian
- [ ] Verify plugin doesn't crash on load (no Node.js/Electron APIs used)

### Mobile-Specific Behavior
- [ ] Large file (> 20MB): verify sync is skipped with a notice on mobile
- [ ] Switch from WiFi to cellular → verify WebSocket reconnects with backoff
- [ ] Lock the device, then unlock → verify sync resumes
- [ ] Verify battery usage is not excessive during sync

---

## 11. Performance Testing

**Goal**: Verify sync performance meets success criteria.

### Latency
- [ ] **On-save sync**: Measure time from file save to server acknowledgment — target < 2s on LAN
- [ ] **Cross-device propagation**: Measure time from save on device A to file appearing on device B — target < 2s on LAN
- [ ] **Share link access**: Measure time from link click to content displayed — target < 2s for files up to 1MB

### Concurrency
- [ ] Connect 10 clients simultaneously → verify no degradation
- [ ] Have 5 clients editing different files concurrently → verify all changes sync correctly
- [ ] Connect and disconnect clients rapidly (10 times in 30 seconds) → verify no WebSocket leaks

### Large Vaults
- [ ] Sync a vault with 1000 files → verify initial sync completes
- [ ] Sync a vault with 100MB of content → verify no timeouts
- [ ] Edit files in a large vault → verify incremental sync is fast (not re-syncing everything)

---

## 12. Security Validation

**Goal**: Verify security measures work as expected.

### Authentication
- [ ] Access any protected endpoint without a token → 401
- [ ] Use an expired JWT → 401
- [ ] Use a revoked refresh token → 401
- [ ] Login with wrong password 6 times → 429 rate limit on 6th attempt
- [ ] Wait 60 seconds → can login again

### Authorization
- [ ] User A creates a vault → User B cannot access it (403)
- [ ] User A shares vault with User B as "read" → User B can GET files but not PUT (403)
- [ ] Revoke User B's access → User B gets 403 immediately

### Input Validation
- [ ] Upload a file with path `../../etc/passwd` → should be rejected (path traversal)
- [ ] Send a WebSocket message with `type: "file_save"` and empty path → error response
- [ ] Create a share link with password "short" (< 8 chars) → 422 validation error
- [ ] Send malformed JSON via WebSocket → error response, connection stays open

### Startup
- [ ] Start server with default `secret_key` → verify warning logged: "SECURITY WARNING: Using default secret_key"
- [ ] Start server with custom `OSS_SECRET_KEY=my-real-secret-key-that-is-long` → no warning

---

## Outstanding Implementation Gaps

The following features are specified but not yet fully implemented. They need to be built before they can be tested:

| Feature | Status | Priority |
|---------|--------|----------|
| File version history (view/diff/restore) | Missing server endpoints + portal page | P2 |
| Admin API (user CRUD, stats, audit log viewer) | Missing | P1 |
| OAuth login (Google, GitHub) | Spec'd, not wired | P2 |
| GDPR data export + account deletion | Models exist, no endpoints/workers | P2 |
| Live sync (real Yjs CRDT) | Placeholder only | P2 |
| External sync workers (GDrive/OneDrive bidirectional) | Connectors exist, no workers/API | P3 |
| Portal: FileHistory, ShareView, Billing, EncryptionPrompt pages | Missing | P2 |
| Billing router not wired into main.py | Missing `include_router` | P3 |
| CLI encryption support | Missing crypto module | P2 |
| AWS CDK stacks | Empty placeholders | P3 |
| Multi-arch Docker builds + publishing | CI builds but doesn't publish | P3 |
| E2E tests (Playwright) | Not started | P3 |
