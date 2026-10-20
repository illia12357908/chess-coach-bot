"""Builds a self-contained interactive game review page (one .html file, no internet needed)."""
import base64
import html as _html
import json
import zlib

import chess
import chess.svg

TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<style>
:root{--bg:#161512;--panel:#262421;--panel2:#302e2b;--tx:#e8e6e3;--mut:#9b9893;--acc:#7fb34a;--red:#e5483f;--org:#f0892b;--yel:#f2c230}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
a{color:#8cb4ff}
.wrap{max-width:1000px;margin:0 auto;padding:12px 12px 40px;display:grid;gap:12px;grid-template-columns:1fr}
@media(min-width:900px){.wrap{grid-template-columns:minmax(0,520px) minmax(0,1fr);align-items:start}.head{grid-column:1/-1}}
.card{background:var(--panel);border-radius:10px;padding:12px}
.wrap>*{min-width:0}
#stripwrap,#strip{min-width:0;max-width:100%}
.head h1{margin:0 0 2px;font-size:19px}.head .sub{color:var(--mut);font-size:13px}
.res{display:inline-block;padding:2px 9px;border-radius:99px;font-weight:700;font-size:13px;margin-right:6px}
.win{background:#3d6b1f}.loss{background:#8c2b25}.draw{background:#5a5a5a}
.acc{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.acc div{background:var(--panel2);border-radius:8px;padding:8px 10px}
.acc b{font-size:22px}.acc span{color:var(--mut);font-size:12px;display:block}
.counts{margin-top:8px;color:var(--mut);font-size:13px}.counts i{font-style:normal;font-weight:700}
.boardrow{display:flex;gap:6px}
#evalbar{width:14px;border-radius:4px;overflow:hidden;background:#333;position:relative;flex:none}
#evalfill{position:absolute;left:0;right:0;background:#f1f1f1;transition:height .2s}
#board{flex:1;min-width:0;width:100%;height:auto;display:block;border-radius:4px;touch-action:pan-y;user-select:none}
.ctrl{display:flex;gap:6px;margin-top:10px}
.ctrl button{flex:1;background:var(--panel2);color:var(--tx);border:0;border-radius:8px;padding:9px 0;font-size:22px;line-height:1.1;cursor:pointer}
.ctrl button:active{background:#454340}
.ctrl svg{width:22px;height:22px;display:block;margin:0 auto;fill:currentColor}
.ctrl button#bPlay{background:var(--acc);color:#10200a}
#info .tip{margin-top:6px;padding:7px 10px;border-left:3px solid var(--acc);background:var(--panel2);border-radius:0 6px 6px 0}
#info .tip b{color:var(--acc)}
.stop{margin-top:6px;color:var(--acc);font-weight:700;font-size:13px}
#info{margin-top:10px;min-height:62px}
.mvtitle{font-weight:700;font-size:16px;display:flex;align-items:center;gap:8px}
.dot{width:12px;height:12px;border-radius:50%;display:inline-block}
.evals{color:var(--mut);margin:2px 0 4px}
#bestbtn{background:var(--acc);color:#10200a;border:0;border-radius:8px;padding:6px 10px;font-weight:700;margin-left:6px;cursor:pointer}
#graph{width:100%;height:110px;display:block;border-radius:6px;touch-action:none;cursor:pointer}
h2{margin:0 0 8px;font-size:14px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.moments{display:flex;flex-wrap:wrap;gap:6px}
.moments button{background:var(--panel2);color:var(--tx);border:0;border-radius:99px;padding:6px 11px;cursor:pointer;font-size:14px}
.moments button b{margin-left:4px}
#moves{max-height:340px;overflow:auto;display:grid;grid-template-columns:34px 1fr 1fr;gap:2px 4px;font-size:15px}
#moves .n{color:var(--mut);text-align:right;padding:5px 4px 5px 0}
#moves .mv{padding:5px 7px;border-radius:6px;cursor:pointer;white-space:nowrap}
#moves .mv:hover{background:var(--panel2)}
#moves .mv.on{background:#4b6b2c;color:#fff}
.bd{margin-left:3px;font-weight:700}
.tips{color:var(--mut);font-size:12px;margin-top:8px}
#info .why{margin:6px 0 2px;line-height:1.45}
#stripwrap{position:relative;margin-top:10px;background:var(--panel2);border-radius:10px;height:58px;transition:opacity .2s}
#stripwrap.dim{opacity:.45}
#strip{display:flex;align-items:center;overflow-x:auto;height:100%;scrollbar-width:none;-webkit-overflow-scrolling:touch;padding:0 calc(50% - 40px);overscroll-behavior-x:contain}
#strip::-webkit-scrollbar{display:none}
.sm{flex:none;width:80px;text-align:center;font-weight:700;font-size:17px;cursor:pointer;opacity:.3;white-space:nowrap;user-select:none}
.sm .no{display:block;font-size:10px;color:var(--mut);font-weight:500;line-height:1.1}
.sm .bg{font-size:12px;margin-left:2px}
#frame{position:absolute;left:50%;top:5px;bottom:5px;width:80px;margin-left:-40px;border:2px solid var(--acc);border-radius:9px;pointer-events:none}
.km{display:flex;gap:10px;align-items:flex-start;padding:9px 8px;border-radius:8px;cursor:pointer}
.km+.km{border-top:1px solid #353230}
.km:hover,.km.on{background:var(--panel2)}
.kb{flex:none;min-width:30px;height:30px;border-radius:50%;color:#fff;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;padding:0 4px}
.kt{font-size:12px;color:var(--mut);margin-left:6px}
.kd{color:var(--tx);font-size:14px;margin-top:1px}
.chips{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}
.chips span{background:var(--panel2);border-radius:99px;padding:4px 10px;cursor:pointer;font-weight:600}
.chips span.on{background:#4b6b2c;color:#fff}
.btnrow{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.btnrow button{background:var(--panel2);color:var(--tx);border:0;border-radius:8px;padding:8px 12px;font-weight:700;cursor:pointer;font-size:14px}
.btnrow button.go{background:var(--acc);color:#10200a}
#momnav{display:none}
#momnav button{flex:1;background:var(--panel2);color:var(--tx);border:0;border-radius:8px;padding:9px 6px;font-size:14px;cursor:pointer}
#momnav button.go{background:var(--acc);color:#10200a;font-weight:700}
</style></head><body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>__PIECES__</defs></svg>
<div class="wrap">
 <div class="card head">
  <h1 id="title"></h1><div class="sub" id="sub"></div>
  <div class="acc"><div><b id="acc1"></b><span id="acc1n"></span></div><div><b id="acc2"></b><span id="acc2n"></span></div></div>
  <div class="counts" id="counts"></div>
 </div>
 <div>
  <div class="card">
   <div class="boardrow"><div id="evalbar"><div id="evalfill"></div></div><svg id="board" viewBox="-56 0 856 860"></svg></div>
   <div class="ctrl"><button id="bFirst" title="Start"></button><button id="bPrev" title="Back"></button><button id="bPlay" title="Play review (stops at key moments)"></button><button id="bNext" title="Forward"></button><button id="bLast" title="End"></button><button id="bFlip" title="Flip board"></button><button id="bSnd" title="Sound on/off"></button></div>
   <div id="stripwrap"><div id="strip"></div><div id="frame"></div></div>
   <div id="info"></div>
  </div>
  <div class="card" style="margin-top:12px"><h2>Key moments (tap to jump)</h2><div id="moments"></div></div>
 </div>
 <div>
  <div class="card"><h2>Evaluation (tap or drag to jump)</h2><svg id="graph" viewBox="0 0 600 110" preserveAspectRatio="none"></svg></div>
  <div class="card" style="margin-top:12px"><div class="tips" style="margin-top:0">Keys: ← → step, Home/End jump, F flip. Swipe the move strip or the board to move through the game.</div></div>
 </div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const $=id=>document.getElementById(id);
function b64ToBytes(h){h=h.replace(/-/g,'+').replace(/_/g,'/');while(h.length%4)h+='=';const bin=atob(h),o=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)o[i]=bin.charCodeAt(i);return o}
async function loadData(){
  const el=$('data');const txt=el&&el.textContent.trim();
  if(txt)return JSON.parse(txt);
  const h=location.hash.slice(1);
  if(!h)throw new Error('No game data in this link. Open the review from the button in Telegram.');
  if(typeof DecompressionStream==='undefined')throw new Error('This browser is too old. Open the link in Chrome or Safari (iOS 16.4+).');
  const stream=new Blob([b64ToBytes(h)]).stream().pipeThrough(new DecompressionStream('deflate'));
  return JSON.parse(await new Response(stream).text());
}
function boot(D){
const M=D.meta;
const AL='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_',PRM={'!':'q','~':'r','*':'b','+':'n'};
const dsq=c=>{const i=AL.indexOf(c);return String.fromCharCode(97+i%8)+(Math.floor(i/8)+1)};
function dmoves(str){const o=[];let i=0;str=str||'';while(i<str.length){if(str[i]==='.'){o.push('');i+=2;continue}let u=dsq(str[i])+dsq(str[i+1]);i+=2;if(PRM[str[i]]){u+=PRM[str[i]];i++}o.push(u)}return o}
let P;
if(D.plies){P=D.plies.map(p=>({u:p[0],c:p[2],cp:p[3],b:p[4]||'',t:p[5]||'',pv:[],s:''}))}
else{const ms=dmoves(D.m),bs=dmoves(D.b);P=ms.map((u,k)=>({u,c:D.c[k],cp:D.e[k]*10,b:bs[k]||'',t:(D.t&&D.t[k])||'',pv:(D.p&&D.p[k])?dmoves(D.p[k]):[],s:''}))}
const N=P.length;
const COL={R:'#1baca6',B:'#e5483f',M:'#f0892b',I:'#f2c230',T:'#8dbb3f',X:'#6aa84f',O:'#a3a98c'};
const SYM={R:'!!',B:'??',M:'?',I:'?!',T:'★',X:'✓',O:'✓'};
const NAME={R:'Brilliant',B:'Blunder',M:'Mistake',I:'Inaccuracy',T:'Best move',X:'Excellent',O:'Good'};
const PN={K:'king',Q:'queen',R:'rook',B:'bishop',N:'knight',P:'pawn'};
let idx=0,flip=M.me==='black',alt=false,timer=null,inTick=false,line=null,progScroll=false,progT=null,scrollT=null;
const wp=cp=>{cp=Math.max(-1000,Math.min(1000,cp));return 50+50*(2/(1+Math.exp(-0.00368208*cp))-1)};
const fmt=cp=>Math.abs(cp)>=9000?(cp>0?'+M':'-M'):((cp>0?'+':'')+(cp/100).toFixed(1));
const cpAt=i=>i===0?D.start_cp:P[i-1].cp;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function xy(f,r){return flip?[(7-f)*100,r*100]:[f*100,(7-r)*100]}
function sq(u){return [u.charCodeAt(0)-97,+u[1]-1]}
// ---- board positions: B[r][f], r=0 is rank 1 ----
function startBoard(){const b=[];const back='RNBQKBNR';
  b.push([...back]);b.push(Array(8).fill('P'));for(let i=0;i<4;i++)b.push(Array(8).fill(null));
  b.push(Array(8).fill('p'));b.push([...back.toLowerCase()]);return b}
function applyUci(b,u){
  const [f1,r1]=sq(u.slice(0,2)),[f2,r2]=sq(u.slice(2,4));let p=b[r1][f1];
  if(p&&p.toLowerCase()==='p'&&f1!==f2&&!b[r2][f2])b[r1][f2]=null;
  if(p&&p.toLowerCase()==='k'&&Math.abs(f2-f1)===2){const rf=f2>f1?7:0,rt=f2>f1?5:3;b[r1][rt]=b[r1][rf];b[r1][rf]=null}
  if(u.length>4)p=p===p.toUpperCase()?u[4].toUpperCase():u[4].toLowerCase();
  b[r2][f2]=p;b[r1][f1]=null}
function reach(b,t,f,r,f2,r2){const df=f2-f,dr=r2-r;
  if(t==='N')return Math.abs(df*dr)===2;
  if(t==='K')return Math.max(Math.abs(df),Math.abs(dr))===1;
  const dg=Math.abs(df)===Math.abs(dr),st=df===0||dr===0;
  if((t==='B'&&!dg)||(t==='R'&&!st)||(t==='Q'&&!dg&&!st))return false;
  const sf=Math.sign(df),sr=Math.sign(dr);let x=f+sf,y=r+sr;
  while(x!==f2||y!==r2){if(b[y][x])return false;x+=sf;y+=sr}return true}
function sanOf(b,u){
  const [f1,r1]=sq(u.slice(0,2)),[f2,r2]=sq(u.slice(2,4)),pc=b[r1][f1];if(!pc)return u;
  const t=pc.toUpperCase(),dst=u.slice(2,4);
  if(t==='K'&&Math.abs(f2-f1)===2)return f2>f1?'O-O':'O-O-O';
  const cap=b[r2][f2]||(t==='P'&&f1!==f2);
  if(t==='P'){let x=(cap?String.fromCharCode(97+f1)+'x':'')+dst;if(u.length>4)x+='='+u[4].toUpperCase();return x}
  const same=[];
  for(let r=0;r<8;r++)for(let f=0;f<8;f++)if((f!==f1||r!==r1)&&b[r][f]===pc&&reach(b,t,f,r,f2,r2))same.push([f,r]);
  let dis='';
  if(same.length){const sf=same.some(a=>a[0]===f1),sr=same.some(a=>a[1]===r1);dis=!sf?String.fromCharCode(97+f1):(!sr?String(r1+1):String.fromCharCode(97+f1)+(r1+1))}
  return t+dis+(cap?'x':'')+dst}
function attacked(b,f,r,byWhite){
  const g=(x,y)=>x>=0&&x<8&&y>=0&&y<8?b[y][x]:null;
  const Pw=byWhite?'P':'p',Nw=byWhite?'N':'n',Kw=byWhite?'K':'k',Bw=byWhite?'B':'b',Rw=byWhite?'R':'r',Qw=byWhite?'Q':'q';
  const pr=byWhite?r-1:r+1;if(g(f-1,pr)===Pw||g(f+1,pr)===Pw)return true;
  for(const [dx,dy] of [[1,2],[2,1],[-1,2],[-2,1],[1,-2],[2,-1],[-1,-2],[-2,-1]])if(g(f+dx,r+dy)===Nw)return true;
  for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++)if((dx||dy)&&g(f+dx,r+dy)===Kw)return true;
  for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]){
    let x=f+dx,y=r+dy;
    while(x>=0&&x<8&&y>=0&&y<8){const c=b[y][x];if(c){if(c===Qw||((dx===0||dy===0)?c===Rw:c===Bw))return true;break}x+=dx;y+=dy}}
  return false}
function inCheck(b,whiteToMove){const k=whiteToMove?'K':'k';
  for(let r=0;r<8;r++)for(let f=0;f<8;f++)if(b[r][f]===k)return attacked(b,f,r,!whiteToMove);return false}
function sanFull(b,u,last){
  const base=sanOf(b,u),[f1,r1]=sq(u.slice(0,2)),pc=b[r1][f1];if(!pc)return base;
  const nb=b.map(r=>r.slice());applyUci(nb,u);const white=pc===pc.toUpperCase();
  if(!inCheck(nb,!white))return base;
  return base+((last&&/checkmate/i.test(M.term||''))?'#':'+')}
const boards=[startBoard()];
for(let k=0;k<N;k++){const p=P[k],prev=boards[k];p.s=sanFull(prev,p.u,k===N-1);const nb=prev.map(r=>r.slice());applyUci(nb,p.u);boards.push(nb)}
window.__san=i=>P[i].s;window.__fen=i=>{let s=[];for(let r=7;r>=0;r--){let row='',e=0;for(let f=0;f<8;f++){const c=boards[i][r][f];if(!c)e++;else{if(e){row+=e;e=0}row+=c}}if(e)row+=e;s.push(row)}return s.join('/')};
function arrow(u,color){
  const [f1,r1]=sq(u.slice(0,2)),[f2,r2]=sq(u.slice(2,4));
  const a=xy(f1,r1).map(v=>v+50),b=xy(f2,r2).map(v=>v+50);
  const dx=b[0]-a[0],dy=b[1]-a[1],L=Math.hypot(dx,dy)||1,ux=dx/L,uy=dy/L;
  const hx=b[0]-ux*36,hy=b[1]-uy*36;
  return `<line x1="${a[0]+ux*8}" y1="${a[1]+uy*8}" x2="${hx}" y2="${hy}" stroke="${color}" stroke-width="18" stroke-linecap="round" opacity=".85"/>`+
   `<polygon points="${b[0]-ux*4},${b[1]-uy*4} ${hx-uy*30},${hy+ux*30} ${hx+uy*30},${hy-ux*30}" fill="${color}" opacity=".9"/>`;
}
// ---- sound (synthesised, no files) ----
let AC=null,muted=false;try{muted=localStorage.getItem('chessMute')==='1'}catch(e){}
function tone(f,t0,dur,vol,type){const c=AC,o=c.createOscillator(),g=c.createGain();o.type=type||'sine';o.frequency.value=f;
  g.gain.setValueAtTime(0.0001,c.currentTime+t0);g.gain.exponentialRampToValueAtTime(vol,c.currentTime+t0+0.005);
  g.gain.exponentialRampToValueAtTime(0.0001,c.currentTime+t0+dur);o.connect(g).connect(c.destination);o.start(c.currentTime+t0);o.stop(c.currentTime+t0+dur+0.02)}
function click(t0,vol,freq){const c=AC,n=Math.floor(c.sampleRate*0.05),buf=c.createBuffer(1,n,c.sampleRate),d=buf.getChannelData(0);
  for(let i=0;i<n;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/n,3);
  const s=c.createBufferSource();s.buffer=buf;const f=c.createBiquadFilter();f.type='bandpass';f.frequency.value=freq;f.Q.value=1.2;
  const g=c.createGain();g.gain.value=vol;s.connect(f).connect(g).connect(c.destination);s.start(c.currentTime+t0)}
function snd(kind){if(muted)return;try{AC=AC||new(window.AudioContext||window.webkitAudioContext)();if(AC.state==='suspended')AC.resume();
  if(kind==='move'){click(0,1.6,900);tone(180,0,0.06,0.25)}
  else if(kind==='capture'){click(0,2.4,700);tone(130,0,0.09,0.4);click(0.03,1.2,1500)}
  else if(kind==='castle'){click(0,1.6,900);click(0.11,1.8,800);tone(170,0.11,0.06,0.25)}
  else if(kind==='check'){click(0,2,800);tone(660,0.02,0.18,0.18,'triangle')}
  else if(kind==='end'){tone(523,0,0.25,0.2,'triangle');tone(392,0.18,0.35,0.2,'triangle')}
  }catch(e){}}
function sndSan(sn,last){if(last)snd('end');else if(/[+#]$/.test(sn))snd('check');else if(/^O-O/.test(sn))snd('castle');else if(sn.includes('x'))snd('capture');else snd('move')}
function soundFor(i){if(i<=0)return;sndSan(P[i-1].s,i===N)}
const IC={
 first:'<svg viewBox="0 0 24 24"><path d="M6 5h2.4v14H6zM19 5v14L9.5 12z"/></svg>',
 prev:'<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7" style="fill:none;stroke:currentColor;stroke-width:2.8;stroke-linecap:round;stroke-linejoin:round"/></svg>',
 next:'<svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" style="fill:none;stroke:currentColor;stroke-width:2.8;stroke-linecap:round;stroke-linejoin:round"/></svg>',
 last:'<svg viewBox="0 0 24 24"><path d="M15.6 5H18v14h-2.4zM5 5v14l9.5-7z"/></svg>',
 play:'<svg viewBox="0 0 24 24"><path d="M7 4.5v15l12.5-7.5z"/></svg>',
 pause:'<svg viewBox="0 0 24 24"><path d="M6.5 5h4v14h-4zM13.5 5h4v14h-4z"/></svg>',
 flip:'<svg viewBox="0 0 24 24"><path d="M8 3 4 7h3v9h2V7h3zM16 21l4-4h-3V8h-2v9h-3z"/></svg>',
 on:'<svg viewBox="0 0 24 24"><path d="M3 9.5v5h3.6L12 19V5L6.6 9.5z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" style="fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round"/></svg>',
 off:'<svg viewBox="0 0 24 24"><path d="M3 9.5v5h3.6L12 19V5L6.6 9.5z"/><path d="M15.5 9.5l5 5M20.5 9.5l-5 5" style="fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round"/></svg>'};
function syncSnd(){$('bSnd').innerHTML=muted?IC.off:IC.on}
function renderBoard(){
  const view=line?0:((alt&&idx>0)?idx-1:idx);let s='';
  for(let f=0;f<8;f++)for(let r=0;r<8;r++){const [x,y]=xy(f,r);s+=`<rect x="${x}" y="${y}" width="100" height="100" fill="${(f+r)%2?'#ebecd0':'#739552'}"/>`}
  const hl=line?(line.i>0?line.uci[line.i-1]:null):(view>0?P[view-1].u:null);
  if(hl){const u=hl;for(const q of [u.slice(0,2),u.slice(2,4)]){const [f,r]=sq(q),[x,y]=xy(f,r);s+=`<rect x="${x}" y="${y}" width="100" height="100" fill="rgba(255,235,59,.5)"/>`}}
  for(let i=0;i<8;i++){
    const fl=flip?7-i:i,rk=flip?i:7-i;
    s+=`<text x="${i*100+50}" y="842" text-anchor="middle" font-size="34" font-weight="700" fill="#c9c7c2">${String.fromCharCode(97+fl)}</text>`;
    s+=`<text x="-28" y="${i*100+62}" text-anchor="middle" font-size="34" font-weight="700" fill="#c9c7c2">${rk+1}</text>`;
  }
  const Bd=line?line.boards[line.i]:boards[view];
  for(let i=0;i<8;i++)for(let f=0;f<8;f++){const ch=Bd[7-i][f];if(!ch)continue;
    const [x,y]=xy(f,7-i),w=ch===ch.toUpperCase();
    s+=`<use href="#${w?'white':'black'}-${PN[ch.toUpperCase()]}" transform="translate(${x},${y}) scale(2.2222)"/>`}
  if(!line&&alt&&idx>0){const p=P[idx-1];if(p.b&&p.b!==p.u)s+=arrow(p.b,'#7fb34a');s+=arrow(p.u,'#e5483f')}
  if(!line&&!alt&&idx>0){const p=P[idx-1];if(SYM[p.c]){const [f,r]=sq(p.u.slice(2,4)),[x,y]=xy(f,r);
    s+=`<circle cx="${x+84}" cy="${y+16}" r="19" fill="${COL[p.c]}" stroke="#fff" stroke-width="2.5"/><text x="${x+84}" y="${y+24}" text-anchor="middle" font-size="${SYM[p.c].length>1?19:22}" font-weight="800" fill="#fff">${SYM[p.c]}</text>`}}
  $('board').innerHTML=s;
  const pct=wp(line?cpAt(line.k):cpAt(view));const fill=$('evalfill');
  fill.style.height=pct+'%';fill.style[flip?'top':'bottom']='0';fill.style[flip?'bottom':'top']='auto';
}
const mineSide=M.me==='white'?0:1;
function pctForX(k,cp){const w=wp(cp);return Math.round(k%2===0?w:100-w)}
function pctFor(k,cp){const w=wp(cp);return Math.round(k%2===0?w:100-w)}
function explain(k){
  const p=P[k],mine=(k%2===mineSide),before=pctFor(k,cpAt(k)),after=pctFor(k,p.cp);
  const bestSan=(p.b&&p.b!==p.u)?sanOf(boards[k],p.b):'';
  const who=mine?'You':'Your opponent',whose=mine?'your':'their';
  let t='';
  if(p.c==='R')t=(mine?'Brilliant! You gave up material, but the position it creates is stronger. This is the kind of move engines love and humans rarely find.':'Your opponent found a brilliant sacrifice here.');
  else if(p.c==='T')t=mine?'This is the engine’s top choice. Well found.':'Your opponent found the best move here.';
  else if(p.c==='X')t=(mine?'You':'They')+' played an excellent move, almost as good as the very best.';
  else if(p.c==='O')t=(mine?'A good, solid move.':'A solid move by your opponent.')+(bestSan?` The engine slightly preferred ${bestSan}.`:'');
  else{
    const nm={I:'an inaccuracy',M:'a mistake',B:'a blunder'}[p.c];
    t=`${who} played ${nm}. ${mine?'Your':'Their'} winning chances dropped from about ${before}% to ${after}%.`;
    if(bestSan)t+=` ${mine?'The better move was':'They should have played'} <b>${esc(bestSan)}</b>.`;
    if(mine){
      for(const g of p.t.split('|').filter(Boolean)){
        if(g==='missed mate')t+=' You had a forced checkmate available and missed it.';
        else if(g==='allowed mate')t+=' This move allows your opponent a forced checkmate.';
        else if(g==='missed material')t+=' A move that wins material was on the board.';
        else if(g==='missed tactic')t+=' A forcing move (a capture or a check) was stronger here. Before quiet moves, scan checks, captures and threats.';
        else if(g.startsWith('hung '))t+=` It leaves your ${g.slice(5)} to be captured.`;
      }
    }else if(k+1<N&&P[k+1]&&(P[k+1].c==='T'||P[k+1].c==='X'))t+=' You took advantage of it.';
    else if(k+1<N&&P[k+1])t+=' This was a chance to gain an advantage.';
  }
  if(mine&&'BMI'.includes(p.c)){
    const tg=p.t.split('|').filter(Boolean);let tip='';
    if(tg.some(g=>g.startsWith('hung ')))tip='Before you release a piece, ask: what can they capture after this move?';
    else if(tg.includes('missed mate'))tip='When their king looks exposed, list every check first. One of them may end the game.';
    else if(tg.includes('allowed mate'))tip='Before moving a defender of your king, look at their checks and forcing replies.';
    else if(tg.includes('missed tactic')||tg.includes('missed material'))tip='Before a quiet move, scan checks, captures and threats for both sides.';
    else tip='Compare two or three candidate moves before you play'+(bestSan?` — here <b>${esc(bestSan)}</b> was stronger.`:'.');
    t+=`<div class="tip"><b>Next time:</b> ${tip}</div>`}
  return t}
function keyInfo(k){
  const p=P[k],mine=(k%2===mineSide),no=Math.floor(k/2)+1,lab=no+(k%2===0?'. ':'... ')+p.s;
  const before=pctFor(k,cpAt(k)),after=pctFor(k,p.cp),bestSan=(p.b&&p.b!==p.u)?sanOf(boards[k],p.b):'';
  if(p.c==='R'&&mine)return{col:COL.R,sym:'!!',lab,name:'Brilliant',d:'A sacrifice that pays off. Open it and press \u201cShow the idea\u201d to see why it works.'};
  if(mine&&(p.c==='B'||p.c==='M')){
    const tg=p.t.split('|').filter(Boolean);let d=`Winning chances ${before}% \u2192 ${after}%.`;
    const hung=tg.find(g=>g.startsWith('hung '));
    if(hung)d=`Left your ${hung.slice(5)} hanging. `+d;
    else if(tg.includes('missed mate'))d='Missed a forced mate. '+d;
    else if(tg.includes('allowed mate'))d='Allowed a forced mate. '+d;
    else if(tg.includes('missed material'))d='Missed a way to win material. '+d;
    else if(tg.includes('missed tactic'))d='Missed a tactic. '+d;
    if(bestSan)d+=` Better: ${bestSan}.`;
    return{col:COL[p.c],sym:SYM[p.c],lab,name:NAME[p.c],d}}
  if(!mine&&p.c==='B'){
    const nx=P[k+1];
    if(nx&&(nx.c==='T'||nx.c==='X'||nx.c==='R'))return{col:'#6aa84f',sym:'\u2713',lab,name:'Opponent blunder',d:'They blundered and you took advantage of it.'};
    const nb=nx&&nx.b&&nx.b!==nx.u?sanOf(boards[k+1],nx.b):'';
    return{col:'#3b82c4',sym:'!',lab,name:'Chance',d:'They blundered here. You could have gained a big advantage'+(nb?` with ${nb}`:'')+'.'}}
  return null}
const KI=P.map((_,k)=>keyInfo(k));
const isKey=k=>!!KI[k];
function renderInfo(){
  if(line){
    const k=line.k,no=Math.floor(k/2)+1,mineMv=(k%2===mineSide),pc=pctFor(k,cpAt(k));
    const verdict=pc>=75?'a winning advantage':pc>=60?'a clear advantage':pc>=45?'a roughly equal game':'a worse position';
    let chips='';line.sans.forEach((sn,j)=>{const ply=k+j,n=Math.floor(ply/2)+1;
      const lab=(ply%2===0?n+'. ':(j===0?n+'... ':''))+sn;chips+=`<span data-j="${j+1}" class="${line.i===j+1?'on':''}">${esc(lab)}</span>`});
    const played=P[k];
    $('info').innerHTML=`<div class="mvtitle">The engine\u2019s line from move ${no}</div><div class="chips" id="chips">${chips}</div>
      <div class="why">In the game: <b>${esc(played.s)}</b> (${NAME[played.c]}). The engine starts with <b>${esc(line.sans[0])}</b>.</div>
      <div class="why">After this line ${mineMv?'you have':'they have'} ${verdict} (${pc}% winning chances).${line.uci.length<10?'':' The engine\u2019s analysis ends here.'}</div>
      <div class="btnrow"><button class="go" id="lnPlay">Play the line</button><button id="lnBack">Back to the game</button></div>`;
    $('chips').onclick=e=>{const t=e.target.closest('span');if(t){stopPlay();line.i=+t.dataset.j;render();sndSan(line.sans[line.i-1],false)}};
    $('lnPlay').onclick=()=>{if(timer)stopPlay();else{line.i=0;render();playLine()}};
    $('lnBack').onclick=exitLine;
    return}
  if(idx===0){$('info').innerHTML=`<div class="mvtitle">Start of the game</div><div class="why" style="color:var(--mut)">Press <b>Next key moment</b> for a guided tour of the turning points, or step through with ▶ and the arrow keys.</div>`;return}
  const p=P[idx-1],k=idx-1,no=Math.floor(k/2)+1,lbl=no+(k%2===0?'. ':'... ')+p.s;
  let h=`<div class="mvtitle"><span class="dot" style="background:${COL[p.c]}"></span>${esc(lbl)} — ${NAME[p.c]}</div><div class="evals">Evaluation ${fmt(cpAt(idx-1))} → ${fmt(p.cp)}</div><div class="why">${explain(k)}</div>`;
  let btns='';
  if(p.b&&p.b!==p.u&&'BMI'.includes(p.c))btns+=`<button id="bestbtn">${alt?'Back to game':'Show the better move'}</button>`;
  if(p.pv&&p.pv.length>1)btns+=`<button class="go" id="lineBtn">${p.c==='R'?'Show the idea':'Show the line'}</button>`;
  if(btns)h+=`<div class="btnrow">${btns}</div>`;
  $('info').innerHTML=h;const b=$('bestbtn');if(b)b.onclick=()=>{alt=!alt;render()};
  const lb=$('lineBtn');if(lb)lb.onclick=()=>startLine(idx-1);
}
function renderGraph(){
  const g=$('graph'),W=600,H=110,n=Math.max(N,1);
  const X=i=>i*W/n,Y=i=>H*(1-wp(cpAt(i))/100);
  let pts='';for(let i=0;i<=N;i++)pts+=` ${X(i).toFixed(1)},${Y(i).toFixed(1)}`;
  let s=`<rect width="${W}" height="${H}" fill="#3a3835"/><polygon points="0,${H}${pts} ${W},${H}" fill="#e9e9e9"/><line x1="0" x2="${W}" y1="${H/2}" y2="${H/2}" stroke="#888" stroke-dasharray="4 4" stroke-width="1"/>`;
  for(let k=0;k<N;k++){const c=P[k].c;if(c==='B'||c==='M')s+=`<circle cx="${X(k+1)}" cy="${Y(k+1)}" r="${c==='B'?5:4}" fill="${COL[c]}" stroke="#111" stroke-width="1"/>`}
  s+=`<line x1="${X(idx)}" x2="${X(idx)}" y1="0" y2="${H}" stroke="#7fb34a" stroke-width="2.5"/>`;
  g.innerHTML=s;
}
function buildStrip(){
  let h='<div class="sm" data-i="0"><span class="no">&nbsp;</span>Start</div>';
  for(let k=0;k<N;k++){const p=P[k],n=Math.floor(k/2)+1,no=k%2===0?n+'.':n+'…';
    const bg=(p.c==='R'||p.c==='B'||p.c==='M'||p.c==='I'||p.c==='T')?`<span class="bg" style="color:${COL[p.c]}">${SYM[p.c]}</span>`:'';
    h+=`<div class="sm" data-i="${k+1}"><span class="no">${no}</span>${esc(p.s)}${bg}</div>`}
  $('strip').innerHTML=h;
  $('strip').onclick=e=>{const t=e.target.closest('.sm');if(t)go(+t.dataset.i)};
  $('strip').addEventListener('scroll',()=>{fadeStrip();
    if(progScroll)return;clearTimeout(scrollT);
    scrollT=setTimeout(()=>{if(line)return;const j=Math.max(0,Math.min(N,Math.round($('strip').scrollLeft/80)));if(j!==idx){const old=idx;go(j,false,true)}},110)},{passive:true});
}
function fadeStrip(){const st=$('strip'),c=st.scrollLeft/80,it=st.children;
  for(let j=0;j<it.length;j++){it[j].style.opacity=Math.max(.2,1-.4*Math.abs(j-c)).toFixed(2)}}
function centerStrip(i,smooth){const st=$('strip');progScroll=true;clearTimeout(progT);
  st.scrollTo({left:i*80,behavior:smooth?'smooth':'auto'});progT=setTimeout(()=>{progScroll=false;fadeStrip()},smooth?500:50);if(!smooth)fadeStrip()}
function buildMoments(){
  let h='';for(let k=0;k<N;k++){const q=KI[k];if(!q)continue;
    h+=`<div class="km" data-i="${k+1}"><span class="kb" style="background:${q.col}">${q.sym}</span><div><b>${esc(q.lab)}</b><span class="kt">${q.name}</span><div class="kd">${esc(q.d)}</div></div></div>`}
  $('moments').innerHTML=h||'<div style="color:var(--mut)">No mistakes or blunders: a clean game.</div>';
  $('moments').onclick=e=>{const t=e.target.closest('.km');if(!t)return;go(+t.dataset.i);try{$('board').scrollIntoView({behavior:'smooth',block:'center'})}catch(x){}};
}
function renderStrip(){$('stripwrap').classList.toggle('dim',!!line);
  document.querySelectorAll('#moments .km').forEach(e=>e.classList.toggle('on',!line&&+e.dataset.i===idx))}
function render(){renderBoard();renderInfo();renderGraph();renderStrip()}
function go(i,quiet,fromStrip){if(timer&&!quiet&&!inTick)stopPlay();
  line=null;const prev=idx;idx=Math.max(0,Math.min(N,i));alt=false;render();
  if(!fromStrip)centerStrip(idx,!quiet);
  if(!quiet&&Math.abs(idx-prev)===1)soundFor(idx);else if(!quiet&&idx!==prev&&idx>0)snd('move')}
function step(d){go(idx+d)}
function stepLine(d){const n=Math.max(0,Math.min(line.uci.length,line.i+d));if(n===line.i)return;line.i=n;render();if(d>0)sndSan(line.sans[n-1],false);else snd('move')}
function stepAny(d){if(line){stopPlay();stepLine(d)}else step(d)}
function stopPlay(){if(timer){clearInterval(timer);timer=null}$('bPlay').innerHTML=IC.play}
function startLine(k){const p=P[k];const mv=(p.pv&&p.pv.length)?p.pv:(p.b?[p.b]:[]);if(!mv.length)return;
  stopPlay();const bs=[boards[k].map(r=>r.slice())],sans=[];
  for(let j=0;j<mv.length;j++){const b=bs[j];sans.push(sanFull(b,mv[j],false));const nb=b.map(r=>r.slice());applyUci(nb,mv[j]);bs.push(nb)}
  line={k,uci:mv,boards:bs,sans,i:0};alt=false;render();playLine()}
function exitLine(){stopPlay();line=null;render();centerStrip(idx,true)}
function playLine(){$('bPlay').innerHTML=IC.pause;
  timer=setInterval(()=>{if(!line||line.i>=line.uci.length){stopPlay();return}stepLine(1);if(line.i>=line.uci.length)stopPlay()},850)}
function play(){if(line){if(timer){stopPlay();return}if(line.i>=line.uci.length)line.i=0;render();playLine();return}
  if(timer){stopPlay();return}
  if(idx>=N)go(0,true);$('bPlay').innerHTML=IC.pause;
  timer=setInterval(()=>{if(idx>=N){stopPlay();return}inTick=true;step(1);inTick=false;
    if(idx>0&&isKey(idx-1)){stopPlay();$('info').insertAdjacentHTML('beforeend','<div class="stop">Paused at a key moment. Press play to continue.</div>')}
    else if(idx>=N)stopPlay()},520)}
function init(){
  const me=M.me==='white'?M.white:M.black,opp=M.me==='white'?M.black:M.white;
  $('title').innerHTML=`<span class="res ${M.outcome}">${M.outcome==='win'?'Win':M.outcome==='loss'?'Loss':'Draw'}</span>${esc(M.white)} vs ${esc(M.black)}`;
  $('sub').innerHTML=`${esc(M.welo)} vs ${esc(M.belo)} · ${esc(M.tc)} · ${M.opening_url?`<a href="${esc(M.opening_url)}" target="_blank" rel="noopener">${esc(M.opening)}</a>`:esc(M.opening)}${M.url?` · <a href="${esc(M.url)}" target="_blank" rel="noopener">chess.com</a>`:''}${M.term?`<br>${esc(M.term)}`:''}`;
  $('acc1').textContent=M.acc_me;$('acc1n').textContent='Your accuracy ('+me+')';
  $('acc2').textContent=M.acc_opp;$('acc2n').textContent='Opponent ('+opp+')';
  $('counts').innerHTML=`Your moves: <i style="color:${COL.B}">${M.blunders} blunder${M.blunders===1?'':'s'}</i> · <i style="color:${COL.M}">${M.mistakes} mistake${M.mistakes===1?'':'s'}</i> · <i style="color:${COL.I}">${M.inaccuracies} inaccurac${M.inaccuracies===1?'y':'ies'}</i>`;
  document.title=M.white+' vs '+M.black;
  buildStrip();buildMoments();render();centerStrip(0,false);
}
$('bFirst').onclick=()=>{if(line){stopPlay();line.i=0;render()}else go(0)};$('bLast').onclick=()=>{if(line){stopPlay();line.i=line.uci.length;render()}else go(N)};$('bPrev').onclick=()=>stepAny(-1);$('bNext').onclick=()=>stepAny(1);
$('bFirst').innerHTML=IC.first;$('bPrev').innerHTML=IC.prev;$('bNext').innerHTML=IC.next;$('bLast').innerHTML=IC.last;$('bFlip').innerHTML=IC.flip;$('bPlay').innerHTML=IC.play;
$('bPlay').onclick=play;$('bSnd').onclick=()=>{muted=!muted;try{localStorage.setItem('chessMute',muted?'1':'0')}catch(e){}syncSnd();if(!muted)snd('move')};syncSnd();$('bFlip').onclick=()=>{flip=!flip;render()};
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowLeft'){stepAny(-1);e.preventDefault()}else if(e.key==='ArrowRight'){stepAny(1);e.preventDefault()}
  else if(e.key==='Home')go(0);else if(e.key==='End')go(N);else if(e.key==='f'||e.key==='F'){flip=!flip;render()}});
let sx=null;const bd=$('board');
bd.addEventListener('touchstart',e=>{sx=e.touches[0].clientX},{passive:true});
bd.addEventListener('touchend',e=>{if(sx===null)return;const d=e.changedTouches[0].clientX-sx;if(Math.abs(d)>40)stepAny(d<0?1:-1);sx=null});
const gr=$('graph');let drag=false;
function seek(e){const r=gr.getBoundingClientRect();go(Math.round((e.clientX-r.left)/r.width*N))}
gr.addEventListener('pointerdown',e=>{drag=true;seek(e)});gr.addEventListener('pointermove',e=>{if(drag)seek(e)});
window.addEventListener('pointerup',()=>{drag=false});
init();
}
function fail(e){document.querySelector('.wrap').innerHTML='<div class="card" style="grid-column:1/-1"><h1>Chess review</h1><p>'+String(e.message||e).replace(/[<>&]/g,'')+'</p></div>'}
loadData().then(boot).catch(fail);
</script></body></html>
"""


def _pieces_svg():
    """Piece artwork: the classic 'cburnett' set shipped inside python-chess (credit: Colin M.L. Burnett)."""
    return "".join(chess.svg.PIECES.values())


_AL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_PR = {"q": "!", "r": "~", "b": "*", "n": "+"}


def _enc(uci):
    """A move in 2 characters (from/to square), plus 1 for a promotion."""
    m = chess.Move.from_uci(uci)
    return _AL[m.from_square] + _AL[m.to_square] + (_PR[chess.piece_symbol(m.promotion)] if m.promotion else "")


def _game_data(s, username=""):
    """Compact game data shared by the embedded and the link versions (format v2)."""
    me = username or s.get("me", "you")
    plies = s["plies"]
    white_me = s["color"] == "white"
    meta = {
        "me": s["color"],
        "white": me if white_me else s["opp"],
        "black": s["opp"] if white_me else me,
        "welo": s["my_rating"] if white_me else s["opp_rating"],
        "belo": s["opp_rating"] if white_me else s["my_rating"],
        "outcome": s["outcome"], "tc": ((s.get("time_class") or "") + " " + str(s.get("time_control", ""))).strip(),
        "opening": s["opening"], "opening_url": s.get("opening_url", ""), "url": s.get("url", ""),
        "term": s.get("termination", ""), "acc_me": s["accuracy"], "acc_opp": s["opp_accuracy"],
        "blunders": s["blunders"], "mistakes": s["mistakes"], "inaccuracies": s["inaccuracies"],
    }
    return {
        "v": 2, "meta": meta, "start_cp": s.get("start_cp", 0),
        "m": "".join(_enc(p[0]) for p in plies),
        "c": "".join(p[1] for p in plies),
        "e": [int(round(p[2] / 10)) for p in plies],
        "b": "".join(_enc(p[3]) if p[3] and p[3] != p[0] else ".." for p in plies),
        "t": {str(k): p[4] for k, p in enumerate(plies) if len(p) > 4 and p[4]},
        "p": {str(k): "".join(_enc(u) for u in p[5].split()) for k, p in enumerate(plies) if len(p) > 5 and p[5]},
    }


def build_viewer(s, username=""):
    """Self-contained page with the game embedded (works offline from a file)."""
    data = _game_data(s, username)
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    meta = data["meta"]
    title = _html.escape(f"{meta['white']} vs {meta['black']}")
    return TEMPLATE.replace("__TITLE__", title).replace("__PIECES__", _pieces_svg()).replace("__DATA__", payload)


def build_static_page():
    """The page that lives on GitHub Pages; the game itself comes in the URL after the #."""
    return TEMPLATE.replace("__TITLE__", "Chess review").replace("__PIECES__", _pieces_svg()).replace("__DATA__", "")


def review_url(base_url, s, username=""):
    """Link to the Pages viewer with the (compressed) game in the fragment."""
    raw = json.dumps(_game_data(s, username), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    token = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")
    return base_url.rstrip("/") + "/#" + token


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--write-static":
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write(build_static_page())
        print("written", sys.argv[2])
