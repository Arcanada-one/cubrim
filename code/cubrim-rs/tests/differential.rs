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
