'use strict';
const {contextBridge,ipcRenderer}=require('electron');
const names=['session','login','token','logout','tmdb','home','search','variants','episodes','stream','choose-mpv','mpv-path','external-play','favorites','favorite','get-progress','save-progress','clear-cache'];
const exposed={};for(const name of names)exposed[name]=(...args)=>ipcRenderer.invoke(name,...args);
exposed.onMpvError=(cb)=>{if(typeof cb==='function')ipcRenderer.on('mpv-error',(_,msg)=>cb(msg));};
contextBridge.exposeInMainWorld('playerApi',Object.freeze(exposed));
