/**
 * Client-side vault encryption: Argon2id key derivation + AES-256-GCM.
 *
 * Encryption flow:
 * 1. Derive key: Argon2id(passphrase, vault_salt) → 256-bit key
 * 2. Encrypt: AES-256-GCM(key, random_nonce, plaintext) → nonce + ciphertext + tag
 * 3. Upload ciphertext to server (server never sees plaintext)
 *
 * Implementation note: Argon2 is imported at runtime via argon2-browser.
 * For the MVP, we use PBKDF2 as a fallback (available via SubtleCrypto).
 */

const NONCE_LENGTH = 12; // AES-GCM nonce
const KEY_LENGTH = 32; // 256 bits
const PBKDF2_ITERATIONS = 600000;

/**
 * Derive an AES-256 key from a passphrase and salt using PBKDF2.
 * (Argon2id will be added when argon2-browser is integrated)
 */
export async function deriveKey(
  passphrase: string,
  salt: string
): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    enc.encode(passphrase),
    "PBKDF2",
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: enc.encode(salt),
      iterations: PBKDF2_ITERATIONS,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

/**
 * Encrypt data with AES-256-GCM. Returns nonce + ciphertext.
 */
export async function encrypt(
  key: CryptoKey,
  plaintext: ArrayBuffer
): Promise<ArrayBuffer> {
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_LENGTH));
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce },
    key,
    plaintext
  );
  // Prepend nonce to ciphertext
  const result = new Uint8Array(NONCE_LENGTH + ciphertext.byteLength);
  result.set(nonce, 0);
  result.set(new Uint8Array(ciphertext), NONCE_LENGTH);
  return result.buffer;
}

/**
 * Decrypt data with AES-256-GCM. Input is nonce + ciphertext.
 */
export async function decrypt(
  key: CryptoKey,
  data: ArrayBuffer
): Promise<ArrayBuffer> {
  const bytes = new Uint8Array(data);
  const nonce = bytes.slice(0, NONCE_LENGTH);
  const ciphertext = bytes.slice(NONCE_LENGTH);
  return crypto.subtle.decrypt(
    { name: "AES-GCM", iv: nonce },
    key,
    ciphertext
  );
}

/**
 * Generate a random salt for vault encryption.
 */
export function generateSalt(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Hash a derived key for server-side passphrase verification.
 * The server stores this hash — it can verify the passphrase is correct
 * without ever seeing the actual encryption key.
 */
export async function hashKey(key: CryptoKey): Promise<string> {
  const exported = await crypto.subtle.exportKey("raw", key);
  // Re-import as non-extractable would fail, so hash the raw bytes
  const hash = await crypto.subtle.digest("SHA-256", exported);
  const hashArray = Array.from(new Uint8Array(hash));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}
