//! Cubrim-2 Addressor: fleet CAS/dedup router over Cubrim-1.
//! Core A (identity/CDC router) + infrastructure; Core B (delta) in delta.rs.

pub mod cas;
pub mod catalog;
pub mod chunker;
pub mod error;
pub mod format;
pub mod lite;
pub mod refs;
pub mod residual;
pub mod router;
