#!/usr/bin/env python3
"""Report TESSY test-object executability without running any test.

Reads the persisted test data (<project>/tessy/persist/tessy/project/<HI>/<LO>/.tdb/<n>/testobject.xml)
and prints, for every test object:

    module-dir  object-name  state_mask  testitem_state_mask  cases  verdict

Verdict:
    executable      state_mask ends with 0x1188 and testitem_state_mask == 0x80
    NOT-executable  otherwise (GUI: "No executable test object selected for execution.")

Usage:
    python check_executable.py --persist "D:\\proj\\tessy\\persist\\tessy\\project"
    python check_executable.py --persist <dir> --module 4\\1E      # filter one module dir
    python check_executable.py --persist <dir> --only-not-executable

This is a read-only diagnostic; it never talks to TESSY.
"""
import argparse
import glob
import os
import xml.etree.ElementTree as ET


def scan(persist, only_not_exec=False, module_dir=None):
    import re
    pat = os.path.join(persist, '*', '*', '.tdb', '*', 'testobject.xml')
    rows = []
    for f in glob.glob(pat):
        parts = f.split(os.sep)
        mod = parts[-5] + os.sep + parts[-4]
        if module_dir and mod.replace('/', os.sep) != module_dir:
            continue
        try:
            r = ET.parse(f).getroot()
        except Exception:
            continue
        sm = int(r.get('state_mask') or '0', 16)
        im = int(r.get('testitem_state_mask') or '0', 16)
        cases = len(list(r.iter('testcase')))
        exe = (sm & 0x8) and (im & 0x80)
        if only_not_exec and exe:
            continue
        rows.append((mod, r.get('name'), hex(sm), hex(im), cases, 'executable' if exe else 'NOT-executable'))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--persist', required=True,
                    help=r'e.g. D:\T1V_Tessytest\tessy\persist\tessy\project')
    ap.add_argument('--module', default=None, help=r'module dir like 4\1E')
    ap.add_argument('--only-not-executable', action='store_true')
    a = ap.parse_args()
    rows = scan(a.persist, a.only_not_executable, a.module)
    if not rows:
        print('no test objects found (check --persist / --module)')
        return
    print('%-10s %-44s %-12s %-8s %5s  %s' % ('module', 'object', 'state', 'item', 'cases', 'verdict'))
    bad = 0
    for mod, name, sm, im, cases, verdict in sorted(rows):
        if verdict != 'executable':
            bad += 1
        print('%-10s %-44s %-12s %-8s %5d  %s' % (mod, name, sm, im, cases, verdict))
    print('\ntotal=%d  not-executable=%d' % (len(rows), bad))


if __name__ == '__main__':
    main()
