#![cfg(feature = "decode-profile")]

use cubrim::{decode, encode};
use serde_json::Value;

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
    assert_eq!(report.substage_schema_version, 1);
    let substage_names: Vec<&str> = report.substages.iter().map(|row| row.name).collect();
    assert_eq!(
        substage_names,
        vec![
            "transforms.start_byte",
            "entropy.predict_bit",
            "entropy.range_get_freq",
            "entropy.range_decode",
            "transforms.update_bit",
            "transforms.end_byte",
        ]
    );

    let json = serde_json::to_value(&report).expect("profile report serializes");
    assert_eq!(json["model_split_schema_version"], Value::from(1));
    assert_eq!(
        json["model_splits"]
            .as_array()
            .expect("model split rows")
            .iter()
            .map(|row| row["name"].as_str().expect("split name"))
            .collect::<Vec<_>>(),
        vec![
            "model.counter_state_lookup",
            "model.dot_products",
            "model.adaptation",
        ]
    );
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
