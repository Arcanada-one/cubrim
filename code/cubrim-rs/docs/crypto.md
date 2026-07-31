# Cubrim Archive Crypto

Encrypted `.cbr` archives use authenticated encryption:

- KDF: Argon2id from the RustCrypto `argon2` crate.
- KDF parameters: 19,456 KiB memory, 2 iterations, parallelism 1, 32-byte key.
- Cipher: AES-256-GCM from the RustCrypto `aes-gcm` crate.
- Salt: 16 random bytes per archive.
- Nonce: 12 random bytes per archive.

The archive payload, including file names and metadata, is encrypted. The outer
magic, version, salt, and nonce remain clear so the reader can identify the
format and derive the key.

Wrong passwords and tampering both fail through GCM authentication and are
reported as authentication failure. Cubrim does not implement custom
cryptographic primitives.
