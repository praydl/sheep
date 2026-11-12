'use strict'

/**
 * 羊了个羊 —— 核心玩法逻辑（纯 JS，不依赖 wx，可直接在 Node 里测试）
 *
 * 玩法：牌堆分层叠放，上层牌压住下层牌。被压住的牌不能点。
 * 点中的牌进入底部卡槽，卡槽里同种牌凑满 3 张就消除。
 * 卡槽 7 格塞满且没有消除 -> 失败；所有牌清空 -> 通关。
 */

const ICON_TYPES = [
  'carrot',
  'grass',
  'wool',
  'bell',
  'milk',
  'corn',
  'mushroom',
  'apple',
  'sun',
  'clover'
]

const TILE_RPX = 84 // 一张牌的边长
const UNIT_RPX = TILE_RPX / 2 // 半格 = 42rpx，上层牌按半格错位才压得住下层
const SLOT_MAX = 7

/**
 * 分层布局。坐标单位是「半格」：一张牌占 2x2 个单位。
 * 上层用半个牌位的偏移，这样正好压住下层的 4 张牌中间。
 */
const LAYERS = [
  { cols: 6, rows: 5, ox: 0, oy: 0 }, // 30 张，最底
  { cols: 5, rows: 4, ox: 1, oy: 1 }, // 20 张
  { cols: 4, rows: 3, ox: 2, oy: 2 }, // 12 张
  { cols: 2, rows: 2, ox: 4, oy: 3 } // 4 张，最顶
]

/* ---------------------------------- 随机 ---------------------------------- */

function mulberry32(seed) {
  let a = seed >>> 0
  return function next() {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function shuffle(list, rng) {
  for (let i = list.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1))
    const tmp = list[i]
    list[i] = list[j]
    list[j] = tmp
  }
  return list
}

/* -------------------------------- 牌堆构建 -------------------------------- */

/** 生成所有牌的几何位置（类型先留空）。 */
function buildTiles() {
  const tiles = []
  let id = 1

  LAYERS.forEach(function eachLayer(cfg, layer) {
    for (let r = 0; r < cfg.rows; r++) {
      for (let c = 0; c < cfg.cols; c++) {
        const ux = cfg.ox + c * 2
        const uy = cfg.oy + r * 2
        tiles.push({
          id: id++,
          layer: layer,
          ux: ux,
          uy: uy,
          left: ux * UNIT_RPX,
          top: uy * UNIT_RPX,
          z: layer * 1000 + r * 10 + c,
          type: ''
        })
      }
    }
  })

  return tiles
}

/**
 * 计算每张牌被哪些牌压住（只看更高层、且有面积重叠的牌）。
 * 两张牌是否重叠：中心距离在半格坐标下 |dx| < 2 且 |dy| < 2。
 */
function buildAbove(tiles) {
  const above = new Map()
  tiles.forEach(function init(t) {
    above.set(t.id, [])
  })

  tiles.forEach(function lower(lo) {
    tiles.forEach(function upper(up) {
      if (up.layer <= lo.layer) return
      if (Math.abs(up.ux - lo.ux) < 2 && Math.abs(up.uy - lo.uy) < 2) {
        above.get(lo.id).push(up.id)
      }
    })
  })

  return above
}

/**
 * 生成一条「必然可通关」的取牌顺序：每次从当前没被压住的牌里随机取一张。
 * 这条顺序同时被用来分配牌型，保证游戏一定解得开。
 */
function buildOrder(tiles, above, rng) {
  const remaining = new Set(
    tiles.map(function id(t) {
      return t.id
    })
  )
  const order = []

  while (remaining.size > 0) {
    const free = []
    remaining.forEach(function check(id) {
      const blockers = above.get(id)
      for (let i = 0; i < blockers.length; i++) {
        if (remaining.has(blockers[i])) return
      }
      free.push(id)
    })

    if (free.length === 0) {
      throw new Error('牌堆存在循环覆盖，布局有误')
    }

    const choice = free[Math.floor(rng() * free.length)]
    order.push(choice)
    remaining.delete(choice)
  }

  return order
}

/** 按给定顺序模拟取牌，返回卡槽变化；中途超过容量则返回 null。 */
function simulate(order, typeById, slotMax) {
  const slot = []

  for (let i = 0; i < order.length; i++) {
    const type = typeById.get(order[i])
    slot.push(type)

    let count = 0
    for (let k = 0; k < slot.length; k++) {
      if (slot[k] === type) count++
    }

    if (count >= 3) {
      let removed = 0
      for (let k = slot.length - 1; k >= 0 && removed < 3; k--) {
        if (slot[k] === type) {
          slot.splice(k, 1)
          removed++
        }
      }
    }

    if (slot.length > slotMax) return null
  }

  return slot
}

/**
 * 分配牌型。
 *
 * 关键点：不能纯随机分配，纯随机生成的牌局大概率无解（羊了个羊第 2 关就是这么来的）。
 * 这里按「可通关顺序」把同种牌三个三个地埋进去：
 * 连续 3 个位置放同一种牌最稳，但那样太简单，所以把 stride 组牌交错摆放
 * （位置 t, t+stride, t+2*stride），再回放验证卡槽不会溢出。
 */
function assignTypes(tiles, order, opts, rng) {
  const total = order.length
  const triples = Math.floor(total / 3)
  const typeCount = Math.min(opts.typeCount, triples)
  const strides = [2, 3, 1]

  for (let s = 0; s < strides.length; s++) {
    const stride = strides[s]

    for (let attempt = 0; attempt < 40; attempt++) {
      const typeSeq = []
      for (let i = 0; i < triples; i++) {
        typeSeq.push(opts.types[i % typeCount])
      }
      shuffle(typeSeq, rng)

      const typeById = new Map()
      let pos = 0
      let tripleIndex = 0

      while (pos < total) {
        const group = Math.min(stride, triples - tripleIndex)
        for (let t = 0; t < group; t++) {
          for (let k = 0; k < 3; k++) {
            typeById.set(order[pos + t + k * group], typeSeq[tripleIndex + t])
          }
        }
        pos += group * 3
        tripleIndex += group
      }

      if (simulate(order, typeById, opts.slotMax) === null) continue

      tiles.forEach(function apply(t) {
        t.type = typeById.get(t.id)
      })

      return { typeById: typeById, stride: stride }
    }
  }

  throw new Error('无法生成可通关牌局')
}

/* --------------------------------- 游戏对象 -------------------------------- */

function createGame(options) {
  const opts = Object.assign(
    {
      seed: Date.now(),
      types: ICON_TYPES,
      typeCount: 10,
      slotMax: SLOT_MAX
    },
    options || {}
  )

  const rng = mulberry32(opts.seed)
  const tiles = buildTiles()
  const above = buildAbove(tiles)
  const order = buildOrder(tiles, above, rng)
  const info = assignTypes(tiles, order, opts, rng)

  const byId = new Map(
    tiles.map(function pair(t) {
      return [t.id, t]
    })
  )
  const onBoard = new Set(
    tiles.map(function id(t) {
      return t.id
    })
  )

  const game = {
    tiles: tiles,
    above: above,
    order: order, // 仅供测试/调试，不要暴露给界面
    seed: opts.seed,
    stride: info.stride,
    slotMax: opts.slotMax,
    slot: [],
    status: 'playing',

    /** 这张牌是否被压住（还有上层牌盖着它）。 */
    covered: function covered(id) {
      const blockers = above.get(id) || []
      for (let i = 0; i < blockers.length; i++) {
        if (onBoard.has(blockers[i])) return true
      }
      return false
    },

    /** 还在牌堆上的牌数。 */
    remaining: function remaining() {
      return onBoard.size
    },

    /** 这张牌是否还在牌堆里（没被点走）。 */
    isOnBoard: function isOnBoard(id) {
      return onBoard.has(id)
    },

    /** 当前可以点的牌（在牌堆上且没被压住）。 */
    pickable: function pickable() {
      return tiles.filter(function ok(t) {
        return onBoard.has(t.id) && !game.covered(t.id)
      })
    },

    /**
     * 点一张牌。
     * @returns {{ok:boolean, reason?:string, matched?:number[], status:string}}
     */
    tap: function tap(id) {
      if (game.status !== 'playing') {
        return { ok: false, reason: 'ended', status: game.status }
      }
      if (!onBoard.has(id)) {
        return { ok: false, reason: 'gone', status: game.status }
      }
      if (game.covered(id)) {
        return { ok: false, reason: 'covered', status: game.status }
      }

      const tile = byId.get(id)
      onBoard.delete(id)
      game.slot.push({ id: id, type: tile.type })

      const matched = []
      let count = 0
      for (let i = 0; i < game.slot.length; i++) {
        if (game.slot[i].type === tile.type) count++
      }

      if (count >= 3) {
        const keep = []
        for (let i = 0; i < game.slot.length; i++) {
          const item = game.slot[i]
          if (item.type === tile.type && matched.length < 3) {
            matched.push(item.id)
          } else {
            keep.push(item)
          }
        }
        game.slot = keep
      }

      if (onBoard.size === 0 && game.slot.length === 0) {
        game.status = 'win'
      } else if (game.slot.length >= game.slotMax) {
        game.status = 'lose'
      }

      return { ok: true, matched: matched, status: game.status }
    }
  }

  return game
}

module.exports = {
  createGame: createGame,
  simulate: simulate,
  buildTiles: buildTiles,
  buildAbove: buildAbove,
  buildOrder: buildOrder,
  mulberry32: mulberry32,
  ICON_TYPES: ICON_TYPES,
  TILE_RPX: TILE_RPX,
  UNIT_RPX: UNIT_RPX,
  SLOT_MAX: SLOT_MAX
}
