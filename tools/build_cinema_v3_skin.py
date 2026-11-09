#!/usr/bin/env python3
"""Generate the three Cinema 3.0 windows from one TV design system.

Run after editing this file. Keep the generated XML in git so Kodi never
requires a build step. Existing v2 windows remain as historical fixtures.
"""
from pathlib import Path
import xml.etree.ElementTree as E

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'plugin.video.fckyo/resources/skins/Default/1080i'
WHITE='FFF5F5F7'; MUTED='FFB6BAC4'; DIM='FF858B98'; RED='FFE50914'
ROWS=tuple(range(401,414))
DRAWER=((201,'Domů'),(208,'Tipy pro tebe'),(202,'Rozkoukané'),
        (203,'Oblíbené'),(205,'Nejlepší podle ČSFD'),(104,'Premiéry'),
        (105,'Žánry'),(109,'Bluey'),(107,'Nastavení'))

def prop(name):return '$INFO[Window.Property('+name+')]'
def item(name):return '$INFO[ListItem.Property('+name+')]'
def nonempty(name):return '!String.IsEmpty(Window.Property('+name+'))'
def equal(name,value):return 'String.IsEqual(Window.Property('+name+'),'+value+')'
def field(c,key,value,**attrs):E.SubElement(c,key,attrs).text=str(value)
def control(parent,kind,x,y,w,h,ident=None,visible=None):
 attrs={'type':kind}
 if ident is not None:attrs['id']=str(ident)
 c=E.SubElement(parent,'control',attrs)
 for k,v in zip(('left','top','width','height'),(x,y,w,h)):field(c,k,v)
 if visible:field(c,'visible',visible)
 return c

def img(parent,x,y,w,h,texture,visible=None,aspect='stretch',tint=None):
 c=control(parent,'image',x,y,w,h,visible=visible);field(c,'texture',texture);field(c,'aspectratio',aspect)
 if tint:field(c,'colordiffuse',tint)
 return c

def label(parent,x,y,w,h,text,font='font13',color=WHITE,visible=None,align='left',textbox=False):
 c=control(parent,'textbox' if textbox else 'label',x,y,w,h,visible=visible)
 field(c,'font',font);field(c,'textcolor',color);field(c,'label',text)
 if not textbox:field(c,'align',align);field(c,'aligny','center');field(c,'scroll','false')
 return c

def button(parent,ident,x,y,w,h,text,prefix='cinema',primary=False,visible=None):
 c=control(parent,'button',x,y,w,h,ident,visible)
 field(c,'label',text);field(c,'font','font13');field(c,'align','center');field(c,'aligny','center')
 field(c,'textcolor','FF111217' if primary else WHITE);field(c,'focusedcolor','FFFFFFFF')
 field(c,'texturefocus',prop(prefix+'_cta_focus'),border='10')
 field(c,'texturenofocus',prop(prefix+('_cta' if primary else '_button')),border='10')
 return c

def nav(c,**links):
 for k,v in links.items():field(c,'on'+k,v)
def first_row(c,direction='down',fallback=103):
 missing=[]
 for i,rid in enumerate(ROWS,1):
  condition=' + '.join(missing+[nonempty('row%d_heading'%i)])
  field(c,'on'+direction,rid,condition=condition)
  missing.append('String.IsEmpty(Window.Property(row%d_heading))'%i)
 field(c,'on'+direction,fallback)

def window(default):
 r=E.Element('window');field(r,'defaultcontrol',default,always='true')
 co=E.SubElement(r,'coordinates')
 for k,v in (('system',1),('posx',0),('posy',0)):field(co,k,v)
 return r,E.SubElement(r,'controls')

def write(name,r):
 E.indent(r,space='    ')
 E.ElementTree(r).write(OUT/name,encoding='utf-8',xml_declaration=True)

def shelf(parent,index):
 rid=ROWS[index];g=control(parent,'group',0,0,1728,320,visible=nonempty('row%d_heading'%(index+1)))
 label(g,4,0,1712,40,prop('row%d_heading'%(index+1)),font='font32')
 c=control(g,'list',0,48,1728,272,rid);field(c,'orientation','horizontal');field(c,'scrolltime',180)
 nav(c,left=200)
 missing=[]
 for prev in reversed(range(index)):
  cond=' + '.join(missing+[nonempty('row%d_heading'%(prev+1))]);field(c,'onup',ROWS[prev],condition=cond)
  missing.append('String.IsEmpty(Window.Property(row%d_heading))'%(prev+1))
 field(c,'onup',108,condition=equal('hero_action','yes'));field(c,'onup',106)
 missing=[]
 for following in range(index+1,len(ROWS)):
  cond=' + '.join(missing+[nonempty('row%d_heading'%(following+1))]);field(c,'ondown',ROWS[following],condition=cond)
  missing.append('String.IsEmpty(Window.Property(row%d_heading))'%(following+1))
 field(c,'ondown',rid)
 for focused in (False,True):
  layout=E.SubElement(c,'focusedlayout' if focused else 'itemlayout',{'width':'346','height':'272'})
  img(layout,4,4,330,186,prop('cinema_tile'))
  art='!String.IsEqual(ListItem.Property(is_more),yes) + !String.IsEqual(ListItem.Property(is_file),yes)'
  img(layout,8,8,322,178,'$INFO[ListItem.Art(fanart)]',art+' + !String.IsEmpty(ListItem.Art(fanart))',aspect='scale')
  img(layout,8,8,322,178,'$INFO[ListItem.Art(poster)]',art+' + String.IsEmpty(ListItem.Art(fanart)) + !String.IsEmpty(ListItem.Art(poster))',aspect='keep')
  fallback='[String.IsEmpty(ListItem.Art(fanart)) + String.IsEmpty(ListItem.Art(poster)) | String.IsEqual(ListItem.Property(is_file),yes)] + !String.IsEqual(ListItem.Property(is_more),yes)'
  label(layout,24,46,290,100,'$INFO[ListItem.Label]',color=MUTED,visible=fallback,textbox=True)
  label(layout,20,40,298,64,'+',font='font45_title',visible='String.IsEqual(ListItem.Property(is_more),yes)',align='center')
  label(layout,20,112,298,40,'Zobrazit další',visible='String.IsEqual(ListItem.Property(is_more),yes)',align='center')
  # Rating badge is wholly within the artwork; provenance comes from Python.
  rate='!String.IsEmpty(ListItem.Property(rating_label))'
  img(layout,16,16,128,30,prop('cinema_chip'),rate)
  label(layout,22,16,116,30,item('rating_label'),font='font12',visible=rate,align='center')
  progress=control(layout,'progress',8,180,322,6,visible='String.IsEqual(ListItem.Property(is_resume),yes)')
  field(progress,'info','ListItem.Property(progress)');field(progress,'texturebg',prop('cinema_chip'));field(progress,'midtexture',prop('cinema_accent'))
  label(layout,8,198,322,32,'$INFO[ListItem.Label]',color=WHITE if focused else 'FFDADCE2')
  label(layout,8,238,90,28,item('year'),font='font12',color=MUTED)
  label(layout,112,238,218,28,item('quality'),font='font12',color=MUTED,align='right')
  if focused:
   for x,y,w,h in ((4,4,330,4),(4,186,330,4),(4,4,4,186),(330,4,4,186)):
    img(layout,x,y,w,h,prop('cinema_focus'),visible='Control.HasFocus(%s)'%rid)

def main_window():
 r,c=window(401)
 c.append(E.Comment('Cinema 3.0: shared TV typography, quiet header, cinematic hero, five-card rails.'))
 img(c,0,0,1920,1080,prop('cinema_background'))
 img(c,560,0,1360,650,prop('hero_art'),nonempty('hero_art'),aspect='scale')
 img(c,1250,110,460,460,prop('hero_poster'),'String.IsEmpty(Window.Property(hero_art)) + '+nonempty('hero_poster'),aspect='keep')
 img(c,0,0,1920,660,prop('cinema_fade'))
 img(c,0,0,1920,148,prop('cinema_headerfade'))
 img(c,156,44,238,56,prop('cinema_brand'),aspect='keep')
 menu=button(c,200,64,44,64,56,'☰');nav(menu,left=103,right=106,down=201)
 # Down opens the drawer explicitly; clicking is also supported by Python.
 field(menu,'ondown',401,condition='!'+equal('menu_open','yes'))
 menu.find('ondown').set('condition',equal('menu_open','yes'))
 top=[(106,'Domů','home',470,116),(101,'Filmy','movies',602,116),
      (102,'Seriály','shows',734,142),(111,'Živá TV','live_tv',892,142),
      (103,'Hledat','search',1050,142)]
 for i,(ident,name,active,x,w) in enumerate(top):
  b=button(c,ident,x,44,w,56,name)
  b.find('texturenofocus').text=prop('cinema_clear')
  nav(b,left=200 if not i else top[i-1][0],right=top[i+1][0] if i+1<len(top) else 200,up=ident)
  first_row(b)
  img(c,x+18,104,w-36,3,prop('cinema_accent'),equal('nav_active',active))
 label(c,1392,46,432,48,prop('active_profile_name'),font='font12',color=MUTED,align='right')
 label(c,96,156,960,30,prop('section_label'),font='font12',color=MUTED)
 label(c,92,196,950,128,prop('hero_title'),font='font45_title',textbox=True)
 label(c,96,334,950,36,prop('hero_info'),color='FFE7E8EC')
 label(c,96,390,820,84,prop('hero_plot'),color='FFD0D3DB',textbox=True)
 actions=[(108,96,222,prop('hero_primary')),(110,334,168,'Podrobnosti'),(112,518,146,'Trailer'),(113,680,210,'+ Oblíbené')]
 for i,(ident,x,w,title) in enumerate(actions):
  visible=equal('hero_action','yes') if ident==108 else equal('hero_media_action','yes')
  b=button(c,ident,x,490,w,60,title,primary=ident==108,visible=visible)
  nav(b,left=actions[i-1][0] if i else 200,right=actions[i+1][0] if i+1<len(actions) else 103,up=106)
  # Live TV has only one action, so do not route into a hidden Details button.
  if ident==108:
   b.remove(b.find('onright'));field(b,'onright',110,condition=equal('hero_media_action','yes'));field(b,'onright',103)
  first_row(b)
 g=control(c,'grouplist',96,596,1728,430,610);field(g,'orientation','vertical');field(g,'itemgap',24);field(g,'scrolltime',180)
 for i in range(13):shelf(g,i)
 label(c,96,1040,1450,24,'Šipky  procházet     OK  vybrat     Zpět  návrat',font='font12',color=DIM)
 label(c,1600,1040,224,24,prop('app_version'),font='font12',color=DIM,align='right')
 label(c,96,626,1200,100,prop('ui_status'),color=MUTED,visible=' + '.join('String.IsEmpty(Window.Property(row%d_heading))'%i for i in range(1,14)),textbox=True)
 # Drawer rendered last: an opaque surface, never labels over the hero text.
 drawer=control(c,'group',0,0,1920,1080,visible=equal('menu_open','yes'))
 img(drawer,0,0,1920,1080,prop('cinema_scrim'))
 img(drawer,40,128,430,838,prop('cinema_panel'))
 label(drawer,76,152,340,42,'Moje KIVORA',font='font32')
 for i,(ident,name) in enumerate(DRAWER):
  b=button(drawer,ident,64,214+i*76,382,64,name)
  b.find('align').text='left';field(b,'textoffsetx',24)
  nav(b,up=DRAWER[i-1][0] if i else 200,down=DRAWER[i+1][0] if i+1<len(DRAWER) else 201,left=200)
  first_row(b,'right')
 return r

def detail_window():
 r,c=window(301)
 img(c,0,0,1920,1080,prop('detail_background'))
 img(c,520,0,1400,700,prop('detail_art'),nonempty('detail_art'),aspect='scale')
 img(c,0,0,1920,1080,prop('detail_fade'))
 label(c,96,70,1300,36,'KIVORA  /  PODROBNOSTI',font='font12',color=MUTED)
 img(c,96,172,320,480,prop('detail_poster'),nonempty('detail_poster'),aspect='keep')
 label(c,468,176,1200,128,prop('detail_title'),font='font45_title',textbox=True)
 label(c,472,326,1210,38,prop('detail_meta'),color=MUTED)
 label(c,472,391,1130,252,prop('detail_plot'),textbox=True)
 label(c,472,674,1170,36,prop('detail_quality'),font='font12',color=MUTED)
 buttons=[(301,96,300,prop('detail_primary')),(302,414,202,'Trailer'),(303,634,252,'+ Oblíbené'),(305,904,300,'Celý popis'),(304,1222,190,'Zpět')]
 for i,(ident,x,w,title) in enumerate(buttons):
  b=button(c,ident,x,788,w,64,title,prefix='detail',primary=ident==301)
  nav(b,left=buttons[i-1][0],right=buttons[(i+1)%len(buttons)][0],up=ident,down=ident)
 label(c,96,986,1600,30,'Přehrávání spustíš až po výběru konkrétní verze.  ·  Popis z ČSFD.',font='font12',color=DIM)
 return r

def settings_window():
 r,c=window(501)
 img(c,0,0,1920,1080,prop('settings_background'))
 label(c,96,70,1000,36,'KIVORA  /  NASTAVENÍ',font='font12',color=MUTED)
 label(c,92,148,1600,90,'Všechno na svém místě.',font='font45_title')
 label(c,96,250,1600,50,'Účet, přehrávání a tvoje knihovna. Vyber oblast, kterou chceš upravit.',color=MUTED)
 categories=[('Účet a přehrávání','Přihlášení k Webshare a chování přehrávače.'),('Filtry a katalog','Kvalita, jazyk, řazení a dostupné tituly.'),('Profily','Oddělené oblíbené a historie sledování.'),('Synchronizace','Přenášení stavu mezi tvými zařízeními.'),('Zálohy','Uložení a obnovení nastavení a knihovny.'),('Diagnostika','Kontrola připojení a řešení potíží.'),('Pokročilé nastavení','Všechna nastavení doplňku Kodi.'),('Zpět do KIVORY','Návrat k filmům a seriálům.')]
 for i,(name,description) in enumerate(categories):
  row,col=divmod(i,4);x=96+col*440;y=358+row*270;ident=501+i
  b=button(c,ident,x,y,408,222,'',prefix='settings')
  nav(b,left=501+row*4+(col-1)%4,right=501+row*4+(col+1)%4,up=501+(1-row)*4+col,down=501+(1-row)*4+col)
  label(c,x+26,y+22,350,28,'%02d'%(i+1),font='font12',color=DIM)
  label(c,x+26,y+76,350,38,name)
  label(c,x+26,y+130,350,70,description,font='font12',color=WHITE,textbox=True)
 label(c,96,986,1600,30,'Šipky  pohyb     OK  otevřít     Zpět  zavřít nastavení',font='font12',color=DIM)
 return r

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 for filename,r in [('fckyo-cinema-v3.xml',main_window()),('fckyo-detail-v2.xml',detail_window()),('fckyo-settings-v2.xml',settings_window())]:write(filename,r)
if __name__=='__main__':main()
