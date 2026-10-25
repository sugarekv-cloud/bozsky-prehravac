# -*- coding: utf-8 -*-
"""Regression for Kodi File Manager showing an empty GitHub Pages folder.

Kodi's CHTTPDirectory.cpp recognizes an HTML directory entry only if the
anchor's displayed name equals its href (after removing trailing '/').
Fancy download call-to-action labels cause an apparently empty directory.
"""
import re
import unittest

import build_repo


KODI_LINK_REGEX=re.compile(
    r'<a href="([^"]*)"[^>]*>\\s*(.*?)\\s*</a>(.+?)(?=<a|</tr|$)',
    re.IGNORECASE | re.DOTALL
)


class KodiHttpListingTests(unittest.TestCase):
    def test_kodi_recognizes_repository_zip_from_web_source(self):
        name="repository.bozskyprehravac-1.0.0.zip"
        page=build_repo.website_index(
            name,"0.35.0","https://sugarekv-cloud.github.io/bozsky-prehravac/")
        links=KODI_LINK_REGEX.findall(page)
        self.assertTrue(links)
        accepted=[href for href,label,metadata in links
                  if href.strip('/').strip()==label.strip().strip('/')]
        self.assertIn(name,accepted)
        self.assertIn("plugin.video.fckyo/plugin.video.fckyo-0.35.0.zip",
                      accepted)
        self.assertTrue(any(meta.strip() for href,label,meta in links if href==name))

    def test_readable_webpage_still_has_installation_instructions(self):
        page=build_repo.website_index(
            "repository.bozskyprehravac-1.0.0.zip",
            "0.35.0","https://sugarekv-cloud.github.io/bozsky-prehravac/")
        self.assertIn("Božský přehrávač",page)
        self.assertIn("Instalovat ze ZIP",page)

    def test_old_descriptive_anchor_would_fail_kodi_directory_parser(self):
        old_html='<a href="repository.bozskyprehravac-1.0.0.zip">Instalovat repozitář</a> next'
        old_links=KODI_LINK_REGEX.findall(old_html)
        self.assertEqual(len(old_links),1)
        self.assertNotEqual(old_links[0][0],old_links[0][1])


if __name__=='__main__':
    unittest.main()
