# -*- coding: utf-8 -*-
"""Regression: Back navigation and one-shot restoration after Kodi playback."""
import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugin.video.fckyo'))
from cinema_navigation import save,consume,discard,FILENAME
if 'xbmcgui' not in sys.modules:
    sys.modules['xbmcgui']=types.ModuleType('xbmcgui')
if not hasattr(sys.modules['xbmcgui'],'WindowXMLDialog'):
    sys.modules['xbmcgui'].WindowXMLDialog=type('WindowXMLDialog',(),{})
if 'xbmc' not in sys.modules:
    sys.modules['xbmc']=types.ModuleType('xbmc')
from cinema_screen_v2 import CinemaScreen


class OneShotReturnTests(unittest.TestCase):
    def test_returns_to_previous_movie_shelf_and_preserves_selection(self):
        with tempfile.TemporaryDirectory() as profile:
            win=CinemaScreen.__new__(CinemaScreen)
            win.return_profile=profile
            win.mode='files'
            win.context=({'title':'Film','kind':'movie','raw':'Film'},None,None)
            win.stack=[('movies',None,401,7)]
            win.close=lambda:None
            win._start_playback('plugin://plugin.video.fckyo/?action=play&token=SECRET')
            state=consume(profile)
            self.assertEqual(state['view'],'movies')
            self.assertEqual(state['stack'],[])
            self.assertEqual(state['focus'],401)
            self.assertEqual(state['index'],7)
            self.assertIsNone(consume(profile))
            self.assertTrue(win.is_play)

    def test_series_comes_back_to_episodes_with_breadcrumbs(self):
        with tempfile.TemporaryDirectory() as profile:
            show={'title':'Bluey','raw':'Bluey','kind':'show',
                  'files':[{'ident':'f1','name':'Bluey.S01E03.CZ.mkv'}]}
            win=CinemaScreen.__new__(CinemaScreen)
            win.return_profile=profile
            win.mode='files'
            win.context=(show,1,3)
            win.stack=[('shows',None,402,2),
                       ('seasons',show,401,0),
                       ('episodes',(show,1),401,2)]
            win.close=lambda:None
            win._start_playback('plugin://play?cookie=SECRET')
            result=consume(profile)
            self.assertEqual(result['view'],'episodes')
            self.assertEqual(result['context'][0]['title'],'Bluey')
            self.assertEqual(result['context'][1],1)
            self.assertEqual(result['stack'][0][0],'shows')
            self.assertEqual(result['stack'][1][0],'seasons')
            self.assertEqual(result['index'],2)
            self.assertEqual(result['focus'],401)

    def test_resume_from_watchlist_returns_to_watchlist(self):
        with tempfile.TemporaryDirectory() as profile:
            win=CinemaScreen.__new__(CinemaScreen)
            win.return_profile=profile
            win.mode='favorites'
            win.context=None
            win.stack=[('home',None,401,4)]
            win.getFocusId=lambda:401
            control=types.SimpleNamespace(getSelectedPosition=lambda:1)
            win.getControl=lambda cid:control
            win.close=lambda:None
            win._start_playback('plugin://play')
            result=consume(profile)
            self.assertEqual(result['view'],'favorites')
            self.assertEqual(result['stack'][0][0],'home')
            self.assertEqual(result['index'],1)

    def test_restore_repaints_original_view_and_its_focus(self):
        win=CinemaScreen.__new__(CinemaScreen)
        screen=[]
        win._screen=lambda view,ctx,stack=False:screen.append((view,ctx,stack))
        win.rail_items=[[{'kind':'movie'} for _ in range(4)]]+[[] for _ in range(12)]
        selected=[]
        win.getControl=lambda cid:types.SimpleNamespace(selectItem=lambda n:selected.append(n))
        win.setFocusId=lambda cid:selected.append(('focus',cid))
        win._update_hero=lambda:None
        saved={'view':'movies','context':None,'stack':[('home',None,401,0)],
               'focus':401,'index':8}
        self.assertTrue(win._restore_return_screen(saved))
        self.assertEqual(screen,[('movies',None,False)])
        self.assertEqual(selected,[('focus',401),3])
        self.assertEqual(win.stack,[('home',None,401,0)])

    def test_back_from_episode_details_reverses_navigation(self):
        win=CinemaScreen.__new__(CinemaScreen)
        win.stack=[('shows',None,401,1)]
        win.rail_items=[[{'ident':'a'},{'ident':'b'},{'ident':'c'}]]+[[] for _ in range(12)]
        win._screen=lambda view,ctx:None
        selected=[]
        win.setFocusId=lambda cid:selected.append(cid)
        win.getControl=lambda cid:types.SimpleNamespace(selectItem=lambda index:selected.append(index))
        win._update_hero=lambda:None
        win._go_back()
        self.assertEqual(selected,[401,1])
        self.assertEqual(win.stack,[])

    def test_no_sensitive_stream_url_or_credentials_written(self):
        with tempfile.TemporaryDirectory() as profile:
            card={'title':'Bluey','raw':'Bluey','kind':'show',
                  'wst':'TOPSECRET','cookie':'VERYSECRET',
                  'stream_url':'https://private/token=ABC',
                  'files':[{'ident':'1','name':'Bluey.S01E01.mkv',
                            'link':'http://private/secret','wst':'PRIVATE',
                            'password':'0'}]}
            self.assertTrue(save(profile,'seasons',card,stack=[]))
            path=os.path.join(profile,FILENAME)
            with io.open(path,encoding='utf8') as fh:
                contents=fh.read()
            for secret in ('TOPSECRET','VERYSECRET','ABC','PRIVATE',
                           'stream_url','wst','cookie','link'):
                self.assertNotIn(secret,contents)
            restored=consume(profile)
            self.assertEqual(restored['context']['files'][0]['ident'],'1')

    def test_reject_stale_or_corrupt_snapshot_and_leave_no_file(self):
        with tempfile.TemporaryDirectory() as profile:
            self.assertTrue(save(profile,'home',None))
            p=os.path.join(profile,FILENAME)
            with io.open(p,encoding='utf8') as fh:
                snapshot=json.load(fh)
            snapshot['timestamp']=time.time()-50000
            with io.open(p,'w',encoding='utf8') as fh:
                json.dump(snapshot,fh)
            self.assertIsNone(consume(profile))
            self.assertFalse(os.path.exists(p))
            with io.open(p,'w',encoding='utf8') as fh:
                fh.write('{INVALID JSON')
            self.assertIsNone(consume(profile))
            self.assertFalse(os.path.exists(p))

    def test_explicit_exit_does_not_keep_saved_position(self):
        with tempfile.TemporaryDirectory() as profile:
            self.assertTrue(save(profile,'movies',None))
            discard(profile)
            self.assertIsNone(consume(profile))


if __name__=='__main__':
    unittest.main()
