#!/usr/bin/env python3
"""Print the *real* TESSY test-data model for one test object (source of truth).

xlsx/csv exports only list columns that already have values, which makes them
misleading when diagnosing "interface is incomplete". The yaml export always
contains the full model:

    Values:      <- the columns TESSY actually exposes (name + direction + values)
    Stubs:       <- [testcase, teststep, stub, body]

Empty Values (only [tc1.1] rows, empty header) means the object's data model is
empty -> interface incomplete / data invalid -> see
references/interface-passing-and-import.md.

Usage:
    python check_data_model.py --collection "New Test Collection" \
        --module demo_signal_UT \
        --object demo_signal_tx

    # or inspect a yaml already exported:
    python check_data_model.py --yaml path\\to\\object.yml
"""
import argparse
import os
import subprocess
import sys
import tempfile

DEFAULT_CMD = r'D:\tessy\TESSY_5.1\bin\tessycmd.exe'


def sh(cmd, *args):
    r = subprocess.run([cmd] + [str(a) for a in args], capture_output=True, text=True)
    return ((r.stdout or '') + (r.stderr or '')).strip()


def sections(text):
    out = {}
    cur = None
    for line in text.splitlines():
        if line and not line.startswith((' ', '-', 'Tessy', 'General', 'Properties', 'Stubs', 'Values', '---')) and line.rstrip().endswith(':'):
            cur = line.rstrip()[:-1]
            out[cur] = []
            continue
        if line.startswith(('Properties:', 'Stubs:', 'Values:')):
            cur = line.rstrip()[:-1]
            out[cur] = []
            continue
        if cur:
            out[cur].append(line)
    return out


def report(text, label):
    print('===== %s' % label)
    sec = sections(text)
    vals = [l for l in sec.get('Values', []) if l.strip()]
    print('-- Values (%d lines)' % len(vals))
    for l in vals[:20]:
        print('   ' + l.strip()[:160])
    if len(vals) <= 2:
        print('   !! Data model looks EMPTY -> interface incomplete / data invalid')
    stubs = [l for l in sec.get('Stubs', []) if l.strip()]
    print('-- Stubs (%d lines)' % len(stubs))
    for l in stubs[:12]:
        print('   ' + l.strip()[:160])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--yaml')
    ap.add_argument('--cmd', default=os.environ.get('TESSY_CMD', DEFAULT_CMD))
    ap.add_argument('--project')
    ap.add_argument('--collection')
    ap.add_argument('--module')
    ap.add_argument('--object')
    a = ap.parse_args()

    if a.yaml:
        report(open(a.yaml, encoding='utf-8', errors='ignore').read(), a.yaml)
        return 0

    if not (a.collection and a.module and a.object):
        print('need --yaml   or   --collection/--module/--object')
        return 1

    work = tempfile.mkdtemp(prefix='tessy_model_')
    sh(a.cmd, 'connect')
    if a.project:
        sh(a.cmd, 'select-project', a.project)
    sh(a.cmd, 'select-test-collection', a.collection)
    sh(a.cmd, 'select-module', '-test-collection', a.module)
    sh(a.cmd, 'select-test-object', a.object)
    res = sh(a.cmd, 'export', '-format', 'yaml', '-file', 'model', work)
    if res:
        print('export failed: %s' % res)
        return 2
    path = os.path.join(work, 'model.yml')
    report(open(path, encoding='utf-8', errors='ignore').read(), a.object)
    print('yaml: %s' % path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
