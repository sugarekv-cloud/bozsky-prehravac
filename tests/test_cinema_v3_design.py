"""Cinema 3.0: shipped XML geometry, navigation and runtime contracts."""
import sys,types,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from xml.etree import ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'plugin.video.fckyo'))
for module in ('xbmc','xbmcgui'):
    if module not in sys.modules:sys.modules[module]=types.ModuleType(module)
if not hasattr(sys.modules['xbmcgui'],'WindowXMLDialog'):
    sys.modules['xbmcgui'].WindowXMLDialog=type('WindowXMLDialog',(),{})
from cinema_screen_v2 import CinemaScreen,DRAWER_IDS,TOP_ACTIONS
from cinema_details import CinemaDetail
from cinema_theme_v3 import ensure_textures,pixel
from tools.build_cinema_v3_skin import main_window,detail_window,settings_window
SKIN=ROOT/'plugin.video.fckyo/resources/skins/Default/1080i'

class GeometryTests(unittest.TestCase):
    def test_generated_files_are_current(self):
        for filename,build in [('fckyo-cinema-v3.xml',main_window),('fckyo-detail-v2.xml',detail_window),('fckyo-settings-v2.xml',settings_window)]:
            actual=E.parse(SKIN/filename).getroot();expected=E.fromstring(E.tostring(build()))
            # Ignore formatting only, not the controls and navigation.
            for r in (actual,expected):
                for node in r.iter():
                    node.text=(node.text or '').strip();node.tail=''
            self.assertEqual(E.tostring(actual),E.tostring(expected))

    def test_navigation_targets_exist_and_ids_are_unique(self):
        for name in ('fckyo-cinema-v3.xml','fckyo-detail-v2.xml','fckyo-settings-v2.xml'):
            root=E.parse(SKIN/name).getroot()
            ids=[c.get('id') for c in root.findall('.//control') if c.get('id')]
            self.assertEqual(len(ids),len(set(ids)))
            for node in root.iter():
                if node.tag in ('onleft','onright','onup','ondown'):
                    self.assertIn(node.text,ids,(name,node.tag,node.text))

    def test_all_sections_remain_accessible(self):
        root=E.parse(SKIN/'fckyo-cinema-v3.xml').getroot()
        ids={int(c.get('id')) for c in root.findall('.//control') if c.get('id')}
        self.assertEqual({TOP_ACTIONS[c] for c in ids if c in TOP_ACTIONS},set(TOP_ACTIONS.values()))
        self.assertTrue(set(DRAWER_IDS).issubset(ids))

    def test_card_art_caption_and_metadata_never_intersect(self):
        root=E.parse(SKIN/'fckyo-cinema-v3.xml').getroot()
        for ident in range(401,414):
            row=root.find(".//control[@id='%s']"%ident)
            for layout in ('itemlayout','focusedlayout'):
                c=row.find(layout);labels=c.findall("control[@type='label']")
                title=next(x for x in labels if x.findtext('label')=='$INFO[ListItem.Label]')
                year=next(x for x in labels if x.findtext('label')=='$INFO[ListItem.Property(year)]')
                quality=next(x for x in labels if x.findtext('label')=='$INFO[ListItem.Property(quality)]')
                bottom=lambda x:int(x.findtext('top'))+int(x.findtext('height'))
                self.assertGreaterEqual(int(title.findtext('top')),190)
                self.assertLessEqual(bottom(title),int(year.findtext('top')))
                self.assertLessEqual(bottom(year),int(c.get('height')))
                self.assertLessEqual(int(year.findtext('left'))+int(year.findtext('width')),int(quality.findtext('left')))
                self.assertNotIn('hide_caption',E.tostring(c).decode())
                for child in c.findall('control'):
                    for start,size,limit in (('left','width',int(c.get('width'))),('top','height',int(c.get('height')))):
                        self.assertLessEqual(int(child.findtext(start))+int(child.findtext(size)),limit)

    def test_footer_is_outside_scrolling_area(self):
        root=E.parse(SKIN/'fckyo-cinema-v3.xml').getroot()
        rail=root.find(".//control[@id='610']")
        bottom=int(rail.findtext('top'))+int(rail.findtext('height'))
        self.assertLessEqual(bottom,1040)
        for ident in (108,110,112,113):
            action=root.find(".//control[@id='%s']"%ident)
            self.assertLess(int(action.findtext('top'))+int(action.findtext('height')),int(rail.findtext('top')))

    def test_top_level_controls_fit_with_tv_safe_margin(self):
        for filename in ('fckyo-cinema-v3.xml','fckyo-detail-v2.xml','fckyo-settings-v2.xml'):
            root=E.parse(SKIN/filename).getroot()
            for c in root.findall('./controls/control'):
                if c.get('type') not in ('button','label','textbox'):continue
                x,y,w,h=[int(c.findtext(k)) for k in ('left','top','width','height')]
                self.assertGreaterEqual(x,40);self.assertGreaterEqual(y,40)
                self.assertLessEqual(x+w,1880);self.assertLessEqual(y+h,1064)

class RuntimeTests(unittest.TestCase):
    def screen(self):
        win=CinemaScreen.__new__(CinemaScreen)
        win.setProperty=Mock();win.setFocusId=Mock();win._apply_background_home=Mock()
        win._go_back=Mock();win._update_hero=Mock()
        return win

    def test_menu_click_and_back_do_not_pop_browse_history(self):
        w=self.screen();w.onClick(200)
        w.setProperty.assert_called_with('menu_open','yes');w.setFocusId.assert_called_with(201)
        w.getFocusId=lambda:203;w.onAction(types.SimpleNamespace(getId=lambda:92))
        w.setProperty.assert_called_with('menu_open','');w.setFocusId.assert_called_with(200)
        w._go_back.assert_not_called()
        w.getFocusId=lambda:401;w.onAction(types.SimpleNamespace(getId=lambda:92))
        w._go_back.assert_called_once()

    def test_leaving_drawer_closes_overlay(self):
        w=self.screen()
        for target in (200,101,401):
            w.setProperty.reset_mock();w.onFocus(target)
            w.setProperty.assert_called_with('menu_open','')

    def test_selecting_drawer_section_uses_visible_focus_target(self):
        w=self.screen();w._refresh=Mock();w.onClick(203)
        w._refresh.assert_called_with('favorites')
        self.assertEqual(w._nav_focus_target,200)
        w.setFocusId.assert_called_with(200)

    def test_full_description_is_readable_without_closing_detail(self):
        w=CinemaDetail.__new__(CinemaDetail);w.card={'title':'Film'};w.description='Dlouhý popis '*300;w.close=Mock()
        dialog=Mock()
        with patch.object(sys.modules['xbmcgui'],'Dialog',return_value=dialog,create=True):w.onClick(305)
        dialog.textviewer.assert_called_once_with('Film',w.description)
        w.close.assert_not_called()

    def test_texture_contrast_and_independent_cache(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            paths=ensure_textures(tmp)
            for path in paths.values():
                self.assertIn('cinema_v3_048',Path(path).name)
                with Image.open(path) as im:im.verify()
            self.assertEqual(ensure_textures(tmp),paths)
        self.assertGreaterEqual(pixel('fade',100,0,384,128)[3],250)
        self.assertGreaterEqual(pixel('detailfade',320,0,384,128)[3],190)
        self.assertEqual(pixel('focus',0,0,2,2),(250,250,252,255))

    def test_all_three_new_windows_are_wired_into_runtime(self):
        for module,xml in [('cinema_screen_v2.py','fckyo-cinema-v3.xml'),('cinema_details.py','fckyo-detail-v2.xml'),('cinema_settings_hub.py','fckyo-settings-v2.xml')]:
            self.assertIn(xml,(ROOT/'plugin.video.fckyo'/module).read_text())
