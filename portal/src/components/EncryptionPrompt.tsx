import { useState, type FormEvent } from "react";

interface EncryptionPromptProps {
  onSubmit: (passphrase: string) => void;
}

export function EncryptionPrompt({ onSubmit }: EncryptionPromptProps) {
  const [passphrase, setPassphrase] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (passphrase.trim()) {
      onSubmit(passphrase);
    }
  }

  return (
    <div className="encryption-prompt">
      <h2>Encrypted Vault</h2>
      <p>Enter your vault passphrase to decrypt the contents.</p>
      <form onSubmit={handleSubmit}>
        <input
          type="password"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          placeholder="Vault passphrase"
          autoFocus
        />
        <button type="submit" disabled={!passphrase.trim()}>
          Unlock
        </button>
      </form>
    </div>
  );
}
