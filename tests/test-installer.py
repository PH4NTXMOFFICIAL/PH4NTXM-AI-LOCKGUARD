# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def execute(self, options=(), **settings):
        with tempfile.TemporaryDirectory(prefix="lockguard-install-test-") as temporary:
            root = Path(temporary)
            project = root / "repo with spaces"
            source = project / "ph4ntxm-ai-lockguard"
            source.mkdir(parents=True)
            shutil.copy(ROOT / "build.sh", project / "build.sh")
            for name in ("install.sh", "ph4ntxm-lockguard.service", "lockguard.toml"):
                shutil.copy(ROOT / "ph4ntxm-ai-lockguard" / name, source / name)
            binary = root / "bin"
            binary.mkdir()
            trace = root / "trace"
            environment = os.environ.copy()
            environment.update(PATH=str(binary) + ":" + os.environ["PATH"], TRACE=str(trace),
                               XDG_CONFIG_HOME=str(root / "config"), REAL_PYTHON=sys.executable,
                               MOCK_ACTIVE="0", MOCK_MISSING="0", MOCK_CHECK_FAIL="0", MOCK_APT_FAIL="0")
            environment.update(settings)
            scripts = {
                "id": '#!/bin/bash\nif [ "$1" = -un ]; then echo tester; else echo 1000; fi\n',
                "dpkg-query": '#!/bin/bash\n[ "$MOCK_MISSING" = 0 ] && echo "install ok installed"\n',
                "sudo": '#!/bin/bash\nexec "$@"\n',
                "apt-get": '#!/bin/bash\nprintf "apt %s\\n" "$*" >> "$TRACE"\n[ "$MOCK_APT_FAIL" = 0 ]\n',
                "loginctl": '#!/bin/bash\nexit 0\n',
                "light-locker-command": '#!/bin/bash\nexit 0\n',
                "pgrep": '#!/bin/bash\nexit 0\n',
                "systemctl": '''#!/bin/bash
printf 'systemctl %s\n' "$*" >> "$TRACE"
if [ "$2" = is-active ]; then
    [ "$MOCK_ACTIVE" = 1 ] || [ -e "$TRACE.started" ]
elif [ "$2" = restart ]; then
    touch "$TRACE.started"
fi
''',
                "python3": '''#!/bin/bash
if [ "$1" = -m ] && [ "$2" = venv ]; then
    mkdir -p "$3/bin"
    cp "$MOCK_VENV_PYTHON" "$3/bin/python"
    chmod +x "$3/bin/python"
    printf 'venv repaired\n' >> "$TRACE"
else
    exec "$REAL_PYTHON" "$@"
fi
''',
            }
            for name, content in scripts.items():
                file = binary / name
                file.write_text(content)
                file.chmod(0o755)
            helper = root / "venv-python"
            helper.write_text('''#!/bin/bash
if [ "$1" = -m ]; then
    printf 'python %s\n' "$*" >> "$TRACE"
    exit 0
elif [[ "$1" = */download_model.py ]]; then
    echo 'model verified' >> "$TRACE"
    exit 0
elif [[ "$1" = */ph4ntxm_lockguard.py ]]; then
    echo 'preflight' >> "$TRACE"
    [ "$MOCK_CHECK_FAIL" = 0 ]
else
    exec "$REAL_PYTHON" "$@"
fi
''')
            environment["MOCK_VENV_PYTHON"] = str(helper)
            (source / ".venv/bin").mkdir(parents=True)
            (source / ".venv/bin/python").write_text("incomplete environment")
            result = subprocess.run(["bash", str(project / "build.sh"), *options], env=environment,
                                    text=True, capture_output=True, timeout=20)
            unit = root / "config/systemd/user/ph4ntxm-lockguard.service"
            return result, trace.read_text() if trace.exists() else "", unit.read_text() if unit.exists() else ""

    def test_repairs_partial_environment_without_starting(self):
        result, trace, unit = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("venv repaired", trace)
        self.assertIn("ensurepip --upgrade", trace)
        self.assertNotIn("systemctl --user enable", trace)
        self.assertNotIn("apt ", trace)
        self.assertIn("repo with spaces", unit)
        self.assertNotIn("%PYTHON%", unit)

    def test_installs_missing_system_dependencies(self):
        result, trace, _ = self.execute(MOCK_MISSING="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("apt update", trace)
        self.assertIn("python3-venv", trace)
        self.assertIn("libseccomp2", trace)

    def test_start_is_explicit_and_follows_preflight(self):
        result, trace, _ = self.execute(("--start",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(trace.index("preflight"), trace.index("systemctl --user enable"))
        self.assertIn("systemctl --user restart", trace)

    def test_preflight_failure_does_not_start(self):
        result, trace, _ = self.execute(("--start",), MOCK_CHECK_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("systemctl --user enable", trace)
        self.assertNotIn("systemctl --user restart", trace)

    def test_package_failure_stops_before_venv(self):
        result, trace, unit = self.execute(MOCK_MISSING="1", MOCK_APT_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("venv repaired", trace)
        self.assertFalse(unit)

    def test_running_service_is_stopped_then_restored(self):
        result, trace, _ = self.execute(MOCK_ACTIVE="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(trace.index("systemctl --user stop"), trace.index("venv repaired"))
        self.assertIn("systemctl --user restart", trace)


if __name__ == "__main__":
    unittest.main()
