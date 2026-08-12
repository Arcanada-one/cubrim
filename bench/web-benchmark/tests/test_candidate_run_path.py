"""The run path for the candidate channel.

The channel landed in #155 with no way to invoke it: `run.py` only ever called
`phase_a_adapters()`. Worse, `validate_codec_attribution` — the gate that is
supposed to stop a `Cubrim-Web` row appearing without a real Web Profile — was
imported by tests and by nothing else. It passed its own tests while guarding
nothing, which is the same shape as the scheme round-trip false green.

So the assertions here are mostly about the seam: that the gate runs during a
run, that a candidate bundle cannot wear the Phase A label, and that the
published Phase A path is untouched by any of it.
"""

import sys
import unittest
import unittest.mock
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

import run
from adapters import CodecAdapter, SubprocessExecutor, candidate_adapters, phase_a_adapters
from capabilities import PHASE_A_CODECS
from run import PhaseARunner, RedactedJournal


def _runner(tmp: Path) -> PhaseARunner:
    return PhaseARunner(
        corpus_root=tmp,
        output_root=tmp / "out",
        journal=RedactedJournal(tmp / "voids.jsonl"),
        runner_code_sha="c" * 40,
        environment={
            "cpu": "test",
            "os": "test",
            "affinity": [0],
            "admission": {"accepted": True},
        },
        config=run.RunnerConfig(),
        executor=SubprocessExecutor(5),
    )


class BundleSelfDescriptionTests(unittest.TestCase):
    """A bundle must describe the run that produced it, not a constant."""

    def _bundle_for(self, adapters):
        runner = PhaseARunner.for_bundle_only(
            runner_code_sha="c" * 40,
            environment={"admission": {"accepted": True}},
        )
        runner._adapters = tuple(adapters)
        return runner.bundle([])

    def test_the_five_incumbents_still_produce_a_phase_a_bundle(self):
        bundle = self._bundle_for(phase_a_adapters())
        self.assertEqual(bundle["phase"], "A")
        self.assertEqual(bundle["protocol"]["codecs"], list(PHASE_A_CODECS))

    def test_a_run_containing_the_candidate_is_never_labelled_phase_a(self):
        bundle = self._bundle_for(phase_a_adapters() + candidate_adapters())
        self.assertEqual(bundle["phase"], "B")
        self.assertIn("cubrim-web", bundle["protocol"]["codecs"])

    def test_a_candidate_only_run_is_also_not_phase_a(self):
        bundle = self._bundle_for(candidate_adapters())
        self.assertEqual(bundle["phase"], "B")
        self.assertEqual(bundle["protocol"]["codecs"], ["cubrim-web"])

    def test_first_decoded_byte_applicability_follows_the_adapters(self):
        # Phase A has no incremental decoder, so the metric stays unavailable
        # with the reason it always gave.
        phase_a = self._bundle_for(phase_a_adapters())
        ttfb = phase_a["applicability"]["time_to_first_decoded_byte"]
        self.assertFalse(ttfb["available"])
        self.assertEqual(ttfb["reason"], "phase_a_codecs_do_not_offer_incremental_decode")

        # The candidate decodes through the streaming reference decoder, so the
        # metric becomes applicable — asserting a hardcoded False here would have
        # silently suppressed the one metric the candidate uniquely supports.
        candidate = self._bundle_for(candidate_adapters())
        ttfb = candidate["applicability"]["time_to_first_decoded_byte"]
        self.assertTrue(ttfb["available"])
        self.assertEqual(ttfb["reason"], "an_incremental_decoder_is_present")

    def test_a_bundle_with_no_recorded_adapters_falls_back_to_phase_a(self):
        # `for_bundle_only` is used by the verifier with no adapters at all;
        # it must keep producing the historical Phase A shape.
        bundle = self._bundle_for(())
        self.assertEqual(bundle["phase"], "A")
        self.assertEqual(bundle["protocol"]["codecs"], list(PHASE_A_CODECS))


class AttributionGateIsWiredTests(unittest.TestCase):
    """The gate has to run during a run, not only in its own test file."""

    def setUp(self):
        import tempfile

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)

    def test_an_unbacked_cubrim_web_adapter_is_refused_before_any_trial(self):
        # An adapter naming itself cubrim-web while declaring no Web Profile is
        # exactly what the gate exists to stop. Before this was wired, such an
        # adapter would have run and produced rows.
        impostor = CodecAdapter(
            "cubrim-web",
            "cubrim-web",
            (),
            {"whole_buffer_decode": True, "incremental_decode": False},
            lambda path: ("cubrim-web", "encode", str(path)),
            lambda path: ("cubrim-web", "decode", str(path)),
        )
        runner = _runner(self.tmp)
        with self.assertRaisesRegex(ValueError, "real Web Profile"):
            runner.execute((), (impostor,))

    def test_a_pending_web_profile_version_is_refused(self):
        impostor = CodecAdapter(
            "cubrim-web",
            "cubrim-web",
            (),
            {
                "web_profile": True,
                "web_profile_version": "pending",
                "encode": True,
                "decode": True,
            },
            lambda path: ("cubrim-web", "encode", str(path)),
            lambda path: ("cubrim-web", "decode", str(path)),
        )
        runner = _runner(self.tmp)
        with self.assertRaisesRegex(ValueError, "real Web Profile"):
            runner.execute((), (impostor,))

    def test_the_refusal_is_journalled_so_it_is_not_a_silent_stop(self):
        impostor = CodecAdapter(
            "cubrim-web",
            "cubrim-web",
            (),
            {},
            lambda path: ("cubrim-web", "encode", str(path)),
            lambda path: ("cubrim-web", "decode", str(path)),
        )
        runner = _runner(self.tmp)
        with self.assertRaises(ValueError):
            runner.execute((), (impostor,))
        journal = (self.tmp / "voids.jsonl").read_text(encoding="utf-8")
        self.assertIn("tool_provenance_mismatch", journal)
        self.assertIn("cubrim-web", journal)

    def test_the_incumbents_pass_the_gate_untouched(self):
        # The gate returns early for anything not named cubrim-web; wiring it in
        # must not have made Phase A refusable.
        from capabilities import validate_codec_attribution

        for adapter in phase_a_adapters():
            validate_codec_attribution(adapter.name, adapter.capabilities)


class OutputPathTests(unittest.TestCase):
    def test_candidate_runs_write_a_different_file_than_the_published_bundle(self):
        # Reading the two names out of the parser's own logic, so a rename of
        # either cannot quietly point a candidate run at phase-a.json.
        source = (BENCH_DIR / "run.py").read_text(encoding="utf-8")
        self.assertIn('"candidate.json" if args.candidate else "phase-a.json"', source)

    def test_candidate_flag_exists_and_defaults_off(self):
        argv = ["--phase-a", "--check"]
        with unittest.mock.patch.object(sys, "argv", ["run.py", *argv]):
            args = run._parse_args()
        self.assertFalse(args.candidate)
        with unittest.mock.patch.object(sys, "argv", ["run.py", *argv, "--candidate"]):
            args = run._parse_args()
        self.assertTrue(args.candidate)


if __name__ == "__main__":
    unittest.main()
