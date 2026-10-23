# -*- coding: utf-8 -*-
import re, unicodedata
from difflib import SequenceMatcher
from html.parser import HTMLParser

def normalize(value):
    t=unicodedata.normalize('NFKD',str(value or ''))
    return re.sub(r'[^a-z0-9]+',' ',''.join(c for c in t if not unicodedata.combining(c)).lower()).strip()
def variants(title,other=None):
    names=[title]+[str(x) for x in (other or []) if x]
    out=[]
    for n in names:
        n=re.sub(r'\s*\((?:19|20)\d\d\)\s*$','',n).strip()
        for v in (n,normalize(n)):
            if v and v not in out:out.append(v)
    return out

def get_resolution(name):
    for p,res in ((r'(?<!\d)(?:2160p|4k|uhd)(?!\d)',2160),(r'(?<!\d)1080[pi](?!\d)',1080),(r'(?<!\d)720p(?!\d)',720),(r'(?<!\d)480p(?!\d)',480)):
        if re.search(p,name,re.I):return res
    return 0

def language_score(name):
    n=normalize(name)
    cz=bool(re.search(r'\b(cz|czech|cesky|cestina|dabing|czdub|czdab)\b',n))
    sub=bool(re.search(r'\b(czsub|czsubs|titulky|subtitles|subs)\b',n))
    if cz and not sub:return 85
    if cz and sub:return 12
    return 0

def rank_file(file,title):
    fn=file.get('name','')
    base=re.sub(r'\.(mkv|avi|mp4|wmv|mov|ts)$','',fn,flags=re.I)
    base=re.split(r'\b(?:2160p|1080p|720p|480p|bluray|brrip|webrip|web.dl|hdtv|x264|x265|hevc|h264|hdr|dv)\b',base,flags=re.I)[0]
    target=normalize(title)
    n=normalize(base)
    overlap=SequenceMatcher(None,n,target).ratio() if target else 0
    if overlap<.40 and target not in normalize(fn):return -1
    res=get_resolution(fn)
    q={2160:95,1080:70,720:43,480:20,0:5}.get(res,5)
    hdr=14 if re.search(r'\b(hdr10|hdr|dolby vision)\b',normalize(fn)) else 0
    try:size=int(file.get('size') or 0)
    except (ValueError,TypeError):size=0
    return int(overlap*220)+q+language_score(fn)+hdr+min(size//(1024**3),25)

def display_quality(file):
    name=file.get('name','');res=get_resolution(name)
    values=[('4K' if res==2160 else str(res)+'p') if res else 'Rozlišení neznámé']
    if re.search(r'\b(hdr|hdr10)\b',normalize(name)):values.append('HDR')
    values.append('CZ v názvu' if language_score(name)>=85 else 'Jazyk neověřen')
    return ' · '.join(values)

class CsfdParser(HTMLParser):
    def __init__(self):
        super().__init__();self.items=[];self.current=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and re.match(r'^/film/\d+',a.get('href','')):
            self.current={'title':'','year':'','original':'','link':a['href']}
    def handle_data(self,data):
        if self.current:self.current['title']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.current:
            x=self.current;self.current=None;x['title']=' '.join(x['title'].split())
            if x['title'] and not any(v['link']==x['link'] for v in self.items):self.items.append(x)
def csfd_lookup(term,session):
    try:
        response=session.get('https://www.csfd.cz/hledat/',params={'q':term},timeout=10)
        response.raise_for_status();p=CsfdParser();p.feed(response.text)
        return p.items[:25]
    except Exception:return []
