'use strict';
const {normalize,matchMetadata,decorate}=require('./catalog.cjs');
async function getJson(url,fetcher=global.fetch){const r=await fetcher(url,{signal:AbortSignal.timeout(8000),headers:{Accept:'application/json'}});if(!r.ok)throw new Error('Metadata API HTTP '+r.status);return r.json();}
class Metadata{
 constructor(fetcher=global.fetch){this.fetcher=fetcher;this.cache=new Map();this.tmdbKey='';}
 setTmdbKey(key){this.tmdbKey=String(key||'').trim();this.cache.clear();}
 async find(title,year,kind){
  const key=kind+'|'+normalize(title)+'|'+(year||'');if(this.cache.has(key))return this.cache.get(key);
  const job=this._find(title,year,kind).catch(()=>null);this.cache.set(key,job);return job;
 }
 async _find(title,year,kind){
  // A user-supplied TMDb key enables Czech titles and overview translations.
  if(this.tmdbKey){try{
    const type=kind==='series'?'tv':'movie';const api='https://api.themoviedb.org/3/search/'+type+'?api_key='+encodeURIComponent(this.tmdbKey)+'&language=cs-CZ&query='+encodeURIComponent(title);
    const data=await getJson(api,this.fetcher);
    const items=(data.results||[]).map(x=>({name:x.title||x.name,originalTitle:x.original_title||x.original_name,year:(x.release_date||x.first_air_date||'').slice(0,4),poster:x.poster_path?'https://image.tmdb.org/t/p/w500'+x.poster_path:'',background:x.backdrop_path?'https://image.tmdb.org/t/p/w1280'+x.backdrop_path:'',description:x.overview,genres:[],rating:x.vote_average}));
    const chosen=matchMetadata(title,year,items)||items.find(x=>normalize(x.originalTitle)===normalize(title)&&(!year||Math.abs(Number(x.year)-year)<=1));
    if(chosen)return chosen;
  }catch{}}
  const type=kind==='series'?'series':'movie';
  const url='https://v3-cinemeta.strem.io/catalog/'+type+'/top/search='+encodeURIComponent(title)+'.json';
  const data=await getJson(url,this.fetcher);
  return matchMetadata(title,year,data.metas||[]);
 }
 async enhance(groups,{limit=24}={}){
  const selected=(groups||[]).slice(0,limit);
  const out=[];
  for(let i=0;i<selected.length;i+=5){const batch=selected.slice(i,i+5);out.push(...await Promise.all(batch.map(async g=>decorate(g,await this.find(g.title,g.year,g.kind)))));}
  return [...out,...(groups||[]).slice(limit)];
 }
}
module.exports={Metadata,getJson};
