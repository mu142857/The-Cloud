"""城市视差（晨打听大象、找古老记载的那座城）。以后改城市图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/city_art.py [--preview 目录]

输出 art/city/*.png（1 倍）和兜帽人的走路帧 art/city/hood_*.png，同时重写 scenes/city_test.tscn
（每层只画有东西的那几行、天缝的斜光、各层人群的参数都从这里算出来，场景里的数不用手改）。
做法照 tools/forest_art.py / cloud_art.py（函数是拷过来的，没有 import 它们）。

第三版（2026-10-28，作者定的方向）：「鸽子笼」。
- 整片一模一样的灰色高层住宅：一格一格的大窗、阳台、楼板线、楼梯间的竖条窗，重复、整齐、冷漠。
  所有楼都从街面冲出画面顶，看不到顶，天只在最远那排楼缝里露几条。越远越小、越淡（同一个设计缩小），
  一层层叠出纵深。没有招牌、晾衣、花盆、烟囱、杂物、小店；亮着的窗只有极少几扇，很暗。
- 颜色以灰为主：亮的（霾、楼板受光的边）带一点点暖（OKLCh h≈85），暗的带一点点冷（h≈255），色度都在 0.01 上下。
  每栋楼只在冷暖上有一点点偏差，不是五颜六色。
- 明暗：近处的楼墙暗，远处往霾里褪；霾在楼腰那一带（y≈130~170）最亮，楼缝深处是一道道发亮的远楼；
  往下沉进街面的暗：晨身后那条（地面往上约 45 像素）又暗又干净。最亮的永远是晨。
- 人：每一层都有一条走道（远处、中远、中景是横贯的高架步道，近处是街面，再近是前景），
  上面一群戴兜帽的人匆匆左右走过，互相不理：远处小、近处大，都是剪影（Godot 里 scripts/city_crowd.gd）。
- 大象：中景有一栋楼的端头是一整面没开窗的山墙，上面一幅褪成浅灰的大象壁画，第二眼才看得出。
图层（scroll_scale 见 SCROLL）：
- sky    霾的色带（屏幕固定），只在 ridge 的楼缝里露出来
- ridge  最远：极小的鸽子笼楼，窗是一个个点
- far    远处：同一种楼，缩小；y≈134 一条高架步道
- midfar 中远：同一种楼；y≈156 一条高架步道
- mid    中景：同一种楼（大窗、阳台、楼梯间），一栋端头是大象山墙；y≈178 一条高架步道
- main   能走的街：路沿一条受光边就是地面（y=228，平的），一排一模一样、不亮的路灯
- front  镜头最近的近黑剪影：头顶两段高架梁、三根细灯杆、底边一组很矮的闸机（都碰不到晨）
第四版（同一天，作者：「不够繁忙、不够焦虑，加一些前景，改兜帽人」）：
- 人更多更快，三两成群、交错超车，每条道上有一小股人挤成一团涌过去；兜帽人换成五种赶路的人
  （高瘦甩手 / 背包 / 提公文包 / 矮胖插兜 / 抱箱子低头），前倾、步子大、手臂摆；前景的大个子只露上半身，一闪而过。
- 机械节奏：中景楼前横过一条高架轨道，隔几秒一列车厢窗冷白的列车呼啸穿过（远处还有一条小的）；
  楼边上一颗颗冷青色信号灯按同一个节拍闪，从左到右错开成一道扫过去的脉冲。
- 前景的两根 22 像素宽方柱会挡住晨，去掉了。
第五版（同一天，作者：「缺细节、质感和氛围感」）：
- 鸽子群（scripts/city_pigeons.gd）：远、中远、中景各一群淡灰白的鸽子在楼间慢慢盘旋，像流体一样拉长挤扁，
  转向时一只接一只翻过来；中景还有一群歇在高架轨道梁上，列车开过来时被惊起，绕一圈再落回梁上另一处。
- 下雨（scripts/city_rain.gd）：远、中、近、前景四层斜雨，整像素硬边；街面上溅小水花。
  （第十二版换成非像素的 GPUParticles2D 细雨，见文末。）
- 湿街面（scripts/city_wet.gdshader）：把地面线以上的亮东西（窗、霾缝、日光灯、信号灯、列车车窗、人影、晨）
  上下翻转照进街面，断成竖条、随雨抖动，几处积水更清楚；晨自己的倒影压得很淡。
- 墙面：窗下、楼板下拖出长短不一的水渍和几道淡锈痕；一排排重复的空调外机；楼梯间竖条窗里的冷白日光灯
  （scripts/city_flicker.gd，个别接触不良，隔几秒快速闪两下）。block_tower 记下楼梯间窗洞的位置给它用。
第六版（同一天）：
- 湿街面倒影不读整屏的细碎东西：每一列看上面那一截城市的平均亮度，只有成块成列的光（霾缝、日光灯、列车车窗）
  在街面上拉成安静的竖光带，边缘被雨打得微微断开；几处积水是镜子。前景底边的栏杆、立柱底座去掉，只留一组很矮的闸机。
- 鸽子群改成 boids（对齐、聚合、分离 + 领头点），整群转向时一大片一起翻亮、翻暗；被列车惊起的那群跟着镜头绕圈，
  落回当前画面里的梁上。墙面水渍压暗两档、空调外机亮一档。
- 居民（作者：「城市居民都要特别高大，主角很矮小、夹在人群中间才有感觉」，「进一步细化每个人身上的比例和东西」）：
  街面一层约 100 像素（晨 52）、前面那层约 128；成年人长比例（头约 1/8、胯在一半略上），
  高瘦 / 宽肩 / 驼背 / 矮壮 / 撑伞几种体型，各有标志物（看手腕、手提袋、公文包、拐杖、纸箱、背包、黑伞），
  外套的下摆、开衩、腰带、口袋盖、袖口，兜帽的帽檐和暗脸里的下巴，裤腿和鞋，肩上一道湿的受光边；8 帧走路。
  people_chart() 画「人物表」（每种人站姿 + 8 帧，旁边站着晨比身高）。
第七版（同一天）：
- 鸽子改成小色块（2~4 像素的实心身体 + 一两格翅膀，远处是一两个点），群读出来是一片点云；翻面按群里沿飞行方向的位置
  排先后，像一道波 0.3 秒扫过整群（scripts/city_pigeons.gd）。
- 人有体积：光从上方偏右来，外套和兜帽每一行右边亮一档、左边暗一档，胯以下整体暗一档，腿、远侧的胳膊腿更暗；
  腰带是暗横条加亮扣，公文包、纸箱、背包有受光面和背光面，伞面亮暗两半。街面那层染色提亮到受光边 L≈0.5，
  外套大面积 0.2~0.33。people_chart(game_bg=…) 再画一版「游戏里真实亮度」的人物表。
第八版（同一天，作者：「城市还是不够有压迫感……白色的鸟很奇怪，去掉；前景可以有经过的人或者车；中景，也就是主角这一层，
可以有更密集的人群。焦虑不是城市想表达的，冷漠才是」）：
- 冷漠 = 整齐、匀速、重复、互不相干（焦虑是乱：快慢不一、超车、成团涌过去、闪烁、急促）。
- 鸽子全去掉（scripts/city_pigeons.gd 留着不用）。
- 人群（scripts/city_crowd.gd）：每条道两股人流，一股往右、一股往左；同一股里所有人一样快、一样的步子节奏、间距几乎相等，
  像流水线，没人超车、停下、回头；不再有成团涌过去的、不再三两成群；速度都按个子的 0.6 倍 / 秒，慢、稳。
  衣服只在冷灰里有一点点差别。晨那一层（Main）人多到把晨包住（大部分在她身后），另一条很稀的（MainNear）画在她前面，
  偶尔有人从她身前直直穿过去。原来前景那两个 128 像素的大个子去掉（hood_128 不再生成）。
- 前景经过的大黑影（scripts/city_passers.gd）：隔七到十二秒，一个很大的路人（art/city/passer.png，470 像素高，只露肩膀到膝盖，
  头被画面上沿切掉）走过去，或者一辆暗色的车（art/city/car.png，冷灰车窗反光、一盏冷白车头灯，不用暖色）开过去；
  几乎全暗，压过晨的时间不到一秒。
- 晨那条街的人群分三排（STREET_ROWS）：远排小一点、浅、往雾里退，中排是晨这个深度，近排最大最暗、在晨前面；
  排和排用明度分开（scripts/city_crowd_ramp.gdshader 把灰度档映射到这一排的 lo..hi），不透明，同排间距比人宽，
  一个一个的人读得出来、前后读得出来（原来是一堵同色调的灰墙）。前景大路人的腿加粗（PASSER_LEG）。
- 日光灯不闪（个别坏的十几二十几秒才换一次亮灭）；信号灯全城一起慢慢亮灭（5 秒一拍）；列车慢一点、隔得久一点，日常的。
第十一版（2026-10-29，作者给城市打 1 分：「一直说在改却没啥变化」「没那个感觉」「背后的人像走在空中」）：
- 明暗结构照森林：上面是夜，楼往上没进去（finish 的 top），楼腰到人头那一带是一层被街灯照亮的冷雨雾（最亮，L≈0.46），
  雾按行算、档边棋盘格抖开（finish 的 smooth）；近楼暗、远楼褪进雾里更淡更冷，楼缝里一层层看得见。少数冷白亮窗（不是暖灯）。
- 头顶的高架梁、前景细灯杆（穿过晨的那道黑线）去掉。
- 光源和焦点：一排一样的冷白路灯（LAMPS，隔 240），每盏一道光锥（cones()，节点叫 Shafts，晨走进去会被照亮），
  光锥里的雨丝亮起来（city_rain.gd 的 lights / only_lit），灯下人行道、路沿一摊光，湿街面里一道倒影。
- 居民重画：长大衣 / 斗篷盖到小腿，只露一截小腿和鞋，步子小，上身随步子抬 1 像素；整体比雾暗，逆光：
  兜帽顶、肩上冷色轮廓光（255）、背上和肩上一道湿反光（200，city_crowd_ramp.gdshader 映射）；速度按步幅算（WALK），脚不打滑，帧不加快。
- 每排人都踩在看得见的地上：三条高架步道是实的（湿路面 + 外沿亮边 + 暗桥身 + 底下影子，越远越窄越高，少褪雾 air），
  街面一面平的楼底座墙（PLINTH_TOP..SW_BACK）+ 湿人行道（比鞋亮）+ 接触影子，路沿立面 CURB_FACE 行，下面才是镜子。
- 湿街面倒影压暗（refl_near 0.4 / refl_far 0.18），竖光条只取真正亮的灯。
第十二版（2026-10-30，作者：「这个下雨能不能不用像素雨，用 Until Someone Passes 的那种非像素的绵绵细雨，GPUParticle 2D 的」）：
- 雨（scripts/city_rain.gd + city_rain.gdshader）改成 GPUParticles2D：每滴一根很细、柔边、半透明的斜线（贴图开场现生成，
  线性过滤；canvas_items 拉伸下按窗口分辨率画，芯约 1 个屏幕像素），出生淡入、到点淡出，打到地面那一行裁掉。
  中景（Mid）、街面（Main）、灯下（LampRain，只在光锥里、密、亮）、前景（Front）四层，越近越长越快越亮。
  远景（Far）那层雨被前面的楼整个挡住，去掉了。整齐匀速，不阵雨；最亮的灯下雨丝也比晨的白发暗。
- 街面上的小涟漪（scripts/city_ripples.gd，节点 Ripples）：压扁的细环撑开淡掉，画在镜子后面、不进倒影。
- 特效 lite 时雨和涟漪的粒子数 × 0.4。
除了天，每层宽 960、左右无缝。所有随机都固定 seed。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.measure import srgb_to_oklab  # noqa: E402
from oscarkit.palette import from_lch, oklab_to_srgb, to_lab  # noqa: E402

W, H = 960, 270
GROUND = 228
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "city"
CHEN = ROOT / "art" / "characters" / "chen" / "chen.png"
SCENE = ROOT / "scenes" / "city_test.tscn"

# 镜头往下挪多少（第十版）：路沿在屏幕上 y = GROUND - CAM_DY = 188，下面 80 行都是湿街面的镜子（原来 40 行）。
# 世界坐标不变（晨、人群、楼都还在原来的 y），只是镜头竖直位置 135 → 175；最上面那 40 行（本来就冲出画面的楼顶）切掉。
CAM_DY = 40
HB = H + CAM_DY                 # 屏幕下沿在世界里的 y：主层、前景层要画到这里
COLD_L = lambda L, C=0.02, h=220: lch(L, C, h)     # 冷光：冷白偏青，不用暖色

SCROLL = {"sky": 0.0, "ridge": 0.06, "far": 0.18, "midfar": 0.38, "mid": 0.62, "main": 1.0, "front": 1.4}

H_WARM = 85     # 亮的一点点暖
H_COOL = 255    # 暗的一点点冷


# ---------------------------------------------------------------- 颜色

def lch(L, C, h):
    return from_lch(L, C, h)


def mix(c, d, t):
    a, b = to_lab(c), to_lab(d)
    return tuple(int(v) for v in oklab_to_srgb((a + (b - a) * t)[None])[0])


def _ab(C, h):
    return np.array([C * np.cos(np.radians(h)), C * np.sin(np.radians(h))])


def lab_col(L, ab):
    return tuple(int(v) for v in oklab_to_srgb(np.array([[L, ab[0], ab[1]]]))[0])


def mat(L, C=0.006, h=H_COOL, n=7, dL=0.042, mid=3):
    """一种灰的色阶（暗 -> 亮），第 mid 档是 (L, C, h)。亮一档往暖偏一点点、暗一档往冷偏一点点。"""
    base = _ab(C, h)
    out = []
    for i in range(n):
        k = i - mid
        ab = base + (abs(k) / 3) * (_ab(0.006, H_WARM) if k > 0 else _ab(0.006, H_COOL))
        out.append(lab_col(float(np.clip(L + k * dL, 0.03, 0.9)), ab))
    return out


# 霾：亮度只跟高度有关；颜色跟亮度走：暗的偏冷、亮的偏一点暖，中间几乎是纯灰
# 第十一版：上面是夜（楼顶没进去，看不到顶），楼腰到人头那一带是街灯照亮的雨雾（最亮，人群在它前面成剪影），
# 再往下沉进街面的暗（晨身后那条）。世界 y：屏幕最上面一行是 40。
HAZE_Y = [0, 40, 70, 90, 110, 125, 140, 155, 170, 185, 200, 218, 232, 270]
HAZE_L = [0.17, 0.165, 0.14, 0.2, 0.35, 0.46, 0.46, 0.39, 0.29, 0.2, 0.14, 0.11, 0.09, 0.08]
HAZE_STEP = 0.02
H_FOG = 212     # 雨雾：冷，偏一点青（色度很低，读出来是冷灰，不是蓝）
H_NIGHT = 250   # 夜：冷灰偏一点蓝紫


def haze_L(y):
    return np.interp(y, HAZE_Y, HAZE_L)


def haze_col(L):
    t = float(np.clip((L - 0.1) / 0.35, 0, 1))
    ab = _ab(0.01, H_NIGHT) * (1 - t) + _ab(0.017, H_FOG) * t
    return lab_col(L, ab)


SHADOW = lab_col(0.07, _ab(0.009, H_COOL))       # 街面最深的暗（偏冷的近黑）
LIT_DIM = lch(0.5, 0.018, 205)                   # 少数几扇亮窗：冷白（日光灯，不是暖灯；晨 L≈0.80）


# ---------------------------------------------------------------- 图层

class Layer:
    """一层图：RGBA + 每个像素的「参照高度」yref（褪色按它查霾色，一栋楼一层楼一个值）+ 自发光（亮窗）。"""

    def __init__(self, w=W, h=H):
        self.a = np.zeros((h, w, 4), np.uint8)
        self.yr = np.zeros((h, w), np.int16)
        self.em = np.zeros((h, w), bool)
        self.air = np.ones((h, w), np.float32)     # 往雾里褪多少的倍数（步道这种要读得出来的结构 < 1，少褪一点）
        self.info = {}

    def paste(self, p, x, y):
        h, w = p.a.shape[:2]
        H_, W_ = self.a.shape[:2]
        for px in (x - W_, x, x + W_):
            x0, y0 = max(0, px), max(0, y)
            x1, y1 = min(W_, px + w), min(H_, y + h)
            if x0 >= x1 or y0 >= y1:
                continue
            sl = (slice(y0 - y, y1 - y), slice(x0 - px, x1 - px))
            m = p.a[sl][..., 3] > 0
            self.a[y0:y1, x0:x1][m] = p.a[sl][m]
            self.yr[y0:y1, x0:x1][m] = p.yr[sl][m]
            self.em[y0:y1, x0:x1][m] = p.em[sl][m]
            self.air[y0:y1, x0:x1][m] = p.air[sl][m]

    def put(self, x, y, c, yref=None, em=False, air=1.0):
        x %= self.a.shape[1]
        if 0 <= y < self.a.shape[0]:
            self.a[y, x] = tuple(c) + (255,)
            self.yr[y, x] = y if yref is None else yref
            self.em[y, x] = em
            self.air[y, x] = air

    def rect(self, x0, y0, x1, y1, c, yref=None, em=False, air=1.0):
        for y in range(max(0, y0), min(self.a.shape[0], y1)):
            for x in range(x0, x1):
                self.put(x, y, c, yref, em, air)

    def save(self, name):
        Image.fromarray(self.a).save(OUT / f"{name}.png")


class Piece(Layer):
    """一栋楼的局部画布：坐标原点 = 楼身左上角，四周留 pad。"""

    def __init__(self, w, h, pad=2):
        super().__init__(w + 2 * pad, h)
        self.pad, self.bw, self.bh = pad, w, h

    def R(self, x0, y0, x1, y1, c, em=False):
        ax0, ax1 = max(0, x0 + self.pad), min(self.a.shape[1], x1 + self.pad)
        ay0, ay1 = max(0, y0), min(self.a.shape[0], y1)
        if ax0 < ax1 and ay0 < ay1:
            self.a[ay0:ay1, ax0:ax1] = tuple(c) + (255,)
            self.em[ay0:ay1, ax0:ax1] = em

    def P(self, x, y, c, em=False):
        self.R(x, y, x + 1, y + 1, c, em)


# ---------------------------------------------------------------- 档位抖动（照 cloud_art：大片硬边，只在档边留窄窄一条）

def narrow_levels(lv):
    lv = np.asarray(lv, float)
    h, w = lv.shape
    gy, gx = np.gradient(lv)
    g = np.hypot(gx, gy) + 1e-6
    lo = np.floor(lv + 1e-9)
    dn = (lo + 1 - lv) / g
    Y, X = np.mgrid[0:h, 0:w]
    p50 = (X + Y) % 2 == 0
    p25 = (X + 2 * (Y % 2)) % 4 == 0
    up = ((dn < 1.0) & p50) | ((dn >= 1.0) & (dn < 2.0) & p25)
    return (lo + up).astype(int)


# ---------------------------------------------------------------- 天

def sky():
    """天：只在最远那排楼的缝里露出窄窄几条。上面是压下来的灰霾，往下到楼腰那一带最亮，再往下沉进街面的暗；
    几道扁扁的烟带横着，楼缝里看得到一截一截的明暗。"""
    lay = Layer(480, H)
    Y, X = np.mgrid[0:H, 0:480].astype(float)
    L = haze_L(Y)
    smog = np.zeros_like(L)
    for (cy, cx, hw, th, k) in ((96, 300, 230, 2.4, 0.04), (113, 250, 190, 1.6, 0.04), (124, 420, 240, 2.6, 0.03),
                                (60, 140, 200, 3.0, 0.03), (40, 380, 260, 3.5, 0.025), (78, 90, 170, 2.5, 0.03)):
        u = (X - cx) / hw
        half = th * np.sqrt(np.clip(1 - u ** 2, 0, 1))
        smog += np.where(np.abs(Y - cy - 3 * u ** 2) < half, k, 0)
    lv = narrow_levels((L - smog) / HAZE_STEP)
    out = np.zeros((H, 480, 4), np.uint8)
    for v in np.unique(lv):
        out[lv == v] = tuple(haze_col(min(0.64, v * HAZE_STEP))) + (255,)
    lay.a = out
    return lay


# ---------------------------------------------------------------- 鸽子笼

# 一栋楼从左到右的竖向单元：C 楼梯间（一条竖的窄窗）、w 窗、b 阳台、B 空墙（山墙，不开窗、没有楼板线）
PATTERN = "CwwbwwbwwC"


def block_tower(rng, dims, L, C, h, top, pattern=PATTERN, lit=(), mural=None):
    """一栋鸽子笼：每层一模一样。dims = dict(bay, core, ww, wh, fh, detail)。返回 (Piece, 宽)。
    lit = [(第几层, 第几个单元), ...]：极少几扇亮着的窗（很暗）。mural = (x, y)：大象画在 B 墙上的位置（楼身坐标）。"""
    bay, core, ww, wh, fh, det = (dims[k] for k in ("bay", "core", "ww", "wh", "fh", "detail"))
    xs, x = [], 0
    for u in pattern:
        uw = core if u == "C" else bay
        xs.append((u, x, uw))
        x += uw
    w = x
    hgt = H - top
    p = Piece(w, hgt)
    wl = mat(L, C, h)
    glass = mat(L - 0.1, 0.006, H_COOL, dL=0.025)
    p.R(0, 0, w, hgt, wl[3])
    # 楼层：从下往上数，底层（落地那层）高一点；最上面的楼层冲出画面
    g_h = fh + fh // 2
    floors = []
    y1 = hgt - g_h
    while y1 > -fh:
        floors.append((y1 - fh, y1))
        y1 -= fh
    yref_rows = np.full(hgt, top + hgt - g_h // 2, np.int16)
    for (a, b) in floors:
        yref_rows[max(0, a):max(0, b)] = top + (a + b) // 2
    # 空调外机挂在哪几格：整栋楼固定那几格（一排排重复），个别楼层没挂
    ac_units = {i for i, (u, ux, uw) in enumerate(xs) if u in "wb" and (i % 3 == 1 or u == "b")}
    p.info["cores"] = []
    for k, (y0, y1) in enumerate(floors):
        for i, (u, ux, uw) in enumerate(xs):
            if u == "B":
                # 山墙：大板拼起来的一整面墙，只有板缝（横的每层一道、竖的每格一道），没有窗
                p.R(ux, y0, ux + uw, y0 + 1, wl[2])
                if i + 1 < len(xs) and xs[i + 1][0] == "B":
                    p.R(ux + uw - 1, y0, ux + uw, y1, wl[2])
                continue
            # 楼板：上沿一行受光、下面一行暗（楼板的影子）
            if det >= 2:
                p.R(ux, y0, ux + uw, y0 + 1, wl[5])
                p.R(ux, y0 + 1, ux + uw, y0 + 2, wl[4] if det >= 3 else wl[3])
                p.R(ux, y0 + 2, ux + uw, y0 + 3, wl[1])
            else:
                p.R(ux, y0, ux + uw, y0 + 1, wl[4])
            on = (k, i) in lit
            if u == "C":
                sw = 1 if det <= 2 else 2
                sx = ux + (uw - sw) // 2
                p.R(sx, y0 + 3 + (det >= 3), sx + sw, y1 - 2, glass[1])
                p.info["cores"].append((sx, y0 + 3 + (det >= 3), sw, (y1 - 2) - (y0 + 3 + (det >= 3))))
            elif u == "w":
                wx = ux + (uw - ww) // 2
                wy = y0 + (3 if det >= 2 else 2)
                p.R(wx, wy, wx + ww, wy + wh, LIT_DIM if on else glass[2], em=on)
                if not on:
                    p.R(wx, wy, wx + ww, wy + 1, glass[0])
                if det >= 2 and ww >= 4:
                    p.R(wx + ww // 2, wy, wx + ww // 2 + 1, wy + wh, wl[2])        # 竖棂
                if det >= 3:
                    p.R(wx, wy + wh // 3, wx + ww, wy + wh // 3 + 1, wl[2])         # 横棂（上面一扇小气窗）
                    p.R(wx, wy + wh, wx + ww, wy + wh + 1, wl[4])                   # 窗台
            elif u == "b":
                # 阳台：整格凹进去（暗），里面一扇门；前面一道实心栏板（亮一档，上沿最亮）
                bx0, bx1 = ux + 1, ux + uw - 1
                if det >= 2:
                    p.R(bx0, y0 + 3, bx1, y1, wl[1])
                    dw = max(2, ww - 2)
                    dx = bx0 + (bx1 - bx0 - dw) // 2
                    p.R(dx, y0 + 4, dx + dw, y1, LIT_DIM if on else glass[1], em=on)
                    ph = max(2, (y1 - y0) * 2 // 5)
                    p.R(bx0 - 1, y1 - ph, bx1 + 1, y1, wl[4])
                    p.R(bx0 - 1, y1 - ph, bx1 + 1, y1 - ph + 1, wl[5])
                    p.R(bx0 - 1, y1 - ph + 1, bx0, y1, wl[5])
                else:
                    p.R(bx0, y0 + 2, bx1, y1 - 1, glass[2])
    # 空调外机：窗下 / 阳台栏板上挂一个小盒子（亮一档的盒子、竖的散热格、底下一道影子）
    if det >= 2:
        aw, ah = (5, 3) if det >= 3 else (3, 2)
        for k, (y0, y1) in enumerate(floors):
            for i, (u, ux, uw) in enumerate(xs):
                if i not in ac_units or rng.random() < 0.18:
                    continue
                ax = ux + uw - aw - 1 if u == "w" else ux + 1
                ay = y1 - ah - (1 if u == "w" else 1)
                p.R(ax, ay, ax + aw, ay + ah, wl[5])
                p.R(ax, ay, ax + aw, ay + 1, wl[6])
                if det >= 3:
                    for gx in range(ax + 1, ax + aw - 1, 2):
                        p.R(gx, ay + 1, gx + 1, ay + ah, wl[3])
                p.R(ax + aw - 1, ay, ax + aw, ay + ah, wl[3])
                p.R(ax, ay + ah, ax + aw, ay + ah + 1, wl[1])
    # 水渍、锈痕：从窗台、空调、楼板往下拖的竖道，长短不一，把墙和楼板压暗两档（不压到玻璃上）
    if det >= 2:
        darker = {tuple(wl[j]): wl[max(0, j - 2)] for j in range(1, len(wl))}
        rust = lab_col(L - 0.05, _ab(0.016, 55))
        n_st = int(w * hgt / (90 if det >= 3 else 160))
        for _ in range(n_st):
            sx = int(rng.integers(1, w - 1))
            sy = int(rng.integers(0, hgt - g_h))
            ln = int(rng.integers(3, fh * (3 if rng.random() < 0.25 else 1) + 3))
            rusty = rng.random() < 0.18
            for yy in range(sy, min(hgt - g_h, sy + ln)):
                if rng.random() < 0.12 and yy > sy + 2:
                    break
                ax, ay = sx + p.pad, yy
                c = tuple(int(v) for v in p.a[ay, ax, :3])
                if c in darker and not p.em[ay, ax]:
                    nc = darker[c]
                    if rusty:
                        nc = mix(nc, rust, 0.5)
                    p.a[ay, ax, :3] = nc
    # 底层：一排暗的门洞
    gy0 = hgt - g_h
    p.R(0, gy0, w, gy0 + 1, wl[5])
    for (u, ux, uw) in xs:
        if u in "wb" and det >= 2:
            p.R(ux + 2, gy0 + 3, ux + uw - 2, hgt, glass[0])
    # 左边一条受光、右边一条背光
    p.R(0, 0, 1, hgt, wl[4])
    p.R(w - 1, 0, w, hgt, wl[2])
    if mural:
        _mural(p, wl, *mural)
    p.yr[:] = yref_rows[:, None]
    return p, w


# 大象（侧面，朝左）：# 身子，e 耳朵，t 象牙
ELEPHANT = [
    "......######.......................",
    "....##########....##########.......",
    "...############.##############.....",
    "..#######eeeee##################...",
    "..######eeeeeee#################...",
    ".#######eeeeeee##################..",
    ".#######eeeeeee##################..",
    ".########eeeee###################..",
    ".##########ee####################..",
    ".###.############################.#",
    ".###tt##########################..#",
    ".###..#########################....",
    ".###...########################....",
    "..##...####.####.......####.####...",
    "..##...####.####.......####.####...",
    "..##...####.####.......####.####...",
    "#.##...####.####.......####.####...",
    ".##....####.####.......####.####...",
]


def _mural(p, wl, x0, y0):
    """褪成浅灰的大象壁画：比山墙只亮一点点，耳朵再淡一档，下面一道很淡的旧框线。第二眼才看得出。"""
    paint = mix(wl[3], wl[5], 0.42)
    ear = mix(wl[3], wl[5], 0.22)
    tusk = mix(wl[3], wl[6], 0.6)
    for yy, row in enumerate(ELEPHANT):
        for xx, ch in enumerate(row):
            if ch == "#":
                p.P(x0 + xx, y0 + yy, paint)
            elif ch == "e":
                p.P(x0 + xx, y0 + yy, ear)
            elif ch == "t":
                p.P(x0 + xx, y0 + yy, tusk)
    # 掉了几块（露出底下的墙）、一道很淡的框
    for (ox, oy, rw, rh) in ((x0 + 24, y0 + 1, 5, 3), (x0 + 12, y0 + 14, 4, 4)):
        p.R(ox, oy, ox + rw, oy + rh, wl[3])
    frame = mix(wl[3], wl[4], 0.5)
    p.R(x0 - 4, y0 + len(ELEPHANT) + 3, x0 + len(ELEPHANT[0]) + 4, y0 + len(ELEPHANT) + 4, frame)


# ---------------------------------------------------------------- 褪色（按 yref）

def finish(lay, t_air, dark_y0, dark_y1, dark_max, glow_air=0.0, em_air=0.3, dark_steps=6, air_steps=8,
           top=(110, 40, 0.0), smooth=False):
    """把每个像素往「它那层楼高度的霾色」里推 t_air（楼腰那一带霾最亮，再多推 glow_air），
    再往街面的暗里推：yref 在 dark_y0 以上不推，到 dark_y1 推 dark_max，分 dark_steps 档。亮窗只推一点霾、不压暗。
    top = (y0, y1, 最多)：往上没进夜里 —— yref 在 y0 以下不推，到 y1 再多推「最多」（那里的霾就是夜色，楼顶化掉，看不到顶）。
    smooth = True（第十一版）：霾按每一行算（不按一层楼一个值），档和档之间用很窄的一条棋盘格抖过去（照 cloud_art 的 narrow_levels）
    —— 雾是一层慢慢变浓的雾，不是一条硬边的横带。"""
    a = lay.a
    m = a[..., 3] > 0
    if smooth:
        yr = np.broadcast_to(np.arange(a.shape[0], dtype=float)[:, None], a.shape[:2])
        hl = narrow_levels(haze_L(yr) / HAZE_STEP)
    else:
        yr = lay.yr.astype(float)
        hl = np.round(haze_L(yr) / HAZE_STEP).astype(int)
    glow = np.exp(-((yr - 134) / 28) ** 2)
    tt = np.clip((top[0] - yr) / (top[0] - top[1]), 0, 1) ** 1.3 * top[2]
    taf = np.clip((t_air + glow_air * glow + tt) * lay.air, 0, 1) * air_steps
    tdf = np.clip((yr - dark_y0) / (dark_y1 - dark_y0), 0, 1) * dark_steps
    if smooth:
        ta, td = narrow_levels(taf), narrow_levels(tdf)
    else:
        ta, td = np.round(taf).astype(int), np.round(tdf).astype(int)
    em = lay.em
    ta = np.where(em, np.round(ta * em_air).astype(int), ta)
    td = np.where(em, 0, td)
    rgb = a[..., :3]
    key = (rgb[..., 0].astype(np.int64) << 40) | (rgb[..., 1].astype(np.int64) << 32) | \
          (rgb[..., 2].astype(np.int64) << 24) | (hl.astype(np.int64) << 12) | (ta.astype(np.int64) << 6) | td
    ks, inv = np.unique(key[m], return_inverse=True)
    cols = np.stack([(ks >> 40) & 255, (ks >> 32) & 255, (ks >> 24) & 255], 1).astype(np.uint8)
    lab = srgb_to_oklab(cols)
    hz = np.array([to_lab(haze_col(min(0.64, v * HAZE_STEP))) for v in ((ks >> 12) & 63)])
    tav = (((ks >> 6) & 63) / air_steps)[:, None]
    tdv = ((ks & 63) / dark_steps * dark_max)[:, None]
    lab = lab * (1 - tav) + hz * tav
    lab = lab * (1 - tdv) + to_lab(SHADOW)[None] * tdv
    new = oklab_to_srgb(lab)
    out = a.copy()
    out[m, :3] = new[inv]
    lay.a = out
    return lay


# ---------------------------------------------------------------- 各层

# 每层：同一种楼缩小。n = 一圈 960 里几栋（楼宽 + 楼缝 = 960 / n），x0 = 第一栋从哪开始（让各层的楼缝错开）
TIERS = {
    "ridge": dict(bay=3, core=2, ww=1, wh=1, fh=4, detail=1, n=30, x0=5, L=0.24, top=-6),
    "far": dict(bay=5, core=4, ww=3, wh=3, fh=6, detail=1, n=16, x0=21, L=0.25, top=-10),
    "midfar": dict(bay=8, core=6, ww=5, wh=5, fh=10, detail=2, n=10, x0=40, L=0.25, top=-20),
    "mid": dict(bay=13, core=9, ww=9, wh=9, fh=16, detail=3, n=5, x0=18, L=0.2, top=-30),
}
DECKS = {"far": 134, "midfar": 156, "mid": 178}      # 横贯的高架步道：桥面最上面一行（人的脚踩在它上面一行）


def tower_row(name, seed, lit_n=0, mural_at=None):
    t = TIERS[name]
    rng = np.random.default_rng(seed)
    lay = Layer()
    period = W // t["n"]
    for i in range(t["n"]):
        # 每栋只在冷暖上有一点点偏差，亮度差一点点
        h = H_COOL if rng.random() < 0.6 else H_WARM
        C = float(rng.uniform(0.003, 0.009))
        L = t["L"] + float(rng.uniform(-0.015, 0.015))
        pat = PATTERN
        mural = None
        if mural_at is not None and i == mural_at:
            pat = "BBBwwbwwC"            # 端头是一整面山墙
            mural = (4, 104 - t["top"])
        lit = []
        fh = t["fh"]
        base = H - (fh + fh // 2)                # 楼层从下往上数：第 k 层的上沿在 base - (k+1)*fh
        k_lo, k_hi = (base - 145) // fh, (base - 50) // fh
        k_lo, k_hi = (base - 150) // fh, (base - 30) // fh
        for _ in range(int(rng.integers(max(0, lit_n - 1), lit_n + 2))):
            k = int(rng.integers(k_lo, k_hi))    # 只在楼腰以上（y 30~150），不进晨身后那条；高处那几扇说明楼还在往上
            lit.append((k, int(rng.choice([1, 2, 4, 5, 7, 8]))))
        p, w = block_tower(rng, t, L, C, h, t["top"], pattern=pat, lit=lit, mural=mural)
        x = t["x0"] + i * period
        lay.paste(p, x - p.pad, t["top"])
        lay.info.setdefault("towers", []).append((x, w))
        for (cx, cy, cw, ch) in p.info.get("cores", []):
            lay.info.setdefault("cores", []).append((x + cx, t["top"] + cy, cw, ch))
    return lay


TRACKS = {"far": 90, "mid": 62}     # 高架轨道梁的上沿（列车的轮子踩在它上面一行）；中景那条从楼前面横过去


def track(lay, y, L, th=4):
    """横贯整层的高架轨道梁：上沿一道受光的钢轨，下面一条深的梁腹，每隔一段一道加劲肋。"""
    m = mat(L, 0.005, H_COOL)
    for x in range(W):
        lay.put(x, y, m[5], yref=y)
        for k in range(1, th):
            lay.put(x, y + k, m[1] if k == th - 1 else m[2], yref=y)
        if x % 16 == 0:
            lay.rect(x, y + 1, x + 1, y + th, m[3], yref=y)


def signals(lay, name, seed, per=2):
    """冷色信号灯的位置：每栋楼右边（背光的那条边）上几颗，只在楼腰以上。返回 [(x, y), ...]。"""
    rng = np.random.default_rng(seed)
    out = []
    for (x, w) in lay.info["towers"]:
        for _ in range(per):
            out.append((x + w - 2, int(rng.integers(20, 140))))
    return out


def deck(lay, y, L, post=6, surf=3, fascia=3, air=0.45):
    """横贯整层的高架步道（第十一版，作者：「背后的人像走在空中」）：要读得出是一条实的路面，人踩在上面。
    从上往下：栏杆（在人背后，扶手 + 一根根立柱）、路面的里沿（暗的一道缝）、路面 surf 行（湿的，反着雾光，比人的鞋亮；
    人的脚踩在 y-1，脚下接触影子落在 y）、路面外沿一道最亮的湿边、桥身侧面 fascia 行（暗）、底下一行最暗的影子。
    步道只往雾里褪 air 倍（楼褪得多）：雾再浓，路面和它下面那道暗的桥身也读得出来，人不会像飘在窗格前面。
    越远的步道路面越窄、越高（far 2 行、midfar 3 行、mid 4 行；街面的人行道 9 行），透视对得上。"""
    m = mat(L, 0.005, H_COOL)
    wet = [lab_col(L + 0.1, _ab(0.012, H_FOG)), lab_col(L + 0.07, _ab(0.01, H_FOG))]
    y_back = y - surf                        # 路面里沿那一行（栏杆脚）
    rail_h = max(3, surf + 2)
    for x in range(W):
        lay.put(x, y_back - rail_h, m[4], yref=y, air=air)                       # 扶手
        if x % post == 0:
            lay.rect(x, y_back - rail_h + 1, x + 1, y_back, m[3], yref=y, air=air)
        lay.put(x, y_back, m[1], yref=y, air=air)                                # 里沿的缝
        for yy in range(y_back + 1, y + 1):                             # 湿路面：往外沿越亮一点，隔几格一道接缝
            c = wet[0] if yy >= y - 1 else wet[1]
            if (x + (yy - y_back) // 2) % (post * 4) == 0:
                c = m[3]
            lay.put(x, yy, c, yref=y, air=air)
        lay.put(x, y + 1, m[6], yref=y, air=air)                                 # 外沿：一道湿的亮边
        for yy in range(y + 2, y + 2 + fascia):
            lay.put(x, yy, m[2] if yy == y + 2 else m[1], yref=y, air=air)        # 桥身侧面
        lay.put(x, y + 2 + fascia, m[0], yref=y, air=air)                        # 底下的影子


def ridge():
    lay = tower_row("ridge", 31)
    ys = np.arange(H)[:, None]
    lay.yr = np.broadcast_to(ys // 6 * 6, lay.yr.shape).astype(np.int16).copy()
    return finish(lay, 0.8, 172, 215, 0.85, glow_air=0.1, em_air=0.6, top=(125, 60, 0.6))


def far():
    lay = tower_row("far", 41, lit_n=2)
    deck(lay, DECKS["far"], 0.24, post=4, surf=2, fascia=2)
    track(lay, TRACKS["far"], 0.24, th=3)
    lay.info["signals"] = signals(lay, "far", 5, per=1)
    deck_lamps(lay, DECKS["far"], FAR_LAMPS["far"], 1)
    return finish(lay, 0.62, 168, 212, 0.85, glow_air=0.35, em_air=0.4, top=(125, 45, 0.6), smooth=True, air_steps=12)


def midfar():
    lay = tower_row("midfar", 52, lit_n=3)
    deck(lay, DECKS["midfar"], 0.24, post=5, surf=3, fascia=2)
    lay.info["signals"] = signals(lay, "midfar", 6, per=2)
    deck_lamps(lay, DECKS["midfar"], FAR_LAMPS["midfar"], 2)
    return finish(lay, 0.42, 165, 206, 0.85, glow_air=0.5, em_air=0.25, top=(125, 40, 0.75), smooth=True, air_steps=12)


def mid():
    lay = tower_row("mid", 63, lit_n=4, mural_at=2)
    deck(lay, DECKS["mid"], 0.2, post=6, surf=4, fascia=4)
    track(lay, TRACKS["mid"], 0.2, th=7)
    lay.info["signals"] = signals(lay, "mid", 7, per=2)
    deck_lamps(lay, DECKS["mid"], FAR_LAMPS["mid"], 3)
    bus_stop(lay, DECKS["mid"], BUS_X)
    return finish(lay, 0.08, 172, 208, 0.9, glow_air=0.55, em_air=0.0, top=(125, 30, 0.9), smooth=True, air_steps=12)


LAMPS = [120, 360, 600, 840]   # 主层一排一模一样的路灯（隔 240，画面里总有两盏）：全亮，冷白，雨里一道光锥（Godot 里叠加）
LIT_LAMPS = LAMPS
LAMP_LENS_Y = GROUND - 112     # 灯罩下沿那一行（世界 y）：比居民的头（≈128）高，光从头顶打下来；湿街面的竖光条正好读这一行
LAMP_ARM = 10                  # 灯臂伸出去多长：灯头的中心在 lx + LAMP_ARM
CURB_FACE = 4                  # 路沿立面几行（228 受光边下面），再往下才是马路（镜子）
PLINTH_TOP = 196               # 街边楼底座那面平墙的上沿（挑檐）
SW_BACK = 218                  # 人行道的里沿（墙脚）：人行道是 SW_BACK..GROUND 这一条，后排的人踩在上面，不是走在空中
VEND_X = 712                   # 人行道里沿靠墙一台自动售货机（冷白的屏、一列青色按钮），在两盏路灯中间，离晨开场站的地方远
VEND_W, VEND_H = 20, 40
FAR_LAMPS = {"far": [150, 610], "midfar": [380, 860], "mid": [250]}   # 远处步道上几盏小路灯（冷白的一两个像素）
BUS_X = 700                    # 中景步道上一个公交站牌灯箱（冷白，里面只有几块没有意思的灰块，没有字、没有广告）


def deck_lamps(lay, y, xs, size):
    """步道上的小路灯：一根细杆，顶上一两个像素的冷白灯（自发光，不被霾吃掉太多）。"""
    post = mat(0.2, 0.005, H_COOL)[2]
    hgt = {1: 7, 2: 11, 3: 18}[size]
    for x in xs:
        lay.rect(x, y - 4 - hgt, x + 1, y - 4, post, yref=y)
        lay.rect(x, y - 4 - hgt, x + size + 1, y - 3 - hgt, post, yref=y)
        lay.rect(x + 1, y - 3 - hgt, x + 1 + size, y - 3 - hgt + max(1, size - 1), COLD_L(0.6), yref=y, em=True)


def bus_stop(lay, y, x):
    """中景步道上的公交站牌：一块竖着的灯箱（冷白，里面几块灰块，没有字），一根杆，一片薄顶棚。"""
    dark = mat(0.16, 0.005, H_COOL)
    lay.rect(x - 2, y - 26, x + 18, y - 24, dark[3], yref=y)          # 顶棚
    lay.rect(x + 16, y - 24, x + 17, y - 4, dark[2], yref=y)          # 杆
    lay.rect(x, y - 22, x + 10, y - 5, dark[1], yref=y)               # 灯箱的框
    lay.rect(x + 1, y - 21, x + 9, y - 6, COLD_L(0.56), yref=y, em=True)
    for (bx, by, bw, bh) in ((2, 3, 5, 2), (2, 7, 3, 4), (6, 8, 2, 1), (2, 13, 6, 1)):
        lay.rect(x + bx, y - 22 + by, x + bx + bw, y - 22 + by + bh, COLD_L(0.44, 0.012), yref=y, em=True)


def main_layer():
    """能走的街：路沿一条受光边就是地面（y=228），人行道一块块石板，下面是很暗的路面。
    街上只有一排间距一样、都不亮的路灯。"""
    lay = Layer(h=HB)
    # 第十一版：人行道（218..227）一块块湿石板，228 路沿受光边，下面 CURB_FACE 行路沿立面，再往下是马路（湿街面的镜子盖住）
    curb = lab_col(0.33, _ab(0.01, H_FOG))
    face_top = lab_col(0.17, _ab(0.008, H_COOL))
    face = lab_col(0.075, _ab(0.008, H_COOL))
    road = lab_col(0.07, _ab(0.008, H_COOL))
    sw_wall, sw_dark = lab_col(0.26, _ab(0.01, H_FOG)), lab_col(0.09, _ab(0.008, H_COOL))
    # 人行道是湿的：贴着墙那几行斜着反到楼腰的雾光，最亮；往前（往路沿）暗一点。比人的鞋亮，脚和脚下的影子读得出来
    sw = [lab_col(L, _ab(0.012, H_FOG)) for L in (0.215, 0.19, 0.165)]
    sheen = lab_col(0.27, _ab(0.014, H_FOG))
    sw_joint = lab_col(0.13, _ab(0.008, H_COOL))
    # 街面这一层的墙脚（第十一版）：楼的底座是一整面没开窗的混凝土墙（PLINTH_TOP..SW_BACK），顶上一道挑檐，
    # 一块块墙板之间一道竖缝 —— 后排人的小腿和脚衬在这面平的暗墙上，不是衬在楼的窗格上；人行道从墙脚开始
    wall = [lab_col(L, _ab(0.008, H_FOG)) for L in (0.11, 0.13, 0.155)]
    for x in range(W):
        lay.put(x, PLINTH_TOP, lab_col(0.22, _ab(0.01, H_FOG)))         # 挑檐上沿（湿的）
        lay.put(x, PLINTH_TOP + 1, lab_col(0.14, _ab(0.008, H_COOL)))
        lay.put(x, PLINTH_TOP + 2, lab_col(0.06, _ab(0.008, H_COOL)))   # 挑檐下的影子
        for y in range(PLINTH_TOP + 3, SW_BACK):
            k = 2 if y < PLINTH_TOP + 8 else (1 if y < SW_BACK - 4 else 0)   # 上面被雾照亮一点，往墙脚暗
            c = wall[k]
            if x % 40 in (0, 1):
                c = wall[0] if x % 40 == 0 else wall[2]                       # 墙板的竖缝（一道暗一道亮）
            lay.put(x, y, c)
    for x in range(W):
        lay.put(x, SW_BACK, sw_wall)
        lay.put(x, SW_BACK + 1, sw_dark)
        for y in range(SW_BACK + 2, GROUND):
            k = (y - SW_BACK - 2) * 3 // (GROUND - SW_BACK - 2)
            xx = x + (y - SW_BACK) // 3            # 缝往前斜
            c = sw[k]
            if xx % 24 == 0:
                c = sw_joint
            elif (y - SW_BACK) % 4 == 1 and (xx % 24) in (3, 4, 5, 6, 11, 12):
                c = sheen                          # 石板上一点湿的反光（远处的雾）
            lay.put(x, y, c)
        lay.put(x, GROUND, curb)
        lay.put(x, GROUND + 1, face_top)
        for y in range(GROUND + 2, GROUND + CURB_FACE + 1):
            lay.put(x, y, face)
        for y in range(GROUND + CURB_FACE + 1, HB):
            lay.put(x, y, road)
    # 路灯：一根 2 像素的杆（右边一道受光），顶上一条横臂，灯头一个扁盒子，下沿一条冷白的灯（自发光）
    dark = mat(0.12, 0.006, H_COOL, dL=0.03)
    pool = [lab_col(L, _ab(0.014, H_FOG)) for L in (0.25, 0.31, 0.37)]
    for lx in LAMPS:
        # 灯下那一段人行道、路沿被照亮：三档硬边的扁椭圆（越往前越宽，跟光锥的落点对上），石板缝还在
        hx = lx + LAMP_ARM
        for y in range(SW_BACK + 2, GROUND + 1):
            for x in range(hx - 40, hx + 41):
                r = np.hypot((x - hx) / (22 + (y - SW_BACK) * 1.4), (y - 225) / 7.0)
                k = 2 if r < 0.45 else (1 if r < 0.75 else (0 if r < 1.0 else -1))
                if k < 0:
                    continue
                cur = tuple(int(v) for v in lay.a[y, x % W, :3])
                if cur == tuple(sw_joint):
                    k = max(0, k - 2)
                    lay.put(x, y, pool[k] if k > 0 else sw[2])
                elif y == GROUND:
                    lay.put(x, y, lab_col(0.33 + 0.07 * (k + 1), _ab(0.014, H_FOG)))
                else:
                    lay.put(x, y, pool[k])
        top = LAMP_LENS_Y - 4
        lay.rect(lx - 1, SW_BACK - 1, lx + 3, SW_BACK + 3, dark[2])           # 底座
        lay.rect(lx - 1, SW_BACK - 1, lx + 3, SW_BACK, dark[4])
        lay.rect(lx, top, lx + 2, SW_BACK - 1, dark[2])
        lay.rect(lx + 1, top, lx + 2, SW_BACK - 1, dark[4])
        lay.rect(lx, top, lx + LAMP_ARM + 2, top + 1, dark[3])                # 横臂
        hx = lx + LAMP_ARM
        lay.rect(hx - 4, top + 1, hx + 5, top + 4, dark[2])                   # 灯头
        lay.rect(hx - 4, top + 1, hx + 5, top + 2, dark[5])
        lay.rect(hx - 3, top + 4, hx + 4, top + 5, COLD_L(0.66, 0.02, 205), em=True)   # 灯（= LAMP_LENS_Y）
        lay.rect(hx - 2, top + 5, hx + 3, top + 6, COLD_L(0.5, 0.02, 205), em=True)
    # 自动售货机：立在路沿上，正面一块冷白的屏（一排排货架是暗一点的横条），右边一列青色按钮，下面取货口；
    # 机身近黑，顶上一道受光边；它照亮脚下那一段路沿
    vx, vt = VEND_X, SW_BACK + 1 - VEND_H
    body_c = mat(0.13, 0.006, H_COOL, dL=0.03)
    lay.rect(vx, vt, vx + VEND_W, SW_BACK + 2, body_c[2])
    lay.rect(vx, vt, vx + 2, SW_BACK + 2, body_c[1])
    lay.rect(vx, vt, vx + VEND_W, vt + 1, body_c[5])
    lay.rect(vx + 3, vt + 4, vx + 14, vt + 24, COLD_L(0.6, 0.015))
    for k in range(5):
        lay.rect(vx + 3, vt + 7 + k * 4, vx + 14, vt + 8 + k * 4, COLD_L(0.47, 0.015))
    for k in range(5):
        lay.rect(vx + 16, vt + 6 + k * 3, vx + 18, vt + 7 + k * 3, COLD_L(0.5, 0.06, 200) if k % 2 == 0 else body_c[4])
    lay.rect(vx + 4, vt + 29, vx + 14, vt + 33, body_c[0])
    lay.rect(vx + 4, vt + 29, vx + 14, vt + 30, body_c[4])
    for y in range(SW_BACK + 2, GROUND):         # 售货机照亮它前面那一块人行道（越往前越淡）
        for x in range(vx - 6 - (y - SW_BACK), vx + VEND_W + 6 + (y - SW_BACK)):
            if (y - SW_BACK) < 6 or (x + y) % 2 == 0:
                lay.put(x, y, COLD_L(0.2 - 0.008 * (y - SW_BACK), 0.012))
    lay.yr[:] = np.arange(HB)[:, None]
    return lay


def front_layer():
    """镜头最近的一层（第十一版）：头顶的高架梁、细灯杆都去掉了 —— 梁把画面封了顶（楼就显不出高），
    细灯杆是一道黑线，走着走着正好穿过晨。只留底边一组很矮的闸机（只露个顶），不挡倒影。
    前景的「大东西」交给偶尔经过的大路人和车（scripts/city_passers.gd）。"""
    lay = Layer(h=HB)
    c = [lab_col(v, _ab(0.006, H_COOL)) for v in (0.035, 0.05, 0.07, 0.14)]
    for k in range(4):
        x = 470 + k * 18
        lay.rect(x, HB - 10, x + 8, HB, c[0])
        lay.rect(x, HB - 10, x + 8, HB - 9, c[3])
    lay.yr[:] = np.arange(HB)[:, None]
    return lay


# ---------------------------------------------------------------- 兜帽人（走路帧）

CROWD_SIZES = (11, 18, 30, 90, 100, 110)
HOOD_FRAMES = 8
# 城里的居民（第十一版，作者：「腿太细、走路像剪刀」）：长大衣 / 长斗篷一直盖到小腿，只露一小截小腿和鞋；
# 步子小、稳，身子随步子很轻地起伏（经过那两帧整个上身抬 1 像素）。都比晨（52 像素）高一倍左右，身子厚重。
# 每种体型比例不同、身上至少一样标志物；Godot 里再按人换一点配色。
#   s 身高比例   sh 肩半宽   hip 胯（0 头顶，1 脚底）   hunch 驼背（肩、头往前探多少）   lean 前倾   stride 大腿摆角（弧度）
#   hem 大衣下摆在哪（0.84~0.9：到小腿）  flare 下摆比肩宽多少（A 字）
#   item: case 公文包 / pack 背包 / umbrella 黑伞 / box 纸箱 / cane 拐杖 / phone 手机 / watch 看手腕
#   collar 立领   belt 腰带   scarf 围巾
HOOD_TYPES = [
    dict(name="高瘦·立领看表", s=1.0, sh=0.095, hip=0.53, hunch=0.0, lean=0.035, stride=0.27, item="watch", collar=True,
         belt=True, scarf=False, hem=0.86, flare=0.012),
    dict(name="极高·长斗篷·低头看手机", s=1.0, sh=0.088, hip=0.53, hunch=0.03, lean=0.03, stride=0.25, item="phone",
         collar=True, belt=False, scarf=True, hem=0.9, flare=0.03),
    dict(name="宽肩·公文包", s=0.97, sh=0.13, hip=0.53, hunch=0.0, lean=0.03, stride=0.27, item="case", collar=False,
         belt=True, scarf=False, hem=0.85, flare=0.0),
    dict(name="宽肩·公文包·围巾·长大衣", s=0.97, sh=0.13, hip=0.53, hunch=0.0, lean=0.03, stride=0.26, item="case",
         collar=False, belt=False, scarf=True, hem=0.88, flare=0.01),
    dict(name="重驼背·拐杖·斗篷", s=0.92, sh=0.11, hip=0.54, hunch=0.13, lean=0.05, stride=0.2, item="cane", collar=False,
         belt=False, scarf=True, hem=0.9, flare=0.035),
    dict(name="驼背·纸箱·低头", s=0.93, sh=0.11, hip=0.54, hunch=0.06, lean=0.04, stride=0.24, item="box", collar=False,
         belt=True, scarf=False, hem=0.85, flare=0.01),
    dict(name="矮壮·背包·缩肩", s=0.84, sh=0.13, hip=0.54, hunch=0.02, lean=0.04, stride=0.25, item="pack", collar=True,
         belt=False, scarf=False, hem=0.84, flare=0.005),
    dict(name="矮壮·缩肩·低头看手机", s=0.84, sh=0.13, hip=0.54, hunch=0.05, lean=0.04, stride=0.24, item="phone",
         collar=True, belt=True, scarf=False, hem=0.86, flare=0.01),
    dict(name="撑伞", s=0.88, sh=0.105, hip=0.53, hunch=0.0, lean=0.03, stride=0.26, item="umbrella", collar=False,
         belt=True, scarf=False, tilt=0.0, hem=0.86, flare=0.01),
    dict(name="撑伞·斜·长斗篷", s=0.88, sh=0.105, hip=0.53, hunch=0.0, lean=0.03, stride=0.25, item="umbrella", collar=True,
         belt=False, scarf=True, tilt=0.14, hem=0.9, flare=0.03),
]
# 灰度档（Godot 里 city_crowd_ramp.gdshader 映射到这一排的 lo..hi）：30..176 身子各档（30 脸最暗）、
# 200 湿的反光（大衣朝光那面几道断开的竖条）、240 手机屏、255 冷色轮廓光（兜帽顶、肩、背 —— 背后雾里的光）
G = dict(rim=255, sheen=200)


def _seg_mask(h, w, a, b, r):
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / max(1e-6, dx * dx + dy * dy), 0, 1)
    return np.hypot(xx - (ax + t * dx), yy - (ay + t * dy)) <= r


def _poly_mask(h, w, pts):
    from matplotlib.path import Path as MPath
    yy, xx = np.mgrid[0:h, 0:w]
    pts_c = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
    return MPath(pts).contains_points(pts_c).reshape(h, w)


def _ell_mask(h, w, c, rx, ry):
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    return ((xx - c[0]) / max(rx, 0.5)) ** 2 + ((yy - c[1]) / max(ry, 0.5)) ** 2 <= 1


def person_frame(hh, tp, ph, stand=False, f=0):
    """一个戴兜帽的居民（朝右走），帧高 hh。ph 是步子的相位（0..2π）；stand = 站姿（不迈步）。
    比例按身高 H = hh·s 算，坐标 u 横（身体中线 0，向前为正）、v 竖（0 头顶，1 脚底），都以 H 为单位。
    第十一版：长大衣盖到小腿，只露一小截小腿和鞋；大衣下摆前沿被前面那条腿的膝盖顶出去、后摆拖在后面；
    步子小，胳膊贴着身子小幅摆；经过的两帧（两腿并拢）上身抬 1 像素（很轻的起伏，腿不动）。"""
    fw = int(np.ceil(hh * 0.66)) + 6
    H_ = hh * tp["s"]
    big = hh >= 30
    img = np.zeros((hh, fw, 4), np.uint8)
    lay = {}          # 名字 -> mask
    order = []

    def add(name, m):
        if name not in lay:
            lay[name] = np.zeros((hh, fw), bool)
            order.append(name)
        lay[name] |= m

    s = 0.0 if stand else np.sin(ph)
    c_ = 1.0 if stand else np.cos(ph)
    lift = (max(1, int(round(hh / 110))) if (not stand and hh >= 60 and c_ * c_ > 0.6) else 0)
    bob = lift / H_
    cx = fw * 0.47
    hun = tp["hunch"]

    def P(u, v, legs=False):
        # 前倾 + 驼背：越往上越往前；驼背的人肩以上再往前探。上身（腿以外）随步子抬起 bob
        sh_v = 0.2
        du = tp["lean"] * (1 - v) + (hun * min(1.0, max(0.0, (0.5 - v) / (0.5 - sh_v))) if v < 0.5 else 0.0)
        return (cx + (u + du) * H_, hh - (1 - (v if legs else v - bob)) * H_)

    def R(r):
        return max(0.55, r * H_)

    def seg(a, b, r, legs=False):
        return _seg_mask(hh, fw, P(*a, legs=legs), P(*b, legs=legs), R(r))

    def poly(pts, legs=False):
        return _poly_mask(hh, fw, [P(*p, legs=legs) for p in pts])

    def ell(c, rx, ry):
        return _ell_mask(hh, fw, P(*c), R(rx), R(ry))

    sh = tp["sh"] * (0.92 if tp["item"] == "pack" else 1.0)
    hipv = tp["hip"]
    st = tp["stride"]
    hem = tp["hem"]
    # ---- 腿：大腿、小腿、鞋。大腿藏在大衣里，只有下摆下面那一截看得见
    FOOT = 0.968
    thigh = shin = (FOOT - hipv) * 0.5
    legs = {}
    for side in (1, -1):              # 1 = 近侧（画在前面），-1 = 远侧
        a1 = st * s * side
        bend = 0.0 if stand else 0.32 * max(0.0, -s * side) + 0.1 * max(0.0, c_ * side)
        kx, ky = np.sin(a1) * thigh, hipv + np.cos(a1) * thigh
        a2 = max(a1 - bend, -0.6)
        ax_, ay_ = kx + np.sin(a2) * shin, min(ky + np.cos(a2) * shin, FOOT)
        legs[side] = ((0.0, hipv), (kx, ky), (ax_, ay_))
        back = a1 < -0.1
        tilt = 0.012 if back else 0.0         # 后脚：脚跟抬起
        lw = 0.027 if tp["s"] > 0.86 else 0.03
        m = seg((0.0, hipv), (kx, ky), lw + 0.004, True) | seg((kx, ky), (ax_, ay_), lw, True)
        toe = 0.06
        if big:
            shoe = poly([(ax_ - 0.026, ay_ - 0.012 - tilt), (ax_ + 0.02, ay_ - 0.01), (ax_ + toe, 1.0 - 0.012 - tilt * 0.4),
                         (ax_ + toe, 1.0 - tilt * 0.3), (ax_ - 0.028, 1.0 - tilt)], legs=True)
        else:
            shoe = seg((ax_, ay_), (ax_ + toe * 0.8, 1.0), 0.018, True)
        add("leg" if side > 0 else "legfar", m)
        add("shoe" if side > 0 else "shoefar", shoe)

    def x_at(side, v):
        """这条腿在高度 v 的那一点的 u（大衣下摆跟着腿走）。"""
        h0, k, a = legs[side]
        for p, q in ((h0, k), (k, a)):
            if min(p[1], q[1]) <= v <= max(p[1], q[1]) and abs(q[1] - p[1]) > 1e-6:
                return p[0] + (q[0] - p[0]) * (v - p[1]) / (q[1] - p[1])
        return a[0]

    # ---- 大衣：肩 → 收一点腰 → A 字放到下摆；前沿被前腿顶出去，后摆拖在后面，背后一道开衩
    sway = 0.012 * s
    xf = max(x_at(1, hem), x_at(-1, hem))
    xb = min(x_at(1, hem), x_at(-1, hem))
    w_hem = sh * 0.92 + tp["flare"]
    fh_ = max(w_hem * 0.75, xf + 0.035)
    bh_ = min(-w_hem, xb - 0.035) - sway
    ww = sh * 0.86
    coat = [(0.0, 0.135), (sh * 0.55, 0.15), (sh, 0.188), (sh * 0.94, 0.3), (ww, hipv - 0.06),
            (fh_, hem - 0.012), (fh_ - 0.012, hem + 0.004), (0.0, hem + 0.01), (bh_ + 0.012, hem + 0.012), (bh_, hem),
            (-ww - hun * 0.25, hipv - 0.06), (-sh * 0.94 - hun * 0.5, 0.3), (-sh - hun * 0.3, 0.19), (-sh * 0.55, 0.15)]
    torso = poly(coat)
    if hun > 0:    # 驼背：背上鼓起来一块
        torso |= ell((-0.05, 0.25), 0.07, 0.085)
    add("body", torso)
    # ---- 兜帽：比头大一圈、厚；帽檐压住脸
    look_down = tp["item"] in ("box", "watch", "phone")
    hd = (0.025 + (0.025 if look_down else 0.0), 0.072 + (0.02 if look_down else 0.0))
    hood = ell(hd, 0.066, 0.072)
    hood |= poly([(hd[0] - 0.01, hd[1] - 0.07), (hd[0] - 0.075, hd[1] - 0.01), (hd[0] - 0.08, hd[1] + 0.07),
                  (-0.045, 0.155), (0.03, 0.155), (hd[0] + 0.052, hd[1] + 0.03)])
    add("body", hood)
    face = ell((hd[0] + 0.036, hd[1] + 0.026), 0.03, 0.04) & hood
    brim = ell((hd[0] + 0.032, hd[1] - 0.005), 0.044, 0.022) & hood & ~face
    opening = ell((hd[0] + 0.03, hd[1] + 0.02), 0.047, 0.056) & hood & ~face
    chin = ell((hd[0] + 0.04, hd[1] + 0.056), 0.017, 0.012) & face
    # ---- 胳膊：贴着身子，和对侧的腿反着小幅摆；拿东西的那只手不摆
    shj = (0.0 if tp["sh"] < 0.12 else -0.005, 0.195 if tp["sh"] < 0.12 else 0.185)
    if tp["item"] == "pack":
        shj = (0.0, 0.18)            # 缩着肩
    ua, fa = 0.16, 0.15
    ar = 0.03 if tp["sh"] < 0.12 else 0.033
    items = tp["item"]
    hands = []
    for side in (-1, 1):             # -1 = 近侧（画在身子前面），1 = 远侧
        a = -st * 0.55 * s * side if not stand else 0.04
        if items in ("case", "tote") and side == -1:
            a = 0.04 * s                                  # 提东西的手只轻轻晃
            el = (shj[0] + np.sin(a) * ua, shj[1] + np.cos(a) * ua)
            hn = (el[0] + np.sin(a) * fa, el[1] + np.cos(a) * fa)
        elif items == "cane" and side == -1:
            el = (shj[0] + 0.05, shj[1] + ua * 0.95)
            hn = (el[0] + 0.07, el[1] + fa * 0.6)
        elif items == "box":
            el = (shj[0] + 0.06, shj[1] + ua * 0.9)
            hn = (el[0] + 0.1, el[1] - 0.01)
        elif items == "umbrella" and side == -1:
            el = (shj[0] + 0.05, shj[1] + ua * 0.85)
            hn = (el[0] + 0.05, el[1] - 0.07)
        elif items == "phone" and side == -1:            # 近侧这只手端着手机，举在胸口下面，低头看
            el = (shj[0] + 0.03, shj[1] + ua * 0.88)
            hn = (el[0] + 0.085, el[1] - 0.04)
        elif items == "watch" and side == 1:            # 远侧那只手抬到胸前，看手腕
            el = (shj[0] + 0.04, shj[1] + ua * 0.9)
            hn = (el[0] + 0.1, el[1] - 0.03)
        elif items == "watch" and side == -1:            # 近侧这只手横过来，露出手腕
            el = (shj[0] + 0.03, shj[1] + ua * 0.92)
            hn = (el[0] + 0.12, el[1] - 0.045)
        else:
            el = (shj[0] + np.sin(a) * ua, shj[1] + np.cos(a) * ua)
            b2 = a + (0.2 if a > -0.05 else 0.08)          # 肘往前弯一点
            hn = (el[0] + np.sin(b2) * fa, el[1] + np.cos(b2) * fa)
        m = seg(shj, el, ar) | seg(el, hn, ar * 0.92)
        cuff = ell(((el[0] * 0.2 + hn[0] * 0.8), (el[1] * 0.2 + hn[1] * 0.8)), ar * 1.1, ar * 1.1) & m
        add("armfar" if side == 1 else "arm", m)
        if side == -1 and big:
            add("cuff", cuff)
        hands.append((side, hn))
    for side, hn in hands:
        add("handfar" if side == 1 else "hand", ell(hn, 0.017, 0.02))
    # ---- 东西
    hn_near = [h for s_, h in hands if s_ == -1][0]
    if items == "case":
        sw = 0.01 * s
        x0, y0 = hn_near[0] - 0.07 + sw, hn_near[1] + 0.02
        add("bag", poly([(x0, y0), (x0 + 0.15, y0), (x0 + 0.15, y0 + 0.1), (x0, y0 + 0.1)]))
        if big:
            add("edge", seg((x0, y0), (x0 + 0.15, y0), 0.004) | seg((x0 + 0.055, y0), (x0 + 0.055, y0 - 0.018), 0.005) |
                seg((x0 + 0.095, y0), (x0 + 0.095, y0 - 0.018), 0.005) | seg((x0 + 0.055, y0 - 0.018), (x0 + 0.095, y0 - 0.018), 0.005))
    elif items == "cane":
        tip = (hn_near[0] + 0.07 + 0.04 * s, 1.0)
        add("edge", seg(hn_near, tip, 0.008) | seg(hn_near, (hn_near[0] - 0.03, hn_near[1] - 0.01), 0.008))
    elif items == "box":
        bx, by = hn_near[0] - 0.02, hn_near[1] - 0.1
        add("box", poly([(bx, by), (bx + 0.17, by), (bx + 0.17, by + 0.13), (bx, by + 0.13)]))
        if big:   # 箱角、封口
            add("boxfold", seg((bx, by + 0.035), (bx + 0.17, by + 0.035), 0.004) | seg((bx + 0.085, by), (bx + 0.085, by + 0.035), 0.004))
            add("edge", seg((bx, by), (bx + 0.17, by), 0.004))
    elif items == "phone":
        px_, py_ = hn_near
        add("phone", poly([(px_ - 0.005, py_ - 0.04), (px_ + 0.03, py_ - 0.045), (px_ + 0.035, py_ + 0.005),
                           (px_, py_ + 0.01)]))
        add("screen", poly([(px_ + 0.004, py_ - 0.035), (px_ + 0.026, py_ - 0.038), (px_ + 0.03, py_ - 0.002),
                            (px_ + 0.006, py_ + 0.002)]) if big else ell((px_ + 0.015, py_ - 0.02), 0.012, 0.012))
    elif items == "pack":
        pk = [(-sh * 0.6, 0.18), (-sh - 0.07, 0.2), (-sh - 0.08, 0.43), (-sh * 0.7, 0.45)]
        add("bag", poly(pk))
        if big:
            add("strap", seg((-0.01, 0.17), (sh * 0.6, 0.215), 0.009) | seg((sh * 0.6, 0.215), (sh * 0.55, 0.37), 0.009))
    elif items == "umbrella":
        tilt = tp.get("tilt", 0.0)
        top = (hn_near[0] - 0.02 + tilt * 0.4, -0.14)
        add("edge", seg(hn_near, top, 0.007))
        if big:   # 弯柄（J 形）
            add("edge", seg(hn_near, (hn_near[0], hn_near[1] + 0.03), 0.007) |
                seg((hn_near[0], hn_near[1] + 0.03), (hn_near[0] - 0.025, hn_near[1] + 0.025), 0.007))
        span, hgt_ = 0.3, 0.13
        cxu, base = top[0], top[1] + hgt_
        pts = []
        for k in range(17):
            a = np.pi * (1 - k / 16)
            pts.append((cxu + span * np.cos(a), base - hgt_ * np.sin(a) + tilt * span * np.cos(a)))
        rim_pts = []
        for k in range(8, -1, -1):
            uu = cxu - span + 2 * span * k / 8
            rim_pts.append((uu, base + tilt * (uu - cxu) + (0.0 if k % 2 == 0 else -0.015)))
        canopy = poly(pts + rim_pts)
        add("canopy", canopy)
        if big:
            for k in (2, 4, 6):
                a = np.pi * (1 - k / 8)
                add("rib", seg(top, (cxu + span * np.cos(a), base + tilt * span * np.cos(a)), 0.003) & canopy)
            add("edge", seg(top, (top[0], top[1] - 0.025), 0.006))              # 伞尖
    # ---- 衣服细节：成块的明暗
    belt_m = np.zeros((hh, fw), bool)
    pocket_m = np.zeros((hh, fw), bool)
    slit_m = np.zeros((hh, fw), bool)
    if big:
        slit_m = seg((-0.05 - sway * 0.5, hem - 0.1), (bh_ + 0.03, hem + 0.012), 0.006) & torso            # 背后开衩
        pocket_m = poly([(0.03, hipv - 0.01), (0.085, hipv - 0.01), (0.085, hipv + 0.012), (0.03, hipv + 0.012)]) & torso
        if tp["belt"]:
            belt_m = poly([(-0.1, hipv - 0.1), (0.09, hipv - 0.1), (0.09, hipv - 0.078), (-0.1, hipv - 0.078)]) & torso
    if tp["collar"]:
        add("collar", poly([(-0.02, 0.122), (0.058, 0.117), (0.072, 0.172), (0.0, 0.182)]) & ~face)
    if tp["scarf"]:
        add("scarf", poly([(-0.035, 0.142), (0.062, 0.142), (0.067, 0.178), (-0.035, 0.178)]))
        add("scarf", poly([(0.03, 0.172), (0.062, 0.172), (0.07 - 0.012 * s, 0.33), (0.044 - 0.012 * s, 0.33)]))
    # ---- 上色。逆光：背后雨雾里的光从上面、后面来 —— 人整体暗（剪影的体量），身上分三四档大块的明暗（朝上的面亮），
    # 兜帽顶、肩、背上一道冷色轮廓光（255），大衣朝光那面几道断开的湿反光（200）。不描边：轮廓光只在朝上、朝后的边。
    STEPS = np.array([40, 58, 76, 94, 112, 130, 148, 166])
    NS = len(STEPS)
    LX, LY = -0.3, -0.95     # 光从背后上方来（雨雾、路灯）：朝上、朝后的面亮，脸那面暗
    yy_, xx_ = np.mgrid[0:hh, 0:fw]
    vv = 1 - (hh - (yy_ + 0.5)) / H_ - bob
    E = np.zeros((hh, fw), bool)

    def get(name):
        return lay.get(name, E)

    def row_u(m):
        u = np.zeros((hh, fw))
        for y in np.nonzero(m.any(1))[0]:
            xs_ = np.nonzero(m[y])[0]
            u[y, xs_] = 2 * (xs_ - xs_.min()) / max(1, xs_.max() - xs_.min()) - 1
        return u

    def planes(m, ambient, contrast):
        if not m.any():
            return np.zeros((hh, fw))
        ys_ = np.nonzero(m.any(1))[0]
        y0_, y1_ = ys_.min(), ys_.max()
        v = 2 * (yy_ - y0_) / max(1, y1_ - y0_) - 1
        t = ambient + contrast * 0.5 * (row_u(m) * LX + v * LY)
        return t * (NS - 1)

    def fold(tone, m, a_, b_, width, sheen=None):
        """斜的衣褶楔子：折痕背光那侧暗两档 / 一档（越往末端越细），朝光那侧贴着折痕亮一档（或湿反光）。"""
        (fx0, fy0), (fx1, fy1) = P(*a_), P(*b_)
        dx, dy = fx1 - fx0, fy1 - fy0
        L = np.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        if nx * LX + ny * LY > 0:
            nx, ny = -nx, -ny
        sa = ((xx_ + 0.5 - fx0) * dx + (yy_ + 0.5 - fy0) * dy) / (L * L)
        d = (xx_ + 0.5 - fx0) * nx + (yy_ + 0.5 - fy0) * ny
        w = width * (1 - 0.5 * np.clip(sa, 0, 1))
        on = m & (sa >= 0) & (sa <= 1)
        tone[on & (d >= 0) & (d < w * 0.5)] -= 2
        tone[on & (d >= w * 0.5) & (d < w)] -= 1
        edge = on & (d >= -1) & (d < 0)
        tone[edge] += 1
        if sheen is not None:
            # 湿反光：折痕朝光那侧，一段一段断开（像雨水顺着布往下流）
            seg_on = ((yy_ // max(2, hh // 22)) % 3 != 1) & (sa > 0.08) & (sa < 0.75)
            sheen |= edge & seg_on

    def put_tone(m, tone):
        if not m.any():
            return
        k = np.clip(np.round(tone), 0, NS - 1).astype(int)
        g = STEPS[k]
        img[m] = np.stack([g, g, g, np.full_like(g, 255)], -1)[m]

    def put(m, g):
        img[m] = (g, g, g, 255)

    fwid = max(1.6, 0.036 * H_)
    sheen = np.zeros((hh, fw), bool)
    # 远侧的腿、鞋、胳膊：比外套暗一档（不是最暗，不绕成黑边）
    put_tone(get("legfar"), planes(get("legfar"), 0.14, 0.3))
    put(get("shoefar"), STEPS[0])
    put_tone(get("armfar"), planes(get("armfar"), 0.2, 0.4))
    put(get("handfar"), STEPS[2])
    # 近侧的腿、鞋（鞋面一道湿的亮）
    put_tone(get("leg"), planes(get("leg"), 0.28, 0.4))
    put(get("shoe"), STEPS[1])
    if big:
        sh_top = get("shoe") & ~np.roll(get("shoe"), 1, 0)
        put(sh_top, STEPS[4])
    # 大衣 + 兜帽
    bm = get("body")
    tone = planes(bm, 0.62, 1.45)
    tone[bm & (vv > hipv - 0.06)] -= 1                 # 腰以下在阴影里
    tone[bm & (vv > hem - 0.07)] -= 1                  # 下摆再暗一档
    if big:
        fold(tone, bm, (0.035, 0.22), (0.05 + (fh_ - w_hem * 0.75) * 0.5, hem - 0.01), fwid)   # 胸前垂下来的长褶
        fold(tone, bm, (-0.055, 0.28), (bh_ * 0.7, hem), fwid * 0.9)                            # 背后那道
        fold(tone, bm, (0.0, hipv), (0.015 - sway * 0.5, hem), fwid * 0.8)                           # 下摆中间
        if hun > 0.05:
            fold(tone, bm, (-0.09, 0.2), (-0.03, 0.33), fwid * 0.7)                                    # 驼背：背上横着的一道
    elif hh >= 18:
        fold(tone, bm, (0.02, 0.25), (0.03, hem), max(1.0, fwid * 0.6))
    put_tone(bm, tone)
    put_tone(belt_m, tone - 2)
    put_tone(pocket_m, tone - 1)
    put_tone(slit_m, tone - 2)
    # 包、纸箱、伞面
    for name, amb, con in (("bag", 0.3, 0.8), ("box", 0.55, 0.7)):
        m = get(name)
        if m.any():
            put_tone(m, planes(m, amb, con))
    if get("boxfold").any():
        put_tone(get("boxfold"), planes(get("box"), 0.55, 0.7) - 1)
    cn = get("canopy")
    if cn.any():
        t2 = planes(cn, 0.28, 1.0)
        put_tone(cn, t2)
        put_tone(get("rib") & cn, t2 - 1)
        if big:   # 湿伞面：伞顶下面一两行一道冷的反光（背光那半边断开），不是一块黑
            cols = np.nonzero(cn.any(0))[0]
            c0, c1 = cols.min(), cols.max()
            for x in cols:
                ys_ = np.nonzero(cn[:, x])[0]
                t = (x - c0) / max(1, c1 - c0)
                if 0.08 < t < 0.75 and not (0.5 < t and x % 3 == 0):
                    for dy in ((1, 2) if t < 0.45 else (1,)):
                        if ys_[0] + dy <= ys_[-1]:
                            img[ys_[0] + dy, x] = (G["sheen"],) * 3 + (255,)
    # 近侧的胳膊：自己一个圆柱，上沿受光
    arm = get("arm")
    at = planes(arm, 0.55, 0.9)
    up1 = np.zeros_like(arm)
    up1[1:] = arm[:-1]
    at[arm & ~up1] += 1
    put_tone(arm, at)
    put_tone(get("cuff"), at - 1)
    put(get("hand"), STEPS[5])
    put(get("strap"), STEPS[3])
    put_tone(get("collar"), planes(get("collar"), 0.55, 0.7))
    sc = get("scarf")
    if sc.any():
        st_ = planes(sc, 0.5, 0.8)
        if big:
            fold(st_, sc, (0.0, 0.15), (0.05, 0.3), max(1.2, fwid * 0.5))
        put_tone(sc, st_)
    put(get("edge"), STEPS[5])
    # 兜帽里：开口一圈暗，帽檐压住的那一道再暗，脸最暗
    if hh >= 18:
        put_tone(opening, tone - 2)
        put(brim, STEPS[0])
        put(face, 30)
        if big:
            put(chin, STEPS[1])
    put(get("phone"), STEPS[1])
    put(get("screen"), 240)
    if items == "phone" and big:
        put(chin, STEPS[4])
    # 湿反光（大衣朝光那面，断开的竖条）
    if big:
        put(sheen & bm & ~get("arm") & ~face, G["sheen"])
    # 冷色轮廓光：朝上的边（上面一行是空的）—— 兜帽顶、肩、伞面、箱子顶；兜帽两侧的边；背（朝后那条边）上半截弱一档
    allm = img[..., 3] > 0
    up = np.zeros_like(allm)
    up[1:] = allm[:-1]
    lf = np.zeros_like(allm)
    lf[:, 1:] = allm[:, :-1]
    rt = np.zeros_like(allm)
    rt[:, :-1] = allm[:, 1:]
    no_face = ~face & ~get("screen")
    top_rim = allm & ~up & (vv < hipv) & no_face
    put(top_rim, G["rim"])
    if big:
        up2 = np.zeros_like(allm)
        up2[2:] = allm[:-2]
        put(allm & ~up2 & up & (vv < 0.12) & no_face, G["rim"])            # 兜帽顶两行
        side_hood = allm & ~lf & (vv < 0.17) & no_face & ~get("canopy")       # 兜帽后脑勺那条边
        put(side_hood, G["rim"])
        back = allm & ~lf & (vv >= 0.16) & (vv < hipv - 0.02) & no_face & ~get("canopy")
        put(back, G["sheen"])
        shoulder = allm & up & ~up2 & (vv >= 0.12) & (vv < hipv) & no_face & ~get("canopy")   # 肩上湿的那一道（轮廓光下面一行）
        put(shoulder, G["sheen"])
    return img, fw


def hood_frames(hh, tp):
    frames = []
    fw = None
    for f in range(HOOD_FRAMES):
        im, fw = person_frame(hh, tp, f / HOOD_FRAMES * 2 * np.pi, f=f)
        frames.append(im)
    return frames, fw


def write_hoods():
    """art/city/hood_<高>.png：每行一种人（HOOD_TYPES 的顺序），每列一帧（8 帧走路）。"""
    info = {}
    for hh in CROWD_SIZES:
        rows = []
        for tp in HOOD_TYPES:
            frames, fw = hood_frames(hh, tp)
            rows.append(np.concatenate(frames, 1))
        sheet = np.concatenate(rows, 0)
        Image.fromarray(sheet).save(OUT / f"hood_{hh}.png")
        info[hh] = fw
    return info


def people_chart(path, hh=100, game_bg=None, tint_L=None):
    """人物表：每种人一行 —— 站姿 + 8 帧走路，最左边是晨（奥斯卡版，站着）比身高，放大 4 倍。
    game_bg = None：调亮版（灰度档 ×1.35，放在中灰底上，看细节）；
    game_bg = 一张游戏截图（480×270）：游戏里的真实亮度 —— 人乘上街面那层的染色（tint_L），放在截图里街面那一截上。"""
    chen = np.array(Image.open(ROOT / "art" / "characters" / "chen" / "chen_oscar.png").convert("RGBA"))[:, 7 * 68:8 * 68]
    if game_bg is None:
        tint = np.array([1.35, 1.37, 1.42])
    else:
        tint = np.array(lab_col(tint_L, _ab(0.006, H_COOL)), float) / 255
    bgc = np.array(lab_col(0.36, _ab(0.006, H_COOL)) + (255,), np.uint8)
    rows = []
    for tp in HOOD_TYPES:
        st, fw = person_frame(hh, tp, 0.0, stand=True)
        frs = [st] + hood_frames(hh, tp)[0]
        wrow = 68 + 10 + (fw + 4) * len(frs)
        row = np.zeros((hh + 4, wrow, 4), np.uint8)
        if game_bg is None:
            row[:] = bgc
        else:   # 截图里街面上方那一截（脚底对齐地面），横向铺满
            src = np.array(game_bg.convert("RGBA"))
            strip = src[GROUND - hh - 2:GROUND + 2]
            reps = int(np.ceil(wrow / strip.shape[1]))
            row[:] = np.concatenate([strip] * reps, 1)[:, :wrow]
        ch = chen.copy()
        y0 = hh + 1 - 57
        m = ch[..., 3] > 0
        row[y0:y0 + 60, 0:68][m] = ch[m]
        for k, fr in enumerate(frs):
            m = fr[..., 3] > 0
            col = np.clip(fr[..., :3].astype(float) * tint, 0, 255).astype(np.uint8)
            sub = row[1:1 + hh, 78 + k * (fw + 4):78 + k * (fw + 4) + fw]
            sub[m, :3] = col[m]
        rows.append(row)
    wmax = max(r.shape[1] for r in rows)
    sheet = np.concatenate([np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0)), mode="edge") for r in rows], 0)
    Image.fromarray(sheet).resize((sheet.shape[1] * 4, sheet.shape[0] * 4), Image.NEAREST).save(path)


# ---------------------------------------------------------------- 前景经过的大黑影（路人、车）

PASSER_H = 470              # 路人的身高（像素）：约晨的 9 倍，离镜头很近
PASSER_TYPES = (1, 2)       # 用 HOOD_TYPES 里的哪几种（高瘦立领提袋、宽肩公文包）
PASSER_CROP = (96, 366)     # 帧图只留这几行（画面上沿切在肩膀上，头和小腿都在画面外）；这几行正好是屏幕的 0..270
PASSER_L = (0.09, 0.16)     # 身子的亮度范围（灰度档 30..176 线性映射过来）；几乎全暗
PASSER_RIM = 0.24           # 肩上那道湿的受光边
PASSER_LEG = 4              # 腿（裤子、远侧的腿）往左右各加粗几像素：兜帽人的腿是按 100 像素的个子画的，放到 470 太细，像竹竿
CAR_W, CAR_H = 560, 160     # 车：只画画面里露出来的那一截（车顶到画面下沿）
CAR_TOP = 110               # 车顶在屏幕的哪一行


def passer_sheet():
    """art/city/passer.png：每行一种人、每列一帧（8 帧走路、朝右），已经裁掉头和脚、左右裁到所有帧的并集。
    颜色直接画好（几乎全暗的冷灰），Godot 里不再染色。"""
    rows, fr_all = [], []
    for i in PASSER_TYPES:
        frs, fw = hood_frames(PASSER_H, HOOD_TYPES[i])
        fr_all.append(frs)
    a = np.zeros((PASSER_H, fw), bool)
    # 腿加粗：灰度档 60（裤子）、44（远侧的腿、鞋），只在胯以下（v > 0.55），只往透明的地方长，颜色跟着腿
    v_leg = int(PASSER_H * 0.55)
    for frs in fr_all:
        for im in frs:
            g = im[..., 0]
            leg = (im[..., 3] > 0) & ((g == 60) | (g == 44))
            leg[:v_leg] = False
            src = im.copy()
            for k in range(1, PASSER_LEG + 1):
                for d in (k, -k):
                    sh = np.roll(leg, d, 1)
                    col = np.roll(src, d, 1)
                    m = sh & (im[..., 3] == 0)
                    im[m] = col[m]
    for frs in fr_all:
        for im in frs:
            a |= im[..., 3] > 0
    xs = np.nonzero(a.any(0))[0]
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = PASSER_CROP
    lut = np.zeros((256, 4), np.uint8)
    for g in range(256):
        if g >= 248:
            L = PASSER_RIM
        elif g >= 225:
            L = 0.42                              # 手机屏：一点冷光
        else:
            L = PASSER_L[0] + (PASSER_L[1] - PASSER_L[0]) * min(1.0, max(0.0, (g - 30) / (176 - 30)))
            L = round(L / 0.01) * 0.01          # 分档，别出几十种近黑
        lut[g] = lab_col(L, _ab(0.03 if 225 <= g < 248 else 0.008, 220 if 225 <= g < 248 else H_COOL)) + (255,)
    for frs in fr_all:
        row = []
        for im in frs:
            c = im[y0:y1, x0:x1]
            out = np.zeros_like(c)
            m = c[..., 3] > 0
            out[m] = lut[c[..., 0][m]]
            row.append(out)
        rows.append(np.concatenate(row, 1))
    sheet = np.concatenate(rows, 0)
    Image.fromarray(sheet).save(OUT / "passer.png")
    return x1 - x0, y1 - y0


def car_image():
    """art/city/car.png：一辆暗色轿车的侧面（朝右开，车头在右），只画露出来的那一截（车顶到画面下沿，轮子下半截在画面外）。
    车身近黑的冷灰，车顶和腰线一道湿的冷灰反光，车窗是冷灰玻璃上几道斜的反光（映着楼缝的霾），
    前窗里一个戴兜帽的司机剪影（看前面，不看晨），车头一盏冷白的灯，车尾灯不亮（不用暖色）。"""
    w, h = CAR_W, CAR_H
    img = np.zeros((h, w, 4), np.uint8)
    C = lambda L, c=0.008, hh=H_COOL: lab_col(L, _ab(c, hh)) + (255,)
    body, body_lo, seam = C(0.11), C(0.095), C(0.08)
    roof_hi, belt_hi, sill = C(0.24), C(0.17), C(0.13)
    glass, glass_dk = C(0.14, 0.012, 240), C(0.115, 0.012, 240)
    refl, refl2 = C(0.27, 0.012, 230), C(0.21, 0.012, 230)
    driver = C(0.085)
    head_l, head_l2 = C(0.62, 0.02, 230), C(0.42, 0.016, 230)
    tail = C(0.15)
    tire, rim_c = C(0.09), C(0.15)
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    from matplotlib.path import Path as MPath
    pts = np.c_[xx.ravel(), yy.ravel()]

    def poly(ps):
        return MPath(ps).contains_points(pts).reshape(h, w)

    # 车身：后备箱、车舱、引擎盖
    lower = poly([(6, 74), (40, 64), (128, 62), (440, 62), (536, 70), (556, 86), (558, 160), (2, 160), (2, 88)])
    cabin = poly([(96, 64), (168, 10), (190, 4), (350, 4), (372, 10), (448, 64)])
    car = lower | cabin
    img[car] = body
    img[car & (yy > 112)] = body_lo
    # 车窗（车舱里面缩一圈），一根 B 柱
    win = poly([(110, 60), (174, 14), (192, 9), (346, 9), (364, 14), (432, 60)])
    img[win] = glass
    img[win & (yy > 46)] = glass_dk
    for bx in (262,):
        img[win & (xx > bx) & (xx < bx + 9)] = body
    # 斜的反光（映着楼缝的霾），跟着窗走
    for k, (x0r, wd, col) in enumerate(((150, 16, refl), (196, 6, refl2), (300, 22, refl), (338, 5, refl2), (392, 10, refl2))):
        band = (xx - x0r + (yy - 9) * 0.9 >= 0) & (xx - x0r + (yy - 9) * 0.9 < wd)
        img[win & band] = col
    # 司机：前窗里一个戴兜帽的剪影，脸朝前
    drv = poly([(290, 60), (292, 34), (300, 24), (312, 21), (324, 25), (330, 36), (334, 60)]) & win
    img[drv] = driver
    # 车顶受光边、腰线反光、门缝、门把手、门槛
    top = car & ~np.roll(car, 1, 0)
    img[top & (yy < 66)] = roof_hi
    img[(yy > 66) & (yy < 68) & car & (xx > 20) & (xx < 548)] = belt_hi
    for sx in (262, 408):
        img[(xx > sx) & (xx < sx + 1.5) & (yy > 64) & (yy < 132) & car] = seam
    for hx in (222, 370):
        img[(xx > hx) & (xx < hx + 10) & (yy > 76) & (yy < 78.5)] = sill
    img[(yy > 128) & (yy < 130) & car & (xx > 120) & (xx < 450)] = sill
    # 车身侧面一道断断续续的反光（湿的）
    side = (yy > 96) & (yy < 97.5) & car & (((xx // 23) % 3) != 1) & (xx > 30) & (xx < 530)
    img[side] = sill
    # 轮拱 + 轮子（下半截在画面外）
    for cx in (120, 448):
        arch = (xx - cx) ** 2 + (yy - 170) ** 2 <= 50 ** 2
        img[arch & car] = C(0.07)
        wheel = (xx - cx) ** 2 + (yy - 172) ** 2 <= 44 ** 2
        img[wheel] = tire
        hub = (xx - cx) ** 2 + (yy - 172) ** 2 <= 26 ** 2
        img[hub] = rim_c
        img[(xx - cx) ** 2 + (yy - 172) ** 2 <= 20 ** 2] = tire
        img[wheel & ((xx - cx) ** 2 + (yy - 172) ** 2 > 42 ** 2) & (yy < 140)] = C(0.13)
    # 车头灯（冷白）、尾灯（不亮）
    img[(xx > 546) & (xx < 557) & (yy > 76) & (yy < 86)] = head_l2
    img[(xx > 549) & (xx < 557) & (yy > 78) & (yy < 84)] = head_l
    img[(xx > 3) & (xx < 9) & (yy > 80) & (yy < 94)] = tail
    # 车窗上几颗雨滴
    rng = np.random.default_rng(7)
    ys_, xs_ = np.nonzero(win & ~drv)
    for i in rng.choice(len(ys_), 26, replace=False):
        img[ys_[i], xs_[i]] = refl
    img[..., 3] = np.where(img[..., 3] > 0, 255, 0)
    Image.fromarray(img).save(OUT / "car.png")


# ---------------------------------------------------------------- 街面冷光源的光晕（Godot 里叠加混合）

def glow_images():
    """art/city/glow_halo.png：灯头周围一圈冷光（三档同心的硬边圆，叠加上去）；
    art/city/glow_pool.png：灯下湿地上一摊冷光（扁椭圆，三档，最外一档隔行断开，像被雨打碎的水面）。
    颜色就是要加上去的量（叠加混合），是特效，所以只有这两张不是「暗的不透明美术」。"""
    def ring_img(w, h, rx, ry, steps, broken=False):
        yy, xx = np.mgrid[0:h, 0:w] + 0.5
        r = np.hypot((xx - w / 2) / rx, (yy - h / 2) / ry)
        img = np.zeros((h, w, 4), np.uint8)
        for k, (rr, add) in enumerate(steps):
            m = r <= rr
            if broken and k == 0:
                m &= (np.arange(h)[:, None] % 2 == 0)
            col = np.array(add) * 255
            img[m] = tuple(int(v) for v in col) + (255,)
        return img
    halo = ring_img(25, 25, 12, 12, [(1.0, (0.035, 0.045, 0.055)), (0.62, (0.06, 0.075, 0.09)), (0.3, (0.08, 0.095, 0.11))])
    Image.fromarray(halo).save(OUT / "glow_halo.png")
    pool = ring_img(96, 18, 48, 9, [(1.0, (0.045, 0.06, 0.075)), (0.66, (0.09, 0.11, 0.13)), (0.36, (0.15, 0.18, 0.2))],
                    broken=True)
    Image.fromarray(pool).save(OUT / "glow_pool.png")


# ---------------------------------------------------------------- 组装

def build():
    OUT.mkdir(parents=True, exist_ok=True)
    layers = {
        "sky": sky(),
        "ridge": ridge(),
        "far": far(),
        "midfar": midfar(),
        "mid": mid(),
        "main": main_layer(),
        "front": front_layer(),
    }
    for k, v in layers.items():
        v.save(k)
    return layers


def check_alpha(layers):
    for k, v in layers.items():
        u = set(np.unique(v.a[..., 3]).tolist())
        assert u <= {0, 255}, (k, u)
        assert v.a.shape[:2] == ((H, 480) if k == "sky" else ((HB, W) if k in ("main", "front") else (H, W))), (k, v.a.shape)


def components(mask, wrap=False):
    """8 连通区域标号（wrap = 左右绕回）。返回 (labels, n)。"""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        st = [(y0, x0)]
        while st:
            y, x = st.pop()
            for yy in (y - 1, y, y + 1):
                if not 0 <= yy < h:
                    continue
                for xx in (x - 1, x, x + 1):
                    if wrap:
                        xx %= w
                    elif not 0 <= xx < w:
                        continue
                    if mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        st.append((yy, xx))
    return lab, n


def check_floating(layers, verbose=True):
    """每一块不透明的东西都要落到这层的底边（楼、街、柱子）。返回 {层: [问题...]}。"""
    bad = {}
    for k, lay in layers.items():
        if k == "sky":
            continue
        lab, n = components(lay.a[..., 3] > 0, wrap=True)
        out = []
        for i in range(1, n + 1):
            yy, xx = np.nonzero(lab == i)
            if yy.max() >= H - 1 or (k == "front" and yy.min() == 0):
                continue
            out.append((len(yy), int(xx.min()), int(xx.max()), int(yy.min()), int(yy.max()), "悬空"))
        bad[k] = out
        if verbose:
            print(f"  {k:7s} 连通区域 {n:4d}，悬空 {len(out)}")
            for b in out[:8]:
                print("     ", b)
    return bad


def check_brightness(layers):
    """背景最亮处要明显低于晨（晨身上大块的米白 L≈0.80）。"""
    worst = 0.0
    for k, v in layers.items():
        m = v.a[..., 3] > 0
        cols = np.unique(v.a[m][:, :3], axis=0)
        lab = srgb_to_oklab(cols)
        worst = max(worst, float(lab[:, 0].max()))
        print(f"  {k:7s} 最亮 L={lab[:, 0].max():.3f}，最大色度 {np.hypot(lab[:, 1], lab[:, 2]).max():.3f}，{len(cols)} 色")
    assert worst < 0.68, f"背景太亮了：L={worst:.3f}"


def check_strip(img):
    """晨身后那一条（地面往上 45 像素，屏幕上）的亮度：最亮、平均。"""
    lab = srgb_to_oklab(img[GROUND - 45:GROUND, :, :3].reshape(-1, 3))
    return float(lab[:, 0].max()), float(lab[:, 0].mean())


def chen_frame(i=3):
    a = np.array(Image.open(CHEN).convert("RGBA"))
    return a[:, i * 40:(i + 1) * 40]


def compose(layers, cam_x, chen_sx=204, chen=True):
    out = np.zeros((H, 480, 4), np.uint8)
    for k in SCROLL:
        a = layers[k].a[:H]
        if a.shape[1] == 480:
            src = a
        else:
            off = int(round(cam_x * SCROLL[k])) % a.shape[1]
            src = np.roll(a, -off, axis=1)[:, :480]
        if k == "front" and chen:
            fr = chen_frame()
            y0, x0 = GROUND + 1 - 42, chen_sx - 20
            m = fr[..., 3] > 0
            out[y0:y0 + 42, x0:x0 + 40][m] = fr[m]
        m = src[..., 3] > 0
        out[m] = src[m]
    return out


def preview(layers, cam_x, path):
    Image.fromarray(compose(layers, cam_x)).resize((1440, 810), Image.NEAREST).save(path)


# ---------------------------------------------------------------- 场景

# 路灯的光锥（第十一版：画面的光源和焦点）：每盏路灯从灯头往下一道冷白的光锥打到人行道上（叠加），
# 画在晨那条街的人群后面一点（远排、中排的人走进去会被照亮），晨画在它上面，所以晨还是最亮；
# 节点叫 Shafts，晨的 env_light.polygon_shafts 照旧读它 —— 晨走到灯下，斗篷和受光边亮一点。
CONE_TOP_W, CONE_BOT_W = 7, 78       # 光锥上沿（灯罩）、下沿（落到地面）的宽
CONE_A = (0.22, 0.13, 0.0)            # 光锥上沿、中段、下沿的 alpha（叠加）：上面亮，落到地面淡掉（地上另外有一摊光）
CONE_COL = "0.78, 0.86, 0.9"


def cones():
    out = ['[node name="Shafts" type="Parallax2D" parent="."]', f"scroll_scale = Vector2({SCROLL['main']}, 1)",
           "repeat_size = Vector2(960, 0)", "repeat_times = 2", ""]
    y0, y1 = LAMP_LENS_Y + 2, GROUND
    ym = y0 + (y1 - y0) * 0.55
    for i, lx in enumerate(LAMPS):
        hx = lx + LAMP_ARM + 0.5
        tw, bw = CONE_TOP_W / 2, CONE_BOT_W / 2
        mw = tw + (bw - tw) * 0.55
        pts = [(hx - tw, y0), (hx + tw, y0), (hx + mw, ym), (hx + bw, y1), (hx - bw, y1), (hx - mw, ym)]
        al = [CONE_A[0], CONE_A[0], CONE_A[1], CONE_A[2], CONE_A[2], CONE_A[1]]
        out += [f'[node name="Cone{i}" type="Polygon2D" parent="Shafts"]', 'material = SubResource("add")',
                "polygon = PackedVector2Array(" + ", ".join(f"{px:.1f}, {py:.1f}" for px, py in pts) + ")",
                "vertex_colors = PackedColorArray(" + ", ".join(f"{CONE_COL}, {v:.3f}" for v in al) + ")", ""]
    return out


# 每条人行道上的人群：层、脚底 y、个子（像素）、人数（两股人流加起来）、速度（像素/秒，这一层的坐标；每股人流在这个很窄的
# 范围里取一个，同一股里所有人一样快）、染色（受光边的颜色；身子是它的 70/255）、
# 间距抖动（占一格间距的几分之几，0 = 绝对等距）、步子对齐（1 = 同一股里齐步走，0 = 只是节奏一样）
CYCLE_T = 1.1 / 0.6   # 一个走路周期多少秒（8 帧，每帧约 0.23 秒；和第八版一样，没有加快帧）


def _cycle_len():
    """一个走路周期身体往前走多远（个子的几倍）= 4 × 着地那只脚离胯的水平距离 × s，各种人取平均 —— 脚不在地上打滑。"""
    out = []
    for tp in HOOD_TYPES:
        leg = (0.968 - tp["hip"]) * 0.5
        out.append(4 * 2 * leg * np.sin(tp["stride"]) * tp["s"])
    return float(np.mean(out))


CYCLE_LEN = _cycle_len()
WALK = CYCLE_LEN / CYCLE_T   # 人走路的速度（个子的几倍 / 秒）：第十一版步子小（长大衣），按步幅算出来，慢、稳
CROWD = [
    ("Far", DECKS["far"] - 1, 11, 40, (11 * WALK, 11 * WALK * 1.03), 0.58, 0.15, 0.5),
    ("MidFar", DECKS["midfar"] - 1, 18, 30, (18 * WALK, 18 * WALK * 1.03), 0.54, 0.15, 0.5),
    ("Mid", DECKS["mid"] - 1, 30, 22, (30 * WALK, 30 * WALK * 1.03), 0.5, 0.12, 0.6),
]
# 晨那条街拆成三排（作者：「分出层次」——原来一堵同色调的灰墙，分不出一个一个的人、看不出前后）。
# 每排一个方向、同排一样快（个子 × WALK）、同排间距比人宽（相邻的人不叠）；排和排用明度分开，全不透明，近排盖住远排：
#   远排：略小、脚底高两像素、往雾里浅（lo/hi 都靠近楼腰的霾，对比小）
#   中排：晨这个深度，细节最多，肩上的受光边最清楚 —— 一个一个的人主要靠这一排读出来
#   近排：最大、脚底比晨还低、近黑，很稀，画在晨前面，从她身前直直穿过去（不绕开、不停）
# 明度是 OKLab L：lo = 灰度档 30（最暗的档：远侧的胳膊腿、脸），hi = 灰度档 176（最亮的档：扣子、手），rim = 255（湿的受光边）
#   name, 父节点, 脚底 y, 个子, 人数, 方向, lo, hi, rim, 间距抖动, 步子对齐, seed
STREET_ROWS = [
    ("CrowdBack", "Main", GROUND - 5, 90, 16, -1, 0.11, 0.3, 0.42, 0.08, 0.75, 11),
    ("CrowdMid", "Main", GROUND - 2, 100, 12, 1, 0.06, 0.34, 0.56, 0.08, 0.75, 14),
    ("Crowd", "MainNear", GROUND, 110, 3, -1, 0.05, 0.22, 0.4, 0.1, 0.75, 12),
]
# 前景经过的大黑影（scripts/city_passers.gd）：隔多少秒来一个（从上一个走出画面算起）、第一个等几秒、
# 路人和车轮流来、路人 / 车的速度（像素/秒，屏幕上）
PASSERS = dict(interval=(7.0, 12.0), first_wait=2.5, walker_speed=260.0, car_speed=820.0)
# 高架列车：层、轨道 y、车厢数、车厢长、车高、速度（像素/秒）、间隔（秒）、方向
TRAINS = [
    ("Mid", TRACKS["mid"], 8, 46, 13, 420.0, (10.0, 16.0), 1),
    ("Far", TRACKS["far"], 7, 20, 5, 200.0, (12.0, 20.0), -1),
]


def write_scene(layers, hood_w, passer_fs=(150, 270)):
    def region(name):
        a = layers[name].a[..., 3] > 0
        r = np.nonzero(a.any(1))[0]
        return max(0, int(r.min()) - 1), int(r.max())

    ext = [
        ('Texture2D', 'res://art/city/sky.png', '1_sky'),
        ('Texture2D', 'res://art/city/ridge.png', '2_ridge'),
        ('Texture2D', 'res://art/city/far.png', '3_far'),
        ('Texture2D', 'res://art/city/midfar.png', '4_midfar'),
        ('Texture2D', 'res://art/city/mid.png', '5_mid'),
        ('Texture2D', 'res://art/city/main.png', '6_main'),
        ('Texture2D', 'res://art/city/front.png', '7_front'),
        ('Script', 'res://scripts/city_test.gd', '20_script'),
        ('Shader', 'res://scripts/vignette.gdshader', '21_vig'),
        ('Script', 'res://scripts/city_crowd.gd', '22_crowd'),
        ('Script', 'res://scripts/city_train.gd', '23_train'),
        ('Script', 'res://scripts/city_signals.gd', '24_signals'),
        ('Script', 'res://scripts/city_passers.gd', '26_passers'),
        ('Script', 'res://scripts/city_rain.gd', '27_rain'),
        ('Script', 'res://scripts/city_flicker.gd', '28_flicker'),
        ('Shader', 'res://scripts/city_wet.gdshader', '29_wet'),
        ('Script', 'res://scripts/city_ripples.gd', '30_ripples'),
        ('PackedScene', 'res://scenes/chen.tscn', '40_chen'),
        ('Texture2D', 'res://art/city/passer.png', '51_passer'),
        ('Texture2D', 'res://art/city/car.png', '52_car'),
        ('Texture2D', 'res://art/city/glow_halo.png', '53_halo'),
        ('Texture2D', 'res://art/city/glow_pool.png', '54_pool'),
    ] + [('Texture2D', f'res://art/city/hood_{hh}.png', f'50_hood{hh}') for hh in CROWD_SIZES]
    s = [f"[gd_scene load_steps={len(ext) + 4} format=3]", ""]
    for t, p, i in ext:
        s.append(f'[ext_resource type="{t}" path="{p}" id="{i}"]')
    s += ["", '[sub_resource type="CanvasItemMaterial" id="add"]', "blend_mode = 1", "",
          '[sub_resource type="ShaderMaterial" id="wet"]', 'shader = ExtResource("29_wet")',
          f"shader_parameter/ground = {GROUND - CAM_DY}.0", "",
          '[sub_resource type="ShaderMaterial" id="vig"]', 'shader = ExtResource("21_vig")',
          "shader_parameter/strength = 0.55", "shader_parameter/tint = Color(0.92, 0.93, 0.95, 1)", "",
          '[node name="CityTest" type="Node2D"]', 'script = ExtResource("20_script")', ""]

    def para(name, key, tex):
        y0, y1 = region(key)
        sc = SCROLL[key]
        out = [f'[node name="{name}" type="Parallax2D" parent="."]',
               f"scroll_scale = Vector2({sc}, {0 if key == 'sky' else 1})"]
        if key != "sky":
            out += ["repeat_size = Vector2(960, 0)", "repeat_times = 2"]
        out += ["", f'[node name="Sprite" type="Sprite2D" parent="{name}"]', f'texture = ExtResource("{tex}")',
                "centered = false", f"position = Vector2(0, {y0})", "region_enabled = true",
                f"region_rect = Rect2(0, {y0}, {layers[key].a.shape[1]}, {y1 - y0 + 1})", ""]
        return out

    def crowd(parent, key, seed):
        _, feet, hh, n, sp, Lt, jit, sync = cr[key]
        r, g, b = (v / 255 for v in lab_col(Lt, _ab(0.006, H_COOL)))
        return [f'[node name="Crowd" type="Node2D" parent="{parent}"]', 'script = ExtResource("22_crowd")',
                f'texture = ExtResource("50_hood{hh}")', f"frame_size = Vector2i({hood_w[hh]}, {hh})",
                f"types = {len(HOOD_TYPES)}", f"frames = {HOOD_FRAMES}",
                f"count = {n}", f"feet_y = {feet}", f"speed = Vector2({sp[0]:.2f}, {sp[1]:.2f})",
                f"tint = Color({r:.3f}, {g:.3f}, {b:.3f}, 1)", f"seed = {seed}", f"jitter = {jit}", f"sync = {sync}",
                f"stride = {CYCLE_LEN:.4f}", ""]

    cr = {c[0]: c for c in CROWD}

    def street_row(row):
        name, parent, feet, hh, n, d, lo, hi, rim_, jit, sync, seed = row
        def c(L):
            r, g, b = (v / 255 for v in lab_col(L, _ab(0.007, H_COOL)))
            return f"Color({r:.3f}, {g:.3f}, {b:.3f}, 1)"

        def glow(lo_):   # 手机屏的冷光：近排暗一点（远排的人本来就浅），都比晨的白发暗得多
            r, g, b = (v / 255 for v in lab_col(0.5 + (0.2 - lo_) * 0.5, _ab(0.035, 220)))
            return f"Color({r:.3f}, {g:.3f}, {b:.3f}, 1)"
        return [f'[node name="{name}" type="Node2D" parent="{parent}"]', 'script = ExtResource("22_crowd")',
                f'texture = ExtResource("50_hood{hh}")', f"frame_size = Vector2i({hood_w[hh]}, {hh})",
                f"types = {len(HOOD_TYPES)}", f"frames = {HOOD_FRAMES}",
                f"count = {n}", f"direction = {d}", f"feet_y = {feet}", f"speed = Vector2({hh * WALK:.2f}, {hh * WALK:.2f})",
                f"seed = {seed}", f"jitter = {jit}", f"sync = {sync}", f"stride = {CYCLE_LEN:.4f}",
                "shadow = 0.65", "ramp = true", f"lo = {c(lo)}", f"hi = {c(hi)}", f"rim = {c(rim_)}", f"glow = {glow(lo)}", ""]

    def train(parent):
        for (par, ty, n, cl, ch, v, iv, d) in TRAINS:
            if par == parent:
                return [f'[node name="Train" type="Node2D" parent="{parent}"]', 'script = ExtResource("23_train")',
                        f"rail_y = {ty}", f"cars = {n}", f"car_len = {cl}", f"car_h = {ch}", f"speed = {v}",
                        f"interval = Vector2({iv[0]}, {iv[1]})", f"dir = {d}", f"far = {'true' if parent == 'Far' else 'false'}", ""]
        return []

    def rain(parent, n, life, seed, ln, w, v, col, bottom, area_y=-10, y_dim=183, dim=0.45, name="Rain",
             lit=False, only_lit=False):
        # GPUParticles2D 细雨（scripts/city_rain.gd）：n 粒、活 life 秒、长 ln、图宽 w、竖直速度 v、颜色 col（带 alpha）
        out = [f'[node name="{name}" type="GPUParticles2D" parent="{parent}"]', f"amount = {n}", f"lifetime = {life}",
               f"seed = {seed}", 'script = ExtResource("27_rain")', f"length = {ln}", f"width = {w}", f"speed = {v}",
               f"color = Color({col[0]}, {col[1]}, {col[2]}, {col[3]})", f"area = Rect2(0, {area_y}, 960, 240)",
               f"bottom = {bottom}", f"y_dim = {y_dim}", f"dim = {dim}"]
        if lit:     # 路灯光锥里的雨丝亮起来（和 cones() 同一组光锥）
            ls = ", ".join(f"{lx + LAMP_ARM + 0.5}, {LAMP_LENS_Y + 2}, {CONE_TOP_W / 2}, {CONE_BOT_W / 2 - 4}" for lx in LAMPS)
            out += [f"lights = PackedVector4Array({ls})", f"light_bottom = {GROUND}.0",
                    "color_lit = Color(0.66, 0.72, 0.75, 1)", "lit_boost = 3.0"]
            if only_lit:
                out += ["only_lit = true"]
        return out + [""]

    def ripples():
        # 街面上的小涟漪（scripts/city_ripples.gd）：远处一条小的、近处一条大的；画在镜子后面
        out = ['[node name="Ripples" type="Parallax2D" parent="."]', f"scroll_scale = Vector2({SCROLL['main']}, 1)",
               "repeat_size = Vector2(960, 0)", "repeat_times = 2", ""]
        top = GROUND + CURB_FACE + 3
        for name, n, life, seed, y0, h, size, a in (("Far", 40, 0.7, 46, top, 20, 5.0, 0.22),
                                                   ("Near", 36, 0.8, 47, top + 21, 52, 10.0, 0.26)):
            out += [f'[node name="{name}" type="GPUParticles2D" parent="Ripples"]', f"amount = {n}", f"lifetime = {life}",
                    f"seed = {seed}", 'script = ExtResource("30_ripples")', f"area = Rect2(0, {y0}, 960, {h})",
                    f"size = {size}", f"color = Color(0.62, 0.67, 0.72, {a})", ""]
        return out

    def passers():
        P = PASSERS
        return ['[node name="Passers" type="CanvasLayer" parent="."]', "layer = 1", "",
                '[node name="Passers" type="Node2D" parent="Passers"]', 'script = ExtResource("26_passers")',
                'walker = ExtResource("51_passer")', f"walker_frame = Vector2i({passer_fs[0]}, {passer_fs[1]})",
                f"walker_frames = {HOOD_FRAMES}", f"walker_types = {len(PASSER_TYPES)}", "walker_top = 0.0",
                f"walker_speed = {P['walker_speed']}", f"walker_stride = {PASSER_H * 1.1:.1f}",
                'car = ExtResource("52_car")', f"car_top = {CAR_TOP}.0", f"car_speed = {P['car_speed']}",
                f"interval = Vector2({P['interval'][0]}, {P['interval'][1]})", f"first_wait = {P['first_wait']}",
                "alternate = true", f"parallax = {SCROLL['front']}", ""]

    def flicker(parent, key, seed, share):
        rng = np.random.default_rng(seed)
        rs = [c for c in layers[key].info.get("cores", []) if 20 < c[1] and c[1] + c[3] < 165 and rng.random() < share]
        return [f'[node name="Flicker" type="Node2D" parent="{parent}"]', 'script = ExtResource("28_flicker")',
                "rects = Array[Rect2]([" + ", ".join(f"Rect2({x}, {y}, {w}, {h})" for x, y, w, h in rs) + "])",
                f"seed = {seed}", ""]

    def sig(parent, key, seed):
        pts = layers[key].info.get("signals", [])
        return [f'[node name="Signals" type="Node2D" parent="{parent}"]', 'script = ExtResource("24_signals")',
                "points = PackedVector2Array(" + ", ".join(f"{x}, {y}" for x, y in pts) + ")",
                f"dot = {1 if key == 'far' else 2}", f"seed = {seed}", ""]
    s += para("Sky", "sky", "1_sky")
    s += para("Ridge", "ridge", "2_ridge")
    s += para("Far", "far", "3_far")
    s += crowd("Far", "Far", 3)
    s += train("Far")
    s += sig("Far", "far", 2)
    s += para("MidFar", "midfar", "4_midfar")
    s += crowd("MidFar", "MidFar", 5)
    s += flicker("MidFar", "midfar", 8, 0.35)
    s += sig("MidFar", "midfar", 4)
    s += para("Mid", "mid", "5_mid")
    s += crowd("Mid", "Mid", 7)
    s += sig("Mid", "mid", 6)
    s += flicker("Mid", "mid", 9, 0.3)
    s += train("Mid")
    s += rain("Mid", 700, 1.3, 42, 6, 0.9, 105, (0.62, 0.66, 0.7, 0.3), 236)
    s += para("Main", "main", "6_main")
    s += street_row(STREET_ROWS[0])
    s += street_row(STREET_ROWS[1])
    s += rain("Main", 800, 1.1, 43, 9, 1.0, 150, (0.62, 0.66, 0.7, 0.36), GROUND, lit=True)
    s += rain("Main", 800, 0.9, 45, 9, 1.0, 150, (0.62, 0.66, 0.7, 0.3), GROUND, name="LampRain", lit=True, only_lit=True)
    s += cones()
    s += ['[node name="Chen" parent="." instance=ExtResource("40_chen")]', f"position = Vector2(204, {GROUND + 1})", ""]
    # 晨同一条街、画在她前面的那几个人（同一个深度、同一个视差）
    s += ['[node name="MainNear" type="Parallax2D" parent="."]', f"scroll_scale = Vector2({SCROLL['main']}, 1)",
          "repeat_size = Vector2(960, 0)", "repeat_times = 2", ""]
    s += street_row(STREET_ROWS[2])
    s += ['[node name="Wet" type="Parallax2D" parent="."]', "scroll_scale = Vector2(0, 0)", "",
          '[node name="Rect" type="ColorRect" parent="Wet"]', 'material = SubResource("wet")',
          f"offset_top = {GROUND - CAM_DY + CURB_FACE + 1}.0", "offset_right = 480.0", "offset_bottom = 270.0", "mouse_filter = 2", ""]
    s += ripples()
    # 冷光源的光晕：灯头一圈、灯下湿地上一摊（叠加；画在镜子后面，所以不会在倒影里再被照一次）
    s += ['[node name="Glow" type="Parallax2D" parent="."]', f"scroll_scale = Vector2({SCROLL['main']}, 1)",
          "repeat_size = Vector2(960, 0)", "repeat_times = 2", ""]
    glows = []
    for lx in LIT_LAMPS:
        glows += [("halo", lx + LAMP_ARM + 1, LAMP_LENS_Y + 1), ("pool", lx + LAMP_ARM + 1, GROUND + CURB_FACE + 6)]
    glows += [("halo", VEND_X + 9, SW_BACK + 1 - VEND_H + 14), ("pool", VEND_X + 10, GROUND + 7)]
    for i, (kind, gx, gy) in enumerate(glows):
        tex = "53_halo" if kind == "halo" else "54_pool"
        s += [f'[node name="G{i}" type="Sprite2D" parent="Glow"]', 'material = SubResource("add")',
              f'texture = ExtResource("{tex}")', f"position = Vector2({gx}, {gy})", ""]
    s += para("Front", "front", "7_front")
    s += rain("Front", 70, 1.0, 44, 16, 1.4, 240, (0.6, 0.64, 0.68, 0.24), 310, area_y=20, y_dim=9999, dim=1.0)
    s += passers()
    s += ['[node name="Camera" type="Camera2D" parent="."]', f"position = Vector2(240, {135 + CAM_DY})", "",
          '[node name="Overlay" type="CanvasLayer" parent="."]', "layer = 10", "",
          '[node name="Vignette" type="ColorRect" parent="Overlay"]', 'material = SubResource("vig")',
          "offset_right = 480.0", "offset_bottom = 270.0", "mouse_filter = 2", ""]
    SCENE.write_text("\n".join(s))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把几张合成预览存到这个目录")
    args = ap.parse_args()
    ls = build()
    hood_w = write_hoods()
    passer_fs = passer_sheet()
    car_image()
    glow_images()
    write_scene(ls, hood_w, passer_fs)
    check_alpha(ls)
    print("亮度：")
    check_brightness(ls)
    print("悬空自检：")
    floating = check_floating(ls)
    for cx in (0, 420, 900):
        mx, mean = check_strip(compose(ls, cx, chen=False))
        print(f"  镜头 {cx}: 晨身后那条 最亮 L={mx:.3f} 平均 {mean:.3f}")
    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for cx in (0, 420, 900):
            preview(ls, cx, d / f"city_{cx}.png")
    print("ok", {k: v.a.shape[1] for k, v in ls.items()})
    n_bad = sum(len(v) for v in floating.values())
    if n_bad:
        sys.exit(f"有 {n_bad} 块悬空，见上面的列表")
