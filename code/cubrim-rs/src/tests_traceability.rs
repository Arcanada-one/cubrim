// V-AC-8: Traceability gate — every module must carry a // R{n} annotation.
//
// This test reads each source module and asserts that the rule reference comment
// is present. It mirrors the prototype's test_traceability.py.

use std::fs;
use std::path::Path;

/// List of (module file, expected rule annotation fragment).
/// Each module must contain at least one `// R{n}` comment.
const MODULES_AND_RULES: &[(&str, &str)] = &[
    ("phi.rs", "// R1"),
    ("domainize.rs", "// R8"),
    ("distance_map.rs", "// R3"),
    ("rle.rs", "// R4"),
    ("bitpack.rs", "// R5"),
    ("cube.rs", "// R1"),
    ("header.rs", "// R6"),
    ("codec.rs", "// R6"),
];

#[test]
fn test_all_modules_have_rule_annotation() {
    // Find the src/ directory relative to this file at compile time.
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let src_dir = Path::new(manifest_dir).join("src");

    let mut missing = Vec::new();

    for (filename, expected_annotation) in MODULES_AND_RULES {
        let path = src_dir.join(filename);
        match fs::read_to_string(&path) {
            Ok(contents) => {
                if !contents.contains(expected_annotation) {
                    missing.push(format!(
                        "Module '{}' is missing annotation '{}'",
                        filename, expected_annotation
                    ));
                }
            }
            Err(e) => {
                missing.push(format!("Cannot read module '{}': {}", filename, e));
            }
        }
    }

    assert!(
        missing.is_empty(),
        "V-AC-8 FAIL: modules missing // R{{n}} rulebook annotations:\n{}",
        missing.join("\n")
    );
}
