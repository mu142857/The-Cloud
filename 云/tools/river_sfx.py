"""河流篇剧本（data/story_river.json）里的音效：35 个一次性 + 4 个环境声（程序生成，以后可以换正式的，文件名不变即可）。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_sfx.py

做法和 tools/forest_story_sfx.py 一样（直接 import 它的合成工具：滤波、混响、敲击模态、低鸣……），
输出 audio/sfx/*.wav（44.1kHz 单声道 16 位），已有的文件一个都不动（wrench 用森林那个）；跑完打印每个文件的时长 / 峰值 / RMS / 频谱质心，
环境声另外打印接缝检查。方向：安静、克制、偏低频、不刺耳；河边的声音带一点水边的混响，妮芙家里的带一点小屋混响。
峰值和森林同类音效对齐（敲击 0.3~0.5、大动静 0.55~0.65、环境声 0.45~0.55），游戏里再按 bus 统一。

原文写到声音的地方照原文（行号 = 剧情姐合订稿）：
  铃舌被泥堵住「只能发出半声闷响」（143）→ bell_dull；铃终于响起来（143）→ bell_ring；
  低鸣「像从桌子底下传出来」（129）→ low_call_tape（影像里的低鸣，旧带子的音色）+ table_hum（手贴桌面感到的震动）；
  修补摊的工具「挂得叮当响」（103）→ tools_clink；管道「咕噜咕噜」（105）→ pipe_gurgle；
  邮差的袋子碰得栏杆「轻轻响」（80）→ rail_tap；计时器响起（82）→ kitchen_timer；肚子响了一声（84）→ stomach。
  bell_soft = 沙漏漏完时桌上的「一声轻铃」（87），也是剧本里她每次重新查记录的提示（87、120、130、151）。

环境声（room.json 的 ambient / 剧本的 ambient）：river_flow 6 秒、underwater 6 秒、pipe_gurgle 4 秒 —— 无缝循环
（尾巴交叉淡化进开头、起点在过零点；.import 里 loop_mode 设成 2）。tools_clink 5 秒：剧本里也当一次性音效播，
所以 .import 不设循环（设了一次性播放会停不下来）；首尾都是安静的，环境声播放器播完重播也听不出缝。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forest_story_sfx as F  # noqa: E402
from forest_story_sfx import (SR, add, band, burst, fades, loop_xfade, lp, lp_tv, mix, modal, noise,  # noqa: E402,F401
                              reverb, rotate_to_zero, tone, tt, unit, wet_room)

OUT = F.OUT
rng = np.random.default_rng(73)


def wet_river(x, wet=0.2):
    """河边：开阔、水面反一点，比林子亮一点、短一点。"""
    return reverb(x, decay=0.9, wet=wet, lo=150, hi=2600, pre=0.015, seed=17)


def env(t, a, r):
    """a 秒起、r 秒尾巴的包络（总长 = t 的长度）。"""
    T = t[-1] if len(t) else 0
    return np.clip(t / max(a, 1e-4), 0, 1) * np.clip((T - t) / max(r, 1e-4), 0, 1)


def fit(x, n):
    """补零 / 截到 n 个样本（几处 int 和 round 取整不一样，差一个样本）。"""
    return np.concatenate([x, np.zeros(max(0, n - len(x)))])[:n]


def water_grains(sec, rate, lo, hi, seed, pitch=(400, 1400)):
    """一串小水声：每一粒是一个往上滑的短正弦（水泡破 / 水滴），加一点噪声。"""
    r = np.random.default_rng(seed)
    n = int(round(sec * SR))
    x = np.zeros(n)
    for _ in range(int(sec * rate)):
        p = int(r.integers(0, max(1, n - 4000)))
        L = int(r.integers(600, 2600))
        t = np.arange(L) / SR
        f0 = r.uniform(*pitch)
        f = f0 * (1 + 1.8 * t / t[-1])
        g = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (t[-1] / 3.5)) * r.uniform(0.2, 1.0)
        x[p:p + L] += g
    return band(x, lo, hi)


# ================================================================== 河岸、飞机
def hatch_open():
    """推开舱门：门闩「咔」一下，铰链吱一小声，门外的空气 / 水声涌进来一点。"""
    sec = 1.3
    t = tt(sec)
    x = np.zeros(len(t))
    add(x, 0.02, mix(modal([(820, 0.03, 0.5), (1900, 0.02, 0.3), (3100, 0.012, 0.15)], 0.2), burst(0.03, 0.006, 800, 5000) * 0.4))
    sq = tt(0.45)
    f = 700 + 260 * np.sin(np.pi * sq / 0.45)                    # 铰链：一小声往上再往下的吱
    hinge = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    hinge *= np.sin(np.pi * sq / 0.45) ** 2 * (0.6 + 0.4 * unit(band(noise(len(sq), 3), 20, 60)))
    add(x, 0.12, band(hinge, 400, 3000), 0.22)
    air = unit(band(noise(len(t), 4), 200, 1500)) * env(t, 0.3, 0.6) * 0.18
    x += air * (t > 0.15)
    add(x, 0.25, water_grains(0.9, 10, 300, 2500, 5), 0.05)
    return wet_river(band(x, 60, 6000), 0.15)


def hatch_close():
    """关舱门：一声闷的「嗵」+ 门闩扣上的「咔哒」。"""
    sec = 0.9
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(tone(95, 0.4, 0.07, 0.9), modal([(210, 0.06, 0.5), (430, 0.04, 0.3)], 0.4), burst(0.05, 0.012, 80, 900) * 0.5))
    add(x, 0.16, mix(modal([(1100, 0.02, 0.4), (2600, 0.012, 0.25)], 0.12), burst(0.02, 0.004, 1500, 6000) * 0.3))
    add(x, 0.22, modal([(1400, 0.015, 0.3)], 0.1), 0.5)
    return band(x, 40, 6000)


def cup_clink():
    """杯子快碰到台阶（原文 75）：瓷杯碰石头，一轻一更轻两下「叮」。"""
    sec = 0.9
    x = np.zeros(int(sec * SR))
    cup = [(2350, 0.18, 0.6), (3720, 0.11, 0.35), (5480, 0.06, 0.18), (1180, 0.08, 0.15)]
    add(x, 0.0, mix(modal(cup, 0.8), burst(0.01, 0.002, 2000, 8000) * 0.3))
    add(x, 0.16, modal([(f * 1.004, d * 0.7, a) for f, d, a in cup], 0.6), 0.35)
    return wet_river(band(x, 300, 9000), 0.12)


def rope_throw():
    """丢来一捆绳子（原文 78）：甩出去的一声「呼」，落在木头上闷闷的一下，绳头再拍一下。"""
    sec = 1.2
    t = tt(sec)
    x = np.zeros(len(t))
    w = tt(0.45)
    cut = 300 + 1300 * np.sin(np.pi * w / 0.45)
    swish = lp_tv(band(noise(len(w), 8), 150, None), cut) * np.sin(np.pi * w / 0.45) ** 2
    add(x, 0.0, unit(swish), 0.5)
    add(x, 0.48, mix(tone(120, 0.25, 0.05, 0.8), burst(0.12, 0.03, 100, 1200) * 0.7, modal([(260, 0.05, 0.3)], 0.2)))
    add(x, 0.62, burst(0.06, 0.015, 300, 2500), 0.25)
    return wet_river(band(x, 50, 5000), 0.15)


def drag_plane():
    """把飞机拖到浅滩（原文 79）：沉沉的刮擦（底下是石头和沙）、水哗啦往外淌，最后停住一下。"""
    sec = 2.8
    t = tt(sec)
    n = len(t)
    pull = np.clip(t / 0.4, 0, 1) * np.clip((2.4 - t) / 0.3, 0, 1)
    grind = fit(F.drag_grains(sec, 260, 80, 1400, 21), n) * (0.6 + 0.4 * np.sin(2 * np.pi * 1.6 * t) ** 2)
    rumble = unit(band(noise(n, 22), 30, 160)) * 0.6
    slosh = water_grains(sec, 30, 200, 3000, 23, (250, 900))
    x = unit(grind) * 0.6 * pull + rumble * pull + unit(slosh) * 0.35 * np.clip(t / 0.8, 0, 1) * np.clip((sec - t) / 0.6, 0, 1)
    add(x, 2.35, mix(tone(70, 0.4, 0.09, 0.7), burst(0.15, 0.04, 60, 700) * 0.5))
    return wet_river(band(x, 30, 4000), 0.18)


def drip():
    """缝隙里往外滴的水（原文 79）：三滴，一滴比一滴慢，落在水面上「嘀」。"""
    sec = 1.6
    x = np.zeros(int(sec * SR))
    for at, f0, a in ((0.05, 900, 0.9), (0.55, 760, 0.7), (1.2, 820, 0.55)):
        t = tt(0.12)
        f = f0 * (1 + 2.2 * t / t[-1])
        d = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.03)
        add(x, at, d, a)
        add(x, at, burst(0.01, 0.002, 1500, 6000), 0.15 * a)
    return wet_river(band(x, 300, 7000), 0.25)


def rail_tap():
    """邮差的袋子碰得栏杆轻轻响（原文 80）：远处铁栏杆两下很轻的「当」，有点空。"""
    sec = 1.2
    x = np.zeros(int(sec * SR))
    rail = [(640, 0.35, 0.5), (1720, 0.2, 0.3), (2980, 0.1, 0.15)]
    add(x, 0.02, mix(modal(rail, 0.9), burst(0.02, 0.004, 400, 3000) * 0.2))
    add(x, 0.34, modal(rail, 0.8), 0.6)
    x = lp(x, 2500)                                              # 远：高频少一点
    return wet_river(band(x, 200, 4000), 0.3)


# ================================================================== 妮芙家
def kitchen_timer():
    """计时器响起（原文 82）：发条小铃，铃锤快敲 1.1 秒，有点旧、不刺耳；最后发条转完「嗒」一下。"""
    sec = 1.7
    x = np.zeros(int(sec * SR))
    bell = [(2650, 0.25, 0.5), (3980, 0.15, 0.3), (6100, 0.06, 0.1), (1330, 0.2, 0.15)]
    k = 0
    while k / 15 < 1.1:
        add(x, 0.02 + k / 15, mix(modal(bell, 0.3), burst(0.004, 0.001, 2000, 7000) * 0.2), 0.55 + 0.1 * (k % 2))
        k += 1
    add(x, 1.2, modal([(1200, 0.02, 0.3), (2500, 0.01, 0.2)], 0.1), 0.35)
    return wet_room(band(lp(x, 5000), 600, 8000), 0.18)


def stomach():
    """肚子响了一声（原文 84）：低低的咕噜，往上挑一下，有点好笑但不夸张。"""
    sec = 1.1
    t = tt(sec)
    f = 140 + 60 * np.sin(np.pi * np.clip(t / 0.7, 0, 1)) + 25 * np.sin(2 * np.pi * 7 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    g = (0.5 + 0.5 * np.sin(2 * np.pi * 11 * t)) ** 2                  # 一串咕噜咕噜
    x = (np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)) * g
    x += unit(band(noise(len(t), 31), 100, 600)) * 0.3 * g
    x *= env(t, 0.06, 0.4)
    return wet_room(band(x, 70, 1500), 0.1)


def cup_scrape():
    """杯子在木桌上挪（原文 84，晨假装是杯底擦过桌面）：短的一声「嗞——」，带一点木头的闷。"""
    sec = 0.6
    t = tt(sec)
    g = 0.4 + unit(lp(np.abs(noise(len(t), 33)), 120)) ** 2
    x = unit(band(noise(len(t), 34), 600, 3200)) * g * np.sin(np.pi * np.clip(t / 0.45, 0, 1)) ** 0.7
    x += unit(band(noise(len(t), 35), 120, 500)) * 0.35 * np.sin(np.pi * np.clip(t / 0.45, 0, 1))
    return wet_room(band(x, 100, 5000), 0.12)


def bell_soft():
    """桌上的一声轻铃（原文 87）：小铜铃、一下，不急，余音慢慢散；全章最常听到的提示，所以轻、圆、不刺。"""
    sec = 2.2
    x = np.zeros(int(sec * SR))
    partials = [(1568, 0.9, 0.7), (1572, 0.85, 0.35), (3770, 0.45, 0.25), (5240, 0.22, 0.1), (784, 0.6, 0.12)]
    add(x, 0.01, mix(modal(partials, 2.1, attack=0.002), burst(0.006, 0.0015, 2500, 7000) * 0.08))
    return wet_room(band(x, 400, 7000), 0.22)


def chair_drag():
    """搬来一把椅子（原文 92）：木椅腿在木地板上蹭两下，放下「笃」。"""
    sec = 1.0
    t = tt(sec)
    x = np.zeros(len(t))
    for at, d in ((0.0, 0.3), (0.38, 0.25)):
        s = tt(d)
        g = 0.3 + unit(lp(np.abs(noise(len(s), int(at * 100) + 40)), 60)) ** 2
        add(x, at, unit(band(noise(len(s), 41), 200, 1600)) * g * np.sin(np.pi * s / d), 0.6)
    add(x, 0.7, mix(tone(150, 0.2, 0.04, 0.7), modal([(320, 0.05, 0.4), (610, 0.03, 0.2)], 0.15), burst(0.03, 0.008, 150, 1500) * 0.4))
    return wet_room(band(x, 60, 5000), 0.14)


def pencil():
    """写几个字（原文 93：在鹿角旁添了两根细枝）：铅笔沙沙的短笔画。"""
    x = F.pen_strokes([(0.0, 0.12, 0.8), (0.18, 0.09, 0.7), (0.33, 0.16, 0.9), (0.56, 0.07, 0.6), (0.7, 0.2, 0.8)],
                      1800, 6000, 51, body=0.15)
    return wet_room(band(x, 400, 8000), 0.08)


def tape_motor(sec, seed, f0=118):
    """旧播放器的马达：低嗡 + 一点点抖（wow）+ 带子的嘶。"""
    t = tt(sec)
    f = f0 * (1 + 0.012 * np.sin(2 * np.pi * 0.9 * t) + 0.004 * np.sin(2 * np.pi * 7 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    hum = 0.5 * np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)
    hiss = unit(band(noise(len(t), seed), 2500, 9000)) * 0.18
    return hum * 0.5 + hiss


def tape_run():
    """影像开始放（原文 97）：机子「咔」地合上，马达转起来，带子沙沙走。"""
    sec = 2.2
    t = tt(sec)
    x = tape_motor(sec, 61) * np.clip((t - 0.08) / 0.35, 0, 1) * np.clip((sec - t) / 0.4, 0, 1)
    add(x, 0.0, mix(modal([(900, 0.03, 0.5), (2100, 0.015, 0.3)], 0.15), burst(0.02, 0.004, 900, 6000) * 0.4))
    return wet_room(band(x, 70, 9000), 0.1)


def table_knock():
    """膝盖碰响了桌腿（原文 97）：闷的一声木头「咚」，桌上的碗跟着轻轻一磕。"""
    sec = 0.8
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(tone(110, 0.3, 0.06, 0.9), modal([(240, 0.08, 0.6), (520, 0.05, 0.3), (980, 0.02, 0.15)], 0.4),
                    burst(0.04, 0.01, 100, 1500) * 0.5))
    add(x, 0.03, modal([(2350, 0.08, 0.3), (3700, 0.05, 0.15)], 0.3), 0.25)
    add(x, 0.07, modal([(2600, 0.06, 0.2)], 0.25), 0.15)
    return wet_room(band(x, 50, 7000), 0.15)


def tape_glitch():
    """画面闪出白纹、声音断掉、播放器停了（原文 97）：嘶声一抽一抽地断，马达往下掉，「咔」停住。"""
    sec = 1.5
    t = tt(sec)
    n = len(t)
    gate = (np.sin(2 * np.pi * (9 + 14 * t) * t) > 0.2).astype(float)
    hiss = unit(band(noise(n, 71), 800, 9000)) * gate * np.clip((1.0 - t) / 0.2, 0, 1)
    f = 118 * np.clip(1 - (t - 0.6) / 0.55, 0.2, 1)
    ph = 2 * np.pi * np.cumsum(f) / SR
    motor = (0.5 * np.sin(ph) + 0.2 * np.sin(2 * ph)) * np.clip((1.15 - t) / 0.55, 0, 1)
    x = hiss * 0.5 + motor * 0.45
    for at in (0.18, 0.42, 0.7):
        add(x, at, burst(0.05, 0.012, 1500, 9000), 0.4)
    add(x, 1.18, mix(modal([(800, 0.03, 0.5), (1900, 0.015, 0.3)], 0.12), burst(0.02, 0.004, 900, 5000) * 0.3))
    return wet_room(band(x, 60, 9000), 0.1)


def button():
    """按播放键（原文 98「连按几次」）：塑料键按下去的短「嗒」，有一点弹簧。"""
    sec = 0.25
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(modal([(1600, 0.012, 0.6), (3300, 0.008, 0.35), (820, 0.02, 0.2)], 0.1), burst(0.008, 0.002, 1500, 7000) * 0.4))
    add(x, 0.06, modal([(1450, 0.01, 0.3), (2900, 0.006, 0.15)], 0.08), 0.4)
    return wet_room(band(x, 300, 9000), 0.08)


def click():
    """新的读取头装上去（原文 124）：金属件扣进卡槽，清脆的「咔」。"""
    sec = 0.3
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(modal([(2100, 0.02, 0.6), (4600, 0.01, 0.3), (1050, 0.03, 0.2)], 0.15), burst(0.006, 0.0015, 2000, 9000) * 0.5))
    add(x, 0.035, modal([(2400, 0.012, 0.3)], 0.1), 0.6)
    return wet_room(band(x, 400, 10000), 0.08)


def lofi(x, seed, lo=260, hi=2600):
    """旧带子的音色：窄带、一点抖（wow）、一层嘶。"""
    t = np.arange(len(x)) / SR
    rate = 1 + 0.008 * np.sin(2 * np.pi * 0.7 * t) + 0.003 * np.sin(2 * np.pi * 5.5 * t)
    y = F.warp(x, rate)
    y = np.concatenate([y, np.zeros(len(x) - len(y))]) if len(y) < len(x) else y[:len(x)]
    y = band(y, lo, hi, order=3)
    y = np.tanh(unit(y) * 1.6) * 0.8
    return y + unit(band(noise(len(x), seed), 2000, 8000)) * 0.06


def low_call_tape():
    """影像里的低鸣（原文 124、129）：和森林里的低鸣同一个合成（elephant_voice），但隔着旧带子：
    窄带、抖、带着嘶，还有一点从水面传过来的空；很低，「像从桌子底下传出来」。"""
    sec = 4.0
    v = F.elephant_voice(3.4, seed=8)
    x = np.zeros(int(sec * SR))
    add(x, 0.12, v)
    dry = x.copy()
    add(x, 0.35, lp(dry, 900, 2), 0.25)                          # 水面上的回声
    x = lofi(x, 81, lo=110, hi=2200)
    t = tt(sec)
    x += unit(band(noise(len(t), 82), 3000, 9000)) * 0.04
    return wet_room(x * np.clip((sec - t) / 0.4, 0, 1) * np.clip(t / 0.05, 0, 1), 0.12)


def tape_rewind():
    """倒带（原文 97「倒回去」、125–128 一遍遍重放）：马达拔高的「嗞——」，尾巴「咔」停住。"""
    sec = 1.1
    t = tt(sec)
    f = 300 + 900 * np.clip(t / 0.25, 0, 1) - 150 * np.clip((t - 0.7) / 0.2, 0, 1)
    ph = 2 * np.pi * np.cumsum(f) / SR
    whirr = (0.5 * np.sin(ph) + 0.25 * np.sin(2 * ph)) * (0.7 + 0.3 * np.sin(2 * np.pi * 31 * t))
    chat = unit(band(noise(len(t), 91), 1500, 7000)) * 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * 47 * t))
    x = (whirr * 0.35 + chat) * np.clip(t / 0.05, 0, 1) * np.clip((0.92 - t) / 0.08, 0, 1)
    add(x, 0.92, mix(modal([(900, 0.03, 0.5), (2000, 0.015, 0.3)], 0.15), burst(0.015, 0.003, 1000, 6000) * 0.3))
    return wet_room(band(x, 100, 9000), 0.08)


def tape_noise():
    """调杂音（原文 129）：嘶声里一阵阵沙沙、偶尔噼啪，调着调着慢慢干净一点。"""
    sec = 1.8
    t = tt(sec)
    n = len(t)
    cut = 6000 - 3500 * np.clip(t / sec, 0, 1)
    hiss = lp_tv(band(noise(n, 101), 1500, None), cut)
    sweep = (0.6 + 0.4 * np.sin(2 * np.pi * 2.3 * t)) * env(t, 0.1, 0.3)
    x = unit(hiss) * 0.5 * sweep
    r = np.random.default_rng(102)
    for _ in range(9):
        add(x, r.uniform(0.05, sec - 0.2), burst(0.01, 0.002, 1500, 8000), r.uniform(0.1, 0.3))
    x += tape_motor(sec, 103) * 0.15 * env(t, 0.1, 0.3)
    return wet_room(band(x, 80, 9000), 0.08)


def table_hum():
    """手掌贴在桌面上，能感觉到一点震动（原文 129）：极低的嗡（40~60Hz）+ 木头的共鸣，几乎是摸得到不是听得到。"""
    sec = 1.8
    t = tt(sec)
    f = 48 + 6 * np.sin(np.pi * t / sec)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * 0.8 + 0.35 * np.sin(2 * ph) + 0.18 * np.sin(3 * ph + 0.4)
    x *= np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 1.5
    wood = band(noise(len(t), 111), 150, 420) * np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 2
    x = x + unit(wood) * 0.12
    return wet_room(band(x, 30, 900), 0.1)


def phone_shutter():
    """用通讯器拍照（原文 134）：很轻的电子「咔嚓」，两下。"""
    sec = 0.35
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(burst(0.03, 0.006, 1500, 8000) * 0.5, modal([(2800, 0.01, 0.3)], 0.05)))
    add(x, 0.07, mix(burst(0.04, 0.01, 1000, 6000) * 0.4, modal([(1900, 0.012, 0.25)], 0.06)))
    return wet_room(band(x, 600, 10000), 0.06)


# ================================================================== 市集、旧街、仓库
def market_bustle():
    """到了高处市集（原文 103「比河岸热闹」）：一层听不清的人声、脚步、远处吆喝一声、篮子吱呀，4 秒，进出淡入淡出。"""
    sec = 4.0
    t = tt(sec)
    n = len(t)
    r = np.random.default_rng(121)
    babble = np.zeros(n)
    for k in range(6):                                           # 几个人的「嗡嗡」：带共振峰的噪声，音节一样的起伏
        syl = (0.5 + 0.5 * np.sin(2 * np.pi * r.uniform(3, 5) * t + r.uniform(0, 6))) ** 2
        v = band(noise(n, 122 + k), r.uniform(250, 400), r.uniform(900, 1500))
        babble += unit(v) * syl * r.uniform(0.4, 1.0)
    x = unit(babble) * 0.5
    for i in range(10):                                          # 脚步
        add(x, 0.15 + i * 0.37 + r.uniform(-0.04, 0.04), mix(tone(130, 0.08, 0.025, 0.5), burst(0.04, 0.01, 200, 2000) * 0.4), 0.3)
    add(x, 1.6, lofi(band(noise(int(0.5 * SR), 125), 400, 1200) * np.sin(np.pi * tt(0.5) / 0.5), 126, 400, 1600), 0.25)
    add(x, 2.6, mix(modal([(1700, 0.12, 0.3), (2600, 0.08, 0.2)], 0.3)), 0.15)   # 远处工具叮一声
    x *= env(t, 0.6, 0.9)
    return wet_river(band(x, 120, 5000), 0.25)


def tank_set():
    """摊主把气瓶放到柜台上（原文 103）：空心铁瓶碰木头，「当」一声闷的、有一点余音。"""
    sec = 1.1
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(modal([(520, 0.35, 0.5), (1310, 0.2, 0.35), (2470, 0.1, 0.2), (3600, 0.05, 0.08)], 1.0),
                    tone(140, 0.25, 0.05, 0.6), burst(0.03, 0.008, 150, 2500) * 0.4))
    add(x, 0.09, modal([(520, 0.1, 0.2)], 0.3), 0.3)
    return wet_river(band(x, 80, 7000), 0.15)


def tools_clink():
    """修补摊的工具挂得叮当响（原文 103）：几件挂着的铁家伙互相碰，随手的几下，5 秒；首尾安静（环境声重播听不出缝）。"""
    sec = 5.0
    x = np.zeros(int(sec * SR))
    r = np.random.default_rng(131)
    tools = [[(1180, 0.25, 0.5), (2900, 0.12, 0.25)], [(1650, 0.3, 0.5), (3900, 0.1, 0.2)],
             [(860, 0.35, 0.5), (2240, 0.15, 0.3)], [(2200, 0.18, 0.4), (5100, 0.06, 0.15)]]
    at = 0.25
    while at < sec - 0.7:
        tl = tools[int(r.integers(0, len(tools)))]
        detune = r.uniform(0.98, 1.02)
        add(x, at, mix(modal([(f * detune, d, a) for f, d, a in tl], 0.8), burst(0.005, 0.001, 1500, 8000) * 0.15),
            r.uniform(0.3, 0.9))
        if r.random() < 0.4:                                      # 碰完又回弹一下
            add(x, at + r.uniform(0.06, 0.12), modal([(f * detune, d * 0.6, a) for f, d, a in tl], 0.5), 0.3)
        at += r.uniform(0.25, 0.9)
    return wet_river(band(x, 400, 8000), 0.25)


def sluice_turn():
    """转闸轮（原文 105–106）：铁轮子一格一格的棘爪「咯、咯、咯」，底下一声铁的呻吟。"""
    sec = 1.6
    t = tt(sec)
    x = np.zeros(len(t))
    for k in range(6):
        add(x, 0.05 + k * 0.2, mix(modal([(1500, 0.03, 0.5), (3200, 0.015, 0.25), (700, 0.04, 0.2)], 0.12),
                                    burst(0.01, 0.003, 800, 6000) * 0.3), 0.5 + 0.1 * (k % 2))
    f = 180 + 30 * np.sin(np.pi * np.clip(t / 1.3, 0, 1))
    groan = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.6 + 0.4 * unit(band(noise(len(t), 141), 15, 40)))
    x += band(groan, 120, 1200) * 0.3 * np.sin(np.pi * np.clip(t / 1.35, 0, 1)) ** 1.5
    return wet_river(band(x, 80, 7000), 0.2)


def water_drop():
    """水位往下落（原文 106）：管道里一口气泄下去的「咕——噜」，水面往下退的哗。"""
    sec = 1.8
    t = tt(sec)
    n = len(t)
    glug = water_grains(sec, 22, 120, 1800, 151, (150, 500)) * np.clip((1.3 - t) / 0.5, 0, 1)
    rush = lp_tv(band(noise(n, 152), 100, None), 1600 - 1100 * np.clip(t / sec, 0, 1))
    x = unit(glug) * 0.6 + unit(rush) * 0.4 * env(t, 0.15, 0.8)
    return wet_river(band(x, 60, 4000), 0.22)


def sluice_open():
    """第二道闸打开、旧街露出来（原文 106–108）：闸门「哐」一下松开，水哗哗往外走，慢慢小下去。"""
    sec = 2.8
    t = tt(sec)
    n = len(t)
    x = np.zeros(n)
    add(x, 0.0, mix(modal([(240, 0.3, 0.6), (610, 0.2, 0.4), (1330, 0.1, 0.2)], 0.8), tone(80, 0.4, 0.08, 0.7),
                    burst(0.06, 0.015, 100, 2000) * 0.5))
    rush = lp_tv(band(noise(n, 161), 120, None), 2200 - 1400 * np.clip((t - 0.3) / 2.3, 0, 1))
    x += unit(rush) * 0.6 * np.clip((t - 0.15) / 0.3, 0, 1) * np.clip((sec - t) / 1.6, 0, 1)
    x += unit(water_grains(sec, 25, 200, 3000, 162)) * 0.25 * np.clip((sec - t) / 1.2, 0, 1)
    return wet_river(band(x, 50, 5000), 0.22)


def splash_in():
    """下水（原文 110）：入水的「哗」，然后声音一下子闷下去，几串气泡往上走。"""
    sec = 1.8
    t = tt(sec)
    n = len(t)
    x = np.zeros(n)
    sp = tt(0.5)
    add(x, 0.0, unit(lp_tv(band(noise(len(sp), 171), 150, None), 3500 - 2800 * sp / 0.5)) * np.exp(-sp / 0.14), 0.8)
    add(x, 0.02, tone(90, 0.3, 0.08, 0.6))
    bub = water_grains(1.4, 18, 200, 1500, 172, (300, 900))
    add(x, 0.3, lp(unit(bub), 1200), 0.35)
    x += unit(band(noise(n, 173), 40, 300)) * 0.18 * np.clip((t - 0.25) / 0.2, 0, 1) * np.clip((sec - t) / 0.5, 0, 1)
    return band(x, 35, 6000)


def bell_dull():
    """铃舌被泥堵住，只能发出半声闷响（原文 143）：铜铃被捂住的「笃」，没有余音。"""
    sec = 0.6
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(modal([(1180, 0.05, 0.5), (2830, 0.025, 0.2), (590, 0.06, 0.3)], 0.4), tone(220, 0.15, 0.03, 0.4),
                    burst(0.02, 0.005, 300, 2500) * 0.3))
    return wet_river(band(lp(x, 2500), 150, 4000), 0.12)


def water_rinse():
    """把泥洗净（原文 143）：手在水里涮铃，水哗啦几下、滴答落回去。"""
    sec = 1.6
    t = tt(sec)
    n = len(t)
    x = np.zeros(n)
    for k, at in enumerate((0.0, 0.42, 0.85)):
        s = tt(0.4)
        sw = lp_tv(band(noise(len(s), 181 + k), 200, None), 1200 + 1400 * np.sin(np.pi * s / 0.4))
        add(x, at, unit(sw) * np.sin(np.pi * s / 0.4) ** 1.5, 0.6)
    x += unit(water_grains(sec, 30, 300, 3500, 185)) * 0.25 * np.clip((sec - t) / 0.5, 0, 1)
    return wet_river(band(x, 100, 6000), 0.2)


def bell_ring():
    """铃终于响起来（原文 143）：清清楚楚的一声铜铃，比桌上的轻铃大、暖、余音长；摇了两下（第二下轻）。"""
    sec = 3.0
    x = np.zeros(int(sec * SR))
    pb = [(1046, 1.3, 0.7), (1050, 1.2, 0.35), (2510, 0.7, 0.35), (3480, 0.4, 0.15), (523, 0.9, 0.2), (4920, 0.2, 0.06)]
    add(x, 0.01, mix(modal(pb, 2.9, attack=0.0015), burst(0.006, 0.0015, 2000, 8000) * 0.1))
    add(x, 0.36, modal([(f * 1.001, d, a * 0.5) for f, d, a in pb], 2.6, attack=0.0015))
    return wet_river(band(x, 300, 8000), 0.25)


# ================================================================== 起飞
def engine_idle():
    """晨把发动机保持在怠速等她（原文 151）：低低的、稳的嗡，有一点抖，3 秒，进出都缓。"""
    sec = 3.0
    t = tt(sec)
    f = 46 + 1.2 * np.sin(2 * np.pi * 0.6 * t)
    x = F.drone(t, f, 0.0) * env(t, 0.5, 0.8)
    x *= 1 + 0.06 * np.sin(2 * np.pi * 7.5 * t)
    x += unit(band(noise(len(t), 191), 100, 600)) * 0.07 * env(t, 0.5, 0.8)
    return band(x, 30, 2500)


def engine_up():
    """关好舱门、飞机升高（原文 152）：嗡声往上走、变满，气流涌起来，最后稳在高处（不飞远，接驾驶舱里）。"""
    sec = 3.2
    t = tt(sec)
    rise = np.clip(t / 2.4, 0, 1)
    f = 46 + 26 * rise ** 1.3
    x = F.drone(t, f, rise) * (0.7 + 0.3 * rise) * np.clip(t / 0.3, 0, 1) * np.clip((sec - t) / 0.6, 0, 1)
    air = lp_tv(band(noise(len(t), 201), 120, None), 400 + 1200 * rise)
    x += unit(air) * (0.1 + 0.3 * rise) * np.clip((sec - t) / 0.6, 0, 1)
    return wet_river(band(x, 30, 3500), 0.12)


# ================================================================== 环境声（无缝循环）
def make_loop(fn, n_sec, xf_sec=0.6):
    n, xf = int(n_sec * SR), int(xf_sec * SR)
    x = fn(n_sec + xf_sec + 0.2)
    return rotate_to_zero(loop_xfade(x, n, xf))


def _river(sec):
    """河水（水道、桥洞，原文 72、136）：持续的流水声（低频的推 + 中频的哗），慢慢起伏，偶尔一串小水泡。"""
    t = tt(sec)
    n = len(t)
    body = band(noise(n, 211), 80, 700)
    surf = lp_tv(band(noise(n, 212), 500, None), 1700 + 500 * np.sin(2 * np.pi * 0.23 * t))
    mod = 0.75 + 0.25 * np.sin(2 * np.pi * 0.17 * t) * np.sin(2 * np.pi * 0.41 * t + 1)
    x = unit(body) * 0.55 * mod + unit(surf) * 0.3 * (1.1 - mod * 0.3)
    x += unit(water_grains(sec, 6, 300, 2500, 213)) * 0.15
    return wet_river(band(x, 50, 5000), 0.2)


def _underwater(sec):
    """水下仓库（原文 111）：很闷的低频（耳朵里的水压）、远处水流的嗡，偶尔一串气泡往上走；不吓人。"""
    t = tt(sec)
    n = len(t)
    rum = band(noise(n, 221), 25, 180)
    mod = 0.8 + 0.2 * np.sin(2 * np.pi * 0.11 * t)
    x = unit(rum) * 0.7 * mod
    x += np.sin(2 * np.pi * 52 * t) * 0.06 * mod
    bub = water_grains(sec, 2.2, 250, 1400, 222, (350, 800))
    x += lp(unit(bub), 1100) * 0.3
    return band(x, 25, 1500)


def _gurgle(sec):
    """管道里咕噜咕噜（原文 105）：管子里一串一串冒泡，空腔共鸣（管子的空心声），节奏不匀。"""
    t = tt(sec)
    n = len(t)
    r = np.random.default_rng(231)
    x = np.zeros(n)
    at = 0.05
    while at < sec - 0.3:
        L = int(r.uniform(0.05, 0.12) * SR)
        s = np.arange(L) / SR
        f0 = r.uniform(160, 320)
        f = f0 * (1 + 0.9 * s / s[-1])
        g = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.clip(np.sin(np.pi * s / s[-1]), 0, 1) ** 1.2
        add(x, at, g, r.uniform(0.4, 1.0))
        at += r.uniform(0.07, 0.22) if r.random() < 0.75 else r.uniform(0.35, 0.6)
    x = F.peak_eq(x, 420, 6, 1.5)
    x += unit(band(noise(n, 232), 80, 400)) * 0.12
    x = reverb(x, decay=0.35, wet=0.35, lo=150, hi=1500, pre=0.004, seed=233)   # 管子里的空
    return band(x, 70, 3000)


JOBS = [
    ("hatch_open", hatch_open, 0.5),
    ("hatch_close", hatch_close, 0.55),
    ("cup_clink", cup_clink, 0.32),
    ("rope_throw", rope_throw, 0.5),
    ("drag_plane", drag_plane, 0.6),
    ("drip", drip, 0.35),
    ("rail_tap", rail_tap, 0.3),
    ("kitchen_timer", kitchen_timer, 0.3),
    ("stomach", stomach, 0.4),
    ("cup_scrape", cup_scrape, 0.3),
    ("bell_soft", bell_soft, 0.32),
    ("chair_drag", chair_drag, 0.45),
    ("pencil", pencil, 0.2),
    ("tape_run", tape_run, 0.4),
    ("table_knock", table_knock, 0.55),
    ("tape_glitch", tape_glitch, 0.45),
    ("button", button, 0.35),
    ("click", click, 0.35),
    ("low_call_tape", low_call_tape, 0.55),
    ("tape_rewind", tape_rewind, 0.35),
    ("tape_noise", tape_noise, 0.35),
    ("table_hum", table_hum, 0.4),
    ("phone_shutter", phone_shutter, 0.3),
    ("market_bustle", market_bustle, 0.45),
    ("tank_set", tank_set, 0.5),
    ("tools_clink", tools_clink, 0.4),
    ("sluice_turn", sluice_turn, 0.5),
    ("water_drop", water_drop, 0.5),
    ("sluice_open", sluice_open, 0.6),
    ("splash_in", splash_in, 0.6),
    ("bell_dull", bell_dull, 0.4),
    ("water_rinse", water_rinse, 0.4),
    ("bell_ring", bell_ring, 0.45),
    ("engine_idle", engine_idle, 0.55),
    ("engine_up", engine_up, 0.6),
    ("river_flow", lambda: make_loop(_river, 6.0), 0.5),
    ("underwater", lambda: make_loop(_underwater, 6.0), 0.5),
    ("pipe_gurgle", lambda: make_loop(_gurgle, 4.0, 0.3), 0.45),
]
LOOPS = {"river_flow", "underwater", "pipe_gurgle"}           # .import 设 loop_mode=2（tools_clink 不设，见文件头）
KEEP = {"wrench"}                                              # 已有、不重做


def set_loop_imports():
    """Godot 导入过以后，给三个环境声的 .import 设上无缝循环（没有 .import 就跳过：先跑一次 --headless --import 再跑本脚本）。"""
    for name in sorted(LOOPS):
        p = OUT / f"{name}.wav.import"
        if not p.exists():
            print(f"  {p.name} 还没有（先 --headless --import）")
            continue
        s = p.read_text()
        if "edit/loop_mode=2" not in s:
            s = s.replace("edit/loop_mode=0", "edit/loop_mode=2")
            p.write_text(s)
            print(f"  {p.name}：loop_mode=2")


def main():
    for name, fn, pk in JOBS:
        assert name not in KEEP
        F.save(name, fn(), pk, loop=name in LOOPS)
    F.report()
    set_loop_imports()


if __name__ == "__main__":
    main()
