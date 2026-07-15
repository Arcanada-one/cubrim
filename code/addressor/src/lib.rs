//! Cubrim-2 Addressor: fleet CAS/dedup router over Cubrim-1.
//! Core A (identity/CDC router) + infrastructure; Core B (delta) in delta.rs.

pub mod bloom;
pub mod cas;
pub mod catalog;
pub mod chunker;
pub mod error;
pub mod format;
pub mod delta;
pub mod lite;
pub mod matrix;
pub mod merkle;
pub mod refs;
pub mod residual;
pub mod router;
