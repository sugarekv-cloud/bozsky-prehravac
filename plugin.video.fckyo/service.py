# -*- coding: utf-8 -*-
"""Track the currently played FCKYO video with Kodi's native Player API.

Runs only while Kodi is open. A short-lived local intent is created AFTER the
Webshare video link resolves; playback is not counted unless the player starts.
"""
import time
from urllib.parse import urlencode
import xbmc
import xbmcaddon
import xbmcvfs
from cinema_user_state import WatchStore


class WatchTracker:
    def __init__(self,profile,player=None,store=None,return_to_addon=None,
                 play_next=None,autoplay_enabled=None):
        self._ended=False
        self._stopped=False
        if player is None:
            tracker=self
            class CallbackPlayer(xbmc.Player):
                def onPlayBackEnded(self):
                    tracker._ended=True
                def onPlayBackStopped(self):
                    tracker._stopped=True
            self.player=CallbackPlayer()
        else:
            self.player=player
        self.store=store or WatchStore(profile)
        self.play_next=(play_next if play_next is not None
                        else self._play_next_episode)
        self.autoplay_enabled=(autoplay_enabled if autoplay_enabled is not None
                               else self._autoplay_enabled)
        self.active=None
        self.was_playing=False
        self.last_position=0
        self.total=0
        self.seeked=False
        self.return_to_addon=(return_to_addon if return_to_addon is not None
                              else self._return_to_addon)

    @staticmethod
    def _return_to_addon():
        """Open the plugin window after our video exits, not Kodi's root."""
        builtin=getattr(xbmc,'executebuiltin',None)
        if builtin:
            builtin('ActivateWindow(Videos,plugin://plugin.video.fckyo/?action=cinematic_home,return)')

    @staticmethod
    def _autoplay_enabled():
        return xbmcaddon.Addon().getSetting('autoplay_next_episode')!='false'

    @staticmethod
    def _play_next_episode(item):
        """Ask the plugin to locate/check the next episode with current credentials."""
        params={'action':'autoplay_episode',
                'title':item.get('title') or '',
                'raw_title':item.get('raw_title') or item.get('title') or '',
                'original':item.get('original') or '',
                'year':item.get('year') or '',
                'poster':item.get('poster') or '',
                'fanart':item.get('fanart') or '',
                'plot':item.get('plot') or '',
                'genre':item.get('genre') or '',
                'season':item.get('season') or '',
                'episode':item.get('episode') or '',
                'previous_name':item.get('name') or ''}
        url='plugin://plugin.video.fckyo/?'+urlencode(params)
        xbmc.executebuiltin('PlayMedia(%s)'%url)

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
                    self._ended=False
                    self._stopped=False
            if self.active:
                try:
                    self.total=max(0,self.player.getTotalTime())
                    if not self.seeked and self.total>0:
                        position=float(self.active.get('resume') or 0)
                        if position>15 and self.total>position+15:
                            self.player.seekTime(position)
                        self.seeked=True
                    self.last_position=max(0,self.player.getTime())
                    self.store.update_progress(self.active,self.last_position,self.total)
                except (RuntimeError,ValueError,AttributeError):
                    pass
        elif self.active:
            current=self.active
            # Kodi calls onPlayBackEnded only for natural playback completion,
            # whereas an early Stop triggers onPlayBackStopped.
            ended=self._ended and not self._stopped
            self.store.update_progress(current,self.last_position,self.total,
                                       completed=ended or (self.total>0 and
                                                  self.last_position/self.total>=0.94))
            self.active=None
            self.seeked=False
            self._ended=False
            self._stopped=False
            # Never autoplay movies, an unidentified episode, or a manual Stop.
            should_advance=(ended and current.get('kind')=='show' and
                            current.get('season') and current.get('episode')
                            and self.autoplay_enabled())
            try:
                if should_advance:
                    self.play_next(current)
                else:
                    self.return_to_addon()
            except Exception:
                self.return_to_addon()
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
