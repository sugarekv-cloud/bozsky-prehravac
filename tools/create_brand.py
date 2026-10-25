#!/usr/bin/env python3
"""Build KIVORA brand PNGs for Kodi using only Pillow (build-time only).

Inspired by the independently generated cinematic mock-up: red play symbol,
bold modern lettering and dark graphite icon. No fonts are bundled.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter

ROOT=Path(__file__).resolve().parent.parent
MEDIA=ROOT/'plugin.video.fckyo'/'resources'
RED=(154,108,255)
WHITE=(249,250,252)


def font(size):
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf',
                 '/usr/share/fonts/truetype/liberation2/LiberationSans-BoldItalic.ttf',
                 'DejaVuSans-BoldOblique.ttf'):
        try:
            return ImageFont.truetype(path,size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def play_symbol(draw,box,highlight=True):
    x,y,w,h=box
    # Unique open red chevron suggests playback without borrowing another logo.
    pts=[(x+.15*w,y+.08*h),(x+.81*w,y+.46*h),
         (x+.81*w,y+.55*h),(x+.15*w,y+.93*h),
         (x+.15*w,y+.70*h),(x+.57*w,y+.50*h),
         (x+.15*w,y+.30*h)]
    draw.line(pts+[pts[0]],fill=RED,width=max(8,int(w*.105)),joint='curve')
    if highlight:
        draw.line([(x+.15*w,y+.08*h),(x+.81*w,y+.46*h)],
                  fill=(203,168,255),width=max(3,int(w*.035)))


def make_menu_icons():
    """Original vector-like PNG navigation icons, independent of Kodi fonts."""
    import math
    icon_folder=MEDIA/'icons'
    icon_folder.mkdir(parents=True,exist_ok=True)
    styles=['home','continue','favorite','genres','csfd','premieres',
            'settings','tips','search']
    for kind in styles:
        image=Image.new('RGBA',(72,72),(0,0,0,0))
        d=ImageDraw.Draw(image)
        c=(236,235,248,255)
        w=5
        if kind=='home':
            d.line([(13,34),(36,13),(59,34)],fill=c,width=w,joint='curve')
            d.line([(20,31),(20,60),(52,60),(52,31)],fill=c,width=w,joint='curve')
            d.rectangle((31,43,41,60),outline=c,width=3)
        elif kind=='continue':
            d.ellipse((8,8,64,64),outline=c,width=4)
            d.polygon([(29,20),(29,53),(52,36)],fill=c)
        elif kind=='favorite':
            d.line([(36,60),(12,38),(10,27),(15,17),(25,16),(36,27),
                    (46,16),(57,17),(62,27),(60,38),(36,60)],
                   fill=c,width=w,joint='curve')
        elif kind=='genres':
            for x in (11,39):
                for y in (11,39):
                    d.rounded_rectangle((x,y,x+22,y+22),radius=5,outline=c,width=4)
        elif kind=='csfd':
            points=[]
            for j in range(10):
                a=-math.pi/2+j*math.pi/5
                radius=27 if j%2==0 else 13
                points.append((36+radius*math.cos(a),36+radius*math.sin(a)))
            d.polygon(points,outline=c)
            d.line(points+[points[0]],fill=c,width=3,joint='curve')
        elif kind=='premieres':
            d.rounded_rectangle((11,24,61,58),radius=6,outline=c,width=4)
            d.polygon([(29,30),(29,51),(47,40)],fill=c)
            d.line((10,15,60,15),fill=c,width=7)
            for x in (18,36,53):
                d.line((x,9,x-8,22),fill=c,width=4)
        elif kind=='settings':
            d.ellipse((18,18,54,54),outline=c,width=6)
            d.ellipse((30,30,42,42),outline=c,width=4)
            for j in range(8):
                a=j*math.pi/4
                d.line((36+20*math.cos(a),36+20*math.sin(a),
                        36+30*math.cos(a),36+30*math.sin(a)),fill=c,width=6)
        elif kind=='search':
            d.ellipse((11,10,48,47),outline=c,width=5)
            d.line((45,45,62,62),fill=c,width=6)
        else:
            d.line([(36,7),(42,28),(64,36),(42,43),(36,64),(29,43),
                    (8,36),(29,29),(36,7)],fill=c,width=4,joint='curve')
        image.save(icon_folder/(kind+'.png'),optimize=True)


def make_brand():
    MEDIA.mkdir(parents=True,exist_ok=True)
    width,height=1050,215
    # Render 2x then downsample so the Kodi branding stays sharp.
    im=Image.new('RGBA',(width,height),(0,0,0,0))
    glow=Image.new('RGBA',im.size,(0,0,0,0))
    d=ImageDraw.Draw(glow)
    play_symbol(d,(32,24,175,165))
    blurred=glow.filter(ImageFilter.GaussianBlur(18))
    blurred.putalpha(blurred.getchannel('A').point(lambda a:int(a*.32)))
    im.alpha_composite(blurred)
    d=ImageDraw.Draw(im)
    play_symbol(d,(32,24,175,165))
    big=font(135)
    d.text((238,17),'KIVORA',font=big,fill=WHITE,stroke_width=1,
           stroke_fill=(242,244,249))
    d.rounded_rectangle((240,177,745,183),radius=3,fill=(154,108,255,242))
    im.save(MEDIA/'brand.png',optimize=True)

    icon=Image.new('RGBA',(512,512),(9,10,15,255))
    pix=icon.load()
    for y in range(512):
        for x in range(512):
            radius=((x-256)**2+(y-220)**2)**.5
            k=max(0,1-radius/495)
            pix[x,y]=(int(9+16*k),int(10+8*k),int(15+18*k),255)
    d=ImageDraw.Draw(icon)
    d.rounded_rectangle((7,7,504,504),radius=102,outline=(87,27,44),width=12)
    # Painted-tooled chevron: deliberately recognizable at Kodi tile size.
    play_symbol(d,(89,76,337,340),True)
    d.text((133,415),'KIVORA',font=font(53),fill=WHITE)
    icon.save(MEDIA/'icon.png',optimize=True)
    make_menu_icons()
    return MEDIA/'brand.png',MEDIA/'icon.png'


if __name__=='__main__':
    print(*map(str,make_brand()),sep='\n')
