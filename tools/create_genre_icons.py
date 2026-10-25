#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build neon/cinematic PNG genre cover art for KIVORA (build time only).

All 24 pieces are self-contained, work offline in Kodi, and share a consistent
dark streaming-service palette. Requires Pillow only during the build.
"""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT=Path(__file__).resolve().parent.parent
DEST=ROOT/'plugin.video.fckyo'/'resources'/'genre_icons'
SIZE=(320,426)
ART={
    'action': 'bolt', 'animation': 'film', 'adventure': 'compass',
    'drama': 'sad', 'fantasy': 'wand', 'horror': 'skull',
    'comedy': 'happy', 'crime': 'cuffs', 'family': 'family',
    'romance': 'heart', 'scifi': 'planet', 'thriller': 'eye',
    'war': 'swords', 'documentary': 'camera', 'mystery': 'question',
    'history': 'temple', 'music': 'music', 'western': 'hat',
    'sport': 'trophy', 'biography': 'person', 'disaster': 'volcano',
    'psychological': 'mind', 'kids': 'teddy', 'short': 'clapper',
}
VIOLET=(176,107,255,255)
WHITE=(251,246,255,255)


def background(salt):
    w,h=SIZE
    im=Image.new('RGBA',SIZE,(0,0,0,255))
    px=im.load()
    cx=w*(.53+((salt%3)-1)*.12)
    cy=h*.40
    for y in range(h):
        for x in range(w):
            dist=min(1.0,math.hypot((x-cx)/(w*.9),(y-cy)/(h*.8)))
            vignette=max(0.0,1-dist)
            glow=vignette**2
            px[x,y]=(int(10+13*glow),int(10+6*glow),
                      int(18+34*glow),255)
    d=ImageDraw.Draw(im)
    for r in (93,126,163):
        d.ellipse((w//2-r,185-r,w//2+r,185+r),outline=(44,24,66,110),width=2)
    for x in (18,w-19):
        d.line((x,24,x,h-24),fill=(64,43,102,150),width=1)
    d.rounded_rectangle((12,12,w-13,h-13),radius=13,outline=(67,44,103,255),width=2)
    d.rectangle((35,h-22,w-35,h-19),fill=(146,84,227,255))
    return im


def artwork(key):
    """Draw a recognizable cinema-genre pictogram at high resolution."""
    im=Image.new('RGBA',SIZE,(0,0,0,0))
    d=ImageDraw.Draw(im)
    ink=WHITE
    stroke=9
    def lines(points,width=stroke,fill=ink,closed=False):
        v=list(points)
        d.line(v+[v[0]] if closed else v,fill=fill,width=width,joint='curve')
    def ring(box,width=stroke,fill=ink):
        d.ellipse(box,outline=fill,width=width)
    def arc(box,a,b,width=stroke):
        d.arc(box,a,b,fill=ink,width=width)
    def rectangle(box,width=stroke,radius=9):
        d.rounded_rectangle(box,radius=radius,outline=ink,width=width)
    def star(cx,cy,outer=54,inner=22,n=5):
        points=[]
        for i in range(2*n):
            angle=-math.pi/2+i*math.pi/n
            radius=outer if i%2==0 else inner
            points.append((cx+math.cos(angle)*radius,cy+math.sin(angle)*radius))
        lines(points,closed=True)
    def ellipse(b):
        ring(b)
    if key=='bolt':
        lines([(179,85),(102,221),(156,221),(127,317),
               (232,174),(178,174),(213,85)],width=12,closed=True)
    elif key=='film':
        rectangle((81,131,239,274),10)
        for y in (146,183,222,253):
            for x in (95,223):
                d.rectangle((x-5,y-6,x+5,y+5),fill=ink)
        lines([(116,193),(158,155),(197,193),(158,233),(116,193)],closed=True)
    elif key=='compass':
        ellipse((82,123,238,279))
        lines([(156,152),(193,226),(124,211),(156,152)],closed=True)
        lines([(160,98),(160,117)],width=7)
        lines([(160,284),(160,302)],width=7)
        lines([(65,200),(77,200)],width=7)
        lines([(244,200),(256,200)],width=7)
    elif key in ('happy','sad'):
        rectangle((90,121,230,274),12,31)
        for x in (131,190):
            arc((x-13,171,x+13,196),180,360,7)
        if key=='happy':
            arc((117,187,204,258),5,176,11)
        else:
            arc((117,217,204,277),184,356,10)
        lines([(109,128),(90,115),(94,143)],width=7)
    elif key=='wand':
        lines([(100,290),(211,130)],width=18)
        star(211,127,42,18)
        for cx,cy in ((99,156),(245,220),(130,93)):
            star(cx,cy,14,6)
    elif key=='skull':
        ellipse((96,116,224,252))
        ring((125,175,150,204),6)
        ring((172,175,197,204),6)
        lines([(161,205),(149,226),(171,226),(161,205)],width=6,closed=True)
        rectangle((124,235,196,283),7,7)
        for x in (144,162,181):
            lines([(x,243),(x,277)],width=4)
    elif key=='cuffs':
        ring((72,160,166,258),12)
        ring((172,144,264,242),12)
        lines([(161,213),(179,202),(169,185)],width=12)
        lines([(89,167),(149,153)],width=5)
    elif key=='family':
        for x,y,r in ((161,134,30),(103,207,22),(220,207,22)):
            ring((x-r,y-r,x+r,y+r),8)
        arc((100,174,222,334),188,352,12)
        arc((61,221,146,330),190,345,10)
        arc((176,221,264,330),195,347,10)
    elif key=='heart':
        lines([(160,287),(91,219),(87,168),(112,142),(145,150),
               (160,170),(176,149),(209,143),(238,165),(231,213),
               (160,287)],closed=True,width=12)
    elif key=='planet':
        ring((100,143,222,270),12)
        arc((54,160,262,256),15,158,13)
        arc((54,160,262,256),193,347,13)
        star(254,118,17,6)
    elif key=='eye':
        lines([(60,202),(103,164),(161,151),(215,171),(259,202),
               (217,236),(160,251),(99,235),(60,202)],closed=True)
        ring((128,168,195,235),9)
        ring((153,194,171,211),7)
    elif key=='swords':
        lines([(93,122),(223,285)],width=16)
        lines([(223,122),(93,285)],width=16)
        lines([(77,151),(108,127)],width=11)
        lines([(210,126),(242,154)],width=11)
        lines([(85,261),(119,278)],width=10)
        lines([(199,280),(237,259)],width=10)
    elif key=='camera':
        rectangle((85,142,235,268),9,13)
        ring((124,162,198,236),10)
        lines([(116,142),(133,122),(186,122),(202,142)],closed=True)
        lines([(110,281),(213,281)],width=7)
    elif key=='question':
        arc((106,120,214,242),190,525,17)
        lines([(163,232),(163,253)],width=13)
        ring((152,278,169,295),8)
    elif key=='temple':
        lines([(62,161),(159,113),(258,161)],width=12)
        lines([(78,176),(240,176)],width=9)
        for x in (98,143,187,230):
            lines([(x,187),(x,273)],width=10)
        lines([(73,285),(249,285)],width=11)
    elif key=='music':
        lines([(165,126),(221,116),(221,241)],width=12)
        lines([(165,126),(165,261)],width=12)
        ellipse((112,242,167,282))
        ellipse((168,215,224,255))
        lines([(165,151),(221,140)],width=11)
    elif key=='hat':
        arc((88,109,230,282),192,347,12)
        lines([(106,247),(213,247)],width=12)
        arc((69,232,256,290),8,171,11)
        lines([(114,230),(205,230)],width=7)
    elif key=='trophy':
        rectangle((112,130,211,216),10)
        arc((66,145,146,218),24,155,11)
        arc((176,145,258,218),23,154,11)
        lines([(161,219),(161,279)],width=12)
        lines([(123,281),(200,281)],width=11)
        star(160,171,26,11)
    elif key=='person':
        ring((123,114,197,189),10)
        arc((76,197,244,327),181,359,14)
        lines([(143,217),(161,239),(180,216)],width=8)
        lines([(163,240),(163,283)],width=8)
    elif key=='volcano':
        lines([(72,287),(129,184),(148,208),(171,180),(251,287)],closed=True)
        lines([(137,170),(156,130),(142,111)],width=10)
        lines([(183,158),(204,138),(187,118)],width=9)
        lines([(78,290),(244,290)],width=10)
    elif key=='mind':
        arc((88,133,232,287),175,480,11)
        arc((113,154,208,258),189,496,10)
        arc((136,178,191,236),205,530,8)
        lines([(158,235),(178,267),(197,267)],width=8)
    elif key=='teddy':
        ring((94,146,227,280),9)
        ring((86,133,124,174),9)
        ring((196,133,234,174),9)
        ring((135,197,149,212),6)
        ring((179,197,193,212),6)
        ring((151,219,176,241),7)
        arc((140,223,188,263),5,167,6)
    elif key=='clapper':
        rectangle((79,170,246,273),10)
        lines([(84,164),(233,128),(242,157),(95,194)],closed=True, width=9)
        for x in (122,172,219):
            lines([(x,152),(x+19,177)],width=6)
        lines([(151,201),(151,243),(187,222),(151,201)],width=9,closed=True)
    else:
        star(160,202)
    return im


def make_genre_icons():
    DEST.mkdir(parents=True,exist_ok=True)
    for i,(name,art) in enumerate(ART.items()):
        im=background(i)
        vector=artwork(art)
        glow=vector.filter(ImageFilter.GaussianBlur(14))
        glow.putalpha(glow.getchannel('A').point(lambda v:int(v*.45)))
        purple=Image.new('RGBA',SIZE,VIOLET)
        purple.putalpha(glow.getchannel('A'))
        im=Image.alpha_composite(im,purple)
        narrow=vector.filter(ImageFilter.GaussianBlur(3))
        violet=Image.new('RGBA',SIZE,(176,91,255,255))
        violet.putalpha(narrow.getchannel('A'))
        im=Image.alpha_composite(im,violet)
        im=Image.alpha_composite(im,vector)
        im.save(DEST/(name+'.png'),optimize=True)
    return [DEST/(name+'.png') for name in ART]


if __name__=='__main__':
    print('Generated',len(make_genre_icons()),'KIVORA genre icons')
