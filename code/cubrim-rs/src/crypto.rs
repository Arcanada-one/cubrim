#![forbid(unsafe_code)]

use aes_gcm::aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Key, Nonce};
use argon2::{Algorithm, Argon2, Params, Version};
use rand::RngCore;

use crate::AppError;

pub const SALT_LEN: usize = 16;
pub const NONCE_LEN: usize = 12;

pub fn random_salt() -> [u8; SALT_LEN] {
    let mut salt = [0u8; SALT_LEN];
    rand::rngs::OsRng.fill_bytes(&mut salt);
    salt
}

pub fn encrypt_payload(
    plaintext: &[u8],
    password: &str,
    salt: &[u8; SALT_LEN],
) -> Result<Vec<u8>, AppError> {
    let key = derive_key(password, salt)?;
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(&key));
    let mut nonce_bytes = [0u8; NONCE_LEN];
    rand::rngs::OsRng.fill_bytes(&mut nonce_bytes);
    let ciphertext = cipher
        .encrypt(Nonce::from_slice(&nonce_bytes), plaintext)
        .map_err(|_| AppError::integrity("encryption failed"))?;
    let mut out = Vec::with_capacity(NONCE_LEN + ciphertext.len());
    out.extend_from_slice(&nonce_bytes);
    out.extend_from_slice(&ciphertext);
    Ok(out)
}

pub fn decrypt_payload(
    data: &[u8],
    password: &str,
    salt: &[u8; SALT_LEN],
) -> Result<Vec<u8>, AppError> {
    if data.len() < NONCE_LEN {
        return Err(AppError::integrity("encrypted archive is truncated"));
    }
    let key = derive_key(password, salt)?;
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(&key));
    cipher
        .decrypt(Nonce::from_slice(&data[..NONCE_LEN]), &data[NONCE_LEN..])
        .map_err(|_| {
            AppError::integrity("authentication failed: wrong password or damaged archive")
        })
}

fn derive_key(password: &str, salt: &[u8; SALT_LEN]) -> Result<[u8; 32], AppError> {
    let params = Params::new(19_456, 2, 1, Some(32))
        .map_err(|err| AppError::usage(format!("invalid Argon2 parameters: {err}")))?;
    let argon2 = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);
    let mut key = [0u8; 32];
    argon2
        .hash_password_into(password.as_bytes(), salt, &mut key)
        .map_err(|err| AppError::integrity(format!("key derivation failed: {err}")))?;
    Ok(key)
}

pub fn resolve_password(value: &Option<String>, purpose: &str) -> Result<Option<String>, AppError> {
    match value {
        None => Ok(None),
        Some(password) if password.is_empty() => {
            rpassword::prompt_password(format!("{purpose} password: "))
                .map(Some)
                .map_err(AppError::from)
        }
        Some(password) => Ok(Some(password.clone())),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_encrypt_decrypt() {
        let salt = random_salt();
        let encrypted = encrypt_payload(b"secret payload", "correct", &salt).unwrap();
        let decrypted = decrypt_payload(&encrypted, "correct", &salt).unwrap();
        assert_eq!(decrypted, b"secret payload");
    }

    #[test]
    fn wrong_password_fails() {
        let salt = random_salt();
        let encrypted = encrypt_payload(b"secret payload", "correct", &salt).unwrap();
        assert!(decrypt_payload(&encrypted, "wrong", &salt).is_err());
    }
}
