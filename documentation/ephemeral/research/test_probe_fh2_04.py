import io
import tarfile
import unittest

from documentation.ephemeral.research import probe_fh2_04_similarity_order as probe


def make_tar(payloads):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        directory = tarfile.TarInfo("tree/")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        for index, payload in enumerate(payloads):
            info = tarfile.TarInfo(f"tree/file-{index}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


class SimilarityOrderTests(unittest.TestCase):
    def test_layout_groups_directory_header_and_preserves_trailer(self):
        data = make_tar([b"alpha", b"beta"])

        layout = probe.parse_tar_layout(data)

        self.assertEqual([frame.name for frame in layout.frames],
                         ["tree/file-0", "tree/file-1"])
        self.assertEqual(layout.frames[0].offset, 0)
        self.assertTrue(layout.trailer.startswith(bytes(1024)))
        self.assertEqual(b"".join(frame.raw for frame in layout.frames) + layout.trailer,
                         data)

    def test_similarity_order_is_deterministic_and_non_identity(self):
        data = make_tar([b"a" * 4096, b"z" * 4096, b"a" * 4000 + b"b" * 96])
        layout = probe.parse_tar_layout(data)

        order = probe.similarity_order(layout.frames)

        self.assertEqual(order, [0, 2, 1])
        self.assertEqual(probe.similarity_order(layout.frames), order)

    def test_inverse_permutation_restores_original_tar(self):
        data = make_tar([b"a" * 2048, b"z" * 2048, b"a" * 2000 + b"b" * 48])
        layout = probe.parse_tar_layout(data)
        order = [0, 2, 1]

        reordered = probe.apply_order(layout, order)
        restored = probe.restore_order(reordered, order)

        self.assertEqual(restored, data)

    def test_prefix_without_terminal_trailer_also_round_trips(self):
        data = make_tar([b"a" * 2048, b"z" * 2048, b"a" * 2000 + b"b" * 48])
        layout = probe.parse_tar_layout(data)
        prefix = probe.TarLayout(layout.frames[:2], b"")
        order = probe.similarity_order(prefix.frames)

        reordered = probe.apply_order(prefix, order)
        restored = probe.restore_order(reordered, order, allow_missing_trailer=True)

        self.assertEqual(restored, b"".join(frame.raw for frame in prefix.frames))

    def test_permutation_charge_matches_preregistered_525_member_cost(self):
        self.assertEqual(probe.permutation_charge(525), 681)


if __name__ == "__main__":
    unittest.main()
