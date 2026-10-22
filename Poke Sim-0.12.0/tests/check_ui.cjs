const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(path.join(__dirname, '../ui.html'), 'utf8');
const source = html.split('<script>')[1].split('</script>')[0].split('(async function boot()')[0];
const elements = new Map();
function el(id) {
  if (!elements.has(id)) elements.set(id, {value:'',checked:false,innerHTML:'',textContent:'',disabled:false,dataset:{},style:{},classList:{toggle(){}},scrollIntoView(){}});
  return elements.get(id);
}
const context=vm.createContext({console,setTimeout(){},requestAnimationFrame(){},alert(){},fetch(){throw Error('fetch unconfigured');},document:{getElementById:el,querySelectorAll(){return [];},querySelector:el}});
vm.runInContext(source, context);
vm.runInContext('S.timeBudget=true; resetState();',context);
assert.equal(vm.runInContext('S.timeBudget',context),false);
assert.doesNotMatch(html, /id="fresh" checked/);
const queue=[];
context.fetch=()=>new Promise(resolve=>queue.push(resolve));
const response=(name)=>({json:async()=>({a:{name,key:'a',moves:[],hp:10,level:5},b:{name:'B',key:'b',moves:[],hp:10,level:5},turns:[],winner:name,final:{a_hp:10,b_hp:0},seed:1})});
(async()=>{
  el('vA').value='older';el('vB').value='b';
  const older=vm.runInContext('runBattle()',context);
  el('vA').value='newer';
  const newer=vm.runInContext('runBattle()',context);
  queue[1](response('NEWER')); await newer;
  queue[0](response('OLDER')); await older;
  assert.match(el('vOut').innerHTML,/NEWER/);
  queue.length=0;
  const oldGenBattle=vm.runInContext('runBattle()',context);
  vm.runInContext('resetState(); GEN=2;',context);
  el('vOut').innerHTML='new generation';
  queue[0](response('OLD GENERATION')); await oldGenBattle;
  assert.equal(el('vOut').innerHTML,'new generation');
  for (const fail of [false,true]) {
    queue.length=0;
    const start=el('start').onclick();
    vm.runInContext('resetState(); GEN=3; S.running=false; S.error="";',context);
    queue[0]({json:async()=>{if(fail)throw Error('old request failed');return {ok:true};}});await start;
    assert.equal(vm.runInContext('S.running',context),false);
    assert.equal(vm.runInContext('S.error',context),'');
  }
  queue.length=0;
  const start=el('start').onclick();queue[0]({json:async()=>({ok:true})});await start;
  assert.equal(vm.runInContext('S.running',context),true);
  queue.length=0;
  const init=vm.runInContext('init()',context);
  queue[0]({ok:false,json:async()=>({error:'missing generation data'})});await init;
  assert.match(vm.runInContext('S.error',context),/missing generation data/);
  console.log('PASS dashboard reset, Fresh default, battle response order, generation changes, Start success/error isolation');
})().catch(e=>{console.error(e);process.exitCode=1;});
