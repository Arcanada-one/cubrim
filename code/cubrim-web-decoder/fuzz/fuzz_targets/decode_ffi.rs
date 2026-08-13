//! Fuzz the native handle-based FFI boundary used by Chromium.
//!
//! This complements `decode_frame`: it exercises pointer validation, stream
//! poisoning, fresh-output accessors, and finish/free sequencing through the
//! exported `cbm_stream_*` ABI rather than calling the Rust decoder directly.
#![no_main]

use cubrim_web_decoder::ffi::{
    cbm_stream_declared_len, cbm_stream_finish, cbm_stream_fresh_len,
    cbm_stream_fresh_ptr, cbm_stream_free, cbm_stream_new, cbm_stream_push,
};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let handle = cbm_stream_new(4 << 20);
    if handle.is_null() {
        return;
    }

    unsafe {
        let _ = cbm_stream_push(handle, data.as_ptr(), data.len());
        let fresh_len = cbm_stream_fresh_len(handle);
        let fresh_ptr = cbm_stream_fresh_ptr(handle);
        if fresh_len > 0 && !fresh_ptr.is_null() {
            let _ = core::slice::from_raw_parts(fresh_ptr, fresh_len);
        }
        let _ = cbm_stream_declared_len(handle);
        let _ = cbm_stream_finish(handle);
        cbm_stream_free(handle);
    }
});
