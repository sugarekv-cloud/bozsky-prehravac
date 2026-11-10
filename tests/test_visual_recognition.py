"""Synthetic previews and mocked APIs; no real videos or paid API calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugin.video.fckyo'))
from cinema_visual_index import VisualIndex, file_ident, identity
from cinema_visual_recognition import (preview_urls, image_data, recognize,
                                       parse_candidates, fetch_file, MAX_IMAGE_BYTES)
from cinema_catalog_v2 import groups, choose_files, grouped_episodes
from cinema_service_v2 import CinemaService


def file(ident='abc1234567',name='12345678.mkv',**kwargs):
    return dict(ident=ident,name=name,size='1000000000',img='https://img.webshare.cz/preview.jpg',**kwargs)


def match(**kwargs):
    return dict({'title':'Zelená míle','original':'The Green Mile','year':'1999','kind':'movie'},**kwargs)


class Available:
    def __init__(self,ok=True):self.ok=ok;self.checked=[]
    def check_groups(self,groups,max_workers=6):
        self.checked.extend(groups)
        return groups if self.ok else []
    def check_files(self,files,limit=24):return files if self.ok else []


def service(profile,available=None,fetch=None):
    svc=CinemaService('test-token',fetch or (lambda *a,**k:([],0)),available or Available(),profile=profile)
    svc.artwork.lookup=lambda *a,**k:None
    return svc


class IndexTests(unittest.TestCase):
    def test_roundtrip_original_filename_and_secret_exclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            index=VisualIndex(folder)
            original=file(wst='never-save',api_key='never-save')
            index.confirm(original,match())
            restored=VisualIndex(folder).search('The Green Mile','1999')
            self.assertEqual(restored[0]['name'],'12345678.mkv')
            self.assertNotIn('never-save',Path(index.path).read_text())
            self.assertEqual(groups(restored,'movie')[0]['title'],'Zelená míle')
            self.assertEqual(choose_files(restored)[0]['ident'],original['ident'])
            index.remove(original['ident'])
            self.assertEqual(VisualIndex(folder).all(),[])

    def test_unknown_file_found_by_confirmed_title_and_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            availability=Available();svc=service(folder,availability)
            svc.visual_index.confirm(file(),match())
            cards=svc.search('Zelená míle (1999)')
            self.assertEqual(len(cards),1)
            self.assertEqual(cards[0]['files'][0]['name'],'12345678.mkv')
            self.assertTrue(availability.checked)
            self.assertEqual(svc.files(cards[0])[0]['ident'],'abc1234567')
            self.assertEqual(svc.search('Zelená míle (2001)'),[])

    def test_deleted_webshare_file_not_exposed(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=service(folder,Available(False))
            svc.visual_index.confirm(file(),match())
            self.assertEqual(svc.search('Zelená míle'),[])

    def test_confirmed_index_works_when_filename_api_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=service(folder,fetch=lambda *a,**k:(None,0))
            svc.visual_index.confirm(file(),match())
            self.assertEqual(svc.search('Zelená míle')[0]['ident'],'abc1234567')

    def test_episode_selection_and_playable_variant_keep_real_name(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=service(folder)
            svc.visual_index.confirm(file(),match(title='Bluey',original='Bluey',year='',kind='episode',season=2,episode=3))
            cards=svc.search('Bluey S02E03')
            self.assertEqual(len(cards),1)
            self.assertEqual(svc.seasons(cards[0])[2][3][0]['name'],'12345678.mkv')
            self.assertEqual(svc.search('Bluey S02E04'),[])
            self.assertEqual(svc.search('Bluey S01'),[])

    def test_manual_mapping_cannot_remove_adult_or_locked_flags(self):
        with tempfile.TemporaryDirectory() as folder:
            index=VisualIndex(folder)
            for bad in (file(adult='1'),file(password='1'),file(removed='1'),
                        file(name='porn.1080p.mkv'),file(name='notes.txt')):
                with self.subTest(bad=bad),self.assertRaises(ValueError):index.confirm(bad,match())
            with self.assertRaises(ValueError):index.confirm(file(),match(title='Porn Movie'))

    def test_series_requires_specific_episode(self):
        with self.assertRaises(ValueError):identity(match(kind='series'))
        with self.assertRaises(ValueError):identity(match(kind='episode'))
        with self.assertRaises(ValueError):identity(match(title='[B]name[/B]'))

    def test_corrupt_index_does_not_break_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'visual-identities-v1.json').write_text('{broken')
            self.assertEqual(VisualIndex(folder).all(),[])

    def test_ident_urls_and_non_webshare_rejected(self):
        for value in ('abc1234567','https://webshare.cz/file/abc1234567/title',
                      'https://webshare.cz/#/file/abc1234567/title'):
            self.assertEqual(file_ident(value),'abc1234567')
        for value in ('https://evil.test/file/abc1234567','https://webshare.cz.evil.test/file/abc1234567','no'):
            with self.assertRaises(ValueError):file_ident(value)


class RecognitionTests(unittest.TestCase):
    def image_response(self,chunks=None):
        response=Mock(status_code=200,headers={'Content-Type':'image/jpeg'})
        response.iter_content.return_value=chunks or [b'fake-jpeg']
        return response

    def test_only_webshare_https_previews_and_two_images_max(self):
        self.assertEqual(len(preview_urls(file(stripe='https://webshare.cz/stripe.jpg'))),2)
        for url in ('http://localhost/p','https://webshare.cz.evil.test/p','https://u:p@webshare.cz/p','https://127.0.0.1/p'):
            self.assertEqual(preview_urls({'img':url}),[])

    def test_download_is_bounded_and_redirects_are_not_followed(self):
        response=self.image_response([b'x'*(MAX_IMAGE_BYTES+1)])
        get=Mock(return_value=response)
        with self.assertRaises(ValueError):image_data(file()['img'],get)
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        response.close.assert_called_once()

    def test_no_api_key_or_no_preview_means_no_request(self):
        post=Mock();get=Mock()
        with self.assertRaises(ValueError):recognize(file(),' ',post,get)
        with self.assertRaises(ValueError):recognize(dict(file(),img=''),'key',post,get)
        post.assert_not_called();get.assert_not_called()

    def test_ai_receives_only_image_bytes_and_returns_unconfirmed_candidates(self):
        get=Mock(return_value=self.image_response())
        response=Mock(status_code=200)
        response.json.return_value={'choices':[{'message':{'content':json.dumps({'explicit':False,'candidates':[match()]})}}]}
        post=Mock(return_value=response)
        result=recognize(file(wst='SECRET_WEBSHARE'),'test-key',post,get)
        self.assertEqual(result[0]['title'],'Zelená míle')
        payload=post.call_args.kwargs['json']
        body=json.dumps(payload)
        self.assertNotIn('SECRET_WEBSHARE',body)
        self.assertNotIn('abc1234567',body)
        self.assertNotIn('img.webshare.cz',body)
        self.assertFalse(payload['store'])
        self.assertIn('data:image/jpeg;base64,',body)

    def test_unknown_explicit_and_malformed_predictions_are_not_results(self):
        for data in ({'explicit':True,'candidates':[match()]},
                     {'candidates':[match()]},{'explicit':False,'candidates':'broken'},
                     {'explicit':False,'candidates':[match(title='Porn Movie')]},
                     {'explicit':False,'candidates':[match(kind='wrong')]}):
            self.assertEqual(parse_candidates(data),[])

    def test_api_errors_hide_body_and_credentials(self):
        response=Mock(status_code=401)
        post=Mock(return_value=response)
        with self.assertRaisesRegex(ValueError,'API klíč') as error:
            recognize(file(),'secret',post,Mock(return_value=self.image_response()))
        self.assertNotIn('secret',str(error.exception))

    def test_file_info_preserves_flags_and_uses_webshare_only(self):
        response=Mock(content=b'<response><status>OK</status><name>12345678.mkv</name><adult>1</adult></response>')
        post=Mock(return_value=response)
        with self.assertRaises(ValueError):fetch_file('abc1234567','token',post)
        self.assertEqual(post.call_args.args[0],'https://webshare.cz/api/file_info/')


class DialogTests(unittest.TestCase):
    def ui(self):
        import types
        if 'xbmcgui' not in sys.modules:
            sys.modules['xbmcgui']=types.ModuleType('xbmcgui')
        import cinema_visual_ui
        return cinema_visual_ui

    def test_manual_confirmation_is_required_and_clears_old_search(self):
        ui=self.ui()
        with tempfile.TemporaryDirectory() as folder:
            svc=service(folder);svc.search_cache['old']=[]
            dialog=Mock()
            dialog.select.side_effect=[1,0]
            dialog.input.side_effect=['Zelená míle','1999','The Green Mile']
            dialog.yesno.return_value=True
            query=ui.identify(Mock(),svc,file(),dialog)
            self.assertEqual(query,'Zelená míle (1999)')
            self.assertEqual(len(svc.visual_index.all()),1)
            self.assertEqual(svc.search_cache,{})

    def test_declining_final_confirmation_never_saves(self):
        ui=self.ui()
        with tempfile.TemporaryDirectory() as folder:
            svc=service(folder);dialog=Mock()
            dialog.select.side_effect=[1,0]
            dialog.input.side_effect=['Matrix','1999','']
            dialog.yesno.return_value=False
            self.assertIsNone(ui.identify(Mock(),svc,file(),dialog))
            self.assertEqual(svc.visual_index.all(),[])

    def test_declining_image_transfer_does_not_call_ai(self):
        ui=self.ui()
        with tempfile.TemporaryDirectory() as folder:
            svc=service(folder);dialog=Mock();addon=Mock()
            addon.getSetting.return_value='test-key'
            dialog.select.return_value=0;dialog.yesno.return_value=False
            with patch.object(ui,'analyze') as analyze:
                self.assertIsNone(ui.identify(addon,svc,file(),dialog))
                analyze.assert_not_called()
            self.assertEqual(svc.visual_index.all(),[])

    def test_cancelled_recognition_never_reaches_paid_api(self):
        post=Mock();get=Mock()
        self.assertEqual(recognize(file(),'key',post,get,cancelled=lambda:True),[])
        post.assert_not_called();get.assert_not_called()

    def test_cancelled_progress_discards_result_and_releases_dialog(self):
        ui=self.ui()
        progress=Mock();progress.iscanceled.return_value=True
        with tempfile.TemporaryDirectory() as folder:
            svc=service(folder)
            with patch.object(ui.xbmcgui,'DialogProgress',return_value=progress,create=True), \
                 patch.object(ui,'recognize',return_value=[match()]):
                self.assertIsNone(ui.analyze(svc,file(),'key'))
            progress.close.assert_called_once()
            self.assertEqual(svc.visual_index.all(),[])

    def test_local_sequel_never_becomes_playback_variant(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=service(folder)
            svc.visual_index.confirm(file(),match(title='Matrix',original='',year='1999'))
            svc.visual_index.confirm(file(ident='sequel1234'),match(title='Matrix Reloaded',original='',year='2003'))
            card=svc.search('Matrix')[0]
            self.assertEqual([f['ident'] for f in svc.files(card)],['abc1234567'])
