# -*- coding: utf-8 -*-
"""A remote-first category hub for KIVORA settings."""
import xbmcgui

CATEGORIES={
    501:'account',
    502:'catalog',
    503:'profiles',
    504:'sync',
    505:'backups',
    506:'diagnostics',
    507:'advanced',
    508:'back',
}
BACK_ACTIONS=(9,10,92,216)

class SettingsHub(xbmcgui.WindowXMLDialog):
    def onInit(self):
        for key in ('background','button','tile','focus','cta_focus'):
            self.setProperty('settings_'+key,self.textures.get(key,''))
        try:
            self.setFocusId(501)
        except (RuntimeError,AttributeError,TypeError):
            pass

    def onClick(self,control_id):
        if control_id in CATEGORIES:
            self.result=CATEGORIES[control_id]
            self.close()

    def onAction(self,action):
        if action.getId() in BACK_ACTIONS:
            self.result='back'
            self.close()

def choose_settings(addon,textures):
    window=SettingsHub('fckyo-settings-v1.xml',addon.getAddonInfo('path'),
                       'Default','1080i')
    window.textures=textures
    window.result='back'
    try:
        window.doModal()
        return window.result
    finally:
        del window
