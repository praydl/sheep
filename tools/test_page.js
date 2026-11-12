'use strict'

/**
 * 页面层冒烟测试：在 Node 里搭个假的 wx / Page 环境，把页面逻辑真跑一遍。
 * 验证：开局、点牌入槽、三消、被压住的牌点不动、静音开关、按保证顺序能通关。
 */

const assert = require('assert')

let pageDef = null
const audioLog = []

global.wx = {
  createInnerAudioContext: function () {
    return {
      src: '',
      volume: 1,
      loop: false,
      obeyMuteSwitch: true,
      onError: function () {},
      play: function () {
        audioLog.push('play')
      },
      stop: function () {},
      pause: function () {},
      destroy: function () {}
    }
  },
  vibrateShort: function () {},
  showToast: function () {}
}

global.Page = function (def) {
  pageDef = def
}

// 让 setTimeout 同步执行，测试就不用等动画
const realSetTimeout = global.setTimeout
global.setTimeout = function (fn) {
  fn()
  return 0
}

require('../pages/game/game.js')

function makePage() {
  const page = Object.assign({}, pageDef)
  page.data = JSON.parse(JSON.stringify(pageDef.data))
  page.setData = function (patch) {
    Object.keys(patch).forEach((key) => {
      this.data[key] = patch[key]
    })
  }
  return page
}

function tap(page, id) {
  page.onTapTile({ currentTarget: { dataset: { id: id } } })
}

/* 1. 初始化 */
const page = makePage()
page.onLoad()
assert.strictEqual(page.data.status, 'idle')
assert.strictEqual(page.data.boardW, 504, '棋盘宽度应为 504rpx')
assert.strictEqual(page.data.boardH, 420, '棋盘高度应为 420rpx')
console.log('[1] 初始化通过：棋盘 ' + page.data.boardW + 'x' + page.data.boardH + 'rpx')

/* 2. 开局 */
page.start()
assert.strictEqual(page.data.status, 'playing')
assert.strictEqual(page.data.tiles.length, 66)
assert.strictEqual(page.data.remaining, 66)
assert.strictEqual(page.data.slot.length, 0)
assert.strictEqual(page.data.emptyCells.length, 7)
assert(audioLog.length > 0, '开局应该播放 BGM')
console.log('[2] 开局通过：66 张牌，卡槽 7 格空位')

/* 3. 被压住的牌点不动 */
const covered = page.game.tiles.filter(function (t) {
  return page.game.isOnBoard(t.id) && page.game.covered(t.id)
})
assert(covered.length > 0)
const beforeCount = page.data.tiles.length
tap(page, covered[0].id)
assert.strictEqual(page.data.tiles.length, beforeCount, '点被压住的牌不应变化')
assert.strictEqual(page.data.slot.length, 0)
console.log('[3] 叠压通过：被压住的牌点不动')

/* 4. 点一张能点的牌，应进入卡槽 */
const pickable = page.game.pickable()
tap(page, pickable[0].id)
assert.strictEqual(page.data.slot.length, 1)
assert.strictEqual(page.data.emptyCells.length, 6)
assert.strictEqual(page.data.remaining, 65)
console.log('[4] 入槽通过：卡槽 1 张，剩余 65')

/* 5. 静音开关 */
page.toggleMute()
assert.strictEqual(page.data.muted, true)
page.toggleMute()
assert.strictEqual(page.data.muted, false)
console.log('[5] 静音开关通过')

/* 6. 按保证顺序完整通关 */
page.start()
const order = page.game.order.slice()
order.forEach((id) => tap(page, id))
assert.strictEqual(page.data.status, 'win', '按保证顺序应当通关')
assert.strictEqual(page.data.remaining, 0)
assert.strictEqual(page.data.slot.length, 0)
assert.strictEqual(page.data.emptyCells.length, 7)
assert.strictEqual(page.data.tiles.length, 0)
console.log('[6] 通关通过：视图剩余 0 张，卡槽清空，状态 win')

/* 7. 通关后点击无效 */
const anyId = page.game.tiles[0].id
tap(page, anyId)
assert.strictEqual(page.data.remaining, 0)
console.log('[7] 终局锁定通过')

/* 8. 再来一局能重置 */
page.start()
assert.strictEqual(page.data.status, 'playing')
assert.strictEqual(page.data.remaining, 66)
assert.strictEqual(page.data.slot.length, 0)
console.log('[8] 重开通过')

/* 9. 一路乱点直到卡槽塞满，必须判负 */
page.start()
let guard = 0
while (page.data.status === 'playing' && guard++ < 100) {
  const exposed = page.game.pickable()
  if (!exposed.length) break
  const slotTypes = page.data.slot.map((s) => s.type)
  const fresh = exposed.filter((t) => slotTypes.indexOf(t.type) < 0)
  tap(page, (fresh.length ? fresh : exposed)[0].id)
}
assert.strictEqual(page.data.status, 'lose', '塞满卡槽应判负')
assert.strictEqual(page.data.slot.length, 7)
console.log('[9] 判负通过：卡槽 7 张 -> lose')

global.setTimeout = realSetTimeout
console.log('\nALL PAGE CHECKS PASSED')
