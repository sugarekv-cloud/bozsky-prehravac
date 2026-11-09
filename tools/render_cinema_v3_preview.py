#!/usr/bin/env python3
"""Approximate XML preview, NOT a Kodi screenshot or an emulator.

Reads the exact v3 window XML and generated textures. Fonts, text wrapping,
focus animations and Kodi's runtime layout may differ. Demo title metadata
is not a live Webshare/CSFD catalogue. No credentials are used.

Usage: python tools/render_cinema_v3_preview.py --output /absolute/preview.png
Optional --download-art retrieves illustrative Cinemeta movie artwork.
"""
import argparse
import concurrent.futures
from pathlib import Path
import re,sys,types,xml.etree.ElementTree as ET
from PIL import Image,ImageDraw,ImageFont,ImageOps,ImageChops
ROOT=Path(__file__).resolve().parents[1]
ADDON=ROOT/'plugin.video.fckyo'
SKIN=ADDON/'resources/skins/Default/1080i'
sys.path.insert(0,str(ADDON))
if 'xbmcgui' not in sys.modules:sys.modules['xbmcgui']=types.SimpleNamespace(WindowXMLDialog=object)
from cinema_theme_v3 import ensure_textures
FILMS=[('Interstellar','2014','tt0816692'),('Duna','2021','tt1160419'),
       ('Počátek','2010','tt1375666'),('Matrix','1999','tt0133093'),
       ('Avatar','2009','tt0499549'),('Oppenheimer','2023','tt15398776')]
SYNOPSIS='Lidstvo hledá nový domov za hranicemi sluneční soustavy. Bývalý pilot Cooper se vydává na cestu, na které se střetává čas, gravitace a pouto k jeho rodině.'

def download(art):
 import requests
 def get(f):
  ident=f[2]
  try:
   r=requests.get('https://v3-cinemeta.strem.io/meta/movie/'+ident+'.json',timeout=20);r.raise_for_status();meta=r.json()['meta']
   for k in ('poster','background'):
    p=art/(ident+'-'+k+'.jpg')
    if not p.exists() and meta.get(k):
     resp=requests.get(meta[k],timeout=20);resp.raise_for_status();p.write_bytes(resp.content)
   return ident,True
  except Exception as exc:return ident,str(exc)
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:print(list(pool.map(get,FILMS)))

def split_top(s,op):
 depth=0;start=0;out=[]
 for i,c in enumerate(s):
  if c in '([':depth+=1
  elif c in ')]':depth-=1
  elif c==op and not depth:out.append(s[start:i]);start=i+1
 return out+[s[start:]]

def rgba(s):
 s=s or 'FFFFFFFF'
 return tuple(int(s[i:i+2],16) for i in (2,4,6,0))

class Renderer:
 def __init__(self,props,art,focus):self.props=props;self.art=art;self.focus=focus
 def value(self,s,card):
  s=s or ''
  s=re.sub(r'Window.Property\(([^)]+)\)',lambda m:str(self.props.get(m[1],'')),s)
  s=re.sub(r'ListItem.(?:Property|Art)\(([^)]+)\)',lambda m:str(card.get(m[1],'')),s)
  return s.replace('ListItem.Label',card.get('title',''))
 def visible(self,s,card):
  if not s:return True
  s=s.strip()
  for op in ('|','+'):
   bits=split_top(s,op)
   if len(bits)>1:
    checks=[self.visible(b,card) for b in bits]
    return any(checks) if op=='|' else all(checks)
  if s.startswith('!'):return not self.visible(s[1:],card)
  if s[0] in '[(' and s[-1] in '])':return self.visible(s[1:-1],card)
  if s.startswith('String.IsEmpty('):return not self.value(s[15:-1],card)
  if s.startswith('String.IsEqual('):
   a,b=s[15:-1].rsplit(',',1);return self.value(a,card)==b
  if s.startswith('Control.HasFocus('):return int(s[17:-1])==self.focus
  if s in ('true','false'):return s=='true'
  raise ValueError('Unsupported visibility: '+s)
 def text(self,s,card):return re.sub(r'\$INFO\[(.*?)\]',lambda m:self.value(m[1],card),s or '')
 def card(self,data):
  title,year,ident=data
  return {'title':title,'year':year,'quality':'1080p','poster':str(self.art/(ident+'-poster.jpg')),'fanart':str(self.art/(ident+'-background.jpg'))}
 def draw(self,c,target,ox=0,oy=0,card=None):
  card=card or {}
  if not self.visible(c.findtext('visible'),card):return
  kind=c.get('type');x=ox+int(c.findtext('left') or 0);y=oy+int(c.findtext('top') or 0)
  w=int(c.findtext('width') or 0);h=int(c.findtext('height') or 0)
  if kind in ('group','grouplist'):
   out=Image.new('RGBA',(w or 1920,h or 1080));offset=0
   for child in c.findall('control'):
    if not self.visible(child.findtext('visible'),card):continue
    self.draw(child,out,0,offset,card)
    if kind=='grouplist':offset+=int(child.findtext('height') or 0)+int(c.findtext('itemgap') or 0)
   target.alpha_composite(out,(x,y));return
  if kind=='list':
   out=Image.new('RGBA',(w,h));rid=int(c.get('id'))
   data=FILMS if rid==401 else FILMS[3:]+FILMS[:3]
   for i,f in enumerate(data):
    layout=c.find('focusedlayout' if rid==self.focus and i==0 else 'itemlayout')
    slot=Image.new('RGBA',(int(layout.get('width')),int(layout.get('height'))))
    for child in layout.findall('control'):self.draw(child,slot,card=self.card(f))
    out.alpha_composite(slot,(i*slot.width,0))
   target.alpha_composite(out,(x,y));return
  if w<=0 or h<=0:return
  out=Image.new('RGBA',(w,h))
  focused=str(self.focus)==c.get('id')
  if kind in ('image','button'):
   tex=c.findtext('texture') if kind=='image' else c.findtext('texturefocus' if focused else 'texturenofocus')
   value=self.text(tex,card);path=Path(value)
   if path.is_file():
    im=Image.open(path).convert('RGBA');aspect=c.findtext('aspectratio') or 'stretch'
    if aspect=='keep':
     im=ImageOps.contain(im,(w,h));out.alpha_composite(im,((w-im.width)//2,(h-im.height)//2))
    elif aspect=='scale':out=ImageOps.fit(im,(w,h))
    elif kind=='button' and im.width>2:
     # Approximation of Kodi's border-preserving texture scaling.
     d=ImageDraw.Draw(out);d.rounded_rectangle((0,0,w-1,h-1),radius=10,fill=im.getpixel((im.width//2,im.height//2)))
    else:out=im.resize((w,h),Image.Resampling.LANCZOS)
    if c.findtext('colordiffuse'):out=ImageChops.multiply(out,Image.new('RGBA',(w,h),rgba(c.findtext('colordiffuse'))))
  if kind in ('button','label','textbox'):
   text=self.text(c.findtext('label'),card)
   size={'font12':18,'font13':22,'font32':30,'font45_title':52,'font40_title':48}.get(c.findtext('font'),22)
   font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if size>=30 else '')+'.ttf',size)
   d=ImageDraw.Draw(out);lines=[]
   if kind=='textbox':
    line=''
    for word in text.split():
     new=(line+' '+word).strip()
     if d.textlength(new,font=font)>w and line:lines.append(line);line=word
     else:line=new
    if line:lines.append(line)
   else:
    while text and d.textlength(text,font=font)>w:text=text[:-2]+'…'
    lines=[text]
   for n,line in enumerate(lines):
    tw=d.textlength(line,font=font);tx=int(c.findtext('textoffsetx') or 0);ty=n*(size+9)
    if c.findtext('align')=='center':tx=(w-tw)/2
    elif c.findtext('align')=='right':tx=w-tw
    if kind in ('button','label'):ty+=max(0,(h-size)/2)
    color=c.findtext('focusedcolor') if focused and kind=='button' else c.findtext('textcolor')
    d.text((tx,ty),line,font=font,fill=rgba(color),anchor='lt')
  target.alpha_composite(out,(x,y))
 def render(self,filename):
  image=Image.new('RGBA',(1920,1080),(10,11,15,255))
  for c in ET.parse(SKIN/filename).getroot().findall('./controls/control'):self.draw(c,image)
  return image.convert('RGB')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--download-art',action='store_true');ap.add_argument('--cache',default='/tmp/kivora048-preview');args=ap.parse_args()
 cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
 if args.download_art:download(cache)
 textures=ensure_textures(str(cache))
 props={'cinema_'+k:v for k,v in textures.items()}
 props.update({'detail_'+k:v for k,v in textures.items()});props.update({'settings_'+k:v for k,v in textures.items()})
 props['detail_fade']=textures['detailfade']
 props.update(cinema_brand=str(ADDON/'resources/brand.png'),section_label='DOPORUČENO PRO TEBE',app_version='v0.48.0',active_profile_name='Hlavní profil',hero_title='Interstellar',hero_primary='Přehrát',hero_info='2014   ·   Sci-fi, Drama',hero_plot=SYNOPSIS,hero_art=str(cache/'tt0816692-background.jpg'),hero_poster=str(cache/'tt0816692-poster.jpg'),hero_action='yes',hero_media_action='yes',nav_active='home',row1_heading='Dnes stojí za pozornost',row2_heading='Další filmy pro tebe',menu_open='',detail_title='Interstellar',detail_meta='2014   ·   Sci-fi, Drama',detail_plot=SYNOPSIS,detail_primary='VYBRAT VERZI',detail_quality='DOSTUPNÉ VERZE  ·  1080p',detail_art=str(cache/'tt0816692-background.jpg'),detail_poster=str(cache/'tt0816692-poster.jpg'))
 main=Renderer(props,cache,401).render('fckyo-cinema-v3.xml')
 detail=Renderer(props,cache,301).render('fckyo-detail-v2.xml')
 settings=Renderer(props,cache,501).render('fckyo-settings-v2.xml')
 board=Image.new('RGB',(1920,1772),(10,11,15));board.paste(main,(0,0))
 d=ImageDraw.Draw(board);f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
 d.text((40,1104),'DETAIL TITULU',font=f,fill='#b6bac4');d.text((1000,1104),'NASTAVENÍ',font=f,fill='#b6bac4')
 board.paste(detail.resize((960,540),Image.Resampling.LANCZOS),(0,1150));board.paste(settings.resize((960,540),Image.Resampling.LANCZOS),(960,1150))
 d.text((40,1720),'KIVORA 0.48.0  /  Vizualizace XML · ukázková data · přibližné fonty · není screenshot z Kodi',font=f,fill='#b6bac4')
 output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);board.save(output)
 print(output)
if __name__=='__main__':main()
