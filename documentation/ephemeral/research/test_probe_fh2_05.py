import io
from pathlib import Path
import tempfile
import tarfile
import unittest

from documentation.ephemeral.research import probe_fh2_05_segment_min as probe


def synthetic_tar() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, payload in (("a.txt", b"alpha"), ("bin/tool", bytes(range(255))),
                              ("empty", b"")):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def synthetic_tar_with_directory() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        directory = tarfile.TarInfo("tree/")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        for name in ("tree/a", "tree/b"):
            payload = name.encode()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


class TarSegmentationTests(unittest.TestCase):
    def test_segments_cover_raw_tar_exactly_once(self):
        data = synthetic_tar()

        segments = probe.parse_tar_segments(data)

        self.assertEqual([segment.name for segment in segments],
                         ["a.txt", "bin/tool", "empty"])
        self.assertEqual(b"".join(segment.raw for segment in segments), data)
        self.assertEqual(segments[0].offset, 0)
        self.assertTrue(all(left.end == right.offset
                            for left, right in zip(segments, segments[1:])))
        self.assertEqual(segments[-1].end, len(data))

    def test_rejects_truncated_member_payload(self):
        data = synthetic_tar()[:700]

        with self.assertRaisesRegex(ValueError, "truncated"):
            probe.parse_tar_segments(data)

    def test_directory_headers_are_charged_with_following_file_member(self):
        data = synthetic_tar_with_directory()

        segments = probe.parse_tar_segments(data)

        self.assertEqual([segment.name for segment in segments], ["tree/a", "tree/b"])
        self.assertEqual(b"".join(segment.raw for segment in segments), data)
        self.assertEqual(segments[0].offset, 0)

    def test_charge_counts_outer_and_per_segment_framing(self):
        self.assertEqual(probe.charged_size([100, 200, 300]), 24 + 3 * 4 + 600)

    def test_screen_is_a_contiguous_prefix_on_member_boundaries(self):
        segments = probe.parse_tar_segments(synthetic_tar())

        screen = probe.select_screen_prefix(segments, min_bytes=1500, max_members=2)

        self.assertEqual(screen, segments[:2])
        self.assertEqual(b"".join(segment.raw for segment in screen),
                         synthetic_tar()[:screen[-1].end])


class CliRoundTripTests(unittest.TestCase):
    @staticmethod
    def make_fake(root: Path) -> Path:
        fake = root / "fake-cubrim"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys\n"
            "cmd=sys.argv[1]; args=[x for x in sys.argv[2:] if x != '-q']\n"
            "if cmd == 'compress':\n"
            " data=pathlib.Path(args[0]).read_bytes()\n"
            " pathlib.Path(args[1]).write_bytes(b'CUBR\\x01\\x03'+len(data).to_bytes(4,'big')+data)\n"
            "elif cmd == 'decompress':\n"
            " blob=pathlib.Path(args[0]).read_bytes()\n"
            " pathlib.Path(args[1]).write_bytes(blob[10:])\n"
            "else: raise SystemExit(2)\n"
        )
        fake.chmod(0o755)
        return fake

    def test_runs_real_cli_path_and_reports_charged_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.make_fake(root)

            result = probe.run_cubrim_roundtrip(fake, b"payload", root / "job", "seg-000")

            self.assertEqual(result.blob_size, 17)
            self.assertEqual(result.mode, 3)
            self.assertEqual(result.cmp, 0)
            self.assertEqual(result.restored_path.read_bytes(), b"payload")

    def test_probe_compares_like_for_like_screen_then_full(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = synthetic_tar()
            fake = self.make_fake(root)

            result = probe.run_probe(
                data,
                fake,
                root / "run",
                expected_baseline_size=len(data) + 10,
                expected_members=3,
                jobs=2,
                screen_min_bytes=1500,
                screen_max_members=2,
            )

            self.assertEqual(result["member_count"], 3)
            self.assertEqual(result["baseline"]["cmp"], 0)
            self.assertEqual(result["screen"]["members"], 2)
            self.assertTrue(result["screen"]["proceed_full"])
            self.assertEqual(result["full"]["cmp"], 0)
            self.assertEqual(result["full"]["verdict"], "NO-GO")


if __name__ == "__main__":
    unittest.main()
