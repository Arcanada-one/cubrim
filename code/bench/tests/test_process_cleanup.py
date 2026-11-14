"""Regression for a codec leader that exits before its writers finish."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from test_holdout_bench import bench


class ProcessCleanupTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'process group cleanup is Unix-specific')
    def test_exited_leader_cannot_leave_writers_running(self):
        for return_code in (0, 17):
            with self.subTest(return_code=return_code), tempfile.TemporaryDirectory() as directory:
                marker = Path(directory) / 'descendant-survived'
                child = f'import time,pathlib;time.sleep(0.4);pathlib.Path({str(marker)!r}).touch()'
                parent = (f'import subprocess,sys;'
                          f'subprocess.Popen([sys.executable,"-S","-c",{child!r}]);'
                          f'sys.exit({return_code})')
                runner = bench.Runner(2, time.monotonic() + 3)
                with self.assertRaisesRegex(bench.BenchmarkError, 'descendant processes'):
                    runner.run([sys.executable, '-S', '-c', parent])
                time.sleep(0.5)
                self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
