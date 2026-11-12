#!/usr/bin/env python3
"""Change the Passing direction of interface elements via `import -set-passing`.

Why: TESSY 5.1 has no CLI for TIE (interface) edits. The xlsx direction row
(second row of the `Values` sheet) is honoured by:
        tessycmd import -set-passing <file.xlsx>
and the only valid markers are:  i = IN,  o = OUT,  x = IRRELEVANT.

Typical uses
------------
1) Make an IRRELEVANT static variable controllable (IRRELEVANT -> IN):
       python set_passing.py --collection "New Test Collection" --module M --object O \
              --column DemoPose.x --direction i
2) Neutralise a struct-pointer parameter that breaks the interface
   (IN -> IRRELEVANT). Pointer parameters have no INOUT in TESSY 5.1:
       python set_passing.py ... --column msg --direction x \
              --object demo_signal_tx

The script exports the current data, updates/creates the column's direction row,
imports with -set-passing, then re-exports the interface XML so you can verify.

WARNING: `import` replaces the object's whole test data. The exported file is
modified in place (values are kept), so data is preserved - but back up first:
    tessycmd select-module ... ; tessycmd save-db -source module -to <dir>
"""
import argparse
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import openpyxl

DEFAULT_CMD = r'D:\tessy\TESSY_5.1\bin\tessycmd.exe'


def sh(cmd, *args):
    r = subprocess.run([cmd] + [str(a) for a in args], capture_output=True, text=True)
    return ((r.stdout or '') + (r.stderr or '')).strip()


def passing_of(cmd, workdir, object_name, find_substr):
    sh(cmd, 'select-test-object', object_name)
    if sh(cmd, 'export', '-format', 'xml', '-file', 'ifcheck', workdir):
        return 'export-failed'
    root = ET.parse(os.path.join(workdir, 'ifcheck.xml')).getroot()
    for el in root.iter('element'):
        if el.get('kind') == 'interface' and find_substr in (el.get('name') or ''):
            return el.get('passing')
    return 'not-found'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cmd', default=os.environ.get('TESSY_CMD', DEFAULT_CMD))
    ap.add_argument('--project')
    ap.add_argument('--collection', required=True)
    ap.add_argument('--module', required=True)
    ap.add_argument('--object', required=True)
    ap.add_argument('--column', required=True, help='interface element name, e.g. msg or DemoPose.x')
    ap.add_argument('--direction', required=True, choices=['i', 'o', 'x'],
                    help='i=IN, o=OUT, x=IRRELEVANT')
    a = ap.parse_args()

    work = tempfile.mkdtemp(prefix='tessy_passing_')
    sh(a.cmd, 'connect')
    if a.project:
        sh(a.cmd, 'select-project', a.project)
    sh(a.cmd, 'select-test-collection', a.collection)
    sh(a.cmd, 'select-module', '-test-collection', a.module)

    before = passing_of(a.cmd, work, a.object, a.column)
    print('before: %s = %s' % (a.column, before))

    sh(a.cmd, 'select-test-object', a.object)
    sh(a.cmd, 'export', '-format', 'xlsx', '-file', 'cur', work)
    path = os.path.join(work, 'cur.xlsx')
    if not os.path.exists(path):
        print('export failed - object name wrong?')
        return 1

    wb = openpyxl.load_workbook(path)
    ws = wb['Values']
    found = 0
    for c in range(1, ws.max_column + 1):
        if ws.cell(1, c).value == a.column:
            ws.cell(2, c).value = a.direction
            found += 1
    if not found:
        # element not exported (it may be IRRELEVANT / value-less) -> append column
        c = ws.max_column + 1
        ws.cell(1, c).value = a.column
        ws.cell(2, c).value = a.direction
        found = 1
    out = os.path.join(work, 'rel.xlsx')
    wb.save(out)

    sh(a.cmd, 'select-test-object', a.object)
    res = sh(a.cmd, 'import', '-set-passing', out)
    print('import: %s' % (res or 'ok'))
    if res:
        print('failed (partial apply possible!) -> restore the module from its TMB backup')
        return 2

    after = passing_of(a.cmd, work, a.object, a.column)
    print('after : %s = %s' % (a.column, after))
    print('work dir: %s' % work)
    return 0


if __name__ == '__main__':
    sys.exit(main())
