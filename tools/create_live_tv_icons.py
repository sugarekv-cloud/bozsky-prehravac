# -*- coding: utf-8 -*-
"""Generate simple 16:9 TV-channel artwork offline for Kodi releases."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'plugin.video.fckyo'/'resources'/'live_tv'
NAMES=(
    ('ocko','ÓČKO','HUDEBNÍ TELEVIZE'),
    ('ocko_expres','ÓČKO','EXPRES'),
    ('ocko_star','ÓČKO','STAR'),
    ('polar','TV POLAR','REGIONÁLNÍ'),
    ('prahatv','PRAHA TV','REGIONÁLNÍ'),
)


def _font(size):
    for name in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                 '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'):
        if Path(name).is_file():
            return ImageFont.truetype(name,size)
    return ImageFont.load_default()


def make_live_tv_icons():
    DEST.mkdir(parents=True,exist_ok=True)
    made=[]
    for ident,title,sub in NAMES:
        im=Image.new('RGB',(640,360),(12,18,27))
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((19,18,621,342),radius=25,
                            outline=(73,83,89),width=2)
        d.rounded_rectangle((44,43,596,317),radius=19,
                            fill=(25,32,43))
        d.rectangle((64,78,71,265),fill=(197,170,113))
        d.text((110,107),title,font=_font(64),fill=(246,242,233))
        d.text((112,213),sub,font=_font(27),fill=(199,176,134))
        d.text((111,280),'ŽIVĚ',font=_font(19),fill=(221,222,220))
        p=DEST/('live_'+ident+'.png')
        im.save(str(p),optimize=True)
        made.append(p)
    return made

if __name__=='__main__':
    make_live_tv_icons()
