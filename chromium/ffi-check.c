// Native C consumer of the cubrim-web-decoder C ABI — CUBR-0079 P0 proof.
//
// The Chromium patch consumes the reference decoder through exactly this
// surface (vendored rust_static_library, C ABI from src/wasm.rs — the module
// is not wasm-gated and builds natively). This program is the standing proof
// that the surface works outside wasm: byte-exact decode of a golden frame,
// clean rejection of a corrupted one, no crash across the FFI boundary.
//
// Build & run (from code/cubrim-web-decoder):
//   cargo build --release        # produces target/release/libcubrim_web_decoder.so
//   gcc -O2 -o ffi-check ../../chromium/ffi-check.c \
//       -L target/release -lcubrim_web_decoder -Wl,-rpath,$PWD/target/release
//   ./ffi-check <fixtures>/tailwind.css.cbr <fixtures>/tailwind.css
//
// Verified 2026-08-12 on cubrim main 53276b3: abi=1, byte-exact 65257 bytes
// from a 10361-byte frame, corrupt frame rejected with
// "invalid distance 24640 (output length 20241)".

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

extern uint32_t cbr_abi_version(void);
extern uint8_t* cbr_alloc(size_t len);
extern void     cbr_free(uint8_t* ptr, size_t len);
extern int32_t  cbr_decode(const uint8_t* ptr, size_t len, size_t max_out);
extern const uint8_t* cbr_out_ptr(void);
extern size_t   cbr_out_len(void);
extern void     cbr_out_clear(void);
extern const uint8_t* cbr_last_error_ptr(void);
extern size_t   cbr_last_error_len(void);

static uint8_t* read_file(const char* path, long* out_len) {
    FILE* f = fopen(path, "rb");
    if (!f) { perror(path); return NULL; }
    fseek(f, 0, SEEK_END);
    *out_len = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t* buf = malloc(*out_len);
    if (!buf || fread(buf, 1, *out_len, f) != (size_t)*out_len) {
        fclose(f);
        free(buf);
        return NULL;
    }
    fclose(f);
    return buf;
}

int main(int argc, char** argv) {
    if (argc != 3) { fprintf(stderr, "usage: ffi-check <frame> <original>\n"); return 2; }
    printf("abi=%u\n", cbr_abi_version());

    long flen, olen;
    uint8_t* frame = read_file(argv[1], &flen);
    uint8_t* orig = read_file(argv[2], &olen);
    if (!frame || !orig) return 2;

    // 1. Byte-exact decode of the golden frame.
    uint8_t* in = cbr_alloc(flen);
    memcpy(in, frame, flen);
    if (cbr_decode(in, flen, 64u << 20) != 1) {
        fprintf(stderr, "decode failed: %.*s\n",
                (int)cbr_last_error_len(), cbr_last_error_ptr());
        return 1;
    }
    cbr_free(in, flen);
    if ((long)cbr_out_len() != olen || memcmp(cbr_out_ptr(), orig, olen) != 0) {
        fprintf(stderr, "MISMATCH: decoded %zu vs original %ld\n", cbr_out_len(), olen);
        return 1;
    }
    cbr_out_clear();
    printf("byte-exact: %ld bytes decoded from %ld-byte frame\n", olen, flen);

    // 2. Corrupted frame must fail cleanly with a message — never crash.
    uint8_t* bad = cbr_alloc(flen);
    memcpy(bad, frame, flen);
    bad[flen / 2] ^= 0xFF;
    if (cbr_decode(bad, flen, 64u << 20) == 1) {
        fprintf(stderr, "corrupt frame ACCEPTED — that is the bug\n");
        return 1;
    }
    printf("corrupt frame rejected: %.*s\n",
           (int)cbr_last_error_len(), cbr_last_error_ptr());
    cbr_free(bad, flen);
    cbr_out_clear();

    free(frame);
    free(orig);
    return 0;
}
