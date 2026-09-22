import importlib.util
import json
from pathlib import Path
import tempfile
import time
import sys
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/guarded_investigation.py'
spec = importlib.util.spec_from_file_location('guard', SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

MOCK = '''#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
mode = Path(__file__).with_suffix('.mode').read_text()
a = sys.argv[1:]
if mode == 'hang': time.sleep(10)
if '--version' in a: print('stripe synthetic fixture'); sys.exit()
if '--help' in a: print('synthetic help'); sys.exit()
if mode == 'auth': print('authentication failed', file=sys.stderr); sys.exit(1)
if a[:2] == ['get', '/v1/account']:
 print(json.dumps({'object':'account','id':'acct_wrong' if mode == 'account' else 'acct_test'})); sys.exit()
if mode == 'bad_json': print('broken'); sys.exit()
second = any('starting-after' in x for x in a)
i = 2 if second and mode != 'repeat' else 1
row = {'id':f'ch_{i}','object':'charge','livemode':mode == 'live','created':100+i,'amount':1000,'currency':'usd','status':'failed'}
print(json.dumps({'object':'list','data':[row],'has_more':not second or mode == 'repeat'}))
'''

class GuardTests(unittest.TestCase):
 def setUp(self):
  self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
  self.cli = Path(self.tmp.name)/'stripe'; self.cli.write_text(MOCK); self.cli.chmod(0o700)
  self.cli.with_suffix('.mode').write_text('ok')
 def run_guard(self, mode='ok', **kw):
  self.cli.with_suffix('.mode').write_text(mode)
  opts = dict(cli=str(self.cli), account='acct_test', mode='test', start=100, end=110, seconds=3, max_pages=3)
  opts.update(kw)
  return guard.investigate(**opts)
 def test_success(self):
  r=self.run_guard(); self.assertEqual(r['status'],'evidence_ready')
  self.assertEqual(len(r['records']),2); self.assertTrue(r['coverage']['pagination_complete'])
  self.assertTrue(all(x['started'] and x['exit_code']==0 for x in r['tool_results']))
 def test_missing_cli(self):
  r=self.run_guard(cli=str(self.cli)+'absent'); self.assertEqual(r['status'],'incomplete')
  c=r['tool_results'][0]; self.assertFalse(c['started']); self.assertIsNone(c['exit_code']); self.assertEqual(r['records'],[])
 def test_auth(self):
  r=self.run_guard('auth'); self.assertEqual(r['status'],'incomplete'); self.assertEqual(r['records'],[])
  self.assertEqual(r['tool_results'][-1]['exit_code'],1)
 def test_deadline(self):
  t=time.monotonic(); r=self.run_guard('hang',seconds=0.8)
  self.assertLess(time.monotonic()-t,1.5); self.assertEqual(r['status'],'incomplete'); self.assertEqual(r['reason'],'deadline')
 def test_bad_inputs(self):
  for mode in ('account','bad_json','live','repeat'):
   with self.subTest(mode=mode): self.assertEqual(self.run_guard(mode)['status'],'incomplete')
 def test_page_limit(self):
  r=self.run_guard(max_pages=1); self.assertEqual(r['status'],'incomplete'); self.assertFalse(r['coverage']['pagination_complete'])
 def response(self, r):
  return {'run_id':r['run_id'],'tool_claims':[{'call_id':x['call_id'],'started':x['started'],'exit_code':x['exit_code']} for x in r['tool_results']], 'findings':[{'record_ids':['ch_1'], 'text':'A failed charge is observed; this does not establish fraud.'}], 'limitations':['Only charge records supplied.'], 'next_check':'Check the associated authenticated session.'}
 def test_valid_response(self):
  r=self.run_guard(); guard.validate_assessment(self.response(r),r)
 def test_forged_receipt(self):
  r=self.run_guard(); a=self.response(r); a['tool_claims'][0]['exit_code']=127
  with self.assertRaises(ValueError): guard.validate_assessment(a,r)
 def test_unknown_call(self):
  r=self.run_guard(); a=self.response(r); a['tool_claims'][0]['call_id']='imaginary'
  with self.assertRaises(ValueError): guard.validate_assessment(a,r)
 def test_wrong_run_record_and_extra_fields(self):
  r=self.run_guard()
  for kind in ('run','record','field'):
   a=self.response(r)
   if kind=='run': a['run_id']='previous_run'
   if kind=='record': a['findings'][0]['record_ids']=['invented']
   if kind=='field': a['status']='complete'
   with self.subTest(kind=kind), self.assertRaises(ValueError): guard.validate_assessment(a,r)
 def test_incomplete_cannot_be_promoted(self):
  r=self.run_guard('auth')
  with self.assertRaises(ValueError): guard.validate_assessment(self.response(r),r)

 def adapter(self, code):
  path=Path(self.tmp.name)/'adapter.py'; path.write_text(code)
  return [sys.executable,str(path)]
 def test_analyst_deadline(self):
  cmd=self.adapter('import time; time.sleep(10)')
  t=time.monotonic(); r=self.run_guard(seconds=1,analyst_command=cmd)
  self.assertLess(time.monotonic()-t,1.7)
  self.assertEqual(r['status'],'incomplete'); self.assertEqual(r['reason'],'deadline')
  self.assertIsNone(r['assessment']); self.assertEqual(len(r['records']),2)
 def test_bad_analyst_rejected(self):
  r=self.run_guard(analyst_command=self.adapter('print("{invalid")'))
  self.assertEqual(r['status'],'rejected'); self.assertIsNone(r['assessment'])
 def test_collection_failure_never_runs_analyst(self):
  sentinel=Path(self.tmp.name)/'called'
  cmd=self.adapter('from pathlib import Path; Path('+repr(str(sentinel))+').touch()')
  r=self.run_guard('auth',analyst_command=cmd)
  self.assertFalse(sentinel.exists()); self.assertEqual(r['status'],'incomplete')
 def test_duplicate_keys_rejected(self):
  with self.assertRaises(ValueError): guard.strict_json('{"a":1,"a":2}')
 def test_valid_analyst_process(self):
  cmd=self.adapter("""import json,sys
p=json.load(sys.stdin)
a={'run_id':p['run_id'],'tool_claims':[{k:c[k] for k in ('call_id','started','exit_code')} for c in p['tool_results']], 'findings':[{'record_ids':['ch_1'],'text':'One failed charge observed.'}], 'limitations':['No session context.'], 'next_check':'Retrieve authorized session evidence.'}
print(json.dumps(a))
""")
  r=self.run_guard(analyst_command=cmd)
  self.assertEqual(r['status'],'assessment_available'); self.assertIsNotNone(r['assessment'])
 def test_oversize_output(self):
  self.cli.write_text('#!/usr/bin/env python3\nprint("x"*2100000)\n')
  r=self.run_guard(); self.assertEqual(r['status'],'incomplete'); self.assertEqual(r['reason'],'output_limit')

 def test_command_line_failure_envelope(self):
  result=subprocess.run([sys.executable,str(SCRIPT),'--cli',str(self.cli)+'absent',
      '--account','acct_test','--mode','test','--start','100','--end','110','--seconds','1'],
      capture_output=True,text=True,timeout=2)
  self.assertEqual(result.returncode,2)
  packet=json.loads(result.stdout)
  self.assertEqual(packet['status'],'incomplete')
  self.assertFalse(packet['tool_results'][0]['started'])
  self.assertIsNone(packet['tool_results'][0]['exit_code'])

if __name__ == '__main__': unittest.main()
