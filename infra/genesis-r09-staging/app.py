"""Minimal *non-authoritative* staged estate role endpoint.

This is a staging landing-zone probe, not the R0.8 execution federation or R0.9 mTLS attestor.
No business operation can ever be accepted by this application.
"""
import hashlib
import http.server
import json
import os

ROLES = frozenset(('authority','gateway','receiver','auditor_witness'))
RELEASE_SHA256 = 'c900b18b4f431394314600918a0ab9669ef22994869dc92790e0ef4dfa958795'

def config(env=None):
    env = env if env is not None else os.environ
    role = env.get('GENESIS_ROLE', '')
    if role not in ROLES:
        raise ValueError('unknown or unset role; deny launch')
    sha = env.get('GENESIS_R08_RELEASE_SHA256', '')
    if sha != RELEASE_SHA256:
        raise ValueError('R0.8 release pin missing or mismatch; deny launch')
    if env.get('GENESIS_BUSINESS_MUTATIONS_ENABLED', '') != 'false':
        raise ValueError('mutations must be explicitly disabled')
    if env.get('GENESIS_SYNTHETIC_ONLY', '') != 'true':
        raise ValueError('synthetic-only must be explicitly enabled')
    if env.get('GENESIS_PRODUCTION_AUTHORITY', '') != 'HOLD':
        raise ValueError('production authority must be HOLD')
    service_id = env.get('RAILWAY_SERVICE_ID', 'local-no-deployment')
    return {'role':role, 'release_sha256':sha,
            'business_mutations_enabled':False,
            'synthetic_only':True,
            'production_authority':'HOLD',
            'independent_host_attested':False,
            'operator_approved':False,
            'receiver_execution_enabled':False,
            'service_id_hash':hashlib.sha256(service_id.encode()).hexdigest()[:12],
            'attestation_protocol':'BLOCKED_NO_INDEPENDENT_MTLS'}

class Handler(http.server.BaseHTTPRequestHandler):
    server_version='Genesis-R09-Preflight/0.1'
    def log_message(self,fmt,*args):
        pass
    def respond(self,code,body):
        payload=json.dumps(body,sort_keys=True,separators=(',',':')).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        if self.path == '/healthz':
            return self.respond(200,{'ok':True,'read_only':True,'role':self.server.cfg['role']})
        if self.path == '/status':
            return self.respond(200,self.server.cfg)
        return self.respond(404,{'error':'unavailable'})
    def do_POST(self):
        return self.respond(403,{'error':'operation_denied','reason':'no_authority_or_mtls_attestation'})
    def do_PUT(self):return self.do_POST()
    def do_PATCH(self):return self.do_POST()
    def do_DELETE(self):return self.do_POST()

def serve(port=8080, env=None, host='0.0.0.0'):
    cfg=config(env)
    if not 1<=port<=65535:raise ValueError('invalid port')
    server=http.server.ThreadingHTTPServer((host,port),Handler)
    server.cfg=cfg
    try:server.serve_forever(poll_interval=.2)
    finally:server.server_close()

if __name__=='__main__':
    port=int(os.environ.get('PORT','8080'))
    serve(port)
