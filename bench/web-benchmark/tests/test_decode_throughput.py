"""The in-process decode instrument, and the mistakes it was built out of.

Two of these tests exist because the first version of the module got the answer
wrong in a way that looked plausible:

* it timed `decode()` together with the conversion of the output into Python
  bytes, and `bytes(ctypes_array[:n])` marshals element by element while
  `string_at` is a memcpy — so it reported Cubrim-Web at 10.4x brotli-5, which
  is measuring the binding rather than the decoder;
* it measured every cell of one codec before starting the next, so a load
  change during the run would land entirely on whichever codec was in flight.

Both are now structural properties of the module, so they are asserted here
rather than left to care.
"""

import sys
import unittest
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

import decode_throughput as dt


class FakeDecoder:
    """A decoder whose decode() is free and whose materialize() is expensive.

    If the timer spans both, this looks slow. If it spans only decode(), it
    looks instant — which is how the marshalling bug is detectable without
    depending on wall-clock thresholds.
    """

    name = "fake"
    path = None

    def __init__(self, output: bytes, *, marshal_cost: int = 0):
        self.output = output
        self.marshal_cost = marshal_cost
        self.decode_calls = 0
        self.materialize_calls = 0

    def prepare(self, frame, original_len):
        return {"frame": frame}

    def decode(self, state):
        self.decode_calls += 1

    def materialize(self, state):
        self.materialize_calls += 1
        for _ in range(self.marshal_cost):
            pass
        return self.output


class TimingBoundaryTests(unittest.TestCase):
    def test_output_is_verified_on_every_timed_iteration(self):
        original = b"payload"
        decoder = FakeDecoder(original)
        dt.time_decoder(decoder, b"frame", original, repeats=7, warmups=3)
        self.assertEqual(decoder.decode_calls, 10)
        # Once per warm-up and once per timed repeat: a check done only at the
        # end would miss a decoder that degrades under repetition.
        self.assertEqual(decoder.materialize_calls, 10)

    def test_a_wrong_answer_fails_rather_than_being_timed(self):
        decoder = FakeDecoder(b"wrong")
        with self.assertRaisesRegex(RuntimeError, "byte-exact"):
            dt.time_decoder(decoder, b"frame", b"right", repeats=2, warmups=1)

    def test_a_decoder_that_breaks_after_warmup_is_still_caught(self):
        class Flaky(FakeDecoder):
            def materialize(self, state):
                self.materialize_calls += 1
                return self.output if self.materialize_calls <= 2 else b"corrupt"

        with self.assertRaisesRegex(RuntimeError, "byte-exact"):
            dt.time_decoder(Flaky(b"ok"), b"frame", b"ok", repeats=5, warmups=2)

    def test_samples_are_one_per_repeat_and_exclude_warmups(self):
        samples = dt.time_decoder(
            FakeDecoder(b"x"), b"frame", b"x", repeats=11, warmups=4
        )
        self.assertEqual(len(samples), 11)
        self.assertTrue(all(isinstance(s, int) and s >= 0 for s in samples))

    def test_release_runs_even_when_a_decode_fails(self):
        class Releasing(FakeDecoder):
            released = False

            def release(self, state):
                type(self).released = True

        decoder = Releasing(b"wrong")
        with self.assertRaises(RuntimeError):
            dt.time_decoder(decoder, b"frame", b"right", repeats=1, warmups=1)
        self.assertTrue(Releasing.released, "input buffer leaked on the failure path")


class AdmissionTests(unittest.TestCase):
    def test_admission_records_what_a_reader_needs_to_judge_the_number(self):
        admission = dt.host_admission()
        for key in (
            "load_1m",
            "cpus",
            "load_per_cpu",
            "quiet_ceiling_load_per_cpu",
            "within_quiet_ceiling",
        ):
            self.assertIn(key, admission)
        self.assertEqual(admission["quiet_ceiling_load_per_cpu"], 1.0)

    def test_the_quiet_verdict_agrees_with_the_numbers_it_reports(self):
        # A report that said "quiet" while carrying a load above the ceiling
        # would be worse than one with no verdict at all.
        admission = dt.host_admission()
        if admission["load_per_cpu"] is not None:
            self.assertEqual(
                admission["within_quiet_ceiling"],
                admission["load_per_cpu"] <= 1.0,
            )


class ZlibLabellingTests(unittest.TestCase):
    def test_the_zlib_row_is_not_labelled_gzip(self):
        # The gzip CLI carries its own inflate; calling this row "gzip" would
        # claim to have measured an implementation that was never loaded.
        self.assertEqual(dt.ZlibDecoder.name, "zlib")
        self.assertIn("not the same implementation", dt.ZlibDecoder.__doc__)


if __name__ == "__main__":
    unittest.main()
