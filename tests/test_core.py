import copy
import json
import random
import unittest
from io import BytesIO
from assistant import MODEL, investigate
from fixtures import demo
from ledger import reconcile
from money import minor
from paypal import SandboxClient, BASE

class LedgerTests(unittest.TestCase):
    def test_known_demo_results(self):
        r = reconcile(demo())
        self.assertEqual(r['summary'], {'orders':6,'review':3,'matched':2,'replays':1})
        self.assertEqual(r['totals']['USD']['actual_minor'], 48450)
        self.assertEqual(r['totals']['USD']['expected_minor'], 70950)
        self.assertEqual(r['totals']['EUR']['actual_minor'], 0)
    def test_replay_does_not_change_money(self):
        b = demo(); before = reconcile(b)
        b['events'] *= 100
        after = reconcile(b)
        self.assertEqual(before['totals'], after['totals'])
        self.assertGreater(after['summary']['replays'], before['summary']['replays'])
    def test_resource_duplicates_do_not_double_count(self):
        b = demo(); before = reconcile(b)
        b['resources'] *= 10
        self.assertEqual(before['totals'], reconcile(b)['totals'])
    def test_delivery_and_resource_order_invariance(self):
        b = demo(); before = reconcile(b)
        for seed in range(100):
            c = copy.deepcopy(b); rng = random.Random(seed)
            rng.shuffle(c['resources']); rng.shuffle(c['events'])
            after = reconcile(c)
            self.assertEqual(before['totals'], after['totals'])
            self.assertEqual(before['summary'], after['summary'])
    def test_conflicting_resource_quarantined(self):
        b=demo(); r=copy.deepcopy(b['resources'][0]); r['amount']='999.00'; b['resources'].append(r)
        c=reconcile(b)['cases'][0]
        self.assertEqual(c['actual_minor'],0)
        self.assertIn('CONFLICT',[i['code'] for i in c['issues']])
    def test_conflicting_event(self):
        b=demo(); e=copy.deepcopy(b['events'][0]); e['resource_id']='OTHER'; b['events'].append(e)
        self.assertIn('EVENT_CONFLICT',[i['code'] for i in reconcile(b)['cases'][0]['issues']])
    def test_orphan_refund_does_not_reduce_balance(self):
        b=demo(); b['resources'][-1]['capture_id']='ABSENT'
        c=reconcile(b)['cases'][-1]
        self.assertEqual(c['actual_minor'],10000)
        self.assertIn('ORPHAN_REFUND',[i['code'] for i in c['issues']])
    def test_pending_not_counted(self):
        self.assertEqual(reconcile(demo())['cases'][3]['actual_minor'],0)
    def test_refund_cannot_exceed_its_own_capture(self):
        b=demo(); b['invoices']=b['invoices'][-1:]; b['invoices'][0]['expected_capture']='200.00'; b['invoices'][0]['expected_refund']='150.00'
        b['resources']=[r for r in b['resources'] if r['order_id']=='ORDER-1006']
        second=copy.deepcopy(b['resources'][0]); second['id']='CAP-SECOND'; b['resources'].append(second)
        b['resources'][1]['amount']='150.00'
        c=reconcile(b)['cases'][0]
        self.assertIn('OVER_REFUND',[i['code'] for i in c['issues']])
        self.assertEqual(c['refunded_minor'],0)
    def test_refund_under_pending_parent_quarantined(self):
        b=demo(); b['resources'][1]['status']='PENDING'
        c=reconcile(b)['cases'][1]
        self.assertIn('ORPHAN_REFUND',[i['code'] for i in c['issues']])
        self.assertEqual(c['refunded_minor'],0)
    def test_conflict_flags_all_implicated_orders(self):
        b=demo(); r=copy.deepcopy(b['resources'][0]); r['order_id']='ORDER-1002'; b['resources'].append(r)
        for c in reconcile(b)['cases'][:2]:
            self.assertIn('CONFLICT',[i['code'] for i in c['issues']])
            self.assertIn('CAP-1001', [r['id'] for r in c['evidence']])
    def test_exact_money(self):
        self.assertEqual(minor('0.10','USD')+minor('0.20','USD'),30)
        self.assertEqual(minor('30','JPY'),30)
        for value,currency in [('NaN','USD'),('Infinity','USD'),('-1','USD'),('0.001','USD'),('0.1','JPY'),('2','XYZ'),('1E999999999','USD'),('9'*1000,'USD')]:
            with self.assertRaises(ValueError):minor(value,currency)
    def test_full_and_partial_refund_states_preserve_gross(self):
        b=demo(); b['resources'][1]['status']='REFUNDED'
        self.assertEqual(reconcile(b)['cases'][1]['captured_minor'],25000)
    def test_unassigned_resources_visible(self):
        b=demo(); b['invoices']=b['invoices'][1:]
        self.assertEqual(len(reconcile(b)['unassigned_resources']),1)
    def test_model_unknown_abstains(self):
        self.assertTrue(MODEL.classify('write a poem about elephants')['abstained'])
    def test_model_returns_evidence(self):
        a=investigate('Find refunds missing from merchant books', reconcile(demo()))
        self.assertEqual(a['prediction']['intent'],'refunds')
        self.assertEqual(a['cases'][0]['invoice'],'INV-1002')
        self.assertIn('REF-1002',a['cases'][0]['resource_ids'])

class Response(BytesIO):
    status=200
class SandboxTests(unittest.TestCase):
    def test_read_pipeline_and_allowlist(self):
        seen=[]
        values=[{'access_token':'fake-token'}, {'purchase_units':[{'payments':{'captures':[{'id':'CAP1'}]}}]},
                {'id':'CAP1','amount':{'value':'100.00','currency_code':'USD'},'status':'PARTIALLY_REFUNDED'},
                {'id':'REF1','amount':{'value':'20.00','currency_code':'USD'},'status':'COMPLETED','links':[{'rel':'up','href':BASE+'/v2/payments/captures/CAP1'}]}]
        def transport(request, timeout):
            seen.append(request)
            return Response(json.dumps(values[len(seen)-1]).encode())
        client=SandboxClient('fake-id','fake-secret',transport)
        bundle=client.order_bundle('ORDER1','100.00','20.00','USD',['REF1'])
        self.assertTrue(all(r.full_url.startswith(BASE+'/') for r in seen))
        self.assertEqual([r.get_method() for r in seen],['POST','GET','GET','GET'])
        self.assertEqual(reconcile(bundle)['cases'][0]['actual_minor'],8000)
        self.assertNotIn('fake-token',json.dumps(bundle))
        with self.assertRaises(ValueError):client.request('/v2/payments/captures/CAP1/refund')
    def test_invalid_resource_rejected_before_network(self):
        client=SandboxClient('fake','fake',lambda *a,**kw: self.fail('Network should not execute'))
        with self.assertRaises(ValueError):client.order_bundle('../secrets','1.00')

if __name__=='__main__': unittest.main()
