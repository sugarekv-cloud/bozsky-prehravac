'use strict';
const {app,BrowserWindow,ipcMain,safeStorage,dialog}=require('electron');
const fs=require('node:fs');const path=require('node:path');const {spawn}=require('node:child_process');
const {Webshare}=require('./webshare.cjs');
const {Metadata}=require('./metadata.cjs');
const {groupFiles,filterAndSort,sortEpisodes,sortFiles}=require('./catalog.cjs');
const ws=new Webshare();const metadata=new Metadata();
let window;
let userPath,profile={favorites:[],progress:{},lastQuery:'',mpvPath:'',tmdbKey:''};
let homeCache={at:0,data:null};
const DEBOUNCE_MS=15*60*1000;
function loadProfile(){userPath=app.getPath('userData');const location=path.join(userPath,'profile.json');try{profile={...profile,...JSON.parse(fs.readFileSync(location,'utf8'))};}catch{}try{if(fs.existsSync(path.join(userPath,'wst.bin'))&&safeStorage.isEncryptionAvailable())ws.setToken(safeStorage.decryptString(fs.readFileSync(path.join(userPath,'wst.bin'))));}catch{}try{if(fs.existsSync(path.join(userPath,'tmdb.bin'))&&safeStorage.isEncryptionAvailable())metadata.setTmdbKey(safeStorage.decryptString(fs.readFileSync(path.join(userPath,'tmdb.bin'))));}catch{}}
function saveProfile(){fs.mkdirSync(userPath,{recursive:true});fs.writeFileSync(path.join(userPath,'profile.json'),JSON.stringify(profile));}
function keepSecret(filename,value){const file=path.join(userPath,filename);if(value&&safeStorage.isEncryptionAvailable()){fs.writeFileSync(file,safeStorage.encryptString(value));return true;}try{fs.rmSync(file,{force:true});}catch{}return false;}
function cleanFile(f){return {ident:String(f.ident||''),name:String(f.name||''),size:Number(f.size||0),password:String(f.password||'0'),img:String(f.img||'')};}
function cleanGroups(groups){return (groups||[]).map(g=>({...g,files:g.files.map(x=>({...cleanFile(x),parsed:x.parsed})),episodes:undefined}));}
async function verified(files,limit=45){const grouped=groupFiles(files);if(!grouped.length)return [];
 const candidates=grouped.slice(0,limit*3);
 const checked=await ws.checkGroups(candidates,{max:limit});
 return metadata.enhance(checked,{limit:Math.min(30,checked.length)});
}
async function getHome(){if(homeCache.data&&Date.now()-homeCache.at<DEBOUNCE_MS)return homeCache.data;
 if(!ws.token)throw new Error('Přihlas se k Webshare, aby se zobrazil katalog.');
 const year=new Date().getFullYear();
 const queries=[String(year),String(year-1),'1080p','S01E'];
 const results=await Promise.allSettled(queries.map((q,i)=>ws.search(q,{sort:i===2?'rating':'recent',pages:2})));
 let films=[],series=[];const seen=new Set();
 results.forEach((r,i)=>{if(r.status==='fulfilled'){for(const f of r.value){if(seen.has(f.ident))continue;seen.add(f.ident);if(i===3)series.push(f);else films.push(f);}}});
 if(!films.length&&!series.length)throw new Error('Webshare nevrátil žádné soubory. Ověř účet nebo použij hledání.');
 const movies=await verified(films,35);
 const seriesGroups=await verified([...series,...films].filter(f=>/[sS]\d\d[eE]\d\d|\d+x\d\d/.test(f.name)),24);
 const data={movies:cleanGroups(movies.filter(x=>x.kind==='movie')),series:cleanGroups(seriesGroups.filter(x=>x.kind==='series'))};
 homeCache={data,at:Date.now()};return data;
}
async function search(query,{kind='all',sort='relevance',quality='all',cz=false,pages=3}={}){
 const q=String(query||'').trim().slice(0,150);if(q.length<2)throw new Error('Zadej alespoň 2 znaky.');
 const candidates=[q,q.replace(/\s+/g,'.')];const different=[...new Set(candidates)];const results=await Promise.allSettled(different.map(v=>ws.search(v,{pages:Math.min(10,Math.max(1,Number(pages)||3))})));
 const files=new Map();for(const row of results)if(row.status==='fulfilled')for(const f of row.value)files.set(f.ident,f);
 if(!files.size&&results.every(x=>x.status==='rejected'))throw results[0].reason;
 const groups=await verified([...files.values()],60);
 // Search itself already filters by Webshare filename; metadata translated titles are display-only.
 return cleanGroups(filterAndSort(groups,{kind,quality,cz,sort}));
}
function corsPolicy(w){w.webContents.session.setPermissionRequestHandler((_wc,_permission,cb)=>cb(false));w.webContents.setWindowOpenHandler(()=>({action:'deny'}));}
function createWindow(){window=new BrowserWindow({width:1460,height:910,minWidth:950,minHeight:620,backgroundColor:'#080e19',autoHideMenuBar:true,webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true}});corsPolicy(window);window.loadFile(path.join(__dirname,'../ui/index.html'));}
function bind(){
 ipcMain.handle('session',()=>({authenticated:!!ws.token,secureStorage:safeStorage.isEncryptionAvailable(),tmdbConfigured:!!metadata.tmdbKey}));
 ipcMain.handle('login',async(_,username,password)=>{await ws.login(String(username||''),String(password||''));const saved=keepSecret('wst.bin',ws.token);homeCache={at:0,data:null};return {ok:true,persisted:saved};});
 ipcMain.handle('token',(_,token)=>{ws.setToken(token);keepSecret('wst.bin',ws.token);homeCache={at:0,data:null};return !!ws.token;});
 ipcMain.handle('logout',()=>{ws.setToken('');keepSecret('wst.bin','');homeCache={at:0,data:null};return true;});
 ipcMain.handle('tmdb',(_,key)=>{metadata.setTmdbKey(key);keepSecret('tmdb.bin',metadata.tmdbKey);homeCache={at:0,data:null};return true;});
 ipcMain.handle('home',getHome);
 ipcMain.handle('search',(_,query,options)=>search(query,options||{}));
 ipcMain.handle('variants',async(_,group)=>{if(!group?.title||!Array.isArray(group.files))throw new Error('Chybí titul.');const rows=await ws.variants(group);return rows.map(f=>({...cleanFile(f),parsed:f.parsed}));});
 ipcMain.handle('episodes',async(_,group)=>{if(!group?.title)throw new Error('Chybí seriál.');let files=[...group.files];const queries=[group.title,group.originalTitle].filter(Boolean);for(const q of queries.slice(0,2)){try{files.push(...await ws.search(q,{pages:10}));}catch{}}const g=groupFiles(files).find(g=>g.kind==='series'&&g.title.toLowerCase()===group.title.toLowerCase());return g?sortEpisodes(g):[];});
 ipcMain.handle('stream',async(_,id)=>{if(typeof id!=='string'||!id||id.length>300)throw new Error('Neplatný soubor');return ws.streamUrl(id);});
 ipcMain.handle('choose-mpv',async()=>{const r=await dialog.showOpenDialog(window,{title:'Vyber soubor mpv.exe',filters:process.platform==='win32'?[{name:'mpv',extensions:['exe']}]:undefined,properties:['openFile']});if(r.canceled)return '';profile.mpvPath=r.filePaths[0];saveProfile();return profile.mpvPath;});
 ipcMain.handle('mpv-path',()=>profile.mpvPath);
 ipcMain.handle('external-play',async(_,file,seconds=0)=>{if(!profile.mpvPath||!fs.existsSync(profile.mpvPath))throw new Error('V nastavení vyber mpv.exe.');const link=await ws.streamUrl(file.ident);const args=['--force-window=yes','--keep-open=no','--start='+Math.max(0,Math.floor(Number(seconds)||0)),link];const child=spawn(profile.mpvPath,args,{detached:true,stdio:'ignore',shell:false,windowsHide:false});child.on('error',e=>window?.webContents.send('mpv-error',e.message));child.unref();return true;});
 ipcMain.handle('favorites',()=>profile.favorites);
 ipcMain.handle('favorite',(_,key)=>{const idx=profile.favorites.indexOf(key);if(idx<0)profile.favorites.push(key);else profile.favorites.splice(idx,1);saveProfile();return profile.favorites;});
 ipcMain.handle('get-progress',()=>profile.progress);
 ipcMain.handle('save-progress',(_,key,seconds,duration)=>{if(typeof key!=='string'||key.length>300)throw new Error('Neplatný klíč');const sec=Number(seconds),total=Number(duration);if(!Number.isFinite(sec)||sec<0)return false;profile.progress[key]={seconds:sec,duration:Number.isFinite(total)?total:0,updated:Date.now()};saveProfile();return true;});
 ipcMain.handle('clear-cache',()=>{homeCache={at:0,data:null};return true;});
}
app.whenReady().then(()=>{loadProfile();bind();createWindow();app.on('activate',()=>{if(BrowserWindow.getAllWindows().length===0)createWindow();});});
app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit();});
