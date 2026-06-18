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
