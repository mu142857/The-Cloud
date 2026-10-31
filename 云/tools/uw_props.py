"""水下仓库里的「东西」（泡在水里的木头家具、铁器、绳、纸）的画法：高度场 + 材质图 → 一张 RGBA。

10-30 作者：「很难看的方形，劣质柜子和木头……细节处理的不是很好」。原来的柜子、木板、门都是平涂的暗褐方块加几条线。
这里每件东西先在一张小画布上「搭」出来：每个像素记高度（朝镜头为正）、材质、木纹坐标（沿纹 gu / 横纹 gv）、零件号；
然后统一打光、上材质：
- 光：法线 = 高度场的梯度，光的方向和作者的水底（underwater_art.LIGHT：右上偏前，从水面打下来）一模一样，
  所以朝上的面、右沿受光，下沿、左沿背光；轮廓不描边，边上的明暗全是高度落差打出来的；再乘场景的光照图（塌顶下面亮、屋顶下面暗），
  越靠上越亮一点（离水面近）。
- 木头：顺着木纹的细纹 + 拉长的噪声（一块板一个深浅），板缝凹下去、最暗；角和边磨掉的地方浅一点、暖一点；
  泡久了偏青（色相从灰褐往青绿那边滑），朝上的面落淤泥、长苔，下半截附着物多。
- 铁：冷灰蓝，锈一片片长（边上、铆钉 / 螺栓周围多），锈水从钉子往下拖成一道道。
- 色阶：每种材质 9 档 × 3 个冷暖（偏青 / 中 / 偏暖），最暗那档都沉到场景的靛蓝里（不是黑）；
  档位交界用小色团抖开（不是棋盘格），再去掉孤立的单像素。
alpha 只有 0 / 255，随机全部固定 seed。
"""
from __future__ import annotations

import math

import numpy as np

import underwater_art as ua
from oscarkit.palette import oklab_to_srgb

N = 9                       # 每种材质的档数
PLAIN = False               # 调试：只看形体（不画木纹、苔、泥、锈）
LIGHT = ua.LIGHT


def _lab(L, C, h):
    r = math.radians(h)
    return np.array([L, C * math.cos(r), C * math.sin(r)])


def ramp(stops, n=N):
    """stops = [(L, C, h), …] 均匀摊在 0..1 上，在 OKLab 里线性插值（中间自然变灰，不绕色相环）。返回 n×3 uint8。"""
    labs = [_lab(*s) for s in stops]
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(labs) - 1)
        k = min(int(t), len(labs) - 2)
        f = t - k
        out.append(labs[k] * (1 - f) + labs[k + 1] * f)
    return oklab_to_srgb(np.array(out))


DARK = (.085, .016, 268)    # 所有材质的最暗档：场景的靛蓝暗部（OKLab L 0.1 以下在 sRGB 里就是黑了，不往下用）

# 材质 id
WOOD, IRON, PAINT, PAPER, ROPE, GLASS, CLOTH, BRASS = 1, 2, 3, 4, 5, 6, 7, 8

# 每种材质 3 个冷暖：0 偏青（长了藻膜） / 1 中 / 2 偏暖（磨掉表面、或者干净一点的地方）
PAL = {
    WOOD: [ramp([DARK, (.155, .015, 222), (.245, .018, 198), (.35, .02, 188)]),
           ramp([DARK, (.155, .014, 40), (.245, .018, 66), (.355, .02, 82)]),
           ramp([DARK, (.16, .017, 36), (.255, .026, 56), (.375, .029, 70)])],
    IRON: [ramp([DARK, (.155, .017, 230), (.25, .021, 214), (.37, .022, 205)]),
           ramp([DARK, (.155, .016, 250), (.25, .019, 238), (.38, .02, 228)]),
           ramp([DARK, (.155, .014, 262), (.255, .015, 248), (.39, .016, 236)])],
    PAINT: [ramp([DARK, (.155, .021, 214), (.245, .027, 200), (.355, .03, 192)]),
            ramp([DARK, (.155, .019, 226), (.245, .024, 212), (.36, .026, 204)]),
            ramp([DARK, (.155, .017, 238), (.25, .02, 226), (.37, .022, 218)])],
    PAPER: [ramp([DARK, (.18, .01, 230), (.3, .012, 205), (.43, .012, 190)]),
            ramp([DARK, (.18, .009, 250), (.3, .011, 90), (.44, .014, 92)]),
            ramp([DARK, (.18, .01, 70), (.31, .016, 82), (.46, .02, 86)])],
    ROPE: [ramp([DARK, (.155, .014, 210), (.25, .02, 190), (.36, .022, 180)]),
           ramp([DARK, (.155, .012, 60), (.25, .018, 76), (.37, .02, 86)]),
           ramp([DARK, (.155, .014, 55), (.26, .021, 70), (.385, .024, 80)])],
    GLASS: [ramp([DARK, (.16, .025, 210), (.27, .036, 196), (.46, .04, 188)])] * 3,
    CLOTH: [ramp([DARK, (.15, .014, 245), (.23, .018, 236), (.34, .02, 228)])] * 3,
    BRASS: [ramp([DARK, (.17, .02, 120), (.27, .03, 100), (.4, .04, 92)])] * 3,
}
RUST = [ramp([(.09, .018, 300), (.15, .024, 34), (.225, .032, 44), (.32, .036, 56)]),
        ramp([(.09, .018, 300), (.16, .027, 38), (.245, .038, 50), (.345, .042, 60)]),
        ramp([(.09, .018, 300), (.15, .02, 28), (.215, .026, 38), (.3, .03, 50)])]
MOSS = ramp([(.09, .018, 250), (.15, .03, 212), (.24, .038, 192), (.34, .042, 176)])
SILT = ramp([(.15, .008, 250), (.22, .009, 236), (.3, .01, 220), (.37, .011, 206)])
DARKC = [tuple(int(v) for v in c) for c in ramp([(.075, .014, 268), (.1, .016, 262)], 2)]   # 接地阴影
BARN = ramp([(.1, .012, 260), (.2, .012, 236), (.32, .012, 214), (.44, .012, 200)])


def hsh(*a):
    """确定性的 0..1 哈希"""
    s = 0.0
    for i, v in enumerate(a):
        s += float(v) * (127.1 + 211.7 * i)
    return (math.sin(s) * 43758.5453) % 1.0


def vn(u, v, seed=0.0):
    """任意浮点坐标上的值噪声（光滑插值），0..1。u、v 是同形的数组。"""
    u = np.asarray(u, float)
    v = np.asarray(v, float)
    iu, iv = np.floor(u), np.floor(v)
    fu, fv = u - iu, v - iv
    fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)

    def h(i, j):
        return (np.sin(i * 127.1 + j * 311.7 + seed * 74.7) * 43758.5453) % 1.0
    a, b = h(iu, iv), h(iu + 1, iv)
    c, d = h(iu, iv + 1), h(iu + 1, iv + 1)
    return (a + (b - a) * fu) * (1 - fv) + (c + (d - c) * fu) * fv


def shift(a, dy, dx, fill=False):
    o = np.full_like(a, fill)
    h, w = a.shape
    if abs(dy) >= h or abs(dx) >= w:
        return o
    o[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = a[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return o


def erode(m, k=1):
    for _ in range(k):
        m = m & shift(m, 1, 0) & shift(m, -1, 0) & shift(m, 0, 1) & shift(m, 0, -1)
    return m


def dist_in(m, kmax=4):
    """mask 里每格到边的距离（4 邻，最多 kmax）。"""
    d = np.zeros(m.shape)
    cur = m.copy()
    for k in range(kmax):
        d += cur
        cur = erode(cur)
    return d


def despeckle(lev, M):
    p = np.pad(lev, 1, mode="edge")
    nb = np.stack([p[1 + dy:p.shape[0] - 1 + dy, 1 + dx:p.shape[1] - 1 + dx]
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
    same = (nb == lev[None]).sum(0)
    med = np.median(nb, axis=0).round().astype(int)
    out = lev.copy()
    fix = M & (same == 0)
    out[fix] = med[fix]
    return out


class Prop:
    """一件东西的画布。ox, oy = 画布左上角在房间里的坐标（打光用房间坐标：越高越亮、场景光照图）。"""

    def __init__(self, w, h, ox=0, oy=0, seed=0):
        self.w, self.h, self.ox, self.oy = w, h, ox, oy
        self.seed = seed
        self.hf = np.zeros((h, w))
        self.mat = np.zeros((h, w), int)
        self.gu = np.zeros((h, w))            # 沿木纹
        self.gv = np.zeros((h, w))            # 横过木纹
        self.part = np.zeros((h, w), int)     # 零件号（每块板自己深浅；零件交界处磨损）
        self.dark = np.zeros((h, w))          # 额外压暗（里面、缝、阴影）
        self.lift = np.zeros((h, w))          # 额外提亮（反光、受光的新茬）
        self.rust = np.zeros((h, w))          # 锈的倾向
        self.moss = np.zeros((h, w))          # 苔的倾向
        self.tint = np.full((h, w), np.nan)   # 指定冷暖（0 青 / 1 中 / 2 暖；nan = 按噪声）
        self.nomoss = np.zeros((h, w), bool)  # 不长苔、不落泥（玻璃、纸、灯）
        self.fixc = np.zeros((h, w, 4), np.uint8)   # 手点的像素（最后盖上去）
        self.yy, self.xx = np.mgrid[0:h, 0:w].astype(float)
        self._pn = 0

    # ---------------------------------------------------------------- 搭
    def new_part(self):
        self._pn += 1
        return self._pn

    def fill(self, m, mat, hgt=0.0, grain="h", round_=0.0, part=None, gu0=0.0, gv0=0.0, dark=0.0):
        """m 这块：材质 mat、高度 hgt（round_ > 0：边往下圆一点）；grain = 'h' 横纹 / 'v' 竖纹 / None 不改木纹坐标。"""
        m = m & np.ones_like(m, bool)
        if not m.any():
            return
        p = self.new_part() if part is None else part
        hh = np.full(m.shape, float(hgt))
        if round_:
            d = dist_in(m, 3)
            hh = hh - round_ * (1 - np.minimum(d, 3) / 3) ** 1.5
        self.hf[m] = hh[m]
        self.mat[m] = mat
        self.part[m] = p
        if grain == "h":
            self.gu[m] = self.xx[m] + gu0
            self.gv[m] = self.yy[m] + gv0
        elif grain == "v":
            self.gu[m] = self.yy[m] + gu0
            self.gv[m] = self.xx[m] + gv0
        self.dark[m] = dark
        return p

    def rect(self, x0, y0, x1, y1):
        """[x0, x1) × [y0, y1) 本地坐标的 mask"""
        return (self.xx >= x0) & (self.xx < x1) & (self.yy >= y0) & (self.yy < y1)

    def R(self, x0, y0, x1, y1):
        """同 rect，但用房间坐标"""
        return self.rect(x0 - self.ox, y0 - self.oy, x1 - self.ox, y1 - self.oy)

    def put(self, x, y, c, room=True):
        """手点一格（房间坐标）"""
        if room:
            x, y = x - self.ox, y - self.oy
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.fixc[y, x] = tuple(int(v) for v in c[:3]) + (255,)

    def drip(self, x, y, ln, amt=0.9, room=True):
        """锈水 / 水渍：从 (x, y) 往下拖一道（断断续续，越往下越淡）。"""
        if room:
            x, y = x - self.ox, y - self.oy
        x, y = int(round(x)), int(round(y))
        for k in range(int(ln)):
            Y = y + k
            if 0 <= Y < self.h and 0 <= x < self.w and self.mat[Y, x]:
                if hsh(x, Y, self.seed) < 0.85:
                    self.rust[Y, x] = max(self.rust[Y, x], amt * (1 - k / (ln + 2)) ** 0.7)

    # ---------------------------------------------------------------- 画
    def render(self, env=None, ambient=0.2, gain=0.62, top_y=110.0, bot_y=226.0, grain_amt=1.0, wear=0.6,
               moss_amt=1.0, silt_amt=1.0, tint_bias=0.0, n=N, axes=((1.0, 0.0), (0.0, 1.0)), world=None):
        """env：场景光照（同画布大小，0..1；None = 0.5）。返回 (h, w, 4) uint8。
        转着画的东西（倒下的柜子）：在不转的局部坐标里搭好，axes = 局部 +x、+y 在房间里的方向（单位向量），
        world = (每格的房间 x, 房间 y)，光的方向、离水面远近、苔 / 泥长在哪一面都按房间算。"""
        if PLAIN:
            grain_amt, moss_amt, silt_amt, wear = 0.0, 0.0, 0.0, 0.0
        M = self.mat > 0
        out = np.zeros((self.h, self.w, 4), np.uint8)
        if not M.any():
            out[self.fixc[..., 3] > 0] = self.fixc[self.fixc[..., 3] > 0]
            return out
        X, Y = self.xx, self.yy
        RX, RY = (X + self.ox, Y + self.oy) if world is None else world
        sd = self.seed
        # 外面的高度：贴着轮廓往下落一截（轮廓上的倒角 = 受光 / 背光，不描边）
        hf = np.where(M, self.hf, -1e9)
        for _ in range(2):
            nb = np.maximum.reduce([shift(hf, 1, 0, -1e9), shift(hf, -1, 0, -1e9), shift(hf, 0, 1, -1e9),
                                    shift(hf, 0, -1, -1e9)])
            hf = np.where(M | (hf > -1e8), hf, nb - 1.6)
        hf = np.where(hf < -1e8, 0, hf)
        wood = self.mat == WOOD
        gu, gv = self.gu, self.gv
        pt = np.array([hsh(p, sd, 3.3) for p in range(self._pn + 2)])
        poff = pt[self.part] * 7.0
        # 光：每个面一档平的底色；明暗全由和上下左右邻居的高度差给（凸起的上沿 / 右沿受光，下沿 / 左沿背光；
        # 凹进去的反过来：上沿在框的影子里、下沿受光）。外面当作比轮廓低 1.6 —— 所以轮廓的上沿亮、下沿暗，不描边。
        hpad = np.where(M, self.hf, hf)
        dU = np.clip(hpad - shift(hpad, 1, 0, -9.0), -1, 1)         # 比上面那格高：上沿
        dD = np.clip(hpad - shift(hpad, -1, 0, -9.0), -1, 1)        # 比下面那格高：下沿
        dR = np.clip(hpad - shift(hpad, 0, -1, -9.0), -1, 1)
        dL = np.clip(hpad - shift(hpad, 0, 1, -9.0), -1, 1)
        stp = 1.0 / (n - 1)
        Ld = np.array([0.57, -0.82])                                 # 房间里光来的方向（右上，从水面）
        ax, ay = np.array(axes[0], float), np.array(axes[1], float)

        def k(nw):
            c = float(np.dot(nw, Ld))
            return 2.3 * c if c > 0 else 1.7 * c
        kU, kD, kR, kL = k(-ay), k(ay), k(ax), k(-ax)
        edge = stp * (kU * dU + kD * dD + kR * dR + kL * dL)
        lam = np.clip(0.5 + edge * 3.0, 0, 1)                       # 「受光程度」：给苔 / 泥 / 磨损判断用
        nrm = np.zeros(hf.shape + (3,))
        nrm[..., 1] = -np.clip(dU, 0, 1)                              # 只用来判断「朝上的面」
        E = 0.5 if env is None else env
        V = (ambient + gain * 0.5) * (0.62 + 0.5 * E) + edge * (0.75 + 0.5 * E)
        V = V + 0.1 * np.clip((bot_y - RY) / (bot_y - top_y), 0, 1.2)      # 离水面近一点就亮一点
        # 每个零件自己深一点浅一点（半档），木头顺纹很慢的一点起伏
        V = V + (pt[self.part] - 0.5) * 0.06 * (self.mat != GLASS)
        V = V + wood * grain_amt * 0.06 * (vn(gu / 18.0 + poff, gv / 6.0, sd + 3) - 0.5)
        metal = (self.mat == IRON) | (self.mat == PAINT) | (self.mat == BRASS)
        V = V + metal * 0.07 * (vn(RX / 5.0, RY / 18.0, sd + 16) - 0.5)        # 铁板上竖着往下的水渍（一道道，很淡）
        V = V - self.dark + self.lift
        # 磨损：轮廓 / 零件交界上，一段段浅一点、暖一点（木头）/ 亮一点（铁：磨出金属）
        rim = M & ~erode(M)
        prim = M & ((self.part != shift(self.part, 1, 0, -1)) | (self.part != shift(self.part, 0, 1, -1)))
        wn = vn(X / 2.2, Y / 2.2, sd + 5)
        worn = (rim | prim) & (wn > 1 - 0.45 * wear) & (lam > 0.3)
        V = V + worn * 0.06
        # 冷暖
        tn = 0.5 * vn(RX / 6.0, RY / 4.0, sd + 6) + 0.5 * vn(RX / 2.2, RY / 2.2, sd + 7) + tint_bias
        tn = tn + 0.18 * np.clip((RY - 200) / 26, 0, 1) + 0.25 * np.clip(self.moss, 0, 1)   # 下半截、长苔的地方：藻膜偏青
        tint = np.where(tn > 0.8, 0, np.where(tn < 0.26, 2, 1))
        tint = np.where(worn & wood, 2, tint)
        tint = np.where(np.isnan(self.tint), tint, np.nan_to_num(self.tint)).astype(int)
        # 档位：大面干净（交界才抖成小色团），去孤点
        step = 1.0 / (n - 1)
        cn = vn(X / 2.4, Y / 2.4, sd + 8) - 0.5
        lev = np.floor(V / step + 0.5 + 0.22 * cn).astype(int)
        # 木纹：顺纹一道道一格宽的暗线，被慢噪声推得弯弯的，断断续续；暗线下面那格在受光的面上亮一档（纹的另一侧边）
        if grain_amt:
            wob = vn(gu / 14.0 + poff, gv / 6.0, sd + 1) * 2.4
            per = 4.4
            ph = (gv + wob + poff * 1.3) / per
            gl = wood & ((ph - np.floor(ph)) < 1.0 / per) & (vn(gu / 8.0 + poff, gv / 2.0, sd + 2) > 0.42)
            gl &= erode(M) & (self.part == shift(self.part, 0, 1, -1))
            lev = lev - gl
            lip = shift(gl, 1, 0) & wood & ~gl & (lam > 0.55)
            lev = lev + (lip & (vn(gu / 3.0, gv, sd + 15) > 0.6))
        # 铁：小坑点（暗一格）
        pits = metal & erode(M) & (vn(X / 1.1, Y / 1.1, sd + 4) > 0.82)
        lev = lev - pits
        lev = np.clip(lev, 0, n - 1)
        lev = despeckle(lev, M)
        for mat, pals in PAL.items():
            for t in range(3):
                mm = M & (self.mat == mat) & (tint == t)
                if mm.any():
                    out[mm, :3] = pals[t][lev[mm]]
        out[M, 3] = 255
        upw = [(dU, -ay, (1, 0)), (dD, ay, (-1, 0)), (dR, ax, (0, -1)), (dL, -ax, (0, 1))]
        up = np.zeros_like(M)
        for (dd, nw, (sy, sx)) in upw:
            if np.dot(nw, (0.0, -1.0)) > 0.55:                        # 这条边的外法线朝上（房间里），外面没东西挡
                up |= M & (dd > 0.5) & ~shift(M, sy, sx)      # 上面没东西挡着的朝上的面
        # 锈（铁、旧漆）：大片 + 小斑 + 钉子下面拖的锈水
        rc = self.rust + 0.55 * (vn(RX / 4.5, RY / 4.0, sd + 9) - 0.5) + 0.35 * (vn(RX / 1.6, RY / 1.6, sd + 10) - 0.5)
        rc = rc + 0.18 * rim + 0.15 * np.clip((RY - 180) / 40, 0, 1)
        rmask = metal & (rc > 0.52) & (not PLAIN)
        rmask |= M & ~metal & (self.rust > 0.5)                          # 木头上的锈水（钉子下面）
        rt = np.where(rc > 0.8, 0, np.where(vn(RX / 5, RY / 5, sd + 11) > 0.5, 1, 2))
        rl = np.clip(lev - (rc > 0.8), 1, n - 1)
        for t in range(3):
            mm = rmask & (rt == t)
            out[mm, :3] = RUST[t][rl[mm]]
        # 苔 / 附着物：朝上的面、下半截、零件交界的缝里
        if moss_amt:
            mc = self.moss + 0.45 * up + 0.12 * np.clip((RY - 195) / 30, 0, 1)
            mc = mc + 0.42 * (vn(RX / 3.2, RY / 2.6, sd + 12) - 0.5) + 0.2 * (vn(RX / 1.2, RY / 1.2, sd + 13) - 0.5)
            mm = M & ~self.nomoss & (mc > 1 - 0.32 * moss_amt)
            ml = np.clip(lev + (up & (lam > 0.5)), 1, n - 2)
            out[mm, :3] = MOSS[ml[mm]]
        # 淤泥：朝上、受光的面上一段一段（不连成线）
        if silt_amt:
            sn = vn(RX / 2.6, RY / 8.0, sd + 14)
            sm = up & ~self.nomoss & (sn > 1 - 0.38 * silt_amt) & (lam > 0.45)
            sl = np.clip((lev[sm] - 1) // 2, 0, len(SILT) - 1)
            out[sm, :3] = SILT[sl]
        fx = self.fixc[..., 3] > 0
        out[fx] = self.fixc[fx]
        return out


def barnacles(out, pts, M=None):
    """几颗藤壶（一格亮 + 左下一格暗）。pts 是本地坐标。"""
    h, w = out.shape[:2]
    for (x, y) in pts:
        if 0 <= x < w and 1 <= y < h and out[y, x, 3] and (M is None or M[y, x]):
            out[y, x, :3] = BARN[3]
            if x > 0 and y + 1 < h and out[y + 1, x - 1, 3]:
                out[y + 1, x - 1, :3] = BARN[0]
            if x + 1 < w and out[y, x + 1, 3]:
                out[y, x + 1, :3] = BARN[2]


def contact(out, x0, x1, y, k=2, base=None):
    """接地的阴影：物件脚下那一行（和下一行）压成最暗的两档（本地坐标，画进物件自己的图里）。"""
    c0, c1 = ua.bramp(2, .04, .07, 266, 260)
    for x in range(max(0, x0), min(out.shape[1], x1)):
        if 0 <= y < out.shape[0]:
            out[y, x] = tuple(c0) + (255,)
        if k > 1 and 0 <= y + 1 < out.shape[0] and (x - x0) % 3 != 1:
            out[y + 1, x] = tuple(c1) + (255,)


def rotate_into(img, ox, oy, w, h, to_local):
    """把局部坐标里画好的图（不转的）转进 w×h 的画布（左上角在房间 ox, oy）：to_local(X, Y) → 局部像素坐标（最近邻）。"""
    out = np.zeros((h, w, 4), np.uint8)
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    lx, ly = to_local(xx + ox + 0.5, yy + oy + 0.5)
    ix, iy = np.floor(lx).astype(int), np.floor(ly).astype(int)
    ok = (ix >= 0) & (ix < img.shape[1]) & (iy >= 0) & (iy < img.shape[0])
    out[ok] = img[iy[ok], ix[ok]]
    return out
