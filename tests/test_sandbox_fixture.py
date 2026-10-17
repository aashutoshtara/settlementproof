import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sandbox_fixture import FixtureClient, FixtureSetup, BASE, load_credentials, main, approval_url

class Response(io.BytesIO):
    status=200

class FixtureTests(unittest.TestCase):
    def test_disallowed_endpoints_before_network(self):
        client=FixtureClient('fake-id','fake-secret',lambda *a,**k:self.fail('Unexpected network'))
        for method,path in [('DELETE','/v2/checkout/orders/ORDER'),('POST','https://api-m.paypal.com/v2/checkout/orders'),('POST','/v2/checkout/orders/../live'),('GET','/v1/oauth2/token'),('POST','/v1/payments/payouts')]:
            with self.assertRaises(ValueError):client.request(method,path)
        with self.assertRaises(ValueError):client.request('POST','/v2/checkout/orders',{})
    def test_transport_origin_headers_and_oauth(self):
        seen=[]
        def transport(req,timeout):
            seen.append(req)
            return Response(json.dumps({'access_token':'fake-token'} if len(seen)==1 else {'id':'ORDER','status':'CREATED'}).encode())
        client=FixtureClient('fake-id','fake-secret',transport)
        key='12345678-1234-1234-1234-123456789abc'
        result=client.request('POST','/v2/checkout/orders',{'intent':'CAPTURE'},key)
        self.assertEqual(result['id'],'ORDER')
        self.assertTrue(all(r.full_url.startswith(BASE+'/') for r in seen))
        self.assertEqual(seen[-1].get_header('Paypal-request-id'),key)
        self.assertEqual(seen[0].get_method(),'POST')
    def test_request_id_survives_unknown_outcome_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'state.json'; keys=[]
            class Client:
                def request(self,method,path,body,key):
                    keys.append(key)
                    self_outer.assertTrue(state.exists())
                    if len(keys)==1:raise TimeoutError('Fake interruption')
                    return {'id':'ORDER1','status':'PAYER_ACTION_REQUIRED','payer':{'email_address':'private@example.invalid'},'links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER1'}]}
            self_outer=self
            with self.assertRaises(TimeoutError):FixtureSetup(Client(),state).create()
            result=FixtureSetup(Client(),state).create()
            self.assertEqual(keys[0],keys[1])
            self.assertEqual(state.stat().st_mode&0o777,0o600)
            self.assertNotIn('private@example.invalid',state.read_text())
            self.assertNotIn('payer',result)
            FixtureSetup(Client(),state).create()
            self.assertEqual(len(keys),2)
    def test_fixed_flow_and_no_duplicate_refund(self):
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            class Client:
                def request(self,method,path,body=None,key=None):
                    calls.append((method,path,body,key))
                    if path=='/v2/checkout/orders':
                        return {'id':'ORDER1','status':'PAYER_ACTION_REQUIRED'}
                    if path=='/v2/checkout/orders/ORDER1':
                        return {'id':'ORDER1','status':'APPROVED','intent':'CAPTURE','purchase_units':[{'amount':{'currency_code':'USD','value':'100.00'}}]}
                    if path.endswith('/capture'):
                        return {'id':'ORDER1','status':'COMPLETED','purchase_units':[{'payments':{'captures':[{'id':'CAP1','status':'COMPLETED'}]}}]}
                    if path=='/v2/payments/captures/CAP1':
                        return {'id':'CAP1','status':'COMPLETED','amount':{'currency_code':'USD','value':'100.00'}}
                    if path.endswith('/refund'):
                        return {'id':'REF1','status':'COMPLETED','payer':{'name':'Must not persist'}}
                    raise AssertionError(path)
            setup=FixtureSetup(Client(),Path(directory)/'state.json')
            setup.create(); setup.capture(); result=setup.refund(); setup.refund()
            writes=[c for c in calls if c[0]=='POST']
            self.assertEqual(len(writes),3)
            self.assertEqual(len({c[3] for c in writes}),3)
            self.assertEqual(writes[0][2]['purchase_units'][0]['amount'],{'currency_code':'USD','value':'100.00'})
            self.assertEqual(writes[-1][2],{'amount':{'currency_code':'USD','value':'25.00'}})
            self.assertEqual(result['refund_id'],'REF1')
            self.assertNotIn('Must not persist',setup.path.read_text())
    def test_config_never_echoes_secrets(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{},clear=True):
            config=Path(directory)/'private.json'; config.write_text(json.dumps({'client_id':'fixture-id','client_secret':'do-not-print'}));config.chmod(0o600)
            self.assertEqual(load_credentials(config),('fixture-id','do-not-print'))
            output=io.StringIO()
            with patch('sandbox_fixture.FixtureClient.request',side_effect=ValueError('Sandbox unavailable')),contextlib.redirect_stdout(output):
                self.assertEqual(main(['create','--config',str(config),'--state',str(Path(directory)/'state.json')]),1)
            self.assertNotIn('fixture-id',output.getvalue());self.assertNotIn('do-not-print',output.getvalue())
            config.chmod(0o644)
            with self.assertRaises(ValueError):load_credentials(config)
    def test_live_approval_link_is_never_returned(self):
        self.assertIsNone(approval_url({'links':[{'rel':'approve','href':'https://www.paypal.com/checkoutnow?token=ORDER'}]}))
    def test_callback_ignores_sensitive_query(self):
        from app import Handler
        handler=object.__new__(Handler)
        handler.path='/paypal-return?token=test-secret&PayerID=private-payer'
        handler.allowed=lambda:True
        outputs=[]
        handler.send=lambda value,**kwargs:outputs.append(value)
        handler.do_GET()
        self.assertNotIn(b'test-secret',outputs[0]);self.assertNotIn(b'private-payer',outputs[0])
        self.assertIn(b'Approval is not proof of capture',outputs[0])

if __name__=='__main__':unittest.main()
