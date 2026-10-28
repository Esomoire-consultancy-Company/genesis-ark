import sys,json
from pathlib import Path
# Optional test dependency: pip install playwright; use a local Chromium binary.
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parent.parent / 'synthetic-baseline'
sys.path.insert(0,str(root))
from engine import SyntheticOracle, load_manifest
m=load_manifest(); oracle=SyntheticOracle(m)
qa=root.parent/'qa';qa.mkdir(exist_ok=True)
scenarios=json.loads((root/'scenarios.json').read_text())
catalog={'synthetic':True,'executable':False,'actors':m['actors'],'organizations':m['organizations'],'memberships':m['memberships'],'representations':m['representations'],'licences':m['licences'],'actions':[p['action'] for p in m['action_policies']]}
script='''window.fetch = async (path, opts={}) => {
  const map = window.__fixtureResponses;
  const key=String(path);
  if(key === '/simulate') {
    const request=JSON.parse(opts.body);
    if(request.request_id && request.request_id.startsWith('SYN-REQ-')) {
       // All synthetic request outcomes are computed deterministically below;
       // this browser harness does not call any live authority.
       return {ok:true,status:200,json:async()=>window.__decisionMap(request)};
    }
    return {ok:false,status:400,json:async()=>({error:'INVALID_SYNTHETIC_REQUEST'})};
  }
  if (!(key in map)) return {ok:false,status:404,json:async()=>({})};
  return {ok:true,status:200,json:async()=>map[key]};
};'''
# Expected outcomes via a fixture lookup on all scenario fields, the oracle validates all 17.
def decide_map(request):
 key=dict(request)
 key.pop('request_id',None)
 for row in scenarios:
  candidate={'environment':'synthetic-ci',**row['request']}
  if candidate==key:
   v=oracle.evaluate({'request_id':request['request_id'],**candidate});return v
 # Generic manual request path has been verified separately by 35 server/engine tests.
 return oracle.evaluate(request)
# Note: use playwright expose_function to compute actual oracle, not JS authoring logic.
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for viewport in [{'width':1440,'height':900},{'width':390,'height':844},{'width':320,'height':720}]:
  page=browser.new_page(viewport=viewport)
  errors=[];page.on('pageerror', lambda e:errors.append(str(e)))
  page.expose_function('__decisionMapPython',decide_map)
  page.add_init_script("window.__fixtureResponses="+json.dumps({'/catalog':catalog,'/scenarios':{'synthetic':True,'executable':False,'scenarios':scenarios}})+";window.__decisionMap=(request)=>window.__decisionMapPython(request);"+script)
  html=(root/'workbench/index.html').read_text().replace('<link rel="stylesheet" href="/workbench.css">','').replace('<script src="/workbench.js" defer></script>','')
  page.set_content(html,wait_until='domcontentloaded')
  page.add_style_tag(content=(root/'workbench/workbench.css').read_text())
  page.evaluate("window.__fixtureResponses="+json.dumps({'/catalog':catalog,'/scenarios':{'synthetic':True,'executable':False,'scenarios':scenarios}}))
  page.evaluate("window.__decisionMap=(request)=>window.__decisionMapPython(request);"+script)
  page.add_script_tag(content=(root/'workbench/workbench.js').read_text())
  page.wait_for_function("document.querySelector('#actor-count').textContent === '10'")
  if viewport['width']==1440:page.screenshot(path=str(qa/'workbench-desktop.png'),full_page=True)
  if viewport['width']==390:page.screenshot(path=str(qa/'workbench-mobile.png'),full_page=True)
  assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
  for i,row in enumerate(scenarios):
   page.locator('#scenario').select_option(str(i))
   page.locator('#run').click()
   page.wait_for_function("!document.querySelector('#run').disabled")
   observed=page.locator('#decision-pill').inner_text()
   if observed!=row['decision']:
    raise AssertionError(f"{viewport['width']} {row['name']}: expected {row['decision']} got {observed}: {page.locator('#decision-explanation').inner_text()}")
   payload=page.locator('#receipt-json').text_content();
   if not payload or not payload.strip().startswith('{'):
    print('BAD RECEIPT',i,row['name'],repr(payload),repr(page.locator('#decision-explanation').inner_text()),errors);raise ValueError('bad receipt')
   receipt=json.loads(payload)
   assert receipt['synthetic'] is True and receipt['executable'] is False
  assert not errors,errors
  print(f"PASS viewport {viewport['width']}, 17 scenario selectors, no overflow, no JS exceptions")
  page.close()
 browser.close()
