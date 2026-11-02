# -*- coding: utf-8 -*-
"""Run: python -m unittest discover -s tests -p 'test_kivora_backup.py'"""
import os
import sys
import json
import tempfile
import unittest
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','plugin.video.fckyo')))
from cinema_backup import export_backup,import_backup
from cinema_user_state import WatchStore

class PortableBackupTests(unittest.TestCase):
    def test_roundtrip_and_secret_scrubbing(self):
        with tempfile.TemporaryDirectory() as root:
            src=os.path.join(root,'source')
            dest=os.path.join(root,'destination')
            os.makedirs(src)
            os.makedirs(dest)
            watch=WatchStore(src)
            watch._write(watch.path,{'watch':{'movie|test|2024':{
                'title':'Test','kind':'movie','ident':'123','name':'test.mkv',
                'position':61,'total':120,'completed':False,'password':'DO_NOT_COPY',
                'token':'DO_NOT_COPY'}},'favorites':{}})
            filename=os.path.join(root,'backup.json')
            self.assertEqual(export_backup(src,filename),(1,0))
            with open(filename,encoding='utf-8') as stream:
                payload=stream.read()
            self.assertNotIn('DO_NOT_COPY',payload)
            self.assertEqual(import_backup(dest,filename),(1,0))
            self.assertEqual(WatchStore(dest)._data()['watch']['movie|test|2024']['position'],61)
    def test_reject_unknown_schema(self):
        with tempfile.TemporaryDirectory() as root:
            filename=os.path.join(root,'invalid.json')
            with open(filename,'w',encoding='utf-8') as stream:
                json.dump({'schema':999,'type':'kivora-library','data':{}},stream)
            with self.assertRaises(ValueError):
                import_backup(root,filename)

if __name__=='__main__':
    unittest.main()
