# -*- coding: utf-8 -*-
"""KIVORA v0.25 regression: retained playback window, working home and Tips."""
import os
import sys
import types
import unittest

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)


def ui():
    import xbmcgui
    if not hasattr(xbmcgui,'WindowXMLDialog'):
        xbmcgui.WindowXMLDialog=type('WindowXMLDialog',(),{})
    from cinema_screen_v2 import CinemaScreen
    return CinemaScreen


class KodiPlaybackAndHomeTests(unittest.TestCase):
    def test_playing_saved_movie_does_not_close_film_window(self):
        import cinema_screen_v2 as module
        win=ui().__new__(ui())
        win.make_url=lambda **kw:'plugin://plugin.video.fckyo/?action=play'
        closed=[]
        win.close=lambda:closed.append(True)
        calls=[]
        original=getattr(module.xbmc,'executebuiltin',None)
        module.xbmc.executebuiltin=lambda cmd:calls.append(cmd)
        try:
            win._play_saved({'ident':'42','name':'Demo.mkv','kind':'movie',
                             'title':'Demo'})
        finally:
            if original is None:
                delattr(module.xbmc,'executebuiltin')
            else:
                module.xbmc.executebuiltin=original
        self.assertEqual(closed,[])
        self.assertEqual(calls,['PlayMedia(plugin://plugin.video.fckyo/?action=play)'])
        self.assertFalse(getattr(win,'is_play',False))

    def test_selected_file_keeps_own_series_episode_context(self):
        import cinema_screen_v2 as module
        win=ui().__new__(ui())
        win.context=({'title':'Series','raw':'Series','kind':'show'},1,2)
        win.make_url=lambda **kw:kwargs.append(kw) or 'plugin://example'
        win.rail_items=[[{'kind':'file','ident':'f1','raw':'Series.S01E02.mkv'}]]
        win._selected=lambda cid=None:win.rail_items[0][0]
        win.close=lambda:closed.append(1)
        kwargs=[];closed=[];calls=[]
        original=getattr(module.xbmc,'executebuiltin',None)
        module.xbmc.executebuiltin=lambda cmd:calls.append(cmd)
        try:
            win.onClick(401)
        finally:
            if original is None:
                delattr(module.xbmc,'executebuiltin')
            else:
                module.xbmc.executebuiltin=original
        self.assertEqual(calls,['PlayMedia(plugin://example)'])
        self.assertEqual(closed,[])
        self.assertEqual(kwargs[0]['season'],'1')
        self.assertEqual(kwargs[0]['episode'],'2')
        self.assertEqual(kwargs[0]['from_cinema'],'1')

    def test_service_does_not_reopen_kodi_when_dialog_is_alive(self):
        import xbmcgui
        import service
        class GlobalWindow:
            def getProperty(self,key):
                return 'yes' if key=='kivora_window_open' else ''
        old_window=getattr(xbmcgui,'Window',None)
        old_builtin=getattr(service.xbmc,'executebuiltin',None)
        calls=[]
        xbmcgui.Window=lambda num:GlobalWindow()
        service.xbmc.executebuiltin=lambda cmd:calls.append(cmd)
        try:
            service.WatchTracker._return_to_addon()
        finally:
            if old_window is None:delattr(xbmcgui,'Window')
            else:xbmcgui.Window=old_window
            if old_builtin is None:delattr(service.xbmc,'executebuiltin')
            else:service.xbmc.executebuiltin=old_builtin
        self.assertEqual(calls,[])

    def test_dialog_missing_uses_backup_reopen(self):
        import xbmcgui
        import service
        class GlobalWindow:
            def getProperty(self,key):return ''
        old_window=getattr(xbmcgui,'Window',None)
        old_builtin=getattr(service.xbmc,'executebuiltin',None)
        calls=[]
        xbmcgui.Window=lambda num:GlobalWindow()
        service.xbmc.executebuiltin=lambda cmd:calls.append(cmd)
        try:
            service.WatchTracker._return_to_addon()
        finally:
            if old_window is None:delattr(xbmcgui,'Window')
            else:xbmcgui.Window=old_window
            if old_builtin is None:delattr(service.xbmc,'executebuiltin')
            else:service.xbmc.executebuiltin=old_builtin
        self.assertEqual(len(calls),1)
        self.assertIn('action=cinematic_home',calls[0])

    def test_home_button_consumes_background_result_before_redrawing(self):
        win=ui().__new__(ui())
        win.stack=[('shows',None,402,0)]
        order=[]
        win.service=types.SimpleNamespace(take_home_refresh=lambda:order.append('consume'))
        win._screen=lambda *args,**kwargs:order.append(('view',args,kwargs))
        win.onClick(106)
        self.assertEqual(win.stack,[])
        self.assertEqual(order,['consume',('view',('home',),{'stack':False})])

    def test_recommendation_page_repaints_when_background_catalogue_arrives(self):
        win=ui().__new__(ui())
        win.mode='recommendations'
        win.context=None
        win._updating_home=False
        win.rail_items=[[{'kind':'tips_retry'}]]+[[] for _ in range(12)]
        win.service=types.SimpleNamespace(take_home_refresh=lambda:{'_all_movies':[]})
        win.getFocusId=lambda:201
        win._update_hero=lambda:None
        calls=[]
        win._screen=lambda *a,**kw:calls.append(a)
        win._apply_background_home()
        self.assertEqual(calls,[('recommendations',None)])
        self.assertFalse(win._updating_home)

    def test_empty_home_has_a_branded_hero_not_a_loading_title(self):
        win=ui().__new__(ui())
        win.mode='home'
        win.rail_items=[[{'kind':'tips_retry','title':'Tipy se připravují'}]]+[[] for _ in range(12)]
        win._selected=lambda:win.rail_items[0][0]
        win.getFocusId=lambda:401
        props={}
        win.setProperty=lambda k,v:props.__setitem__(k,v)
        win._update_hero()
        self.assertEqual(props.get('hero_title'),'KIVORA')
        self.assertIn('FILMOVÝ SVĚT',props.get('hero_info',''))
        self.assertEqual(props.get('hero_art'),'')

    def test_explicit_retry_after_finished_worker(self):
        from cinema_service_v2 import CinemaService
        with __import__('tempfile').TemporaryDirectory() as profile:
            service=CinemaService('token',lambda *a,**k:([],0),None,profile=profile)
            service._background_started=True
            service._background_done.set()
            service._background_result={}
            service.home_cache={'_all_movies':[]}
            service._snapshot_age=2
            service.home=lambda force=False:{'_all_movies':[],'_all_shows':[]}
            service.most_watched_movies=lambda *a:[]
            service.most_watched_shows=lambda *a:[]
            self.assertTrue(service.start_home_refresh(force=True))
            self.assertTrue(service._background_started)


if __name__=='__main__':unittest.main()
