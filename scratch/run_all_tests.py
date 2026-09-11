import os
import subprocess
import sys

tests_dir = r"c:\Users\admin\Desktop\programming\game\tests"
test_files = [f for f in os.listdir(tests_dir) if f.startswith("test_") and f.endswith(".py")]

passed = 0
failed = 0

for tf in test_files:
    path = os.path.join(tests_dir, tf)
    env = dict(os.environ)
    env["PYTHONPATH"] = r"c:\Users\admin\Desktop\programming\game"
    res = subprocess.run([sys.executable, path], cwd=r"c:\Users\admin\Desktop\programming\game", capture_output=True, text=True, env=env)
    if res.returncode == 0:
        passed += 1
        print(f"[PASS] {tf}")
    else:
        failed += 1
        print(f"[FAIL] {tf}")
        print(res.stderr or res.stdout)

print(f"\nSummary: {passed} passed, {failed} failed out of {len(test_files)} total test files.")
