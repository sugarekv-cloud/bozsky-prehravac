#!/usr/bin/env python3
"""Build FCKYO brand PNGs for Kodi using only Pillow (build-time only).

Inspired by the independently generated cinematic mock-up: red play symbol,
bold modern lettering and dark graphite icon. No fonts are bundled.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter

ROOT=Path(__file__).resolve().parent.parent
MEDIA=ROOT/'plugin.video.fckyo'/'resources'
RED=(242,28,63)
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
                  fill=(255,104,113),width=max(3,int(w*.035)))


def make_brand():
    MEDIA.mkdir(parents=True,exist_ok=True)
    width,height=1120,215
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
    d.text((238,17),'FCKYO',font=big,fill=WHITE,stroke_width=1,
           stroke_fill=(242,244,249))
    d.rounded_rectangle((240,177,745,183),radius=3,fill=(220,29,58,242))
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
    d.text((133,415),'FCKYO',font=font(53),fill=WHITE)
    icon.save(MEDIA/'icon.png',optimize=True)
    return MEDIA/'brand.png',MEDIA/'icon.png'


if __name__=='__main__':
    print(*map(str,make_brand()),sep='\n')
