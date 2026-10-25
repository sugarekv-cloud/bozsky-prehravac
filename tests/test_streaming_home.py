# -*- coding: utf-8 -*-
"""Streaming home layout and bottom-of-screen navigation regression tests."""
import os
import sys
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUG=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUG)
SKIN=os.path.join(PLUG,'resources','skins','Default','1080i','fckyo-cinema-v2.xml')


def cinema_screen():
    if 'xbmcgui' not in sys.modules:
        gui=types.ModuleType('xbmcgui')
        gui.WindowXMLDialog=type('WindowXMLDialog',(),{})
        sys.modules['xbmcgui']=gui
    if 'xbmc' not in sys.modules:
        sys.modules['xbmc']=types.ModuleType('xbmc')
    from cinema_screen_v2 import CinemaScreen
    return CinemaScreen


class StreamingHomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ET.parse(SKIN).getroot()

    def test_all_visible_rails_have_landscape_backdrops(self):
        for cid in range(401,408):
            rail=self.root.find(".//control[@id='%d']"%cid)
            self.assertIsNotNone(rail)
            self.assertEqual(rail.findtext('orientation'),'horizontal')
            item=rail.find('itemlayout')
            self.assertGreater(int(item.get('width')),int(item.get('height')))
            posters=[image for image in item.findall("control[@type='image']")
                     if image.findtext('texture')=='$INFO[ListItem.Art(thumb)]']
            self.assertEqual(len(posters),1)
            poster=posters[0]
            self.assertGreater(int(poster.findtext('width')),
                               int(poster.findtext('height')))

    def test_bottom_navigation_never_jumps_back_to_header(self):
        for cid in range(401,408):
            rail=self.root.find(".//control[@id='%d']"%cid)
            links=rail.findall('ondown')
            self.assertTrue(links)
            self.assertEqual(links[-1].text,str(cid))
            self.assertTrue(all(int(link.text)>=cid for link in links))
        bottom=self.root.find(".//control[@id='407']")
        self.assertEqual(bottom.findall('ondown')[-1].text,'407')

    def test_empty_rows_are_skipped_by_conditional_navigation(self):
        for cid in range(401,407):
            rail=self.root.find(".//control[@id='%d']"%cid)
            links=rail.findall('ondown')
            self.assertTrue(all(link.get('condition') for link in links[:-1]))
            if cid<406:
                self.assertTrue(any(int(link.text)>cid+1 for link in links[:-1]))

    def test_dark_theme_and_more_space_for_scroll(self):
        container=self.root.find(".//control[@id='610']")
        self.assertEqual(container.get('type'),'grouplist')
        self.assertEqual(container.findtext('orientation'),'vertical')
        self.assertGreaterEqual(int(container.findtext('height')),500)
        with open(os.path.join(PLUG,'cinematic_home.py'),encoding='utf8') as f:
            code=f.read()
        self.assertIn("stream_v4_",code)
        self.assertIn("color = (154,108,255,255)",code)

    def test_last_visible_rail_stays_focused_on_down(self):
        window=cinema_screen().__new__(cinema_screen())
        window.rail_items=[[1],[2],[],[3],[],[],[]]
        self.assertEqual(window._last_filled_rail(),404)
        window.getFocusId=lambda:404
        events=[]
        window._update_hero=lambda:events.append('update')
        window._go_back=lambda:events.append('back')
        window.onAction(types.SimpleNamespace(getId=lambda:4))
        self.assertEqual(events,['update'])

    def test_back_restores_selected_row_and_item(self):
        window=cinema_screen().__new__(cinema_screen())
        window.stack=[('home',None,405,8)]
        window.rail_items=[[],[],[],[],[1]*10,[],[]]
        events=[]
        window._screen=lambda view,ctx:events.append(('screen',view))
        window.setFocusId=lambda cid:events.append(('focus',cid))
        window.getControl=lambda cid:types.SimpleNamespace(
            selectItem=lambda index:events.append(('item',index)))
        window._update_hero=lambda:events.append(('hero',))
        window._go_back()
        self.assertEqual(events,[('screen','home'),('focus',405),
                                 ('item',8),('hero',)])


if __name__=='__main__':
    unittest.main()
