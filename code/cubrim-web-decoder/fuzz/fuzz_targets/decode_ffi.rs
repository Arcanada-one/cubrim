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
    let mut input = data.to_vec();
    if input.len() >= 14 {
        input[0..4].copy_from_slice(&[0xCB, b'R', b'I', b'M']);
        input[4] = 1;
        input[5] = 18;
    }

    let handle = cbm_stream_new(4 << 20);
    if handle.is_null() {
        return;
    }

    unsafe {
        let split = input.len() / 2;
        let first = cbm_stream_push(handle, input.as_ptr(), split);
        let second = cbm_stream_push(handle, input[split..].as_ptr(), input.len() - split);
        if first == 0 || second == 0 {
            let _ = cbm_stream_push(handle, input.as_ptr(), input.len());
        }
        let fresh_len = cbm_stream_fresh_len(handle);
        let fresh_ptr = cbm_stream_fresh_ptr(handle);
        if fresh_len > 0 && !fresh_ptr.is_null() {
            let _ = core::slice::from_raw_parts(fresh_ptr, fresh_len);
        }
        let _ = cbm_stream_declared_len(handle);
        let _ = cbm_stream_finish(handle);
        cbm_stream_free(handle);

        let bad = cbm_stream_new(4 << 20);
        if !bad.is_null() {
            let _ = cbm_stream_push(bad, core::ptr::null(), 1);
            let _ = cbm_stream_push(bad, input.as_ptr(), input.len());
            let _ = cbm_stream_finish(bad);
            cbm_stream_free(bad);
        }
    }
});
