from __future__ import annotations

import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


def _load_parity_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_error_class_parity.py"
    spec = importlib.util.spec_from_file_location("check_error_class_parity", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LoadActualFromSdkTests(unittest.TestCase):
    def test_only_uses_verify_attestation_locally_returns(self) -> None:
        module = _load_parity_module()
        source = textwrap.dedent(
            """
            def helper():
                return (False, "AttestationShouldNotBeCounted")

            def verify_attestation_locally():
                return (False, "AttestationRealMismatch")
            """
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            vendored_path = Path(tmpdir) / "_verify_local_vendored.py"
            vendored_path.write_text(source, encoding="utf-8")
            with mock.patch.object(module, "VENDORED_SDK_PATH", vendored_path):
                actual = module.load_actual_from_sdk()

        self.assertEqual(actual, {"AttestationRealMismatch"})


if __name__ == "__main__":
    unittest.main()
