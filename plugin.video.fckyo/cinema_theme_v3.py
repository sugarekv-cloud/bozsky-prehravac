# -*- coding: utf-8 -*-
"""Cinema 3.0 textures: generated locally with stdlib, versioned separately.

No Pillow dependency at runtime. Legacy windows keep their original palette.
"""
import os
import struct
import zlib
from cinematic_home import _chunk

CACHE_PREFIX='cinema_v3_048b_'
SPECS={'background':(2,2),'focus':(2,2),'accent':(2,2),'clear':(2,2),
       'scrim':(2,2),'panel':(2,2),'chip':(2,2),'tile':(128,72),
       'button':(128,64),'cta':(128,64),'cta_focus':(128,64),
       'fade':(384,128),'detailfade':(384,128),'headerfade':(2,128)}

def pixel(kind,x,y,w,h):
    if kind=='background':return (10,11,15,255)
    if kind=='focus':return (250,250,252,255)
    if kind=='accent':return (229,9,20,255)
    if kind=='clear':return (0,0,0,0)
    if kind=='scrim':return (0,0,0,145)
    if kind=='panel':return (18,20,27,255)
    if kind=='chip':return (10,11,15,225)
    if kind in ('fade','detailfade'):
        u=x/float(w-1);v=y/float(h-1)
        # Strong reading area at left; preserve faces on the right.
        left=255 if u<.34 else int(255*max(0,1-(u-.34)/.51)**1.6)
        bottom=int(255*max(0,(v-.48)/.52)**1.2)
        return (10,11,15,max(left,bottom,190 if kind=='detailfade' else 0))
    if kind=='headerfade':return (10,11,15,int(245*(1-y/float(h-1))**.65))
    color={'button':(35,38,47,240),'cta':(245,245,247,255),
           'cta_focus':(229,9,20,255),'tile':(26,29,37,255)}[kind]
    if kind=='tile':return color
    radius=10
    dx=max(radius-x,0,x-(w-radius-1));dy=max(radius-y,0,y-(h-radius-1))
    return (0,0,0,0) if dx*dx+dy*dy>radius*radius else color

def ensure_textures(profile):
    folder=os.path.join(profile,'cinematic_ui');os.makedirs(folder,exist_ok=True)
    result={}
    for kind,(w,h) in SPECS.items():
        path=os.path.join(folder,CACHE_PREFIX+kind+'.png');result[kind]=path
        if os.path.isfile(path):continue
        raw=bytearray()
        for y in range(h):
            raw.append(0)
            for x in range(w):raw.extend(pixel(kind,x,y,w,h))
        data=b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))
        data+=_chunk(b'IDAT',zlib.compress(bytes(raw),6))+_chunk(b'IEND',b'')
        # A separate temp filename avoids concurrent screen/preview writers.
        import tempfile
        fd,tmp=tempfile.mkstemp(prefix=CACHE_PREFIX,dir=folder)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(data)
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return result
