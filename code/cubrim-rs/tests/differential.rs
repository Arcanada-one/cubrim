// V-AC-7: Cross-implementation differential parity test.
//
// Asserts:
//   1. rust_encode(x) == python_encode(x)  (byte-identical blobs)
//   2. rust_decode(python_blob) == x       (Rust reads Python output)
//
// Python fixture blobs were captured from cubrim_proto.codec.encode()
// and committed to tests/fixtures/. They are the ground truth.

use std::fs;
use std::path::Path;

fn fixture_path(name: &str) -> std::path::PathBuf {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    Path::new(manifest_dir).join("tests").join("fixtures").join(name)
}

/// Differential fixture: (name, input_bytes, python_blob_bytes)
fn load_fixture(name: &str) -> (Vec<u8>, Vec<u8>) {
    let input = fs::read(fixture_path(&format!("{name}.input")))
        .unwrap_or_else(|e| panic!("Cannot read fixture {name}.input: {e}"));
    let python_blob = fs::read(fixture_path(&format!("{name}.python_blob")))
        .unwrap_or_else(|e| panic!("Cannot read fixture {name}.python_blob: {e}"));
    (input, python_blob)
}

macro_rules! differential_test {
    ($name:ident) => {
        #[test]
        fn $name() {
            let fixture_name = stringify!($name);
            let (input, python_blob) = load_fixture(fixture_name);

            // Test 1: rust_encode(x) byte-identical to python_encode(x)
            let rust_blob = cubrim::encode(&input);
            assert_eq!(
                rust_blob, python_blob,
                "V-AC-7 FAIL [{fixture_name}]: Rust blob ({} bytes) != Python blob ({} bytes). First diff at byte {}",
                rust_blob.len(), python_blob.len(),
                rust_blob.iter().zip(python_blob.iter()).position(|(a, b)| a != b).unwrap_or(usize::MAX)
            );

            // Test 2: rust_decode(python_blob) == original input
            let recovered = cubrim::decode(&python_blob)
                .unwrap_or_else(|e| panic!("V-AC-7 FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}"));
            assert_eq!(
                recovered, input,
                "V-AC-7 FAIL [{fixture_name}]: rust_decode(python_blob) != original input"
            );
        }
    };
}

differential_test!(hello_world_test);
differential_test!(empty);
differential_test!(single_byte);
differential_test!(all_same_100);
differential_test!(all_distinct_256);
differential_test!(text_1kb);
differential_test!(random_1kb);

/// Entropy differential parity test.
///
/// Asserts:
///   1. rust_encode_entropy(x) == python_encode_entropy(x)  (byte-identical blobs)
///   2. rust_decode(python_entropy_blob) == x                (cross-decode: Rust reads Python output)
///   3. rust_decode(rust_entropy_blob) == x                  (Rust round-trip on its own blob)
///
/// Fixture was captured by cubrim_proto.codec.encode(x, value_scheme=VALUE_SCHEME_ENTROPY).
/// SHA256: input=6054930ecdf15ca4c8a0c3d3f412d06d2b4ca4fbcb96902454793cda228efd17
///         blob =ad5ec425ba0080f9ed85c5e27bc8ba1150397b56345ba7c9fb697ddde183123e
#[test]
fn text_entropy() {
    use cubrim::{EncodeConfig, GapScheme, ValueScheme, encode_with_config, decode};

    let fixture_name = "text_entropy";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::Entropy,
    };

    // Test 1: rust_encode_entropy(x) byte-identical to python_encode_entropy(x)
    let rust_blob = encode_with_config(&input, &config);
    assert_eq!(
        rust_blob, python_blob,
        "Entropy parity FAIL [{fixture_name}]: Rust blob ({} bytes) != Python blob ({} bytes). First diff at byte {}",
        rust_blob.len(), python_blob.len(),
        rust_blob.iter().zip(python_blob.iter()).position(|(a, b)| a != b).unwrap_or(usize::MAX)
    );

    // Test 2: rust_decode(python_entropy_blob) == original input (cross-decode)
    let recovered_from_python = decode(&python_blob)
        .unwrap_or_else(|e| panic!("Entropy parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}"));
    assert_eq!(
        recovered_from_python, input,
        "Entropy parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input"
    );

    // Test 3: Rust round-trip on its own blob (redundant but explicit)
    let recovered_from_rust = decode(&rust_blob)
        .unwrap_or_else(|e| panic!("Entropy parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}"));
    assert_eq!(
        recovered_from_rust, input,
        "Entropy parity FAIL [{fixture_name}]: rust_decode(rust_blob) != original input"
    );
}

/// EntropyContext (T4) differential parity test.
///
/// Asserts:
///   1. rust_encode_entropy_context(x) == python_encode_entropy_context(x)  (byte-identical blobs)
///   2. rust_decode(python_entropy_context_blob) == x                         (cross-decode: Rust reads Python output)
///   3. rust_decode(rust_entropy_context_blob) == x                           (Rust round-trip on its own blob)
///
/// Fixture was captured by cubrim_proto.codec.encode(x, value_scheme=VALUE_SCHEME_ENTROPY_CONTEXT).
/// SHA256: input=0160b7a1b4311fa6b273b63125f8cff4603205d8dc7fcc7cf9186691570c5415
///         blob =29f5de04681c4a8ec07bf2646113badf4b179d96c8401254951937d1fd69dfdd
#[test]
fn text_entropy_context() {
    use cubrim::{EncodeConfig, GapScheme, ValueScheme, encode_with_config, decode};

    let fixture_name = "text_entropy_context";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::EntropyContext,
    };

    // Test 1: rust_encode_entropy_context(x) byte-identical to python_encode_entropy_context(x)
    let rust_blob = encode_with_config(&input, &config);
    assert_eq!(
        rust_blob, python_blob,
        "EntropyContext parity FAIL [{fixture_name}]: Rust blob ({} bytes) != Python blob ({} bytes). First diff at byte {}",
        rust_blob.len(), python_blob.len(),
        rust_blob.iter().zip(python_blob.iter()).position(|(a, b)| a != b).unwrap_or(usize::MAX)
    );

    // Test 2: rust_decode(python_entropy_context_blob) == original input (cross-decode)
    let recovered_from_python = decode(&python_blob)
        .unwrap_or_else(|e| panic!("EntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}"));
    assert_eq!(
        recovered_from_python, input,
        "EntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input"
    );

    // Test 3: Rust round-trip on its own blob (redundant but explicit)
    let recovered_from_rust = decode(&rust_blob)
        .unwrap_or_else(|e| panic!("EntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}"));
    assert_eq!(
        recovered_from_rust, input,
        "EntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) != original input"
    );
}

/// BwtEntropyContext (T5) differential parity — text-like input.
///
/// Closes DO-1 from QA: AC-3 promised a Python-twin differential oracle for the BWT path
/// (scheme byte 5). Three assertions per fixture mirror the T3/T4 differential structure:
///   1. rust_encode_bwt(x) == python_encode_bwt(x)  (byte-identical blobs)
///   2. rust_decode(python_bwt_blob) == x             (cross-decode: Rust reads Python output)
///   3. rust_decode(rust_bwt_blob) == x               (Rust round-trip on its own blob)
///
/// Input: "the quick brown fox…" line cycled 2048 bytes (same as Rust bwt_ec_round_trip_text_like).
/// Python blob captured from cubrim_proto.codec.encode(x, value_scheme=VALUE_SCHEME_BWT_ENTROPY_CONTEXT).
/// SHA256: input=26d874167aa31651a515b62445981bdb377f411eda2ca5ae40453f0ab7a03989
///         blob =99ccea90f3104926576a81f0168cc1b10bf1d1178d28ee967b47584417d62e5b
#[test]
fn bwt_entropy_context_text() {
    use cubrim::{EncodeConfig, GapScheme, ValueScheme, encode_with_config, decode};

    let fixture_name = "bwt_entropy_context_text";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::BwtEntropyContext,
    };

    // Test 1: rust_encode_bwt(x) byte-identical to python_encode_bwt(x)
    let rust_blob = encode_with_config(&input, &config);
    assert_eq!(
        rust_blob, python_blob,
        "BwtEntropyContext parity FAIL [{fixture_name}]: Rust blob ({} bytes) != Python blob ({} bytes). First diff at byte {}",
        rust_blob.len(), python_blob.len(),
        rust_blob.iter().zip(python_blob.iter()).position(|(a, b)| a != b).unwrap_or(usize::MAX)
    );

    // Test 2: rust_decode(python_bwt_blob) == original input (cross-decode)
    let recovered_from_python = decode(&python_blob)
        .unwrap_or_else(|e| panic!("BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}"));
    assert_eq!(
        recovered_from_python, input,
        "BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input"
    );

    // Test 3: Rust round-trip on its own blob (redundant but explicit)
    let recovered_from_rust = decode(&rust_blob)
        .unwrap_or_else(|e| panic!("BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}"));
    assert_eq!(
        recovered_from_rust, input,
        "BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) != original input"
    );
}

/// BwtEntropyContext (T5) differential parity — log-like input.
///
/// Log lines with structured repeated prefixes and numeric counters; BWT entropy
/// reduction +91.4% vs i-order baseline on this corpus class (AC-2 probe result).
/// SHA256: input=5bea23804108ec46933a081289ced8e430752e21d8d4117c94624542507ed6cb
///         blob =a84cc9b4e758351735f4179e55f6e7744f3453cf325193ecbba79c87cd8adf86
#[test]
fn bwt_entropy_context_log() {
    use cubrim::{EncodeConfig, GapScheme, ValueScheme, encode_with_config, decode};

    let fixture_name = "bwt_entropy_context_log";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::BwtEntropyContext,
    };

    // Test 1
    let rust_blob = encode_with_config(&input, &config);
    assert_eq!(
        rust_blob, python_blob,
        "BwtEntropyContext parity FAIL [{fixture_name}]: Rust blob ({} bytes) != Python blob ({} bytes). First diff at byte {}",
        rust_blob.len(), python_blob.len(),
        rust_blob.iter().zip(python_blob.iter()).position(|(a, b)| a != b).unwrap_or(usize::MAX)
    );

    // Test 2
    let recovered_from_python = decode(&python_blob)
        .unwrap_or_else(|e| panic!("BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}"));
    assert_eq!(recovered_from_python, input,
        "BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input");

    // Test 3
    let recovered_from_rust = decode(&rust_blob)
        .unwrap_or_else(|e| panic!("BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}"));
    assert_eq!(recovered_from_rust, input,
        "BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) != original input");
}

/// BwtEntropyContext (T5) differential parity — small adversarial input.
///
/// 4-symbol cyclic input, 800 bytes — tests minimal-distinct-alphabet BWT path
/// and adversarial short block (just above raw-store bound, n_distinct=4).
/// SHA256: input=f7fc0486a6feaf00e26843f61d8f175814015eb39d2c56d6dc5aa9416dc75010
///         blob =c41d983ea9e8103189ab18e74be631cf51d6980251270bc2d13a25e68c7ec829
#[test]
fn bwt_entropy_context_small() {
    use cubrim::{EncodeConfig, GapScheme, ValueScheme, encode_with_config, decode};

    let fixture_name = "bwt_entropy_context_small";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::BwtEntropyContext,
    };

    // Test 1
    let rust_blob = encode_with_config(&input, &config);
    assert_eq!(
        rust_blob, python_blob,
        "BwtEntropyContext parity FAIL [{fixture_name}]: Rust blob ({} bytes) != Python blob ({} bytes). First diff at byte {}",
        rust_blob.len(), python_blob.len(),
        rust_blob.iter().zip(python_blob.iter()).position(|(a, b)| a != b).unwrap_or(usize::MAX)
    );

    // Test 2
    let recovered_from_python = decode(&python_blob)
        .unwrap_or_else(|e| panic!("BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}"));
    assert_eq!(recovered_from_python, input,
        "BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input");

    // Test 3
    let recovered_from_rust = decode(&rust_blob)
        .unwrap_or_else(|e| panic!("BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}"));
    assert_eq!(recovered_from_rust, input,
        "BwtEntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) != original input");
}

/// RleCodes differential parity test.
///
/// Asserts:
///   1. rust_encode_rlecodes(x) == python_encode_rlecodes(x)  (byte-identical blobs)
///   2. rust_decode(python_rlecodes_blob) == x                 (cross-decode: Rust reads Python output)
///   3. rust_decode(rust_rlecodes_blob) == x                   (Rust round-trip on its own blob)
///
/// This makes the Python oracle's RleCodes decode path machine-enforced: fixture
/// sparse_clustered_rlecodes.python_blob was produced by cubrim_proto.codec.encode()
/// with value_scheme=VALUE_SCHEME_RLE_CODES. If Python decode() crashes on it, the
/// fixture capture itself fails — meaning the Python oracle fix is required before
/// fixtures can be committed.
#[test]
fn sparse_clustered_rlecodes() {
    use cubrim::{EncodeConfig, GapScheme, ValueScheme, encode_with_config, decode};

    let fixture_name = "sparse_clustered_rlecodes";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::RleCodes,
    };

    // Test 1: rust_encode_rlecodes(x) byte-identical to python_encode_rlecodes(x)
    let rust_blob = encode_with_config(&input, &config);
    assert_eq!(
        rust_blob, python_blob,
        "RleCodes parity FAIL [{fixture_name}]: Rust blob ({} bytes) != Python blob ({} bytes). First diff at byte {}",
        rust_blob.len(), python_blob.len(),
        rust_blob.iter().zip(python_blob.iter()).position(|(a, b)| a != b).unwrap_or(usize::MAX)
    );

    // Test 2: rust_decode(python_rlecodes_blob) == original input (cross-decode)
    let recovered_from_python = decode(&python_blob)
        .unwrap_or_else(|e| panic!("RleCodes parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}"));
    assert_eq!(
        recovered_from_python, input,
        "RleCodes parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input"
    );

    // Test 3: Rust round-trip on its own blob (redundant but explicit)
    let recovered_from_rust = decode(&rust_blob)
        .unwrap_or_else(|e| panic!("RleCodes parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}"));
    assert_eq!(
        recovered_from_rust, input,
        "RleCodes parity FAIL [{fixture_name}]: rust_decode(rust_blob) != original input"
    );
}
