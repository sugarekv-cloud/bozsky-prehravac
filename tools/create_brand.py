#!/usr/bin/env python3
"""Build Božský přehrávač god-inspired brand PNGs for Kodi using only Pillow (build-time only).

Original Zeus-like god illustration, golden Czech wordmark and Kodi icon.
No fonts are bundled.
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


def god_portrait(size=360):
    """Original Zeus-like god portrait, crisp as a Kodi add-on icon.

    Fully procedural artwork: no network calls, external graphics or fonts.
    """
    import math
    scale=3
    w=h=360*scale
    im=Image.new('RGBA',(w,h),(0,0,0,0))
    layer=Image.new('RGBA',(w,h),(0,0,0,0))
    d=ImageDraw.Draw(layer)
    def pt(points):
        return [(int(x*scale),int(y*scale)) for x,y in points]
    def polygon(points,fill,outline=None,width=1):
        pp=pt(points)
        d.polygon(pp,fill=fill)
        if outline:d.line(pp+[pp[0]],fill=outline,width=width*scale,joint='curve')
    def line(points,fill,width=2):
        d.line(pt(points),fill=fill,width=width*scale,joint='curve')
    def ellipse(box,fill,outline=None,width=1):
        d.ellipse(tuple(int(v*scale) for v in box),fill=fill,outline=outline,width=width*scale)
    # Lightning and golden divine rays.
    for points in ([(18,120),(72,132),(43,171),(105,151)],
                   [(331,102),(287,137),(316,150),(267,181)]):
        line(points,(130,100,55,100),12)
        line(points,(251,200,103,255),5)
    for angle in range(0,360,30):
        a=math.radians(angle)
        line([(176+144*math.cos(a),176+144*math.sin(a)),
              (176+164*math.cos(a),176+164*math.sin(a))],
             (218,164,64,130),3)
    # Robe and hair silhouettes.
    polygon([(56,342),(78,278),(111,251),(240,251),(281,285),(315,344)],
            (27,33,44,255),(174,131,64,255),3)
    polygon([(90,95),(118,57),(147,48),(178,35),(222,51),(248,76),
             (277,105),(286,169),(272,239),(237,260),(107,261),
             (76,219),(66,165)],(70,73,80,255),(244,203,115,255),3)
    for x in [65,81,94,109,124,140,202,218,238,256,271]:
        y=86+abs(x-170)*.15
        polygon([(x,y),(x-14,y+72),(x+3,y+120),(x+14,y+43)],
                (181,183,189,250))
    # Sculptural temples, cheeks, brows and nose.
    polygon([(122,105),(158,81),(207,82),(242,105),(249,169),
             (220,220),(178,240),(134,219),(111,164)],
            (192,162,133,255),(101,75,58,255),3)
    polygon([(124,146),(157,132),(170,138),(160,152),(128,155)],
            (59,57,67,255))
    polygon([(189,138),(204,131),(235,145),(232,157),(191,151)],
            (59,57,67,255))
    for x in (153,207):
        ellipse((x-12,152,x+11,159),(174,247,247,255))
        ellipse((x-4,152,x+4,158),(34,120,168,255))
    line([(176,150),(168,185),(190,188)],(101,69,52,255),4)
    # Waves of silver beard and moustache.
    polygon([(110,188),(135,188),(163,204),(181,194),(198,205),
             (219,185),(250,192),(261,241),(232,289),(212,322),
             (183,352),(156,325),(125,288),(100,240)],
            (215,217,217,255),(145,132,117,255),3)
    polygon([(119,183),(162,190),(179,209),(144,225),(105,211)],
            (242,237,222,255))
    polygon([(183,210),(211,188),(252,183),(254,215),(213,225)],
            (242,237,222,255))
    for x in (128,147,169,194,217,235):
        off=abs(x-180)
        line([(x,229),(x-8,275),(x+2,323-off*.45)],
             (155,157,165,170),5)
        line([(x+4,235),(x+5,267),(x+8,298-off*.22)],
             (248,249,242,190),3)
    # White curled eyebrows and swept hair.
    line([(110,131),(147,113),(175,126)],(232,234,230,255),13)
    line([(187,125),(218,113),(248,133)],(232,234,230,255),13)
    polygon([(94,93),(135,65),(161,69),(177,49),(205,68),(228,69),
             (258,101),(237,94),(202,98),(184,88),(151,96),(111,111)],
            (236,238,235,255),(155,158,168,255),3)
    # Laurel crown / gold headpiece unmistakably divine.
    line([(88,120),(100,78),(145,47),(181,42),(218,47),(262,78),(271,120)],
         (243,192,85,255),6)
    for x,y in ((112,81),(129,64),(147,56),(210,56),(232,65),(248,83)):
        polygon([(x,y),(x-11,y-16),(x-2,y-23),(x+12,y-8)],
                (242,194,87,255))
    ellipse((171,35,190,55),(255,225,131,255))
    # Subtle cold glow, then sharp illustration.
    blur=layer.filter(ImageFilter.GaussianBlur(9*scale))
    alpha=blur.getchannel('A').point(lambda a:int(a*.22))
    blur.putalpha(alpha)
    im.alpha_composite(blur)
    im.alpha_composite(layer)
    return im.resize((size,size),Image.Resampling.LANCZOS)


def make_brand():
    MEDIA.mkdir(parents=True,exist_ok=True)
    god=god_portrait(410)
    # Wide transparent Kodi title logo; matches the actual Czech add-on name.
    im=Image.new('RGBA',(1150,275),(0,0,0,0))
    im.alpha_composite(god.resize((262,262),Image.Resampling.LANCZOS),(8,4))
    d=ImageDraw.Draw(im)
    gold=(232,188,100,255)
    champagne=(252,245,219,255)
    d.text((281,27),'BOŽSKÝ',font=font(130),fill=champagne,
           stroke_width=2,stroke_fill=(135,91,44,255))
    d.text((291,160),'PŘEHRÁVAČ',font=font(70),fill=gold)
    d.line((293,247,1050,247),fill=(190,140,65,230),width=4)
    im.save(MEDIA/'brand.png',optimize=True)

    # Kodi's square add-on icon: same recognizable portrait, no unrelated logo.
    icon=Image.new('RGBA',(512,512),(9,10,13,255))
    base=ImageDraw.Draw(icon)
    base.rounded_rectangle((11,11,500,500),radius=92,
                           outline=(179,134,64,255),width=9)
    icon.alpha_composite(god.resize((440,440),Image.Resampling.LANCZOS),
                         (37,10))
    base=ImageDraw.Draw(icon)
    base.rounded_rectangle((48,427,464,494),radius=18,fill=(9,10,14,238))
    base.text((101,435),'BOŽSKÝ',font=font(47),
              fill=(248,213,146,255))
    icon.save(MEDIA/'icon.png',optimize=True)
    make_menu_icons()
    return MEDIA/'brand.png',MEDIA/'icon.png'


if __name__=='__main__':
    print(*map(str,make_brand()),sep='\n')
