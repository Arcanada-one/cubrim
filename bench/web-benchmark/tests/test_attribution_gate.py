import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

import adapters
from adapters import SubprocessExecutor, adapter_for
from capabilities import (
    PHASE_A_CODECS,
    energy_capability,
    first_decoded_byte_ms,
    validate_codec_attribution,
)


def _pin_drift(codec: str) -> str | None:
    """Why `codec` cannot be provenance-checked here, or None if it can.

    Returns a reason only when the host's installed tool is not the pinned one.
    On the measurement host every pin matches, so this returns None for all five
    codecs and nothing is skipped — a drift there still fails the test.
    """
    import shutil

    adapter = adapter_for(codec)
    binary = shutil.which(adapter.binary_name)
    if binary is None:
        return f"{adapter.binary_name} is not installed on this host"
    pin = adapters.RELEASE_PINS[adapter.binary_name]
    actual = adapters._tool_version(adapter.binary_name, Path(binary).resolve())
    if actual != pin.cli_version:
        return (
            f"host {adapter.binary_name} is {actual!r}; the measurement pin is "
            f"{pin.cli_version!r} — provenance is only checkable on the pinned host"
        )
    return None


class AttributionGateTests(unittest.TestCase):
    def test_phase_a_allowlist_is_exact(self):
        # Real web transport runs the fast presets on dynamic responses and the
        # maximum ones on precompressed assets. Measuring only the archival end
        # flatters a candidate's speed and understates the ratio it must beat.
        self.assertEqual(
            PHASE_A_CODECS, ("gzip-9", "brotli-11", "brotli-5", "zstd-19", "zstd-3")
        )

    def test_cubrim_web_requires_a_real_profile_capability(self):
        with self.assertRaisesRegex(ValueError, "real Web Profile"):
            validate_codec_attribution("Cubrim-Web", {})
        with self.assertRaisesRegex(ValueError, "real Web Profile"):
            validate_codec_attribution(
                "Cubrim-Web",
                {"web_profile": True, "web_profile_version": "pending"},
            )

        validate_codec_attribution(
            "Cubrim-Web",
            {
                "web_profile": True,
                "web_profile_version": "1",
                "encode": True,
                "decode": True,
            },
        )

    def test_codec_argv_matches_the_preregistered_commands(self):
        path = Path("/tmp/input.bin")
        expected = {
            "gzip-9": (
                ("gzip", "-9", "-c", str(path)),
                ("gzip", "-d", "-c", str(path)),
            ),
            "brotli-11": (
                ("brotli", "--quality=11", "--stdout", str(path)),
                ("brotli", "--decompress", "--stdout", str(path)),
            ),
            "brotli-5": (
                ("brotli", "--quality=5", "--stdout", str(path)),
                ("brotli", "--decompress", "--stdout", str(path)),
            ),
            "zstd-19": (
                ("zstd", "-19", "--quiet", "--stdout", str(path)),
                ("zstd", "--decompress", "--quiet", "--stdout", str(path)),
            ),
            "zstd-3": (
                ("zstd", "-3", "--quiet", "--stdout", str(path)),
                ("zstd", "--decompress", "--quiet", "--stdout", str(path)),
            ),
        }
        # Every allowlisted codec must have a preregistered command pair; a new
        # preset cannot slip in without its argv being written down here first.
        self.assertEqual(tuple(expected), PHASE_A_CODECS)
        for codec, (compress, decompress) in expected.items():
            with self.subTest(codec=codec):
                self.assertEqual(adapter_for(codec).compress_argv(path), compress)
                self.assertEqual(adapter_for(codec).decompress_argv(path), decompress)

    def test_installed_releases_keep_upstream_and_build_provenance_distinct(self):
        # Two presets of one codec share a binary, so they share its upstream
        # release: the preset lives in the flags, not in a different build.
        #
        # This one reaches the host's actual toolchain, so it can only run where
        # the pinned tools are installed — on the measurement host it must run
        # in full, and a version drift there has to stay a hard failure, since
        # that is precisely the drift that would invalidate a published number.
        # Elsewhere (a hosted CI runner ships its own zstd) the affected codec
        # is skipped with both versions named, so the gap is never silent.
        expected = {
            "gzip-9": "80006351d3bb5d9099b74c41fefd6649424a9a28",
            "brotli-11": "ed738e842d2fbdf2d6459e39267a633c4a9b2f5d",
            "brotli-5": "ed738e842d2fbdf2d6459e39267a633c4a9b2f5d",
            "zstd-19": "63779c798237346c2b245c546c40b72a5a5913fe",
            "zstd-3": "63779c798237346c2b245c546c40b72a5a5913fe",
        }
        for codec, source_commit in expected.items():
            with self.subTest(codec=codec):
                drift = _pin_drift(codec)
                if drift is not None:
                    self.skipTest(drift)
                identity = adapter_for(codec).identity()
                self.assertFalse(hasattr(identity, "codec_code_sha"))
                self.assertEqual(identity.upstream_release_sha, source_commit)
                self.assertIn(source_commit, identity.upstream_source_reference)
                self.assertRegex(identity.binary_sha256, r"^[0-9a-f]{64}$")
                self.assertTrue(hasattr(adapters, "compute_build_provenance_sha256"))
                self.assertEqual(
                    identity.codec_build_provenance_sha256,
                    adapters.compute_build_provenance_sha256(identity),
                )
                self.assertRegex(identity.codec_build_provenance_sha256, r"^[0-9a-f]{64}$")

    def test_executor_replaces_path_lookup_with_the_resolved_hashed_binary(self):
        adapter = adapter_for("gzip-9")
        identity = adapter.identity()
        source = Path("/tmp/input.bin")
        self.assertTrue(hasattr(SubprocessExecutor, "exact_argv"))
        with tempfile.TemporaryDirectory() as directory:
            swapped = Path(directory) / "gzip"
            swapped.write_text("#!/bin/false\n", encoding="utf-8")
            swapped.chmod(0o755)
            with patch.dict(os.environ, {"PATH": directory}):
                argv = SubprocessExecutor.exact_argv(
                    adapter.compress_argv(source),
                    identity,
                )
        self.assertEqual(argv[0], identity.binary_path)
        self.assertEqual(argv[1:], ("-9", "-c", str(source)))

    def test_network_sandbox_command_has_process_tree_timeout_and_private_network(self):
        executor = SubprocessExecutor(timeout_seconds=2)
        self.assertTrue(hasattr(executor, "sandbox_command"))
        command = executor.sandbox_command(
            ("/usr/bin/gzip", "-9", "-c", "/tmp/input.bin"),
            Path("/tmp/trial/output.bin"),
            Path("/tmp/trial/status.json"),
            Path("/tmp/trial/time.txt"),
            Path("/tmp/trial/stderr.txt"),
        )
        joined = "\n".join(command)
        self.assertEqual(command[0], "systemd-run")
        self.assertIn("PrivateNetwork=yes", joined)
        self.assertIn("KillMode=control-group", joined)
        self.assertIn("RuntimeMaxSec=2s", joined)
        self.assertNotIn("shell", joined.casefold())

    def test_system_mode_is_explicit_when_user_manager_is_unavailable(self):
        executor = SubprocessExecutor(timeout_seconds=2)
        with patch.dict(os.environ, {"CUBRIM_SYSTEMD_MODE": "system"}), patch(
            "adapters.os.geteuid", return_value=0
        ):
            command = executor.sandbox_command(
                ("/usr/bin/gzip", "-9", "-c", "/tmp/input.bin"),
                Path("/tmp/trial/output.bin"),
                Path("/tmp/trial/status.json"),
                Path("/tmp/trial/time.txt"),
                Path("/tmp/trial/stderr.txt"),
            )
        self.assertNotIn("--user", command)
        self.assertIn("systemd-run", command)

    def test_cli_or_package_version_mismatch_fails_closed(self):
        with patch("adapters._tool_version", return_value="gzip 9.99"):
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                adapter_for("gzip-9").identity()
        with patch(
            "adapters._package_provenance",
            return_value=("gzip", "1.12-unknown"),
        ):
            with self.assertRaisesRegex(ValueError, "package mismatch"):
                adapter_for("gzip-9").identity()

    def test_first_decoded_byte_requires_incremental_nonempty_output(self):
        with self.assertRaisesRegex(ValueError, "incremental"):
            first_decoded_byte_ms(False, 100, [(200, b"payload")])
        with self.assertRaisesRegex(ValueError, "non-empty"):
            first_decoded_byte_ms(True, 100, [(200, b""), (300, b"")])

        self.assertEqual(
            first_decoded_byte_ms(True, 100, [(150, b""), (350_100, b"x")]),
            0.35,
        )

    def test_energy_requires_readable_rapl_and_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            counter = Path(directory) / "energy_uj"
            counter.write_text("12345\n", encoding="utf-8")
            self.assertIsNone(energy_capability(counter, None))
            capability = energy_capability(
                counter,
                {"baseline_joules": 0.01, "batch_duration_ms": 250},
            )
            self.assertEqual(capability["counter_path"], str(counter))
            self.assertEqual(capability["initial_energy_uj"], 12345)

            counter.write_text("not-a-number\n", encoding="utf-8")
            self.assertIsNone(
                energy_capability(
                    counter,
                    {"baseline_joules": 0.01, "batch_duration_ms": 250},
                )
            )


if __name__ == "__main__":
    unittest.main()
