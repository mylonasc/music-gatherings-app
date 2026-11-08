/** Non-secret deduplication token. getRandomValues also works on LAN HTTP. */
export function createIdempotencyKey(): string | undefined {
  try {
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  } catch {
    // Older/restricted browsers can still search/import without a client key.
    // Do not replace missing cryptography with a predictable security token.
    return undefined;
  }
}
