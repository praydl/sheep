const logic = require('../../game/logic')
const audio = require('../../game/audio')

Page({
  data: {
    status: 'idle', // idle | playing | win | lose
    tiles: [],
    slot: [],
    emptyCells: [],
    remaining: 0,
    boardW: 0,
    boardH: 0,
    muted: false
  },

  onLoad() {
    // 棋盘尺寸由布局常量算出来，跟逻辑层共用一份数据
    const tiles = logic.buildTiles()
    let boardW = 0
    let boardH = 0
    tiles.forEach(function measure(t) {
      boardW = Math.max(boardW, t.left + logic.TILE_RPX)
      boardH = Math.max(boardH, t.top + logic.TILE_RPX)
    })

    this.game = null
    this.tileById = {}
    this.shakeId = 0
    this.setData({ boardW: boardW, boardH: boardH })
  },

  onShow() {
    if (this.data.status === 'playing') audio.playBgm()
  },

  onHide() {
    audio.pauseBgm()
  },

  onUnload() {
    audio.destroy()
  },

  /* ------------------------------ 开局 / 重开 ------------------------------ */

  start() {
    const game = logic.createGame({ seed: Date.now() })

    this.game = game
    this.tileById = {}
    this.shakeId = 0
    game.tiles.forEach((t) => {
      this.tileById[t.id] = t
    })

    this.setData({
      status: 'playing',
      slot: [],
      emptyCells: this.emptyCells(0),
      remaining: game.remaining()
    })
    this.syncBoard()
    audio.playBgm()
  },

  /* -------------------------------- 交互 -------------------------------- */

  onTapTile(e) {
    if (this.data.status !== 'playing' || !this.game) return

    const id = Number(e.currentTarget.dataset.id)
    const result = this.game.tap(id)

    if (!result.ok) {
      if (result.reason === 'covered') this.shake(id)
      return
    }

    audio.play('tap')
    const tile = this.tileById[id]
    const slot = this.data.slot.concat([
      { id: id, type: tile.type, clearing: false }
    ])

    if (result.matched && result.matched.length === 3) {
      // 凑满三张：先在卡槽里播消除动画，再真正移除
      const matched = {}
      result.matched.forEach(function mark(mid) {
        matched[mid] = true
      })
      slot.forEach(function flag(item) {
        if (matched[item.id]) item.clearing = true
      })

      this.setData({ slot: slot })
      this.syncBoard()
      audio.play('match')

      setTimeout(() => {
        const left = this.data.slot.filter(function keep(item) {
          return !item.clearing
        })
        this.setData({ slot: left, emptyCells: this.emptyCells(left.length) })
        this.finishIfNeeded()
      }, 240)
      return
    }

    this.setData({ slot: slot, emptyCells: this.emptyCells(slot.length) })
    this.syncBoard()

    if (result.status !== 'playing') this.finish(result.status)
  },

  toggleMute() {
    const muted = audio.setMuted(!this.data.muted)
    this.setData({ muted: muted })
  },

  /* -------------------------------- 内部 -------------------------------- */

  /** 把逻辑层的状态同步到视图（只渲染还在牌堆上的牌）。 */
  syncBoard() {
    if (!this.game) return

    const game = this.game
    const shakeId = this.shakeId
    const tiles = []

    game.tiles.forEach(function build(t) {
      if (!game.isOnBoard(t.id)) return
      tiles.push({
        id: t.id,
        type: t.type,
        left: t.left,
        top: t.top,
        z: t.z,
        covered: game.covered(t.id),
        shake: t.id === shakeId
      })
    })

    this.setData({ tiles: tiles, remaining: game.remaining() })
  },

  emptyCells(filled) {
    const list = []
    for (let i = filled; i < logic.SLOT_MAX; i++) list.push(i)
    return list
  },

  shake(id) {
    this.shakeId = id
    this.syncBoard()
    if (wx.vibrateShort) wx.vibrateShort({ type: 'light' })
    setTimeout(() => {
      this.shakeId = 0
      this.syncBoard()
    }, 320)
  },

  finishIfNeeded() {
    if (!this.game) return
    if (this.game.status !== 'playing') this.finish(this.game.status)
  },

  finish(status) {
    setTimeout(() => {
      this.setData({ status: status })
      audio.play(status === 'win' ? 'win' : 'lose')
      if (status === 'lose') audio.pauseBgm()
      if (wx.vibrateShort) {
        wx.vibrateShort({ type: status === 'win' ? 'heavy' : 'medium' })
      }
    }, 260)
  }
})
