# -*- coding: utf-8 -*-
"""Profile isolation, path validation and legacy compatibility tests."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0,os.path.abspath(os.path.join(
    os.path.dirname(__file__),'..','plugin.video.fckyo')))
from cinema_profiles import (list_profiles,active_profile,add_profile,
    activate_profile,delete_profile,state_paths)
from cinema_user_state import WatchStore

class ProfileTests(unittest.TestCase):
    def test_legacy_main_state_survives_profile_switch(self):
        with tempfile.TemporaryDirectory() as root:
            original=WatchStore(root)
            self.assertTrue(original.path.endswith('fckyo-watch-state-v1.json'))
            sample={'watch':{'movie|classic|1990':{'title':'Classic',
                     'kind':'movie','name':'Classic.mkv','ident':'101'}},
                    'favorites':{}}
            original._write(original.path,sample)
            alternate=add_profile(root,'Jiný divák')
            self.assertEqual(active_profile(root)['id'],alternate)
            second=WatchStore(root)
            self.assertNotEqual(second.path,original.path)
            self.assertEqual(second._data()['watch'],{})
            activate_profile(root,'main')
            self.assertEqual(WatchStore(root)._data()['watch'],sample['watch'])
            activate_profile(root,alternate)
            self.assertEqual(WatchStore(root)._data()['watch'],{})
    def test_names_and_ids_are_validated(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                add_profile(root,'  ')
            user=add_profile(root,'Obývák')
            self.assertEqual(len(list_profiles(root)),2)
            with self.assertRaises(ValueError):
                activate_profile(root,'../../secrets')
            with self.assertRaises(ValueError):
                add_profile(root,'Obývák')
            with self.assertRaises(ValueError):
                delete_profile(root,user)
            activate_profile(root,'main')
            delete_profile(root,user)
            self.assertEqual(len(list_profiles(root)),1)
    def test_registry_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root,'kivora-profiles-v1.json'),'w') as f:
                f.write('{broken json')
            self.assertEqual(active_profile(root)['id'],'main')
            self.assertIn('fckyo-watch-state-v1.json',state_paths(root)[0])

if __name__=='__main__':
    unittest.main()
