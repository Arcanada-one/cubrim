import unittest
import struct

from documentation.ephemeral.research import probe_fh2_07_typed_fields as probe


class ArithmeticCoderTests(unittest.TestCase):
    def test_binary_arithmetic_coder_round_trips_adaptive_contexts(self):
        bits = [int(ch) for ch in "001011101001111000101010"]
        contexts = [(index % 3, index % 5) for index in range(len(bits))]

        payload = probe.encode_bits(bits, contexts)

        self.assertEqual(probe.decode_bits(payload, contexts, len(bits)), bits)


def smooth_float_records(records=96):
    output = bytearray()
    for row in range(records):
        for field in range(7):
            value = field * 1000.0 + row * (field + 1) * 0.125
            output.extend(struct.pack("<f", value))
    return bytes(output)


class RecordModelTests(unittest.TestCase):
    def test_detects_28_byte_stride_and_selects_value_fields_where_they_win(self):
        data = smooth_float_records(128)

        width = probe.detect_width(data, minimum_size=256)
        schema = probe.detect_schema(data, width, training_records=128)

        self.assertEqual(width, 28)
        self.assertEqual(sum(field.width for field in schema), 28)
        self.assertEqual([field.offset for field in schema],
                         [sum(prior.width for prior in schema[:index])
                          for index in range(len(schema))])
        self.assertGreaterEqual(sum(field.kind == "f32le" for field in schema), 2)

    def test_baseline_and_typed_archives_round_trip(self):
        data = smooth_float_records(40)
        schema = [probe.Field(offset, "f32le") for offset in range(0, 28, 4)]

        for variant in ("baseline", "typed"):
            with self.subTest(variant=variant):
                blob, _ = probe.encode_archive(data, 28, schema, variant)
                self.assertEqual(probe.decode_archive(blob), data)

    def test_typed_context_does_not_look_past_stop_position(self):
        original = smooth_float_records(20)
        stop = 28 * 8 + 11
        poisoned = original[:stop] + bytes(byte ^ 0xA5 for byte in original[stop:])
        schema = [probe.Field(offset, "f32le") for offset in range(0, 28, 4)]

        before = probe.context_trace(original, 28, schema, "typed", stop)
        after = probe.context_trace(poisoned, 28, schema, "typed", stop)

        self.assertEqual(before, after)

    def test_typed_archive_charges_transmitted_schema(self):
        data = smooth_float_records(12)
        schema = [probe.Field(offset, "f32le") for offset in range(0, 28, 4)]

        baseline_blob, baseline = probe.encode_archive(data, 28, schema, "baseline")
        typed_blob, typed = probe.encode_archive(data, 28, schema, "typed")

        self.assertEqual(baseline["charged_size"], len(baseline_blob))
        self.assertEqual(typed["charged_size"], len(typed_blob))
        self.assertEqual(typed["schema_bytes"], len(schema))
        self.assertEqual(baseline["schema_bytes"], 0)

    def test_run_probe_reports_paired_sizes_and_round_trips(self):
        data = smooth_float_records(24)
        schema = [probe.Field(offset, "f32le") for offset in range(0, 28, 4)]

        result = probe.run_probe(data, 28, schema)

        self.assertEqual(result["input_size"], len(data))
        self.assertTrue(result["baseline"]["roundtrip"])
        self.assertTrue(result["typed"]["roundtrip"])
        self.assertEqual(result["baseline"]["charged_size"],
                         result["baseline"]["archive_size"])
        self.assertEqual(result["typed"]["charged_size"],
                         result["typed"]["archive_size"])


if __name__ == "__main__":
    unittest.main()
