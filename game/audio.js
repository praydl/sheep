'use strict'

/**
 * 音频管理：BGM 循环 + 短音效复用。
 * 所有文件都是脚本生成的本地 wav，不需要网络。
 */

const FILES = {
  bgm: '/assets/bgm.wav',
  tap: '/assets/sfx/tap.wav',
  match: '/assets/sfx/match.wav',
  win: '/assets/sfx/win.wav',
  lose: '/assets/sfx/lose.wav'
}

const VOLUME = {
  bgm: 0.35,
  tap: 0.55,
  match: 0.7,
  win: 0.75,
  lose: 0.7
}

let bgm = null
const sfx = {}
let muted = false

function create(src, volume, loop) {
  const ctx = wx.createInnerAudioContext()
  ctx.src = src
  ctx.volume = volume
  ctx.loop = !!loop
  ctx.obeyMuteSwitch = false
  return ctx
}

function ensureBgm() {
  if (!bgm) {
    bgm = create(FILES.bgm, VOLUME.bgm, true)
    bgm.onError(function (err) {
      console.warn('[audio] bgm 播放失败', err)
    })
  }
  return bgm
}

function playBgm() {
  if (muted) return
  try {
    ensureBgm().play()
  } catch (err) {
    console.warn('[audio] playBgm', err)
  }
}

function pauseBgm() {
  if (bgm) bgm.pause()
}

function stopBgm() {
  if (bgm) bgm.stop()
}

function play(name) {
  if (muted || !FILES[name]) return
  let ctx = sfx[name]
  if (!ctx) {
    ctx = create(FILES[name], VOLUME[name] || 0.6, false)
    sfx[name] = ctx
  }
  try {
    ctx.stop()
    ctx.play()
  } catch (err) {
    console.warn('[audio] play ' + name, err)
  }
}

function setMuted(value) {
  muted = !!value
  if (muted) {
    pauseBgm()
  } else {
    playBgm()
  }
  return muted
}

function isMuted() {
  return muted
}

function destroy() {
  if (bgm) {
    bgm.destroy()
    bgm = null
  }
  Object.keys(sfx).forEach(function (key) {
    sfx[key].destroy()
    delete sfx[key]
  })
}

module.exports = {
  playBgm: playBgm,
  pauseBgm: pauseBgm,
  stopBgm: stopBgm,
  play: play,
  setMuted: setMuted,
  isMuted: isMuted,
  destroy: destroy
}
