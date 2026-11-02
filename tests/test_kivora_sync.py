# -*- coding: utf-8 -*-
"""Shared-folder sync tests without Kodi or a network connection."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0,os.path.abspath(os.path.join(
    os.path.dirname(__file__),'..','plugin.video.fckyo')))
from cinema_sync import set_folder,sync_now,configured_folder
from cinema_user_state import WatchStore

MOVIE={'kind':'movie','title':'Ukázka','raw':'Ukázka','year':'2024',
       'ident':'123','name':'Ukazka.2024.mkv','token':'NEVER-COPY'}

class SharedSyncTests(unittest.TestCase):
    def test_two_tv_roundtrip_and_favorite_removal(self):
        with tempfile.TemporaryDirectory() as root:
            a=os.path.join(root,'tv1')
            b=os.path.join(root,'tv2')
            shared=os.path.join(root,'nas')
            for p in (a,b,shared):
                os.mkdir(p)
                set_folder(p,shared)
            first=WatchStore(a)
            first.update_progress(MOVIE,60,120)
            first.toggle_favorite(MOVIE)
            self.assertEqual(sync_now(a),(1,1))
            self.assertEqual(sync_now(b),(1,1))
            self.assertEqual(len(WatchStore(b).favorite_cards()),1)
            self.assertEqual(len(WatchStore(b).continue_cards()),1)
            with open(os.path.join(shared,os.listdir(shared)[0]),encoding='utf-8') as fh:
                self.assertNotIn('NEVER-COPY',fh.read())
            other=WatchStore(b)
            other.toggle_favorite(MOVIE)
            self.assertEqual(len(other.favorite_cards()),0)
            sync_now(b)
            sync_now(a)
            self.assertEqual(WatchStore(a).favorite_cards(),[])
    def test_invalid_network_credentials_and_corrupt_remote(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                set_folder(root,'smb://username:password@server/share')
            set_folder(root,root)
            self.assertEqual(configured_folder(root),root)
            self.assertEqual(sync_now(root),(0,0))
            for entry in os.listdir(root):
                if entry.startswith('kivora-library-'):
                    with open(os.path.join(root,entry),'w') as fh:
                        fh.write('not JSON')
            with self.assertRaises(ValueError):
                sync_now(root)

if __name__=='__main__':
    unittest.main()
