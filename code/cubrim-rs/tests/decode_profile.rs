#![cfg(feature = "decode-profile")]

use cubrim::{decode, encode};

#[test]
fn profile_report_has_the_six_stage_contract() {
    let report = cubrim::decode_profile::empty_report(32, 16);
    let names: Vec<&str> = report.stages.iter().map(|stage| stage.name).collect();
    assert_eq!(
        names,
        vec![
            "framing",
            "entropy",
            "transforms",
            "match_copy",
            "allocation",
            "output_materialization",
        ]
    );
    assert_eq!(report.input_bytes, 32);
    assert_eq!(report.output_bytes, 16);
    assert_eq!(report.schema_version, 1);
}

#[test]
fn profile_round_trip_records_framing_and_exact_output() {
    let input = b"profiled raw-store input".to_vec();
    let blob = encode(&input);

    cubrim::decode_profile::begin(blob.len());
    let (decoded, total) = cubrim::decode_profile::measure_total(|| decode(&blob));
    let output = decoded.expect("profiled decode");
    let report = cubrim::decode_profile::finish(output.len()).expect("active profile");
    let mut report = report;
    report.set_total(total);
    cubrim::decode_profile::assign_residual_stage(
        &mut report,
        cubrim::decode_profile::Stage::OutputMaterialization,
        total,
    );

    assert_eq!(output, input);
    assert!(report
        .stages
        .iter()
        .find(|stage| stage.name == "framing")
        .is_some_and(|stage| stage.calls > 0));
    assert!(report
        .stages
        .iter()
        .find(|stage| stage.name == "output_materialization")
        .is_some_and(|stage| stage.calls > 0));
}
