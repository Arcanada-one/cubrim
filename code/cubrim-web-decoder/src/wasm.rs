//! Minimal C ABI for the browser, hand-rolled rather than generated.
//!
//! No `wasm-bindgen`: the module is a decoder with three entry points, and a
//! generated binding layer would add build tooling and bytes for nothing. The
//! JS side (`web/cubrim.js`) is ~40 lines against this ABI.
//!
//! Contract:
//!   `cbr_alloc(len) -> ptr`            allocate an input buffer
//!   `cbr_free(ptr, len)`               release a buffer
//!   `cbr_decode(ptr, len, max_out)`    decode; returns an output HANDLE or 0
//!   `cbr_out_ptr() -> ptr`             pointer to the last decode's output
//!   `cbr_out_len() -> len`             length of the last decode's output
//!   `cbr_last_error_ptr/len()`         UTF-8 message for the last failure
//!
//! Every entry point is total: a malformed frame returns 0 and leaves an error
//! message, and no path can panic across the ABI boundary (the crate is built
//! with `panic = "abort"`, and the decoder itself returns `Result`).

use alloc::string::String;
use alloc::vec::Vec;
use core::cell::RefCell;

use crate::{decode_with_limits, DecodeLimits};

thread_local! {
    static OUTPUT: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) };
    static LAST_ERROR: RefCell<String> = const { RefCell::new(String::new()) };
}

/// Allocate `len` bytes for the caller to write a compressed frame into.
///
/// # Safety
/// The returned pointer must be released with [`cbr_free`] using the same
/// length, and must not be used after that.
#[no_mangle]
pub extern "C" fn cbr_alloc(len: usize) -> *mut u8 {
    let mut buf = Vec::with_capacity(len);
    buf.resize(len, 0);
    let ptr = buf.as_mut_ptr();
    core::mem::forget(buf);
    ptr
}

/// Release a buffer obtained from [`cbr_alloc`].
///
/// # Safety
/// `ptr` must come from `cbr_alloc` with the same `len`, and must not be used
/// afterwards.
#[no_mangle]
pub unsafe extern "C" fn cbr_free(ptr: *mut u8, len: usize) {
    if ptr.is_null() || len == 0 {
        return;
    }
    // SAFETY: the caller guarantees this pointer/length pair came from
    // `cbr_alloc`, which built the allocation with capacity == len.
    unsafe {
        drop(Vec::from_raw_parts(ptr, len, len));
    }
}

/// Decode the frame at `ptr[..len]`, bounded by `max_out` bytes of output.
///
/// Returns 1 on success (output readable via [`cbr_out_ptr`] / [`cbr_out_len`])
/// and 0 on failure (message via [`cbr_last_error_ptr`] / [`cbr_last_error_len`]).
///
/// # Safety
/// `ptr[..len]` must be a readable buffer for the duration of the call.
#[no_mangle]
pub unsafe extern "C" fn cbr_decode(ptr: *const u8, len: usize, max_out: usize) -> u32 {
    if ptr.is_null() {
        set_error("null input pointer");
        return 0;
    }
    // SAFETY: the caller guarantees ptr[..len] is readable.
    let input = unsafe { core::slice::from_raw_parts(ptr, len) };
    let limits = DecodeLimits {
        max_output_size: if max_out == 0 {
            DecodeLimits::DEFAULT_MAX_OUTPUT
        } else {
            max_out
        },
    };
    match decode_with_limits(input, &limits) {
        Ok(out) => {
            OUTPUT.with(|slot| *slot.borrow_mut() = out);
            LAST_ERROR.with(|slot| slot.borrow_mut().clear());
            1
        }
        Err(err) => {
            OUTPUT.with(|slot| slot.borrow_mut().clear());
            set_error(&err.0);
            0
        }
    }
}

/// Pointer to the last successful decode's output.
#[no_mangle]
pub extern "C" fn cbr_out_ptr() -> *const u8 {
    OUTPUT.with(|slot| slot.borrow().as_ptr())
}

/// Length of the last successful decode's output.
#[no_mangle]
pub extern "C" fn cbr_out_len() -> usize {
    OUTPUT.with(|slot| slot.borrow().len())
}

/// Release the buffer holding the last decode's output.
#[no_mangle]
pub extern "C" fn cbr_out_clear() {
    OUTPUT.with(|slot| {
        let mut out = slot.borrow_mut();
        out.clear();
        out.shrink_to_fit();
    });
}

/// Pointer to the UTF-8 message describing the last failure.
#[no_mangle]
pub extern "C" fn cbr_last_error_ptr() -> *const u8 {
    LAST_ERROR.with(|slot| slot.borrow().as_ptr())
}

/// Length of the last failure message.
#[no_mangle]
pub extern "C" fn cbr_last_error_len() -> usize {
    LAST_ERROR.with(|slot| slot.borrow().len())
}

/// ABI version, so the JS glue can refuse a module it does not understand.
#[no_mangle]
pub extern "C" fn cbr_abi_version() -> u32 {
    1
}

fn set_error(message: &str) {
    LAST_ERROR.with(|slot| {
        let mut slot = slot.borrow_mut();
        slot.clear();
        slot.push_str(message);
    });
}
