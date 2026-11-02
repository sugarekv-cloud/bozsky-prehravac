"""CI stub only; real Kodi injects its built-in xbmcaddon module."""
class Addon:
    def __init__(self,*args,**kwargs):
        pass
    def getSetting(self,key):
        return ''
    def getAddonInfo(self,key):
        return ''
