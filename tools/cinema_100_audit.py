#!/usr/bin/env python3
"""100-repeat FULL Kodi regression audit, per-shard JSON evidence and fail-fast.

Each repetition invokes *every* discovered test (functions, UI layout, real PNG
texture pixels and data handling), unlike the narrower skin-only checks.
No running Kodi player is simulated by these file/unit tests.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--shard', type=int, required=True)
    p.add_argument('--iterations', type=int, default=10)
    p.add_argument('--report-dir', default='audit-results')
    args = p.parse_args()
    if args.shard < 0 or args.shard > 9:
        p.error('shard must be 0..9')
    if args.iterations != 10:
        p.error('each of 10 shards must run exactly 10 full suites')

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    summary = {'shard': args.shard, 'iterations': args.iterations,
               'type': 'complete-discovered-Python-test-suite',
               'runs': [], 'passed': 0, 'failed': 0, 'total_assertion_tests': 0,
               'real_android_tv_runtime_tested': False,
               'started_utc': datetime.now(timezone.utc).isoformat()}
    try:
        for j in range(args.iterations):
            global_number = args.shard * 10 + j + 1
            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    [sys.executable, '-m', 'unittest', 'discover',
                     '-s', 'tests', '-q'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, errors='replace', timeout=180)
                output = proc.stdout
                code = proc.returncode
            except subprocess.TimeoutExpired as exc:
                output = str(exc)
                code = 124
            found = re.search(r'Ran\s+(\d+)\s+tests?\s+in', output)
            cases = int(found.group(1)) if found else 0
            successful = code == 0 and bool(re.search(r'(?m)^OK\s*$', output))
            successful &= cases >= 260
            record = {'run': global_number, 'passed': bool(successful),
                      'test_cases': cases, 'exit_code': code,
                      'elapsed_seconds': round(time.monotonic()-t0, 2)}
            summary['runs'].append(record)
            summary['passed' if successful else 'failed'] += 1
            summary['total_assertion_tests'] += cases
            print('Full run %03d/100 %s (%s checks, %ss)' % (
                global_number, 'PASS' if successful else 'FAIL',
                cases, record['elapsed_seconds']), flush=True)
            if not successful:
                print(output[-14000:], file=sys.stderr, flush=True)
                break
    finally:
        summary['ended_utc'] = datetime.now(timezone.utc).isoformat()
        path = report_dir / ('shard-%02d.json' % args.shard)
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n',
                        encoding='utf-8')
        print('Evidence: %s' % path, flush=True)
    if summary['passed'] != 10 or summary['failed']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
