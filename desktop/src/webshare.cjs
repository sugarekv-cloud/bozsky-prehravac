'use strict';
const crypto=require('node:crypto');
const {groupFiles,sortFiles}=require('./catalog.cjs');
const BASE='https://webshare.cz/api/';
function md5(data){return crypto.createHash('md5').update(data).digest();}
function md5crypt(password,salt){
 const pass=Buffer.from(String(password),'utf8');
 let s=String(salt||'').replace(/^\$1\$/,'').split('$')[0].slice(0,8);
 const sb=Buffer.from(s,'utf8');const magic=Buffer.from('$1$');
 let ctx=[pass,magic,sb];const alt=md5(Buffer.concat([pass,sb,pass]));
 for(let n=pass.length;n>0;n-=16)ctx.push(alt.subarray(0,Math.min(16,n)));
 for(let n=pass.length;n>0;n>>=1)ctx.push((n&1)?Buffer.from([0]):pass.subarray(0,1));
 let out=md5(Buffer.concat(ctx));
 for(let i=0;i<1000;i++){
  const parts=[(i&1)?pass:out];
  if(i%3)parts.push(sb);
  if(i%7)parts.push(pass);
  parts.push((i&1)?out:pass);
  out=md5(Buffer.concat(parts));
 }
 const abc='./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
 function to64(v,n){let x='';while(n--){x+=abc[v&63];v>>>=6;}return x;}
 const b=(a,b,c,n)=>to64((a<<16)|(b<<8)|c,n);
 return '$1$'+s+'$'+b(out[0],out[6],out[12],4)+b(out[1],out[7],out[13],4)+b(out[2],out[8],out[14],4)+b(out[3],out[9],out[15],4)+b(out[4],out[10],out[5],4)+b(0,0,out[11],2);
}
function unescapeXml(s){return String(s||'').replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos);/gi,(_,e)=>{if(e[0]==='#'){const n=e[1].toLowerCase()==='x'?parseInt(e.slice(2),16):parseInt(e.slice(1),10);return n>=0&&n<=0x10ffff?String.fromCodePoint(n):'';}return {amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"}[e.toLowerCase()]||'';});}
function tag(xml,name){const m=new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${name}>`,'i').exec(xml||'');return m?unescapeXml(m[1]):'';}
function xmlFiles(xml){return [...String(xml||'').matchAll(/<file\b[^>]*>([\s\S]*?)<\/file>/gi)].map(([,x])=>{const r={};for(const k of ['ident','name','img','size','password','type','positive_votes','negative_votes'])r[k]=tag(x,k);return r;}).filter(x=>x.ident&&x.name);}
class Webshare{
 constructor(fetcher=global.fetch){this.fetcher=fetcher;this.token='';}
 setToken(token){this.token=String(token||'').trim();}
 async call(path,params={},requiresToken=false){
  const body=new URLSearchParams(params);
  if(requiresToken&&this.token)body.set('wst',this.token);
  const response=await this.fetcher(BASE+path+'/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','Accept':'text/xml'},body,signal:AbortSignal.timeout(12000)});
  if(!response.ok)throw new Error('Webshare HTTP '+response.status);
  const xml=await response.text();if(tag(xml,'status')!=='OK')throw new Error('Webshare: '+(tag(xml,'message')||tag(xml,'code')||'Chyba API'));
  return xml;
 }
 async login(username,password){
  if(!username||!password)throw new Error('Vyplň přihlašovací údaje.');
  const salt=tag(await this.call('salt',{username_or_email:username}),'salt');if(!salt)throw new Error('Webshare nevrátil sůl hesla.');
  const hash=crypto.createHash('sha1').update(md5crypt(password,salt)).digest('hex');
  const digest=crypto.createHash('md5').update(username+':Webshare:'+hash).digest('hex');
  const xml=await this.call('login',{username_or_email:username,password:hash,digest,keep_logged_in:1});
  const token=tag(xml,'token');if(!token)throw new Error('Webshare nevrátil přihlašovací token.');this.token=token;return true;
 }
 async search(query,{sort='rating',pages=2}={}){
  if(!String(query||'').trim())return [];
  if(!this.token)throw new Error('Nejdřív se přihlas k Webshare.');
  const results=[],seen=new Set();
  for(let p=0;p<Math.min(10,pages);p++){
   const xml=await this.call('search',{what:query,category:'video',sort,limit:100,offset:p*100},true);
   const rows=xmlFiles(xml);
   for(const f of rows){if(f.password==='1'||seen.has(f.ident))continue;seen.add(f.ident);results.push(f);}
   const total=Number(tag(xml,'total')||0);
   if(rows.length<100||(total>0&&(p+1)*100>=total))break;
  }
  return results;
 }
 async verify(ident){try{const xml=await this.call('file_exists',{ident});return tag(xml,'exists')==='1'&&tag(xml,'downloadable')==='1';}catch{return false;}}
 async checkGroups(groups,{max=30}={}){
  const candidates=groups.slice(0,Math.min(groups.length,max*3));const good=[];
  for(let i=0;i<candidates.length;i+=6){
   const batch=candidates.slice(i,i+6);
   const tests=await Promise.all(batch.map(async g=>{for(const f of sortFiles(g.files).slice(0,3)){if(await this.verify(f.ident))return {...g,verified:true};}return null;}));
   good.push(...tests.filter(Boolean));if(good.length>=max)break;
  }
  return good.slice(0,max);
 }
 async variants(group){const aliases=[group.title,group.originalTitle].filter(Boolean);const found=[...group.files];for(const q of aliases.slice(0,2)){try{found.push(...await this.search(q,{pages:3}));}catch{}}
  const idents=new Set();const same=groupFiles(found).find(g=>g.kind===group.kind&&g.title.toLowerCase()===group.title.toLowerCase()&&(!group.year||!g.year||g.year===group.year));
  const choices=sortFiles(same?.files||group.files).filter(f=>{if(idents.has(f.ident))return false;idents.add(f.ident);return true;});
  const checked=[];for(let i=0;i<choices.length;i+=6){const batch=choices.slice(i,i+6);const yes=await Promise.all(batch.map(f=>this.verify(f.ident)));batch.forEach((f,j)=>{if(yes[j])checked.push(f);});if(checked.length>=30)break;}return checked;
 }
 async streamUrl(ident){if(!this.token)throw new Error('Nepřihlášen.');
  if(!(await this.verify(ident)))throw new Error('Soubor už není dostupný.');
  const xml=await this.call('file_link',{ident,download_type:'video_stream',force_https:1},true);
  const url=tag(xml,'link');if(!/^https:\/\//i.test(url))throw new Error('Webshare nevrátil platný HTTPS odkaz.');return url;
 }
}
module.exports={md5crypt,tag,xmlFiles,Webshare};
