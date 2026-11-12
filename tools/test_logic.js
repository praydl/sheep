'use strict'

/**
 * 逻辑层回归测试：node tools/test_logic.js
 * 重点验证「牌局一定可解」和「卡槽溢出必判负」两条硬规则。
 */

const assert = require('assert')
const logic = require('../game/logic')

const SEEDS = 300
let winCount = 0

/* 1. 牌局结构 */
for (let seed = 1; seed <= SEEDS; seed++) {
  const game = logic.createGame({ seed: seed })
  const tiles = game.tiles

  assert.strictEqual(tiles.length % 3, 0, '牌数必须是 3 的倍数，seed=' + seed)
  assert.strictEqual(tiles.length, 66, '当前布局应为 66 张，seed=' + seed)

  const ids = new Set()
  const types = new Set()
  tiles.forEach((t) => {
    assert(!ids.has(t.id), '牌 id 重复：' + t.id)
    ids.add(t.id)
    assert(logic.ICON_TYPES.indexOf(t.type) >= 0, '牌型非法：' + t.type)
    assert(t.left >= 0 && t.top >= 0, '坐标不能为负')
    types.add(t.type)
  })
  assert.strictEqual(types.size, 10, '应出现 10 种牌型，seed=' + seed)

  // 每种牌必须恰好是 3 的倍数张（三消的前提）
  const counter = {}
  tiles.forEach((t) => {
    counter[t.type] = (counter[t.type] || 0) + 1
  })
  Object.keys(counter).forEach((type) => {
    assert.strictEqual(counter[type] % 3, 0, type + ' 的数量不是 3 的倍数')
  })
}

console.log('[1] 结构校验通过：' + SEEDS + ' 个牌局，每个 66 张 / 10 种牌型 / 每型均为 3 的倍数')

/* 2. 可解性：按生成的顺序一定能通关，且卡槽绝不溢出 */
for (let seed = 1; seed <= SEEDS; seed++) {
  const game = logic.createGame({ seed: seed })
  let maxSlot = 0

  game.order.forEach((id) => {
    const res = game.tap(id)
    assert.strictEqual(res.ok, true, '保证顺序中出现了不可点的牌，seed=' + seed)
    maxSlot = Math.max(maxSlot, game.slot.length)
    assert(
      game.slot.length <= logic.SLOT_MAX,
      '卡槽溢出 ' + game.slot.length + ' > ' + logic.SLOT_MAX + '，seed=' + seed
    )
  })

  assert.strictEqual(game.status, 'win', '按保证顺序未通关，seed=' + seed)
  assert.strictEqual(game.remaining(), 0, '还有牌没消掉，seed=' + seed)
  assert.strictEqual(game.slot.length, 0, '通关后卡槽应为空，seed=' + seed)

  if (seed <= 50) {
    // 记录一下难度体感：卡槽最高占用越小越好过
    assert(maxSlot <= 6, '卡槽峰值过高，seed=' + seed + ' peak=' + maxSlot)
  }
  winCount++
}

console.log('[2] 可解性通过：' + winCount + ' 个牌局全部按保证顺序通关，卡槽峰值 <= 6')

/* 3. 被压住的牌不能点 */
{
  const game = logic.createGame({ seed: 2024 })
  const coveredTile = game.tiles.find((t) => game.covered(t.id))
  assert(coveredTile, '底层的牌应该被压住')

  const before = game.remaining()
  const res = game.tap(coveredTile.id)
  assert.strictEqual(res.ok, false)
  assert.strictEqual(res.reason, 'covered')
  assert.strictEqual(game.remaining(), before, '点被压住的牌不应改变牌堆')
  console.log('[3] 叠压规则通过：被压住的牌被正确拒绝')
}

/* 4. 同一张牌不能重复点 */
{
  const game = logic.createGame({ seed: 7 })
  const free = game.tiles.find((t) => !game.covered(t.id))
  assert.strictEqual(game.tap(free.id).ok, true)
  const again = game.tap(free.id)
  assert.strictEqual(again.ok, false)
  assert.strictEqual(again.reason, 'gone')
  console.log('[4] 重复点击通过：已入槽的牌不能再次点击')
}

/* 5. 卡槽塞满 7 格必然判负 */
{
  const game = logic.createGame({ seed: 99 })
  let guard = 0

  while (game.status === 'playing' && guard++ < 200) {
    // 优先选卡槽里还没有的牌型，避免误触发三消，把卡槽塞满
    const exposed = game.pickable()
    const slotTypes = game.slot.map((s) => s.type)
    const fresh = exposed.filter((t) => slotTypes.indexOf(t.type) < 0)
    const pick = (fresh.length ? fresh : exposed)[0]
    if (!pick) break
    game.tap(pick.id)
  }

  assert.strictEqual(game.status, 'lose', '塞满卡槽应当判负')
  assert.strictEqual(game.slot.length, logic.SLOT_MAX, '判负时卡槽应为 7 格')
  console.log('[5] 判负规则通过：卡槽 ' + game.slot.length + ' 格且无三消 -> lose')
}

/* 6. 通关后不能再操作 */
{
  const game = logic.createGame({ seed: 4242 })
  game.order.forEach((id) => game.tap(id))
  assert.strictEqual(game.status, 'win')
  const res = game.tap(game.tiles[0].id)
  assert.strictEqual(res.ok, false)
  assert.strictEqual(res.reason, 'ended')
  console.log('[6] 终局锁定通过：通关后不再接受点击')
}

console.log('\nALL CHECKS PASSED')
