/* Pure helpers used by the real, stateless specialty browser. */
const assert = require('node:assert/strict');
const nav = require('../assets/site/navigation.js');
const base = 'https://example.org/Medwiki/';
const registry = {
  dermatology: {title:'皮膚科',url:'03_outputs/web/dermatology/index.html'},
  psychiatry: {title:'精神科',url:'03_outputs/web/psychiatry/index.html'}
};
assert.equal(nav.normalise(' ＭＤＤ '),' mdd ');
assert.equal(nav.matchesRow({search:'圓禿 Alopecia areata',group:'毛髮',specialties:['dermatology']},{query:'ALOPECIA 圓禿',group:'毛髮',specialty:'dermatology'}),true);
assert.equal(nav.matchesRow({search:'圓禿 Alopecia areata',group:'毛髮',specialties:['dermatology']},{query:'areata',group:'水疱',specialty:''}),false);
assert.equal(nav.matchesRow({search:'MDD',group:'',specialties:['psychiatry']},{query:'MDD',group:'',specialty:'dermatology'}),false);
assert.deepEqual(nav.pageSlice([1,2,3,4,5],999,2),{items:[5],page:3,pages:3,total:5,start:5,end:5});
assert.deepEqual(nav.pageSlice([],0,15),{items:[],page:1,pages:1,total:0,start:0,end:0});
assert.equal(nav.pageSlice([1,2,3],NaN,2).page,1);
assert.equal(nav.pageSlice([1,2,3],-200,2).page,1);
assert.equal(nav.pageSlice([1,2,3],Infinity,2).page,1);
const state=nav.readState(new URL(base+'?tab=reasoning&q=MDD&group=%E6%B2%BB%E7%99%82&page=999999999999999999999'),['diseases','reasoning'],['治療'],Object.keys(registry));
assert.equal(state.tab,'reasoning');assert.equal(state.query,'MDD');assert.equal(state.group,'治療');
assert.equal(nav.readState(new URL(base+'?tab=evil&group=evil&specialty=unknown&page=-5'),['diseases'],[],Object.keys(registry)).tab,'diseases');
assert.equal(nav.readState(new URL(base+'?q='+('x'.repeat(400))),['diseases'],[],[]).query.length,256);
assert.equal(nav.specialtyContext('psychiatry',registry,base,['psychiatry']).url,base+'03_outputs/web/psychiatry/index.html');
assert.equal(nav.specialtyContext('dermatology',registry,base,['psychiatry']),null,'known but irrelevant specialty must not become a return target');
assert.equal(nav.specialtyContext('unknown',registry,base),null);
assert.equal(nav.specialtyContext('__proto__',registry,base),null);
assert.equal(nav.specialtyContext('dermatology',{dermatology:{title:'bad',url:'https://evil.example/'}},base),null);
assert.equal(nav.specialtyContext('dermatology',{dermatology:{title:'bad',url:'/outside/index.html'}},base),null);
assert.equal(nav.siteUrl('javascript:alert(1)',base),null);
assert.equal(nav.siteUrl('https://example.org/Medwiki-evil/index.html',base),null);
assert.equal(nav.siteUrl('https://example.org/Medwiki/../private/index.html',base),null);
assert.equal(nav.scopedUrl(base+'03_outputs/web/sjs-ten/index.html?atlas=d12#atlas-d12','dermatology',registry,base),base+'03_outputs/web/sjs-ten/index.html?atlas=d12&specialty=dermatology#atlas-d12');
assert.equal(nav.scopedUrl('https://evil.example/','dermatology',registry,base),null);
const restored=nav.stateUrl(new URL(base+'directory.html#results'),{tab:'reasoning',query:'MDD',group:'',specialty:'',page:2},'diseases');
assert.equal(restored.searchParams.get('tab'),'reasoning');assert.equal(restored.searchParams.get('q'),'MDD');assert.equal(restored.searchParams.get('page'),'2');assert.equal(restored.hash,'#results');
assert.equal(nav.stateUrl(restored,{tab:'diseases',query:'',group:'',specialty:'',page:1},'diseases').search,'');
assert.equal(nav.preferredContext(new URL(base+'?atlas=d12&specialty=dermatology'),registry,base,['dermatology']),null,'atlas return has precedence over specialty return');
assert.equal(nav.preferredContext(new URL(base+'?specialty=psychiatry'),registry,base,['psychiatry']).id,'psychiatry');
const mobileBack={href:'old',hidden:false,textContent:'← 返回',hasAttribute:key=>key==='data-mobile-return'};
const bodyBack={href:'old',hidden:false,textContent:'← 返回皮膚科',hasAttribute:()=>false};
assert.equal(nav.applyAtlasReturn([mobileBack,bodyBack],base+'03_outputs/web/dermatology-atlas/index.html?q=SSSS#entry-d12',base),true);
assert.equal(mobileBack.hidden,false,'phone back link must remain visible when returning to atlas');
assert.equal(mobileBack.textContent,'← 返回圖譜');
assert.equal(mobileBack.href,base+'03_outputs/web/dermatology-atlas/index.html?q=SSSS#entry-d12');
assert.equal(bodyBack.hidden,true,'hide only duplicate specialty returns');
assert.equal(nav.applyAtlasReturn([mobileBack], 'https://evil.example/',base),false);
console.log('PASS: specialty paging, filters, URL restoration, project boundaries and validated return context');
