// Archivo GENERADO desde app_remota/index.html con herramientas/generar_app_web.py
// No lo edites a mano: edita index.html y vuelve a generarlo.
#pragma once
#include <pgmspace.h>

const char APP_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f172a">
<meta name="apple-mobile-web-app-capable" content="yes">
<link rel="manifest" href="manifest.json">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-192.png">
<title>Monitoreo del hogar</title>
<style>
:root{--bg:#eef2f7;--card:#fff;--tx:#0f172a;--mut:#64748b;--line:#e2e8f0;--ok:#15803d;--okbg:#dcfce7;--bad:#dc2626;--badbg:#fee2e2;--warn:#b45309;--warnbg:#fef3c7;--off:#64748b;--offbg:#e2e8f0;--acc:#2563eb}
@media(prefers-color-scheme:dark){:root{--bg:#0b1220;--card:#131c2e;--tx:#e5e9f0;--mut:#94a3b8;--line:#223049;--okbg:#14331f;--ok:#4ade80;--badbg:#3b1414;--bad:#f87171;--warnbg:#3a2a0c;--warn:#fbbf24;--offbg:#1e293b;--off:#94a3b8;--acc:#60a5fa}}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--tx);-webkit-tap-highlight-color:transparent}
header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:12px 16px;display:flex;align-items:center;gap:10px}
header h1{font-size:17px;margin:0;flex:1}
header small{display:block;font-size:12px;font-weight:500;color:var(--mut)}
#hora{font-size:12px;color:var(--mut);text-align:right}
.dot{width:10px;height:10px;border-radius:50%;background:var(--off);flex:none}
.dot.ok{background:#22c55e}.dot.bad{background:#ef4444}
main{max-width:720px;margin:0 auto;padding:14px 14px 40px;display:grid;gap:12px}
.btn{border:0;border-radius:10px;padding:10px 14px;font-size:15px;font-weight:600;cursor:pointer;font-family:inherit}
.btn:active{transform:scale(.98)}
.btn.blanco{background:#fff;color:#b91c1c}
.btn.rojo{background:var(--bad);color:#fff}
.btn.azul{background:var(--acc);color:#fff}
.btn.sec{background:var(--offbg);color:var(--tx)}
#banner{display:none;background:#dc2626;color:#fff;border-radius:16px;padding:16px;animation:pulso 1.2s infinite}
#banner h2{margin:0 0 8px;font-size:20px}
#banner ul{margin:0 0 12px;padding-left:20px;line-height:1.5}
@keyframes pulso{50%{box-shadow:0 0 0 8px rgba(220,38,38,.25)}}
.aviso{display:none;border-radius:12px;padding:10px 14px;font-size:14px;background:var(--warnbg);color:var(--warn)}
#alertas{display:flex;align-items:center;justify-content:space-between;gap:10px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 14px;font-size:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px}
.card.alarma{border:2px solid var(--bad)}
.card.inactivo{opacity:.75}
.top{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.top h3{margin:0;font-size:16px;flex:1}
.ico{font-size:22px}
.badge{font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px;white-space:nowrap}
.b-ok{background:var(--okbg);color:var(--ok)}.b-bad{background:var(--badbg);color:var(--bad)}.b-off{background:var(--offbg);color:var(--off)}.b-warn{background:var(--warnbg);color:var(--warn)}
.fila{display:flex;justify-content:space-between;gap:10px;font-size:14px;padding:3px 0;color:var(--mut)}
.fila b{color:var(--tx);font-weight:600;text-align:right}
.barra{height:8px;background:var(--offbg);border-radius:4px;overflow:hidden;margin:2px 0 6px}
.barra i{display:block;height:100%;background:var(--acc);transition:width .5s}
.barra i.alto{background:#f59e0b}.barra i.lleno{background:var(--bad)}
.alarmas{background:var(--badbg);color:var(--bad);border-radius:10px;padding:8px 10px;margin:6px 0;font-size:14px;font-weight:600}
.sw{display:flex;align-items:center;justify-content:space-between;padding:10px 0 2px;border-top:1px solid var(--line);margin-top:8px;font-size:14px}
.tg{position:relative;width:48px;height:28px;flex:none}
.tg input{opacity:0;width:0;height:0}
.tg span{position:absolute;inset:0;background:var(--offbg);border-radius:28px;transition:.2s;cursor:pointer}
.tg span:before{content:"";position:absolute;width:22px;height:22px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
.tg input:checked+span{background:#22c55e}
.tg input:checked+span:before{transform:translateX(20px)}
.tg input:disabled+span{opacity:.4;cursor:not-allowed}
.acciones{display:flex;gap:8px;margin-top:8px}
h2.sec{font-size:14px;color:var(--mut);margin:10px 4px 0;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
#eventos{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:6px 16px;font-size:13px}
.ev{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}
.ev:last-child{border:0}
.ev span{color:var(--mut);white-space:nowrap;font-variant-numeric:tabular-nums}
.ev.a b{color:var(--bad)}
.ev b{font-weight:500}
#config{display:none}
#config label{display:block;font-size:13px;color:var(--mut);margin:10px 0 4px}
#config input{width:100%;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--tx);font-size:15px;font-family:inherit}
#config p{font-size:13px;color:var(--mut);margin:6px 0 0}
#pie{text-align:center;font-size:13px;color:var(--mut)}
#pie a{color:var(--acc);cursor:pointer}
</style>
</head>
<body>
<header>
  <div class="dot" id="dot"></div>
  <h1>Monitoreo del hogar<small id="modo">Conectando…</small></h1>
  <div id="hora">—</div>
</header>
<main>
  <div class="aviso" id="avisoConexion"></div>
  <div class="aviso" id="avisoHora"></div>

  <div class="card" id="config">
    <div class="top"><span class="ico">🌐</span><h3>Acceso remoto</h3></div>
    <p>Datos del servidor MQTT (HiveMQ Cloud). Se guardan sólo en este celular.</p>
    <label>URL WebSocket</label>
    <input id="cUrl" placeholder="wss://xxxxxxxx.s1.eu.hivemq.cloud:8884/mqtt" autocapitalize="off" autocorrect="off">
    <label>Usuario</label>
    <input id="cUser" autocapitalize="off" autocorrect="off">
    <label>Clave</label>
    <input id="cPass" type="password">
    <label>ID de la casa (el mismo ID_CASA de la central)</label>
    <input id="cId" autocapitalize="off" autocorrect="off">
    <div class="acciones"><button class="btn azul" onclick="guardarConfig()">Guardar y conectar</button></div>
  </div>

  <div id="banner">
    <h2>🚨 ALARMA</h2>
    <ul id="listaAlarmas"></ul>
    <button class="btn blanco" onclick="silenciarTodo()">Silenciar todas</button>
  </div>
  <div id="alertas">
    <span id="txtAlertas">🔕 Alertas desactivadas en este celular</span>
    <button class="btn sec" id="btnAlertas" onclick="activarAlertas()">Activar</button>
  </div>
  <div id="nodos"></div>
  <h2 class="sec">Historial</h2>
  <div id="eventos"><div class="ev"><b>Cargando…</b></div></div>
  <div id="pie"></div>
</main>
<script>
const AL={SM:1,AGUA:2,GAS:4,TEMP:8,INT:16};
const FL={C1:1,C2:2,NOCHE:4,MADR:8,CAL:16,ERR:32,HORA:64};
const ICONOS=['🚪','🛏️','🚿','🚰','🔥'];
const MQTT_LIB='https://cdn.jsdelivr.net/npm/mqtt@5/dist/mqtt.min.js';
const CFG_KEY='alarmaHogarCfg';
let modo=null,estado=null,cliente=null,cfg=null,centralOnline=null,ultimoDato=0;
let alertasOn=false,audio=null,ultimoRender='',alarmasPrevias=null;
const $=id=>document.getElementById(id);
const mmss=s=>{s=Math.max(0,s|0);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')};
const min=s=>Math.round(s/60);

/* ---------------- Presentación ---------------- */
function textosAlarma(n){
  const a=n.al,t=[];
  if(a&AL.INT)t.push('Movimiento en la entrada durante la madrugada');
  if(a&AL.SM)t.push('Sin movimiento por '+min(n.id==4?n.l2:n.l1)+' min');
  if(a&AL.AGUA)t.push('Agua corriendo más de '+min(n.l1)+' min');
  if(a&AL.GAS)t.push('Gas detectado por más de '+min(n.l1)+' min');
  if(a&AL.TEMP)t.push('Temperatura alta: '+n.v1.toFixed(1)+' °C');
  return t;
}
function fila(k,v){return `<div class="fila"><span>${k}</span><b>${v}</b></div>`}
function barra(c,l){const p=Math.min(100,l?c*100/l:0);return `<div class="barra"><i class="${p>=100?'lleno':p>=75?'alto':''}" style="width:${p}%"></i></div>`}
function sw(n,sub,etq,on){
  return `<div class="sw"><span>${etq}</span><label class="tg"><input type="checkbox" ${on?'checked':''} ${n.enLinea?'':'disabled'} onchange="cmd(${n.id},this.checked?'activar':'desactivar',${sub})"><span></span></label></div>`;
}
function detalle(n){
  const f=n.fl,h=n.hab&1;let s='';
  const cal=(f&FL.CAL)?' (calentando sensor)':'';
  switch(n.id){
    case 0:
      s+=fila('Movimiento',(n.mov?'Sí':'No')+cal);
      s+=fila('Horario',!(f&FL.HORA)?'Hora no sincronizada':(f&FL.MADR)?'Madrugada: vigilando':'Fuera de la madrugada');
      s+=sw(n,0,'Vigilancia de madrugada',h);break;
    case 1:
      s+=fila('Movimiento',(n.mov?'Sí':'No')+cal);
      if(f&FL.NOCHE)s+=fila('Horario nocturno','Pausa automática (el cuidador puede activarla)');
      if(h&&(f&FL.C1)){s+=fila('Sin movimiento',mmss(n.c1)+' / '+mmss(n.l1));s+=barra(n.c1,n.l1);}
      s+=sw(n,0,'Vigilancia de inactividad',h);break;
    case 2:
      s+=fila('Movimiento',(n.mov?'Sí':'No')+cal);
      if(f&FL.C1){s+=fila('Sin movimiento',mmss(n.c1)+' / '+mmss(n.l1));s+=barra(n.c1,n.l1);}
      else s+=fila('Estado',h?'Esperando que alguien entre':'—');
      s+=sw(n,0,'Vigilancia del baño',h);break;
    case 3:
      s+=fila('Caudal',n.v1.toFixed(1)+' L/min');
      if(f&FL.C1){s+=fila('Agua corriendo',mmss(n.c1)+' / '+mmss(n.l1));s+=barra(n.c1,n.l1);}
      else s+=fila('Llave',n.mov?'Abierta':'Cerrada');
      s+=sw(n,0,'Vigilancia de agua',h);break;
    case 4:{
      const h2=n.hab&2;
      s+=fila('Temperatura',(f&FL.ERR)?'⚠ Error de sensor':n.v1.toFixed(1)+' °C');
      s+=fila('Sensor de gas',n.v2+cal);
      if(f&FL.C1){s+=fila('Gas detectado',mmss(n.c1)+' / '+mmss(n.l1));s+=barra(n.c1,n.l1);}
      s+=fila('Movimiento',n.mov?'Sí':'No');
      if(h2&&(f&FL.C2)){s+=fila('Sin movimiento',mmss(n.c2)+' / '+mmss(n.l2));s+=barra(n.c2,n.l2);}
      s+=sw(n,0,'Gas y temperatura',h);
      s+=sw(n,1,'Presencia (inactividad)',h2);break;}
  }
  return s;
}
function tarjeta(n){
  let badge,cls='card';
  if(!n.visto){badge='<span class="badge b-warn">Esperando nodo</span>';cls+=' inactivo';}
  else if(!n.enLinea){badge='<span class="badge b-warn">Sin conexión</span>';}
  else if(n.al){badge='<span class="badge b-bad">ALARMA</span>';cls+=' alarma';}
  else if(!n.hab){badge='<span class="badge b-off">Desactivado</span>';cls+=' inactivo';}
  else badge='<span class="badge b-ok">Vigilando</span>';
  const al=textosAlarma(n);
  return `<div class="${cls}">
    <div class="top"><span class="ico">${ICONOS[n.id]}</span><h3>${n.nombre}</h3>${badge}</div>
    ${al.length?`<div class="alarmas">${al.join('<br>')}</div><div class="acciones"><button class="btn rojo" onclick="cmd(${n.id},'silenciar')">Silenciar</button></div>`:''}
    ${n.visto?detalle(n):'<div class="fila"><span>Enciende este nodo para que se conecte a la central.</span></div>'}
    ${n.visto&&!n.enLinea?fila('Último dato','hace '+n.hace+' s'):''}
  </div>`;
}
function render(){
  const e=estado;if(!e)return;
  $('hora').textContent=e.hora;
  const ah=$('avisoHora');
  if(!e.horaValida){ah.style.display='block';ah.textContent='La central no tiene la hora; los horarios (madrugada / noche) no funcionan hasta sincronizarla.';}
  else ah.style.display='none';
  const html=e.nodos.map(tarjeta).join('');
  if(html!==ultimoRender){$('nodos').innerHTML=html;ultimoRender=html;}
  const lista=listaAlarmas(e);
  $('banner').style.display=lista.length?'block':'none';
  $('listaAlarmas').innerHTML=lista.map(a=>`<li><b>${a.nombre}:</b> ${a.texto}</li>`).join('');
  document.title=lista.length?'🚨 ALARMA — Hogar':'Monitoreo del hogar';
  $('eventos').innerHTML=e.eventos.length?e.eventos.map(v=>`<div class="ev ${v.a?'a':''}"><span>${v.t}</span><b>${v.x}</b></div>`).join(''):'<div class="ev"><b>Sin eventos</b></div>';
}
function listaAlarmas(e){
  const l=[];e.nodos.forEach(n=>textosAlarma(n).forEach(t=>l.push({nombre:n.nombre,texto:t})));return l;
}
function conexion(ok,texto){
  $('dot').className='dot '+(ok?'ok':'bad');
  const a=$('avisoConexion');a.style.display=ok?'none':'block';a.textContent=texto||'';
}

/* ---------------- Datos recibidos (local o remoto) ---------------- */
function alRecibirEstado(j){
  estado=j;render();
  const actuales=listaAlarmas(j).map(a=>a.nombre+': '+a.texto);
  if(alarmasPrevias!==null){
    const nuevas=actuales.filter(x=>!alarmasPrevias.includes(x));
    if(nuevas.length)notificar(nuevas);
  }
  alarmasPrevias=actuales;
}

/* ---------------- Modo local (servida por la central) ---------------- */
async function cargarLocal(){
  try{
    const c=new AbortController();const to=setTimeout(()=>c.abort(),4000);
    const r=await fetch('/api/estado',{cache:'no-store',signal:c.signal});clearTimeout(to);
    alRecibirEstado(await r.json());conexion(true);
  }catch(err){conexion(false,'Sin conexión con la central. Verifica que el celular esté en el WiFi de la casa.');}
}

/* ---------------- Modo remoto (MQTT por internet) ---------------- */
function leerCfg(){try{return JSON.parse(localStorage.getItem(CFG_KEY))}catch(e){return null}}
function mostrarConfig(){
  const c=leerCfg()||{};
  $('cUrl').value=c.url||'';$('cUser').value=c.user||'';$('cPass').value=c.pass||'';$('cId').value=c.id||'';
  $('config').style.display='block';
}
function guardarConfig(){
  const c={url:$('cUrl').value.trim(),user:$('cUser').value.trim(),pass:$('cPass').value,id:$('cId').value.trim()};
  if(!/^wss?:\/\//.test(c.url)||!c.id){alert('Revisa la URL (debe empezar por wss://) y el ID de la casa.');return;}
  try{localStorage.setItem(CFG_KEY,JSON.stringify(c));}catch(e){}
  cfg=c;$('config').style.display='none';
  if(cliente){try{cliente.end(true)}catch(e){}cliente=null;}
  conectarMqtt();
}
function cargarScript(src){return new Promise((ok,err)=>{const s=document.createElement('script');s.src=src;s.onload=ok;s.onerror=err;document.head.appendChild(s);});}
async function conectarMqtt(){
  conexion(false,'Conectando con el servidor…');
  if(!window.mqtt){
    try{await cargarScript(MQTT_LIB);}catch(e){conexion(false,'No se pudo cargar la librería MQTT. ¿Hay internet?');return;}
  }
  const base='casa/'+cfg.id+'/';
  cliente=mqtt.connect(cfg.url,{username:cfg.user,password:cfg.pass,
    clientId:'app-'+Math.random().toString(16).slice(2,10),reconnectPeriod:4000,connectTimeout:10000,clean:true});
  cliente.on('connect',()=>{cliente.subscribe([base+'estado',base+'online'],{qos:1});actualizarConexionRemota();});
  cliente.on('message',(t,msg)=>{
    const s=msg.toString();
    if(t.endsWith('/online'))centralOnline=(s==='1');
    else{try{ultimoDato=Date.now();alRecibirEstado(JSON.parse(s));}catch(e){}}
    actualizarConexionRemota();
  });
  ['close','offline','reconnect'].forEach(ev=>cliente.on(ev,actualizarConexionRemota));
  cliente.on('error',e=>{if(/auth|Not authorized|Bad User/i.test(e.message||'')){conexion(false,'Usuario o clave del servidor incorrectos.');mostrarConfig();}});
}
function actualizarConexionRemota(){
  if(modo!=='remoto')return;
  if(!cliente||!cliente.connected)conexion(false,'Sin conexión con el servidor. Revisa el internet del celular.');
  else if(centralOnline===false)conexion(false,'La central de la casa está desconectada de internet (se fue la luz o el WiFi). Los datos pueden no estar al día.');
  else if(!ultimoDato)conexion(false,'Esperando datos de la central… Revisa que el ID de la casa sea el mismo.');
  else if(Date.now()-ultimoDato>30000)conexion(false,'Sin datos recientes de la central (hace '+Math.round((Date.now()-ultimoDato)/1000)+' s).');
  else conexion(true);
}

/* ---------------- Acciones ---------------- */
async function cmd(nodo,accion,sub=0){
  if(modo==='local'){
    try{
      const r=await fetch(`/api/cmd?nodo=${nodo}&accion=${accion}&sub=${sub}`,{method:'POST'});
      if(!r.ok)alert('No se pudo enviar: el nodo no está conectado.');
    }catch(e){alert('Sin conexión con la central');}
    ultimoRender='';setTimeout(cargarLocal,500);
  }else{
    if(!cliente||!cliente.connected){alert('Sin conexión con el servidor');ultimoRender='';render();return;}
    cliente.publish('casa/'+cfg.id+'/cmd',`${nodo}:${accion}:${sub}`,{qos:1});
  }
}
async function silenciarTodo(){
  if(modo==='local'){try{await fetch('/api/silenciar_todo',{method:'POST'});}catch(e){}setTimeout(cargarLocal,500);}
  else if(cliente&&cliente.connected)cliente.publish('casa/'+cfg.id+'/cmd','todo:silenciar',{qos:1});
}

/* ---------------- Alertas: sonido, vibración y notificaciones ---------------- */
async function activarAlertas(){
  try{audio=audio||new (window.AudioContext||window.webkitAudioContext)();audio.resume();}catch(e){}
  alertasOn=true;
  let txt='🔔 Sonido y vibración activados';
  if('Notification' in window && window.isSecureContext){
    let p=Notification.permission;
    if(p==='default'){try{p=await Notification.requestPermission();}catch(e){}}
    txt+=p==='granted'?' + notificaciones':' (notificaciones bloqueadas en el navegador)';
  }
  $('txtAlertas').textContent=txt;$('btnAlertas').style.display='none';
  pitido(0.15);
}
function pitido(dur){
  if(!audio)return;
  const o=audio.createOscillator(),g=audio.createGain();
  o.type='square';o.frequency.value=880;g.gain.value=0.15;
  o.connect(g);g.connect(audio.destination);o.start();o.stop(audio.currentTime+dur);
}
async function notificar(lista){
  if(!('Notification' in window)||Notification.permission!=='granted')return;
  const opciones={body:lista.join('\n'),tag:'alarma-hogar',renotify:true,requireInteraction:true,vibrate:[400,200,400,200,400],icon:'icon-192.png'};
  try{
    const reg=navigator.serviceWorker&&await navigator.serviceWorker.getRegistration();
    if(reg)await reg.showNotification('🚨 Alarma en casa',opciones);
    else new Notification('🚨 Alarma en casa',opciones);
  }catch(e){}
}
setInterval(()=>{
  const hay=estado&&estado.nodos.some(n=>n.al);
  if(hay&&alertasOn){pitido(0.4);if(navigator.vibrate)navigator.vibrate(400);}
},1000);

/* ---------------- Arranque: ¿estoy en casa o afuera? ---------------- */
async function iniciar(){
  try{
    const c=new AbortController();const to=setTimeout(()=>c.abort(),2500);
    const r=await fetch('/api/estado',{cache:'no-store',signal:c.signal});clearTimeout(to);
    const j=r.ok?await r.json():null;
    if(j&&j.nodos){
      modo='local';$('modo').textContent='En casa (conexión directa)';
      alRecibirEstado(j);conexion(true);setInterval(cargarLocal,2000);
      fetch('/api/hora?epoch='+Math.floor(Date.now()/1000),{method:'POST'}).catch(()=>{});
      return;
    }
  }catch(e){}
  modo='remoto';$('modo').textContent='Acceso remoto';
  $('pie').innerHTML='<a onclick="mostrarConfig()">Configurar acceso remoto</a>';
  if('serviceWorker' in navigator&&window.isSecureContext)navigator.serviceWorker.register('sw.js').catch(()=>{});
  setInterval(actualizarConexionRemota,3000);
  cfg=leerCfg();
  if(!cfg){conexion(false,'Configura el acceso remoto para empezar.');$('eventos').innerHTML='<div class="ev"><b>—</b></div>';mostrarConfig();return;}
  conectarMqtt();
}
iniciar();
</script>
</body>
</html>
)rawliteral";
