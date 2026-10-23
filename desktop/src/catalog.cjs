'use strict';
// Only filenames returned by Webshare may create playable titles.
const extensions = /\.(?:mkv|mp4|avi|mov|m4v|ts|webm)$/i;
function normalize(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();}
const tech = /(?:^|[._\s-])(2160p|1080[pi]|720p|480p|4k|uhd|x264|x265|h264|h265|hevc|avc|bluray|blu-ray|web-dl|webrip|hdr10|hdr|remux|hdtv|dvdrip|cz|cze|sk|multi|eng|aac|dts|ddp|ac3|dd5\.1)(?=[._\s-]|$)/i;
function parseFile(f){
  const name=String(f?.name||''); if(!extensions.test(name))return null;
  let stem=name.replace(extensions,'').replace(/[\[\]{}]/g,' ');
  const ep=/\bS(\d{1,2})[ ._-]*E(\d{1,3})\b|\b(\d{1,2})x(\d{1,3})\b/i.exec(stem);
  const season=ep? Number(ep[1]||ep[3]):null,episode=ep?Number(ep[2]||ep[4]):null;
  const yearMatch=/(?:^|[._\s(])((?:19|20)\d{2})(?=[._\s)]|$)/.exec(stem);
  const year=yearMatch?Number(yearMatch[1]):null;
  const marker=ep?ep.index:yearMatch?yearMatch.index:((t)=>t?t.index:stem.length)(tech.exec(stem));
  let title=stem.slice(0,marker).replace(/[._-]+/g,' ').replace(/\s+/g,' ').trim();
  // If a technical marker appears at position zero (e.g. film title "Czech ..."), do not delete the title.
  if(title.length<2){ const until=ep?.index??yearMatch?.index??stem.length;title=stem.slice(0,until).replace(/[._-]+/g,' ').replace(/\s+/g,' ').trim(); }
  if(title.length<2 || /^(?:sample|test|clip|trailer|video)$/i.test(title))return null;
  const qualities=[...name.matchAll(/\b(4320|2160|1080|720|480)[pi]\b/gi)].map(x=>Number(x[1]));
  const resolution=qualities.length?Math.max(...qualities):/\b(4k|uhd)\b/i.test(name)?2160:0;
  const subs=/(?:cz[._ -]?(?:subs?|titulky)|czech[._ -]?subtitles?|české titulky)/i.test(name);
  const dub=/(?:cz[._ -]?(?:dabing|dub|audio)|czech[._ -]?(?:dub|audio)|český dabing)/i.test(name);
  const cz=dub||(!subs&&/(?:^|[. _-])(?:CZ|CZE|CZSK)(?=[. _-]|$)/i.test(name));
  const label=(resolution>=2160?'4K':resolution?resolution+'p':'Kvalita ?')+' · '+(cz?'CZ dle názvu':subs?'CZ titulky':'Jazyk ?')+(/\b(?:HDR|DV|Dolby.Vision)\b/i.test(name)?' · HDR':'');
  return {title,year,season,episode,resolution,cz,subs,label,kind:season!==null?'series':'movie'};
}
function groupFiles(files){
 const map=new Map();const seen=new Set();
 for(const file of files||[]){if(!file?.ident||seen.has(file.ident)||String(file.password||'0')==='1')continue;seen.add(file.ident);
  const p=parseFile(file);if(!p)continue;
  const key=p.kind+'|'+normalize(p.title)+'|'+(p.kind==='movie'?(p.year||''):'');
  if(!map.has(key))map.set(key,{id:key,title:p.title,year:p.year||null,kind:p.kind,files:[],episodes:{},best:p,poster:'',backdrop:'',description:'',rating:null,genres:[]});
  const group=map.get(key);group.files.push({...file,parsed:p});
  if(p.resolution>(group.best?.resolution||0))group.best=p;
  if(p.kind==='series'){const k=`${p.season}:${p.episode}`;(group.episodes[k]??=[]).push({...file,parsed:p});}
 }
 return [...map.values()];
}
function sortEpisodes(group){return Object.entries(group.episodes).sort(([a],[b])=>{const [as,ae]=a.split(':').map(Number),[bs,be]=b.split(':').map(Number);return as-bs||ae-be;}).map(([k,files])=>({season:Number(k.split(':')[0]),episode:Number(k.split(':')[1]),files:sortFiles(files)}));}
function sortFiles(files){return [...files].sort((a,b)=> (b.parsed?.resolution||0)-(a.parsed?.resolution||0)||Number(b.parsed?.cz||false)-Number(a.parsed?.cz||false)||Number(b.size||0)-Number(a.size||0));}
function matchMetadata(title,year,results){const target=normalize(title);for(const row of results||[]){const n=normalize(row.name||row.title);const sourceYear=parseInt(String(row.releaseInfo||row.year||'').slice(0,4),10);if((n===target||n.replace(/\bthe\b/g,'').trim()===target.replace(/\bthe\b/g,'').trim())&&(!year||!sourceYear||Math.abs(year-sourceYear)<=1))return row;}return null;}
function decorate(group,meta){if(!meta)return group;return {...group,displayTitle:meta.name||meta.title||group.title,poster:meta.poster||meta.poster_path||'',backdrop:meta.background||meta.backdrop_path||'',description:meta.description||meta.overview||'',rating:meta.imdbRating||meta.vote_average||null,genres:meta.genres||[],originalTitle:meta.name||meta.title||''};}
function filterAndSort(groups,{query='',kind='all',quality='all',cz=false,sort='relevance',genre='all',year='all'}={}){let rows=(groups||[]).filter(g=>{if(kind!=='all'&&g.kind!==kind)return false;if(query&&!normalize(g.displayTitle||g.title).includes(normalize(query))&&!normalize(g.title).includes(normalize(query)))return false;if(year!=='all'&&Number(g.year)!==Number(year))return false;if(genre!=='all'&&!(g.genres||[]).some(x=>normalize(x).includes(normalize(genre))))return false;return g.files.some(x=>(quality==='all'||x.parsed.resolution>=Number(quality))&&(!cz||x.parsed.cz));});if(sort==='title')rows.sort((a,b)=>(a.displayTitle||a.title).localeCompare(b.displayTitle||b.title,'cs'));if(sort==='year')rows.sort((a,b)=>(b.year||0)-(a.year||0));if(sort==='rating')rows.sort((a,b)=>(b.rating||0)-(a.rating||0));if(sort==='quality')rows.sort((a,b)=>(b.best?.resolution||0)-(a.best?.resolution||0));return rows;}
module.exports={normalize,parseFile,groupFiles,sortEpisodes,sortFiles,matchMetadata,decorate,filterAndSort};
