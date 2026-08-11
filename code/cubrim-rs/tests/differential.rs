// V-AC-7: Cross-implementation differential parity test.
//
// Reoriented contract. The ≤64 KB encode freeze is open: below the cube-size limit the
// Rust encoder now also offers the strong MODE_CM2 backend and selects it whenever it is
// strictly smaller, so `rust_encode(x)` is no longer required to be byte-identical to the
// frozen v1 Python blob. Byte-equality to the frozen bytes was an internal test invariant,
// not a user-observable contract; the guarantees that ARE user contracts, and which this
// oracle now enforces, are:
//   1. lossless round-trip:        rust_decode(rust_encode(x)) == x
//   2. old-archive decode parity:  rust_decode(python_v1_blob) == x
//
// (2) is the durable back-compat guarantee: the current binary must still decode archives
// produced by the original v1 encoder. The Python fixture blobs, captured from
// cubrim_proto.codec.encode() and committed to tests/fixtures/, ARE canonical frozen-v1
// archives and serve as the old-archive corpus. They remain the decode ground truth.

use std::fs;
use std::path::Path;

fn fixture_path(name: &str) -> std::path::PathBuf {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    Path::new(manifest_dir)
        .join("tests")
        .join("fixtures")
        .join(name)
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

            // (1) lossless round-trip on the current encoder's own blob (whichever mode it
            //     selects — base v1 for these sub-2 KB fixtures, or MODE_CM2 once open).
            let rust_blob = cubrim::encode(&input);
            let rust_rt = cubrim::decode(&rust_blob).unwrap_or_else(|e| {
                panic!("V-AC-7 FAIL [{fixture_name}]: rust_decode(rust_encode(x)) error: {e}")
            });
            assert_eq!(
                rust_rt, input,
                "V-AC-7 FAIL [{fixture_name}]: round-trip rust_decode(rust_encode(x)) != x"
            );

            // (2) old-archive decode parity: the current binary decodes the frozen v1
            //     Python archive to the original plaintext.
            let recovered = cubrim::decode(&python_blob).unwrap_or_else(|e| {
                panic!("V-AC-7 FAIL [{fixture_name}]: rust_decode(python_v1_blob) error: {e}")
            });
            assert_eq!(
                recovered, input,
                "V-AC-7 FAIL [{fixture_name}]: rust_decode(python_v1_blob) != original input"
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
    use cubrim::{decode, encode_with_config, EncodeConfig, GapScheme, ValueScheme};

    let fixture_name = "text_entropy";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::Entropy,
        min_ctx_count: None,
        cm2_column_variants: true,
        cm2_max_tbits: None,
        web_profile: false,
        web_block_size: None,
    };

    // (reoriented) The value scheme still round-trips (Test 3 below); byte-equality to the
    // frozen v1 Python blob is retired now that the ≤64 KB freeze is open (see module header).
    let rust_blob = encode_with_config(&input, &config);

    // Test 2: rust_decode(python_entropy_blob) == original input (cross-decode)
    let recovered_from_python = decode(&python_blob).unwrap_or_else(|e| {
        panic!("Entropy parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}")
    });
    assert_eq!(
        recovered_from_python, input,
        "Entropy parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input"
    );

    // Test 3: Rust round-trip on its own blob (redundant but explicit)
    let recovered_from_rust = decode(&rust_blob).unwrap_or_else(|e| {
        panic!("Entropy parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}")
    });
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
    use cubrim::{decode, encode_with_config, EncodeConfig, GapScheme, ValueScheme};

    let fixture_name = "text_entropy_context";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::EntropyContext,
        min_ctx_count: None,
        cm2_column_variants: true,
        cm2_max_tbits: None,
        web_profile: false,
        web_block_size: None,
    };

    // (reoriented) The value scheme still round-trips (Test 3 below); byte-equality to the
    // frozen v1 Python blob is retired now that the ≤64 KB freeze is open (see module header).
    // This fixture is 16 KB and compressible, so the default encoder now selects MODE_CM2.
    let rust_blob = encode_with_config(&input, &config);

    // Test 2: rust_decode(python_entropy_context_blob) == original input (cross-decode)
    let recovered_from_python = decode(&python_blob).unwrap_or_else(|e| {
        panic!("EntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}")
    });
    assert_eq!(
        recovered_from_python, input,
        "EntropyContext parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input"
    );

    // Test 3: Rust round-trip on its own blob (redundant but explicit)
    let recovered_from_rust = decode(&rust_blob).unwrap_or_else(|e| {
        panic!("EntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}")
    });
    assert_eq!(
        recovered_from_rust, input,
        "EntropyContext parity FAIL [{fixture_name}]: rust_decode(rust_blob) != original input"
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
    use cubrim::{decode, encode_with_config, EncodeConfig, GapScheme, ValueScheme};

    let fixture_name = "sparse_clustered_rlecodes";
    let (input, python_blob) = load_fixture(fixture_name);

    let config = EncodeConfig {
        b: 256,
        raw_store_bound: 320,
        use_square_limit: true,
        n_override: None,
        gap_scheme: GapScheme::RleU16,
        value_scheme: ValueScheme::RleCodes,
        min_ctx_count: None,
        cm2_column_variants: true,
        cm2_max_tbits: None,
        web_profile: false,
        web_block_size: None,
    };

    // (reoriented) The value scheme still round-trips (Test 3 below); byte-equality to the
    // frozen v1 Python blob is retired now that the ≤64 KB freeze is open (see module header).
    let rust_blob = encode_with_config(&input, &config);

    // Test 2: rust_decode(python_rlecodes_blob) == original input (cross-decode)
    let recovered_from_python = decode(&python_blob).unwrap_or_else(|e| {
        panic!("RleCodes parity FAIL [{fixture_name}]: rust_decode(python_blob) error: {e}")
    });
    assert_eq!(
        recovered_from_python, input,
        "RleCodes parity FAIL [{fixture_name}]: rust_decode(python_blob) != original input"
    );

    // Test 3: Rust round-trip on its own blob (redundant but explicit)
    let recovered_from_rust = decode(&rust_blob).unwrap_or_else(|e| {
        panic!("RleCodes parity FAIL [{fixture_name}]: rust_decode(rust_blob) error: {e}")
    });
    assert_eq!(
        recovered_from_rust, input,
        "RleCodes parity FAIL [{fixture_name}]: rust_decode(rust_blob) != original input"
    );
}
