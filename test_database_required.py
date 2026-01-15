#!/usr/bin/env python3
"""Test that DATABASE_URL is required."""

import subprocess
import sys
import os

# Create a test script
test_script = """
import sys
import os

# Remove all DATABASE_* variables
for key in list(os.environ.keys()):
    if 'DATABASE' in key.upper():
        del os.environ[key]

try:
    from app import app
    print('ERROR: Should have raised RuntimeError')
    sys.exit(1)
except RuntimeError as e:
    error_msg = str(e)
    if 'DATABASE_URL' in error_msg and 'required' in error_msg:
        print(f'OK: {error_msg}')
        sys.exit(0)
    else:
        print(f'ERROR: Wrong error message: {error_msg}')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    sys.exit(1)
"""

result = subprocess.run(
    [sys.executable, '-c', test_script],
    cwd='c:\\Users\\makok\\Desktop\\Makokha-Medical-Centre',
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    # Filter out logging output
    for line in result.stderr.split('\n'):
        if 'RuntimeError' in line or 'DATABASE_URL' in line:
            print(line)

if result.returncode == 0:
    print('\n✅ Test passed: DATABASE_URL is required')
else:
    print(f'\n❌ Test failed with exit code {result.returncode}')
    print('STDERR:', result.stderr[:500])
