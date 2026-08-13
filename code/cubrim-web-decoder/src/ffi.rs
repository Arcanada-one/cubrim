//! Handle-based native C ABI for the streaming decoder (CUBR-0079).
//!
//! The wasm ABI in [`crate::wasm`] keeps its stream state in a `thread_local`
//! single slot — correct for a wasm module, whose instance IS the isolation
//! unit, and **wrong for a native embedder**: Chromium's network service
//! interleaves many response streams on one task-runner thread, and a second
//! concurrent stream would silently clobber the first. This module is the
//! native surface: every stream is an owned heap object behind an opaque
//! pointer, so any number of streams interleave freely on any threads (one
//! stream must not be used from two threads at once — same contract as any
//! C object).
//!
//! Contract (all functions total; no panic crosses the boundary):
//!
//! ```text
//! cbm_ffi_abi_version() -> 1
//! cbm_stream_new(max_output) -> handle | NULL      max_output 0 = default
//! cbm_stream_push(h, ptr, len) -> 1 | 0            0 = error, message set
//! cbm_stream_fresh_ptr/len(h)                      bytes newly decoded by
//!                                                  the LAST push; valid
//!                                                  until the next call on h
//! cbm_stream_declared_len(h) -> u64                u64::MAX until the header
//! cbm_stream_finish(h) -> 1 | 0                    verifies length+checksum
//! cbm_stream_error_ptr/len(h)                      UTF-8, last failure
//! cbm_stream_free(h)                               always safe, accepts NULL
//! ```
//!
//! After a `push` or `finish` returns 0 the stream is poisoned: further
//! pushes fail with the same message. `finish` may be called exactly once;
//! the caller frees the handle in every path.

use alloc::string::{String, ToString};
use alloc::vec::Vec;

use crate::{DecodeLimits, StreamDecoder};

/// Opaque stream object. `decoder` is `None` after finish or a fatal error.
pub struct CbmStream {
    decoder: Option<StreamDecoder>,
    /// Bytes newly produced by the last `push`, copied out so the pointer
    /// stays valid regardless of the decoder's internal reallocation.
    fresh: Vec<u8>,
    error: String,
}

impl CbmStream {
    fn poison(&mut self, message: &str) {
        if self.error.is_empty() {
            self.error = message.to_string();
        }
        self.decoder = None;
        self.fresh = Vec::new();
    }
}

/// Bump when the surface above changes shape.
#[no_mangle]
pub extern "C" fn cbm_ffi_abi_version() -> u32 {
    1
}

/// # Safety
/// Returns an owned pointer; release it with [`cbm_stream_free`].
#[no_mangle]
pub extern "C" fn cbm_stream_new(max_output: usize) -> *mut CbmStream {
    let mut limits = DecodeLimits::default();
    if max_output != 0 {
        limits.max_output_size = max_output;
    }
    let stream = CbmStream {
        decoder: Some(StreamDecoder::new(limits)),
        fresh: Vec::new(),
        error: String::new(),
    };
    alloc::boxed::Box::into_raw(alloc::boxed::Box::new(stream))
}

/// # Safety
/// `handle` must be a live pointer from [`cbm_stream_new`]; `ptr` must be
/// readable for `len` bytes. NULL handle returns 0.
#[no_mangle]
pub unsafe extern "C" fn cbm_stream_push(
    handle: *mut CbmStream,
    ptr: *const u8,
    len: usize,
) -> i32 {
    let Some(stream) = (unsafe { handle.as_mut() }) else {
        return 0;
    };
    if stream.decoder.is_none() {
        if stream.error.is_empty() {
            stream.error = "push after finish".to_string();
        }
        stream.fresh = Vec::new();
        return 0;
    }
    if ptr.is_null() && len != 0 {
        stream.poison("null input pointer");
        return 0;
    }
    let Some(decoder) = stream.decoder.as_mut() else {
        stream.poison("push after finish");
        return 0;
    };
    let chunk = if len == 0 {
        &[][..]
    } else {
        unsafe { core::slice::from_raw_parts(ptr, len) }
    };
    match decoder.push_into(chunk, &mut stream.fresh) {
        Ok(()) => 1,
        Err(e) => {
            let message = e.to_string();
            stream.poison(&message);
            0
        }
    }
}

/// # Safety
/// `handle` must be live. The pointer is valid until the next call on this
/// handle. NULL handle returns NULL/0.
#[no_mangle]
pub unsafe extern "C" fn cbm_stream_fresh_ptr(handle: *const CbmStream) -> *const u8 {
    match unsafe { handle.as_ref() } {
        Some(s) => s.fresh.as_ptr(),
        None => core::ptr::null(),
    }
}

/// # Safety
/// `handle` must be live or NULL.
#[no_mangle]
pub unsafe extern "C" fn cbm_stream_fresh_len(handle: *const CbmStream) -> usize {
    match unsafe { handle.as_ref() } {
        Some(s) => s.fresh.len(),
        None => 0,
    }
}

/// The frame's declared decoded length, or `u64::MAX` until the header has
/// arrived (or on NULL). Lets the embedder pre-check its own output budget
/// before decoding a single block.
///
/// # Safety
/// `handle` must be live or NULL.
#[no_mangle]
pub unsafe extern "C" fn cbm_stream_declared_len(handle: *const CbmStream) -> u64 {
    match unsafe { handle.as_ref() } {
        Some(s) => s
            .decoder
            .as_ref()
            .and_then(|d| d.declared_len())
            .map(|l| l as u64)
            .unwrap_or(u64::MAX),
        None => u64::MAX,
    }
}

/// Verify the completed frame (declared length + whole-stream checksum).
/// All decoded bytes were already handed out through the fresh window; this
/// call only decides whether they were authentic.
///
/// # Safety
/// `handle` must be live. NULL returns 0.
#[no_mangle]
pub unsafe extern "C" fn cbm_stream_finish(handle: *mut CbmStream) -> i32 {
    let Some(stream) = (unsafe { handle.as_mut() }) else {
        return 0;
    };
    let Some(decoder) = stream.decoder.take() else {
        if stream.error.is_empty() {
            stream.error = "finish after finish".to_string();
        }
        return 0;
    };
    stream.fresh = Vec::new();
    match decoder.finish() {
        Ok(_verified) => 1,
        Err(e) => {
            stream.error = e.to_string();
            0
        }
    }
}

/// # Safety
/// `handle` must be live or NULL.
#[no_mangle]
pub unsafe extern "C" fn cbm_stream_error_ptr(handle: *const CbmStream) -> *const u8 {
    match unsafe { handle.as_ref() } {
        Some(s) => s.error.as_ptr(),
        None => core::ptr::null(),
    }
}

/// # Safety
/// `handle` must be live or NULL.
#[no_mangle]
pub unsafe extern "C" fn cbm_stream_error_len(handle: *const CbmStream) -> usize {
    match unsafe { handle.as_ref() } {
        Some(s) => s.error.len(),
        None => 0,
    }
}

/// # Safety
/// `handle` must be NULL or a pointer from [`cbm_stream_new`] not yet freed.
#[no_mangle]
pub unsafe extern "C" fn cbm_stream_free(handle: *mut CbmStream) {
    if !handle.is_null() {
        drop(unsafe { alloc::boxed::Box::from_raw(handle) });
    }
}
