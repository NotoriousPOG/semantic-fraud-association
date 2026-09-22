#!/usr/bin/env python3
"""Bounded, read-only Stripe collection with an optional untrusted analyst adapter.

Standard library only. This runner is a host control, not an agent sandbox.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone

MAX_OUTPUT = 2_000_000


class StopCollection(Exception):
    pass


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def execute(argv, deadline, receipts, stdin=None):
    receipt = {'call_id': f'call_{len(receipts)+1}', 'argv': argv,
               'started': False, 'exit_code': None, 'status': 'not_started',
               'started_at': None}
    receipts.append(receipt)
    if time.monotonic() >= deadline:
        raise StopCollection('deadline')
    with tempfile.TemporaryFile() as inp, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        inp.write((stdin or '').encode()); inp.seek(0)
        try:
            proc = subprocess.Popen(argv, stdin=inp, stdout=out, stderr=err,
                                    start_new_session=(os.name == 'posix'))
        except OSError as exc:
            receipt['error_type'] = type(exc).__name__
            raise StopCollection('executable_unavailable') from exc
        receipt.update(started=True, started_at=utcnow(), status='running')
        reason = None
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                reason = 'deadline'
            elif os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > MAX_OUTPUT:
                reason = 'output_limit'
            if reason:
                break
            time.sleep(min(0.01, max(0, deadline-time.monotonic())))
        # Kill the process group even if the parent exited, to close background
        # children holding output files on POSIX. Windows requires host isolation.
        if os.name == 'posix':
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            reason = reason or 'deadline'
        out.seek(0); err.seek(0)
        raw = out.read(MAX_OUTPUT + 1); errors = err.read(MAX_OUTPUT + 1)
        if len(raw) + len(errors) > MAX_OUTPUT:
            reason = reason or 'output_limit'
        receipt.update(exit_code=proc.returncode, finished_at=utcnow(),
                       status=reason or 'exited',
                       stdout_sha256=hashlib.sha256(raw).hexdigest(),
                       stderr_sha256=hashlib.sha256(errors).hexdigest(),
                       output_truncated=(len(raw)+len(errors)>MAX_OUTPUT))
        # Raw stderr may contain credentials or customer data. Publish hashes
        # and actual process status, never a generated account/auth diagnosis.
        if reason:
            raise StopCollection(reason)
        if proc.returncode != 0:
            raise StopCollection('command_failed')
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise StopCollection('invalid_encoding') from exc


def strict_json(value):
    def pairs(items):
        obj = {}
        for key, item in items:
            if key in obj:
                raise ValueError('duplicate JSON key')
            obj[key] = item
        return obj
    def invalid_constant(value):
        raise ValueError('invalid JSON constant')
    return json.loads(value, object_pairs_hook=pairs, parse_constant=invalid_constant)


def validate_assessment(answer, packet):
    """Validate structure/provenance, NOT the truth of narrative interpretation."""
    def require(ok):
        if not ok:
            raise ValueError('assessment does not match the evidence contract')
    require(packet['status'] == 'evidence_ready')
    require(type(answer) is dict and set(answer) == {'run_id','tool_claims','findings','limitations','next_check'})
    require(answer['run_id'] == packet['run_id'])
    expected = [{'call_id': c['call_id'], 'started': c['started'], 'exit_code': c['exit_code']}
                for c in packet['tool_results']]
    # JSON comparison distinguishes boolean true from integer 1.
    require(json.dumps(answer['tool_claims'], sort_keys=True) == json.dumps(expected, sort_keys=True))
    ids = {r['id'] for r in packet['records']}
    require(type(answer['findings']) is list and len(answer['findings']) <= 100)
    for finding in answer['findings']:
        require(type(finding) is dict and set(finding) == {'record_ids','text'})
        refs = finding['record_ids']
        require(type(refs) is list and bool(refs) and all(type(x) is str and x in ids for x in refs))
        require(type(finding['text']) is str and 0 < len(finding['text']) <= 2000)
    require(type(answer['limitations']) is list and bool(answer['limitations']))
    require(all(type(x) is str and 0 < len(x) <= 2000 for x in answer['limitations']))
    require(type(answer['next_check']) is str and 0 < len(answer['next_check']) <= 2000)


def investigate(*, cli, account, mode, start, end, seconds=45, max_pages=10,
                project=None, connected_account=None, analyst_command=None):
    deadline = time.monotonic() + seconds - min(0.25, seconds/4)
    packet = {'schema_version':1, 'run_id':str(uuid.uuid4()), 'status':'incomplete',
              'reason':None, 'scope':{'account':account, 'mode':mode, 'start':start, 'end':end,
              'interval':'inclusive', 'connected_account':connected_account},
              'coverage':{'pages':0, 'pagination_complete':False},
              'tool_results':[], 'records':[], 'record_sources':{}, 'assessment':None,
              'limitations':['Charge collection is not all payment activity.',
                             'Retrieved now; historical information availability is not established.',
                             'Narrative interpretations are not verified by this runner.']}
    try:
        if (not math.isfinite(seconds) or seconds < 0.4 or max_pages < 1 or max_pages > 100
                or start < 0 or start > end or mode not in ('test','live')
                or not re.fullmatch(r'acct_[A-Za-z0-9]+',account)
                or connected_account is not None and connected_account != account):
            raise StopCollection('invalid_configuration')
        common = ['--color=off']
        if project:
            common.append('--project-name='+project)
        if mode == 'live':
            common.append('--live')
        if connected_account:
            common.append('--stripe-account='+connected_account)
        def call(args):
            return execute([cli]+args, deadline, packet['tool_results'])
        call(['--version'])
        call(['get','--help'])
        call(['charges','list','--help'])
        ctx = strict_json(call(['get','/v1/account']+common))
        if type(ctx) is not dict or ctx.get('object') != 'account' or ctx.get('id') != account:
            raise StopCollection('account_mismatch')
        cursor = None
        received_bytes = 0
        seen = set()
        for _ in range(max_pages):
            args = ['charges','list','--limit=100','-d',f'created[gte]={start}',
                    '-d',f'created[lte]={end}']+common
            if cursor:
                args.append('--starting-after='+cursor)
            page_text = call(args)
            received_bytes += len(page_text.encode('utf-8'))
            if received_bytes > 1_000_000:
                raise StopCollection('collection_size_limit')
            page = strict_json(page_text)
            if (type(page) is not dict or page.get('object') != 'list'
                    or type(page.get('data')) is not list or type(page.get('has_more')) is not bool
                    or len(page['data']) > 100):
                raise StopCollection('invalid_page')
            new = []
            page_ids = set()
            for row in page['data']:
                if (type(row) is not dict or row.get('object') != 'charge'
                        or not isinstance(row.get('id'),str) or not re.fullmatch(r'ch_[A-Za-z0-9]+',row['id'])
                        or row['id'] in seen or row['id'] in page_ids
                        or row.get('livemode') is not (mode == 'live')
                        or type(row.get('created')) is not int or not start <= row['created'] <= end):
                    raise StopCollection('invalid_record_or_scope')
                page_ids.add(row['id']); new.append(row)
            if page['has_more'] and not new:
                raise StopCollection('empty_continuation')
            seen.update(page_ids); packet['records'].extend(new)
            receipt = packet['tool_results'][-1]
            for row in new:
                packet['record_sources'][row['id']] = {
                    'call_id':receipt['call_id'], 'retrieved_at':receipt['finished_at']}
            packet['coverage']['pages'] += 1
            if not page['has_more']:
                packet['coverage']['pagination_complete'] = True
                break
            cursor = new[-1]['id']
        if not packet['coverage']['pagination_complete']:
            raise StopCollection('page_limit')
        packet['status'] = 'evidence_ready'
        if analyst_command is not None:
            if (type(analyst_command) is not list or not analyst_command
                    or any(type(x) is not str or not x for x in analyst_command)):
                raise StopCollection('invalid_analyst_command')
            # Analyst process receipts are separate from the Stripe tool claims.
            analyst_receipts = []
            packet['analyst_execution'] = analyst_receipts
            raw = execute(analyst_command, deadline, analyst_receipts, json.dumps(packet))
            try:
                answer = strict_json(raw)
                validate_assessment(answer, packet)
            except (ValueError, TypeError, KeyError) as exc:
                packet.update(status='rejected', reason='invalid_assessment', finished_at=utcnow())
                return packet
            packet.update(status='assessment_available', assessment=answer)
    except StopCollection as exc:
        packet.update(status='incomplete', reason=str(exc))
    except (ValueError, TypeError, KeyError) as exc:
        packet.update(status='incomplete', reason='invalid_json_or_shape')
    packet['finished_at'] = utcnow()
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', default='stripe')
    parser.add_argument('--account', required=True, help='Expected current or connected account ID')
    parser.add_argument('--connected-account', help='Optional Connect request context; must equal --account')
    parser.add_argument('--project')
    parser.add_argument('--mode', choices=['test','live'], required=True)
    parser.add_argument('--start',type=int,required=True,help='Inclusive charge creation Unix time')
    parser.add_argument('--end',type=int,required=True)
    parser.add_argument('--seconds',type=float,default=45)
    parser.add_argument('--max-pages',type=int,default=10)
    parser.add_argument('--analyst-command-file',type=Path,help='Host-owned JSON argv list; never supplied by evidence')
    opts = vars(parser.parse_args())
    adapter = opts.pop('analyst_command_file')
    if adapter:
        try:
            opts['analyst_command'] = strict_json(adapter.read_text())
        except (OSError, ValueError):
            print(json.dumps({'status':'incomplete','reason':'invalid_analyst_configuration'}))
            return 2
    result = investigate(**opts)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['status'] in ('evidence_ready','assessment_available') else 2


if __name__ == '__main__':
    raise SystemExit(main())
