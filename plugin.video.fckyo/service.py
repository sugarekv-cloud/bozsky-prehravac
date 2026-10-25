# -*- coding: utf-8 -*-
"""Track the currently played FCKYO video with Kodi's native Player API.

Runs only while Kodi is open. A short-lived local intent is created AFTER the
Webshare video link resolves; playback is not counted unless the player starts.
"""
import time
import xbmc
import xbmcaddon
import xbmcvfs
from cinema_user_state import WatchStore


class WatchTracker:
    def __init__(self,profile,player=None,store=None):
        self.player=player or xbmc.Player()
        self.store=store or WatchStore(profile)
        self.active=None
        self.was_playing=False
        self.last_position=0
        self.total=0
        self.seeked=False

    def tick(self):
        playing=self.player.isPlayingVideo()
        if playing:
            if not self.active and not self.was_playing:
                pending=self.store.pop_pending()
                if pending.get('ident') and pending.get('name'):
                    self.active=pending
                    self.last_position=0
                    self.total=0
                    self.seeked=False
            if self.active:
                try:
                    self.total=max(0,self.player.getTotalTime())
                    if not self.seeked:
                        position=float(self.active.get('resume') or 0)
                        if position>15 and self.total>position+15:
                            self.player.seekTime(position)
                        self.seeked=True
                    self.last_position=max(0,self.player.getTime())
                    self.store.update_progress(self.active,self.last_position,self.total)
                except (RuntimeError,ValueError,AttributeError):
                    pass
        elif self.active:
            self.store.update_progress(self.active,self.last_position,self.total,
                                       completed=(self.total>0 and
                                                  self.last_position/self.total>=0.94))
            self.active=None
            self.seeked=False
        self.was_playing=playing

    def run(self,monitor=None):
        monitor=monitor or xbmc.Monitor()
        while not monitor.abortRequested():
            self.tick()
            if monitor.waitForAbort(4):
                break
        if self.active:
            self.store.update_progress(self.active,self.last_position,self.total)


def main():
    addon=xbmcaddon.Addon()
    profile=xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    WatchTracker(profile).run()


if __name__=='__main__':
    main()
