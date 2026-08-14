"""The candidate channel, and the guarantee that it leaves Phase A alone.

Cubrim-Web is our own codec. Measuring it beside the incumbents is the point of
the exercise and also the easiest place in this repository to accidentally
publish a flattering number, so most of what is asserted here is what the
candidate is *not* allowed to do: it cannot enter the published five-codec
comparison, it cannot inherit the incumbents' provenance contract, and it
cannot be attributed at all without a real Web Profile capability.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

import adapters
from adapters import (
    CUBRIM_WEB_CRATE,
    adapter_for,
    candidate_adapter_for,
    candidate_adapters,
    phase_a_adapters,
)
from capabilities import (
    CANDIDATE_CODECS,
    PHASE_A_CODECS,
    require_candidate_codec,
    validate_codec_attribution,
)


class ChannelSeparationTests(unittest.TestCase):
    def test_the_published_phase_a_list_is_exactly_the_five_incumbents(self):
        # If this ever changes, every existing bundle, canonical fingerprint and
        # database row silently means something different.
        self.assertEqual(
            PHASE_A_CODECS,
            ("gzip-9", "brotli-11", "brotli-5", "zstd-19", "zstd-3"),
        )
        self.assertNotIn("cubrim-web", PHASE_A_CODECS)
        self.assertEqual(
            [a.name for a in phase_a_adapters()], list(PHASE_A_CODECS)
        )

    def test_the_candidate_cannot_be_fetched_through_the_phase_a_entry_point(self):
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            adapter_for("cubrim-web")

    def test_an_incumbent_cannot_be_smuggled_in_as_a_candidate(self):
        for incumbent in PHASE_A_CODECS:
            with self.assertRaisesRegex(ValueError, "incumbent"):
                require_candidate_codec(incumbent)

    def test_candidate_allowlist_is_closed(self):
        self.assertEqual(CANDIDATE_CODECS, ("cubrim-web",))
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            require_candidate_codec("cubrim-web-but-faster")


class CandidateAdapterTests(unittest.TestCase):
    def test_argv_mirrors_the_incumbents_file_in_stdout_out_shape(self):
        adapter = candidate_adapter_for("cubrim-web")
        path = Path("/corpus/tailwind.css")
        self.assertEqual(
            adapter.compress_argv(path), ("cubrim-web", "encode", str(path))
        )
        self.assertEqual(
            adapter.decompress_argv(path),
            ("cubrim-web", "decode", "--stream", "--chunk", "65536", str(path)),
        )

    def test_the_candidate_declares_an_incremental_decoder(self):
        # This is the one capability no incumbent here has, and it is the reason
        # first-decoded-byte is measurable for the candidate at all.
        capabilities = candidate_adapter_for("cubrim-web").capabilities
        self.assertTrue(capabilities["incremental_decode"])
        for incumbent in phase_a_adapters():
            self.assertFalse(incumbent.capabilities["incremental_decode"])

    def test_declared_capabilities_actually_satisfy_the_attribution_gate(self):
        # The gate and the adapter are written in different files; a capability
        # dict that does not pass its own gate would fail only at run time.
        validate_codec_attribution(
            "cubrim-web", candidate_adapter_for("cubrim-web").capabilities
        )

    def test_candidate_supplies_its_own_provenance_and_incumbents_do_not(self):
        self.assertIsNotNone(candidate_adapter_for("cubrim-web")._identity_factory)
        for incumbent in phase_a_adapters():
            self.assertIsNone(incumbent._identity_factory)


FAKE_SHA = "a" * 40


class CandidateProvenanceTests(unittest.TestCase):
    """The identity path, which is where a first-party binary can lie.

    `_git_code_sha` is patched throughout. Letting these tests read the real
    HEAD would make them pass only on a clean checkout — green in CI, red for
    anyone with uncommitted work, and silent about which. The clean-tree
    requirement is a property of the identity path, so it is asserted directly
    below rather than imposed on every test in the class.
    """

    def setUp(self):
        import run
        import tempfile

        patcher = patch.object(run, "_git_code_sha", return_value=FAKE_SHA)
        self.git_code_sha = patcher.start()
        self.addCleanup(patcher.stop)

        # A stand-in binary, so these tests do not require a release build to
        # exist. What is under test is the identity path, not the executable.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.binary = Path(directory.name) / "cubrim-web"
        self.binary.write_bytes(b"not a real executable, only its identity")
        self.crate_version = adapters._crate_version(CUBRIM_WEB_CRATE / "Cargo.toml")

        binary_patcher = patch.object(
            adapters, "_cubrim_web_binary", return_value=self.binary
        )
        binary_patcher.start()
        self.addCleanup(binary_patcher.stop)

        version_patcher = patch.object(
            adapters,
            "_tool_version",
            return_value=f"cubrim-web {self.crate_version}",
        )
        self.tool_version = version_patcher.start()
        self.addCleanup(version_patcher.stop)

    def _identity(self):
        return candidate_adapter_for("cubrim-web").identity()

    def test_provenance_demands_a_clean_committed_tree(self):
        self._identity()
        self.git_code_sha.assert_called_once_with(require_clean=True)

    def test_a_stale_binary_is_refused_rather_than_measured(self):
        self.tool_version.return_value = "cubrim-web 0.0.1"
        with self.assertRaisesRegex(ValueError, "stale, rebuild"):
            self._identity()

    def test_a_binary_under_another_name_is_refused(self):
        impostor = self.binary.with_name("brotli")
        impostor.write_bytes(b"wrong tool")
        with patch.object(adapters, "_cubrim_web_binary", return_value=impostor):
            with self.assertRaisesRegex(ValueError, "must be named cubrim-web"):
                self._identity()

    def test_provenance_records_the_reconstructible_triple(self):
        identity = self._identity()
        # commit, build command, resulting hash — the three things a third party
        # needs to rebuild this binary and compare.
        self.assertEqual(identity.upstream_release_sha, FAKE_SHA)
        self.assertIn("cargo build --locked --release", identity.upstream_source_reference)
        self.assertIn(identity.upstream_release_sha, identity.upstream_source_reference)
        self.assertRegex(identity.binary_sha256, r"\A[0-9a-f]{64}\Z")
        self.assertEqual(identity.binary_package, "cubrim-web-cli")
        self.assertEqual(identity.source_package, "cubrim")

    def test_the_binary_hash_is_of_the_binary_actually_resolved(self):
        identity = self._identity()
        resolved = Path(identity.binary_path)
        self.assertTrue(resolved.is_file())
        self.assertEqual(adapters.hash_file(resolved), identity.binary_sha256)

    def test_build_provenance_digest_changes_with_the_binary(self):
        identity = self._identity()
        mutated = adapters.compute_build_provenance_sha256(
            adapters.ToolIdentity(
                **{
                    **identity.__dict__,
                    "binary_sha256": "0" * 64,
                }
            )
        )
        self.assertNotEqual(mutated, identity.codec_build_provenance_sha256)


class CrateVersionParsingTests(unittest.TestCase):
    """`version =` appears under several tables; reading the wrong one would
    silently attribute a measurement to a version that does not exist."""

    def _parse(self, text: str) -> str:
        import tempfile

        with tempfile.NamedTemporaryFile(
            "w", suffix=".toml", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(text)
            path = Path(handle.name)
        self.addCleanup(path.unlink)
        return adapters._crate_version(path)

    def test_reads_the_package_version_not_a_dependency_version(self):
        self.assertEqual(
            self._parse(
                '[package]\nname = "cubrim-web-cli"\nversion = "0.1.0"\n\n'
                '[dependencies]\nblake3 = { version = "1.8.5" }\n'
            ),
            "0.1.0",
        )

    def test_a_table_before_package_does_not_shadow_it(self):
        self.assertEqual(
            self._parse(
                '[workspace]\nversion = "9.9.9"\n\n[package]\nversion = "0.1.0"\n'
            ),
            "0.1.0",
        )

    def test_the_real_manifest_parses_to_a_plausible_version(self):
        version = adapters._crate_version(CUBRIM_WEB_CRATE / "Cargo.toml")
        self.assertRegex(version, r"\A\d+\.\d+\.\d+")

    def test_a_manifest_without_a_package_table_is_an_error(self):
        with self.assertRaisesRegex(ValueError, r"no \[package\] version"):
            self._parse('[dependencies]\nversion = "9.9.9"\n')


if __name__ == "__main__":
    unittest.main()
