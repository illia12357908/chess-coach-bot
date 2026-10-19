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
#momnav{display:flex;gap:6px;margin-top:8px}
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
   <div class="boardrow"><div id="evalbar"><div id="evalfill"></div></div><svg id="board" viewBox="0 0 800 800"></svg></div>
   <div class="ctrl"><button id="bFirst" title="Start">⏮</button><button id="bPrev" title="Back">‹</button><button id="bPlay" title="Autoplay">▶</button><button id="bNext" title="Forward">›</button><button id="bLast" title="End">⏭</button><button id="bFlip" title="Flip board">⇅</button><button id="bSnd" title="Sound on/off">🔊</button></div>
   <div id="info"></div><div id="momnav"><button id="mPrev">« Previous key moment</button><button id="mNext" class="go">Next key moment »</button></div>
  </div>
 </div>
 <div>
  <div class="card"><h2>Evaluation (tap or drag to jump)</h2><svg id="graph" viewBox="0 0 600 110" preserveAspectRatio="none"></svg></div>
  <div class="card" style="margin-top:12px"><h2>Your key moments</h2><div class="moments" id="moments"></div></div>
  <div class="card" style="margin-top:12px"><h2>Moves</h2><div id="moves"></div>
   <div class="tips">Keys: ← → step, Home/End jump, F flip. On a phone: swipe the board left/right.</div></div>
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
const P=D.plies.map(p=>({u:p[0],s:p[1],c:p[2],cp:p[3],b:p[4],t:p[5]||''})),N=P.length;
const COL={B:'#e5483f',M:'#f0892b',I:'#f2c230',T:'#8dbb3f',X:'#6aa84f',O:'#a3a98c'};
const SYM={B:'??',M:'?',I:'?!',T:'★',X:'✓',O:'✓'};
const NAME={B:'Blunder',M:'Mistake',I:'Inaccuracy',T:'Best move',X:'Excellent',O:'Good'};
const PN={K:'king',Q:'queen',R:'rook',B:'bishop',N:'knight',P:'pawn'};
let idx=0,flip=M.me==='black',alt=false,timer=null;
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
const boards=[startBoard()];
for(const p of P){const nb=boards[boards.length-1].map(r=>r.slice());applyUci(nb,p.u);boards.push(nb)}
window.__san=i=>sanOf(boards[i],P[i].u);window.__fen=i=>{let s=[];for(let r=7;r>=0;r--){let row='',e=0;for(let f=0;f<8;f++){const c=boards[i][r][f];if(!c)e++;else{if(e){row+=e;e=0}row+=c}}if(e)row+=e;s.push(row)}return s.join('/')};
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
function soundFor(i){if(i<=0)return;const p=P[i-1];
  if(i===N)snd('end');else if(/[+#]$/.test(p.s))snd('check');else if(/^O-O/.test(p.s))snd('castle');else if(p.s.includes('x'))snd('capture');else snd('move')}
function syncSnd(){$('bSnd').textContent=muted?'🔇':'🔊'}
function renderBoard(){
  const view=(alt&&idx>0)?idx-1:idx;let s='';
  for(let f=0;f<8;f++)for(let r=0;r<8;r++){const [x,y]=xy(f,r);s+=`<rect x="${x}" y="${y}" width="100" height="100" fill="${(f+r)%2?'#ebecd0':'#739552'}"/>`}
  if(view>0){const u=P[view-1].u;for(const q of [u.slice(0,2),u.slice(2,4)]){const [f,r]=sq(q),[x,y]=xy(f,r);s+=`<rect x="${x}" y="${y}" width="100" height="100" fill="rgba(255,235,59,.5)"/>`}}
  for(let i=0;i<8;i++){
    const fl=flip?7-i:i,rk=flip?i:7-i;
    s+=`<text x="${i*100+6}" y="${flip?18:792}" font-size="20" font-weight="700" fill="${(i+(flip?0:7))%2?'#739552':'#ebecd0'}">${String.fromCharCode(97+fl)}</text>`;
    s+=`<text x="${flip?776:6}" y="${i*100+22}" font-size="20" font-weight="700" fill="${i%2?'#ebecd0':'#739552'}">${rk+1}</text>`;
  }
  const Bd=boards[view];
  for(let i=0;i<8;i++)for(let f=0;f<8;f++){const ch=Bd[7-i][f];if(!ch)continue;
    const [x,y]=xy(f,7-i),w=ch===ch.toUpperCase();
    s+=`<use href="#${w?'white':'black'}-${PN[ch.toUpperCase()]}" transform="translate(${x},${y}) scale(2.2222)"/>`}
  if(alt&&idx>0){const p=P[idx-1];if(p.b&&p.b!==p.u)s+=arrow(p.b,'#7fb34a');s+=arrow(p.u,'#e5483f')}
  if(!alt&&idx>0){const p=P[idx-1];if(SYM[p.c]){const [f,r]=sq(p.u.slice(2,4)),[x,y]=xy(f,r);
    s+=`<circle cx="${x+84}" cy="${y+16}" r="19" fill="${COL[p.c]}" stroke="#fff" stroke-width="2.5"/><text x="${x+84}" y="${y+24}" text-anchor="middle" font-size="${SYM[p.c].length>1?19:22}" font-weight="800" fill="#fff">${SYM[p.c]}</text>`}}
  $('board').innerHTML=s;
  const pct=wp(cpAt(view));const fill=$('evalfill');
  fill.style.height=pct+'%';fill.style[flip?'top':'bottom']='0';fill.style[flip?'bottom':'top']='auto';
}
const mineSide=M.me==='white'?0:1;
const moments=[];for(let k=0;k<N;k++)if(P[k].c==='B'||P[k].c==='M')moments.push(k+1);
function nextMoment(d){let t=null;
  if(d>0){t=moments.find(m=>m>idx)}else{for(const m of moments)if(m<idx)t=m}
  if(t===null||t===undefined){$('info').insertAdjacentHTML('beforeend','<div class="why" style="color:var(--mut)">No more key moments in that direction.</div>');return}
  go(t)}
function pctFor(k,cp){const w=wp(cp);return Math.round(k%2===0?w:100-w)}
function explain(k){
  const p=P[k],mine=(k%2===mineSide),before=pctFor(k,cpAt(k)),after=pctFor(k,p.cp);
  const bestSan=(p.b&&p.b!==p.u)?sanOf(boards[k],p.b):'';
  const who=mine?'You':'Your opponent',whose=mine?'your':'their';
  let t='';
  if(p.c==='T')t=mine?'This is the engine’s top choice. Well found.':'Your opponent found the best move here.';
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
  return t}
function renderInfo(){
  if(idx===0){$('info').innerHTML=`<div class="mvtitle">Start of the game</div><div class="why" style="color:var(--mut)">Press <b>Next key moment</b> for a guided tour of the turning points, or step through with ▶ and the arrow keys.</div>`;return}
  const p=P[idx-1],k=idx-1,no=Math.floor(k/2)+1,lbl=no+(k%2===0?'. ':'... ')+p.s;
  let h=`<div class="mvtitle"><span class="dot" style="background:${COL[p.c]}"></span>${esc(lbl)} — ${NAME[p.c]}</div><div class="evals">Evaluation ${fmt(cpAt(idx-1))} → ${fmt(p.cp)}</div><div class="why">${explain(k)}</div>`;
  if(p.b&&p.b!==p.u&&'BMI'.includes(p.c))h+=`<div style="margin-top:6px"><button id="bestbtn" style="margin-left:0">${alt?'Back to game':'Show the better move'}</button></div>`;
  $('info').innerHTML=h;const b=$('bestbtn');if(b)b.onclick=()=>{alt=!alt;render()};
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
function buildMoves(){
  let h='';for(let k=0;k<N;k+=2){
    h+=`<div class="n">${k/2+1}.</div>`;
    for(const j of [k,k+1]){if(j>=N){h+='<div></div>';continue}
      const p=P[j],b=SYM[p.c]&&p.c!=='O'&&p.c!=='X'?`<span class="bd" style="color:${COL[p.c]}">${SYM[p.c]}</span>`:'';
      h+=`<div class="mv" data-i="${j+1}">${esc(p.s)}${b}</div>`}}
  $('moves').innerHTML=h;
  $('moves').onclick=e=>{const t=e.target.closest('.mv');if(t){go(+t.dataset.i)}};
}
function renderMoves(){
  document.querySelectorAll('#moves .mv').forEach(e=>e.classList.toggle('on',+e.dataset.i===idx));
  const on=document.querySelector('#moves .mv.on');if(on){const c=$('moves');const t=on.offsetTop-c.offsetTop-c.clientHeight/2+on.clientHeight;c.scrollTo({top:t,behavior:'smooth'})}
}
function render(){renderBoard();renderInfo();renderGraph();renderMoves()}
function go(i,quiet){const prev=idx;idx=Math.max(0,Math.min(N,i));alt=false;render();if(!quiet&&Math.abs(idx-prev)===1)soundFor(idx);else if(!quiet&&idx!==prev&&idx>0)snd('move')}
function step(d){go(idx+d)}
function play(){if(timer){clearInterval(timer);timer=null;$('bPlay').textContent='▶';return}
  if(idx>=N)idx=0;$('bPlay').textContent='⏸';timer=setInterval(()=>{if(idx>=N){play();return}step(1)},900)}
function init(){
  const me=M.me==='white'?M.white:M.black,opp=M.me==='white'?M.black:M.white;
  $('title').innerHTML=`<span class="res ${M.outcome}">${M.outcome==='win'?'Win':M.outcome==='loss'?'Loss':'Draw'}</span>${esc(M.white)} vs ${esc(M.black)}`;
  $('sub').innerHTML=`${esc(M.welo)} vs ${esc(M.belo)} · ${esc(M.tc)} · ${M.opening_url?`<a href="${esc(M.opening_url)}" target="_blank" rel="noopener">${esc(M.opening)}</a>`:esc(M.opening)}${M.url?` · <a href="${esc(M.url)}" target="_blank" rel="noopener">chess.com</a>`:''}${M.term?`<br>${esc(M.term)}`:''}`;
  $('acc1').textContent=M.acc_me;$('acc1n').textContent='Your accuracy ('+me+')';
  $('acc2').textContent=M.acc_opp;$('acc2n').textContent='Opponent ('+opp+')';
  $('counts').innerHTML=`Your moves: <i style="color:${COL.B}">${M.blunders} blunder${M.blunders===1?'':'s'}</i> · <i style="color:${COL.M}">${M.mistakes} mistake${M.mistakes===1?'':'s'}</i> · <i style="color:${COL.I}">${M.inaccuracies} inaccurac${M.inaccuracies===1?'y':'ies'}</i>`;
  document.title=M.white+' vs '+M.black;
  const mine=M.me==='white'?0:1;let km='';
  for(let k=0;k<N;k++){if(k%2===mine&&(P[k].c==='B'||P[k].c==='M')){const no=Math.floor(k/2)+1;km+=`<button data-i="${k+1}">${no}${k%2?'...':'.'} ${esc(P[k].s)}<b style="color:${COL[P[k].c]}">${SYM[P[k].c]}</b></button>`}}
  $('moments').innerHTML=km||'<span style="color:var(--mut)">No mistakes or blunders. Clean game! 👏</span>';
  $('moments').onclick=e=>{const t=e.target.closest('button');if(t)go(+t.dataset.i)};
  buildMoves();render();
}
$('bFirst').onclick=()=>go(0);$('bLast').onclick=()=>go(N);$('bPrev').onclick=()=>step(-1);$('bNext').onclick=()=>step(1);
$('bPlay').onclick=play;$('bSnd').onclick=()=>{muted=!muted;try{localStorage.setItem('chessMute',muted?'1':'0')}catch(e){}syncSnd();if(!muted)snd('move')};syncSnd();$('mNext').onclick=()=>nextMoment(1);$('mPrev').onclick=()=>nextMoment(-1);$('bFlip').onclick=()=>{flip=!flip;render()};
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowLeft'){step(-1);e.preventDefault()}else if(e.key==='ArrowRight'){step(1);e.preventDefault()}
  else if(e.key==='Home')go(0);else if(e.key==='End')go(N);else if(e.key==='f'||e.key==='F'){flip=!flip;render()}});
let sx=null;const bd=$('board');
bd.addEventListener('touchstart',e=>{sx=e.touches[0].clientX},{passive:true});
bd.addEventListener('touchend',e=>{if(sx===null)return;const d=e.changedTouches[0].clientX-sx;if(Math.abs(d)>40)step(d<0?1:-1);sx=null});
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


def _game_data(s, username=""):
    """Compact game data shared by the embedded and the link versions."""
    me = username or s.get("me", "you")
    board = chess.Board()
    plies = []
    for p in s["plies"]:
        u, cls, cp, best = p[0], p[1], p[2], p[3]
        tags = p[4] if len(p) > 4 else ""
        mv = chess.Move.from_uci(u)
        san = board.san(mv)
        board.push(mv)
        row = [u, san, cls, cp, best if best != u else "", tags]
        while row and row[-1] == "":
            row.pop()
        plies.append(row)
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
    return {"meta": meta, "start_cp": s.get("start_cp", 0), "plies": plies}


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
