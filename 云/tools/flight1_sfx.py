"""飞行段一（data/story_flight1.json，驾驶舱）的音效，全部程序生成；以后换正式的，文件名不变即可。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/flight1_sfx.py

合成工具（tt / band / modal / burst / reverb / loop_xfade …）直接用 tools/forest_story_sfx.py 里的，方向一样：
安静、克制、偏低频、不刺耳。驾驶舱是一个小小的铁皮舱：混响短、偏亮一点点（cabin()）。
输出 audio/sfx/*.wav（44.1kHz 16 位；debris_pass_l / debris_pass_r 是立体声、自带方位，其余单声道）。

循环（.import 里要 edit/loop_mode=2，脚本跑完自己改好已经存在的 .import；第一次没有 .import 时，
Godot 导入后再跑一次本脚本，或者手动改）：
  hiss_thin     3.0 秒：右侧接口漏气的细白汽声（ambient，放在 cockpit_leak 上）。
  airflow_loop  6.0 秒：避碎石时平稳的气流（窗外那条淡淡的气流线）。
"""
from __future__ import annotations

import re
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forest_story_sfx as F  # noqa: E402
from forest_story_sfx import (SR, add, band, burst, fades, loop_xfade, lp, mix, modal, noise, peak_eq,  # noqa: E402
                              reverb, rotate_to_zero, tone, tt, unit, warp)

OUT = F.OUT
rng = np.random.default_rng(1029)


def cabin(x, wet=0.14):
    """驾驶舱：小铁皮舱，短、有一点金属味。"""
    return reverb(x, decay=0.42, wet=wet, lo=180, hi=3600, pre=0.004, seed=29)


def nz(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def beep(f, dur, amp=1.0, soft=0.012, harm=0.12):
    """柔一点的提示音：正弦 + 很少的三次谐波，起落都有一点斜坡。"""
    t = tt(dur + 0.02)
    ph = 2 * np.pi * f * t
    x = np.sin(ph) + harm * np.sin(3 * ph)
    e = np.clip(t / soft, 0, 1) * np.clip((dur - t) / 0.025, 0, 1)
    return x * e * amp


def thump(sec, f0, decay, seed, hi=900):
    """闷的一下：低频衰减的正弦（音高往下掉一点）+ 一小团低通噪声。"""
    t = tt(sec)
    f = f0 * (1 + 0.6 * np.exp(-t / 0.015))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    x += 0.4 * unit(band(nz(len(t), seed), 40, hi)) * np.exp(-t / (decay * 0.4))
    return x


# ================================================================== 警报
def alarm():
    """进场时的告警（不是坠毁那个坏掉的警报）：隔着机壳的「嘀—嘟」，五组，越来越急一点，最后一组拖尾。约 4 秒。"""
    sec = 4.4
    x = np.zeros(int(sec * SR))
    HI, LO = 660, 554
    at = 0.05
    for k in range(5):
        gap = 0.40 - 0.04 * k
        add(x, at, beep(HI, 0.16, 1.0))
        add(x, at + 0.2, beep(LO, 0.18 if k < 4 else 0.32, 0.9))
        at += 0.2 + gap + 0.18
    x = band(x, 250, 1600)
    return cabin(x, 0.16)


def alarm_stop():
    """警报停：最后半声被掐断，继电器「咔」一下，一点电流声往下掉。"""
    x = np.zeros(int(1.0 * SR))
    add(x, 0.0, beep(660, 0.07, 0.8))
    add(x, 0.075, modal([(1700, 0.006, 0.5), (620, 0.02, 0.4), (2900, 0.003, 0.2)], 0.12))
    t = tt(0.6)
    hum = (np.sin(2 * np.pi * 100 * t) + 0.4 * np.sin(2 * np.pi * 200 * t)) * np.exp(-t / 0.15) * 0.18
    add(x, 0.08, hum)
    return cabin(band(x, 80, 3000), 0.12)


# ================================================================== 本子、笔、卡
def book_close():
    """合上本子：纸页扇一下的风声 + 封皮合上的软「啪」。"""
    x = np.zeros(int(0.6 * SR))
    t = tt(0.12)
    add(x, 0.0, unit(band(nz(len(t), 3), 600, 3500)) * np.sin(np.pi * t / 0.12) ** 2 * 0.25)
    add(x, 0.11, thump(0.3, 180, 0.03, 4, 1800) * 0.9)
    add(x, 0.11, burst(0.02, 0.003, 800, 3000) * 0.25)
    return cabin(band(x, 90, 4000), 0.1)


def pen_tap():
    """笔帽在本子上点三下（轻、木木的）。"""
    x = np.zeros(int(0.7 * SR))
    for i, at in enumerate((0.0, 0.17, 0.30)):
        add(x, at, mix(modal([(1450, 0.008, 0.4), (2600, 0.004, 0.15), (520, 0.012, 0.3)], 0.06),
                       burst(0.005, 0.001, 900, 3500) * 0.2), 1.0 - 0.15 * i)
    return cabin(band(x, 250, 4000), 0.08)


def card_beep():
    """通勤卡：贴上去的一声老读卡器「嘀」（短、圆，不刺耳），前面一点塑料碰到的「嗒」。"""
    x = np.zeros(int(0.5 * SR))
    add(x, 0.0, modal([(1900, 0.004, 0.3), (700, 0.01, 0.25)], 0.04))
    add(x, 0.06, beep(1175, 0.13, 0.8, soft=0.006, harm=0.05))
    return cabin(band(x, 300, 3200), 0.12)


# ================================================================== 转化装置
def converter_burn():
    """转化装置烧东西：盖子里「呼」地一下点着（低的、闷的），然后一阵暖暖的低吼和细碎的噼啪，慢慢稳下来。约 2.6 秒。"""
    sec = 2.8
    t = tt(sec)
    n = len(t)
    whoomp = unit(band(nz(n, 11), 40, 400)) * np.clip(t / 0.08, 0, 1) * np.exp(-t / 0.35)
    roar_e = np.clip((t - 0.05) / 0.3, 0, 1) * (0.55 + 0.45 * np.exp(-t / 0.8)) * np.clip((sec - t) / 0.9, 0, 1)
    roar = unit(band(nz(n, 12), 60, 700)) * roar_e * (1 + 0.25 * unit(lp(nz(n, 13), 5)))
    x = whoomp * 0.8 + roar * 0.45
    r = np.random.default_rng(14)
    for _ in range(14):
        at = float(r.uniform(0.2, 2.3))
        add(x, at, burst(0.02, 0.003, 900, 3000) * float(r.uniform(0.04, 0.12)))
    x = peak_eq(x, 120, 3)
    return cabin(band(x, 35, 2600), 0.18)


def drop_in():
    """东西放进转化装置：落进铁槽的一下轻碰 + 滑下去的小摩擦 + 盖子轻轻落下的闷响。"""
    x = np.zeros(int(1.0 * SR))
    add(x, 0.0, modal([(1250, 0.03, 0.4), (2300, 0.015, 0.2), (480, 0.05, 0.4)], 0.25))
    tl = tt(0.25)
    add(x, 0.06, unit(band(nz(len(tl), 21), 700, 2500)) * np.sin(np.pi * tl / 0.25) * 0.12)
    add(x, 0.42, thump(0.4, 120, 0.05, 22, 1200) * 0.6)
    add(x, 0.42, modal([(820, 0.03, 0.2), (1500, 0.015, 0.1)], 0.2))
    return cabin(band(x, 70, 3800), 0.16)


def crumbs():
    """抖背包：帆布哗啦两下，几粒碎屑落在铁地板上（很轻的沙沙 + 几颗小点）。"""
    x = np.zeros(int(1.2 * SR))
    for at in (0.0, 0.28):
        tl = tt(0.22)
        add(x, at, unit(band(nz(len(tl), int(at * 100) + 31), 300, 2200)) * np.sin(np.pi * tl / 0.22) ** 1.5 * 0.35)
    r = np.random.default_rng(32)
    for _ in range(16):
        at = float(r.uniform(0.35, 1.0))
        add(x, at, modal([(float(r.uniform(2500, 4200)), 0.004, 0.2)], 0.02) * float(r.uniform(0.2, 0.6)))
    return cabin(band(x, 200, 5000), 0.1)


# ================================================================== 发动机
def engine_tone(f, t, bright=0.4):
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.5 * np.sin(2 * ph) + bright * 0.3 * np.sin(3 * ph)
    x *= 1 + 0.15 * np.sin(ph / 6)
    return x


def engine_boost():
    """多了燃料：发动机从低往上提一档（音高慢慢升、更满），带一点气流，最后稳在高一点的地方。约 2.8 秒。"""
    sec = 3.0
    t = tt(sec)
    f = 62 + 30 / (1 + np.exp(-(t - 1.0) / 0.3))
    x = engine_tone(f, t) * 0.6
    air = unit(band(nz(len(t), 41), 200, 1500)) * (0.2 + 0.25 / (1 + np.exp(-(t - 1.1) / 0.3)))
    e = np.clip(t / 0.2, 0, 1) * np.clip((sec - t) / 0.7, 0, 1)
    x = (x + air * 0.5) * e
    return cabin(band(x, 40, 1800), 0.12)


def thruster_off():
    """关推进器：发动机声往下掉、松下来，最后一下「咔」的机械停住，留一点余音。约 2.4 秒。"""
    sec = 2.6
    t = tt(sec)
    f = 30 + 52 * np.exp(-t / 0.7)
    e = np.exp(-t / 0.9) * np.clip(t / 0.02, 0, 1)
    x = engine_tone(f, t, 0.2) * e * 0.7
    x += unit(band(nz(len(t), 51), 100, 900)) * np.exp(-t / 0.5) * 0.2
    add(x, 1.7, modal([(420, 0.04, 0.5), (980, 0.02, 0.3), (1900, 0.008, 0.1)], 0.3) * 0.5)
    return cabin(band(x, 30, 2200), 0.15)


def switch_off():
    """拨下一个开关：一声硬的「嗒」，后面一点电的嗡声往下掉（灯暗下去）。"""
    x = np.zeros(int(0.7 * SR))
    add(x, 0.0, modal([(2100, 0.006, 0.45), (3400, 0.003, 0.15), (700, 0.012, 0.35)], 0.1))
    add(x, 0.0, burst(0.005, 0.001, 1200, 4500) * 0.2)
    t = tt(0.5)
    f = 120 * (1 - 0.3 * t)
    hum = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12) * 0.12
    add(x, 0.01, hum)
    return cabin(band(x, 90, 4500), 0.1)


# ================================================================== 导航屏
def nav_alert():
    """导航屏告警：两个往下走的软音「嘟—嘟」，像旧屏幕的提示，不吓人。"""
    x = np.zeros(int(0.8 * SR))
    add(x, 0.0, beep(880, 0.12, 0.8, harm=0.06))
    add(x, 0.18, beep(740, 0.18, 0.8, harm=0.06))
    return cabin(band(x, 300, 2800), 0.12)


def nav_beep():
    """导航屏确认：两个往上的短音「嘀嘀」（到范围了）。"""
    x = np.zeros(int(0.6 * SR))
    add(x, 0.0, beep(988, 0.07, 0.7, harm=0.05))
    add(x, 0.11, beep(1319, 0.11, 0.7, harm=0.05))
    return cabin(band(x, 300, 3200), 0.12)


# ================================================================== 手、阀、接口
def pat():
    """拍拍操纵台：手掌拍在铁皮上两下（闷、软，带一点铁皮的低嗡）。"""
    x = np.zeros(int(0.8 * SR))
    for at, a in ((0.0, 1.0), (0.24, 0.8)):
        add(x, at, thump(0.25, 150, 0.025, int(at * 100) + 61, 1400) * a)
        add(x, at, modal([(340, 0.09, 0.15), (760, 0.05, 0.06)], 0.4) * a)
    return cabin(band(x, 70, 3000), 0.14)


def valve_lock():
    """拧紧阀门：转盘吱的一小下（很短、低），然后锁扣「咔嗒」落位。"""
    x = np.zeros(int(0.9 * SR))
    tl = tt(0.32)
    f = 520 + 120 * tl / 0.32
    sq = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 26 * tl)) ** 3
    add(x, 0.0, sq * np.sin(np.pi * tl / 0.32) * 0.18)
    add(x, 0.0, unit(band(nz(len(tl), 71), 400, 1800)) * np.sin(np.pi * tl / 0.32) * 0.15)
    add(x, 0.40, modal([(380, 0.06, 0.6), (900, 0.03, 0.35), (2100, 0.008, 0.15)], 0.4))
    add(x, 0.40, burst(0.01, 0.002, 600, 3000) * 0.25)
    return cabin(band(x, 90, 3800), 0.15)


def hiss_thin():
    """漏气（循环 3 秒）：一缕很细的气声，中高频窄带，轻轻抖；比树屋 pipe_hiss 的尖响更软、更低一点。"""
    sec, xf = 3.0, 0.5
    n = int((sec + xf) * SR)
    t = np.arange(n) / SR
    fl = 1 + 0.3 * unit(lp(nz(n, 81), 3)) + 0.08 * np.sin(2 * np.pi * 5.5 * t)
    h = unit(band(nz(n, 82), 2200, 3600, order=3)) * 0.6 + unit(band(nz(n, 83), 900, 2200)) * 0.25
    x = h * fl
    y = loop_xfade(x, int(sec * SR), int(xf * SR))
    y = lp(y, 5000)                                       # 去掉最上面那点嘶，软一点
    return rotate_to_zero(cabin(y, 0.08)[: int(sec * SR)])


def wire_scrape():
    """擦过废弃的架空线：机身外一道长的金属刮擦（被机壳闷住，不尖），中间线绷了一下发出一声低的「嗡」。"""
    sec = 1.8
    t = tt(sec)
    n = len(t)
    e = np.clip(t / 0.1, 0, 1) * np.clip((1.3 - t) / 0.4, 0, 1)
    stick = (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(38 + 20 * t) / SR)) ** 3
    scr = unit(band(nz(n, 91), 700, 2200)) * (0.5 + 0.5 * stick) * e
    twang = np.zeros(n)
    tl = tt(1.2)
    add(twang, 0.45, (np.sin(2 * np.pi * 96 * tl) + 0.4 * np.sin(2 * np.pi * 193 * tl)) * np.exp(-tl / 0.35))
    x = scr * 0.5 + twang * 0.5
    return cabin(band(x, 60, 2400), 0.18)


# ================================================================== 水
def splash():
    """飞机砸到水面：一下低的拍击，接着一大片水往两边哗地分开、溅起又落下，后面是水擦着机腹的嘶嘶声。约 2.8 秒。"""
    sec = 3.0
    t = tt(sec)
    n = len(t)
    x = thump(sec, 70, 0.12, 101, 600) * 0.9
    wash_e = np.clip(t / 0.05, 0, 1) * np.exp(-t / 0.7)
    x += unit(band(nz(n, 102), 200, 2600)) * wash_e * 0.55
    hiss_e = np.clip((t - 0.3) / 0.3, 0, 1) * np.clip((sec - t) / 1.2, 0, 1)
    x += unit(band(nz(n, 103), 500, 3000)) * hiss_e * 0.18 * (1 + 0.4 * unit(lp(nz(n, 104), 4)))
    r = np.random.default_rng(105)
    for _ in range(18):                                   # 溅起的水落回来
        at = float(r.uniform(0.4, 1.6))
        add(x, at, burst(0.04, 0.01, 600, 2500) * float(r.uniform(0.03, 0.09)))
    return cabin(band(x, 30, 3200), 0.15)


def wood_knock():
    """浮木碰到机身：一根湿木头空空地撞一下（木头的空响 + 机壳一点低嗡），带一点水声。"""
    x = np.zeros(int(0.8 * SR))
    add(x, 0.0, modal([(210, 0.05, 0.6), (470, 0.03, 0.35), (980, 0.012, 0.12)], 0.5))
    add(x, 0.0, burst(0.02, 0.004, 200, 1500) * 0.3)
    add(x, 0.0, modal([(130, 0.12, 0.15)], 0.6))
    tl = tt(0.4)
    add(x, 0.05, unit(band(nz(len(tl), 111), 300, 1500)) * np.exp(-tl / 0.12) * 0.08)
    return cabin(band(x, 60, 2500), 0.15)


def thud():
    """卡进窄水道停住：很重的一下闷响（低、短），机身轻轻一晃的余震。"""
    x = np.zeros(int(1.2 * SR))
    add(x, 0.0, thump(1.0, 55, 0.14, 121, 500))
    add(x, 0.0, modal([(170, 0.18, 0.2), (390, 0.08, 0.1)], 1.0))
    add(x, 0.25, thump(0.5, 70, 0.06, 122, 400) * 0.3)
    return cabin(band(x, 25, 1800), 0.18)


def crate_bump():
    """木箱漂过来碰了机身：木箱「咚」一下（比浮木方、短），一点水拍。"""
    x = np.zeros(int(0.9 * SR))
    add(x, 0.0, modal([(260, 0.04, 0.6), (610, 0.02, 0.3), (1300, 0.008, 0.1)], 0.4))
    add(x, 0.0, burst(0.015, 0.003, 300, 2000) * 0.25)
    add(x, 0.18, modal([(250, 0.03, 0.25)], 0.2))         # 弹开再轻碰一下
    tl = tt(0.5)
    add(x, 0.02, unit(band(nz(len(tl), 131), 300, 1400)) * np.exp(-tl / 0.15) * 0.1)
    return cabin(band(x, 70, 2600), 0.14)


# ================================================================== 碎石带
def debris_pass(side):
    """碎石从一侧掠过（立体声）：一阵「呼」的风压 + 石头翻滚的低沉沙沙，从一边的前方掠到后面，
    声像在那一侧（side=-1 左、+1 右）从 0.9 收到 0.5，高频先多后少（像擦身而过）。约 1.3 秒。"""
    sec = 1.4
    t = tt(sec)
    n = len(t)
    e = np.exp(-((t - 0.5) / 0.25) ** 2)
    whoosh = unit(band(nz(n, 141 + side), 150, 1600)) * e
    bright = unit(band(nz(n, 143 + side), 1200, 2600)) * np.exp(-((t - 0.42) / 0.12) ** 2) * 0.15
    rumble = unit(band(nz(n, 145 + side), 40, 300)) * e * (0.6 + 0.4 * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * t)))
    mono = whoosh * 0.55 + bright + rumble * 0.45
    mono = cabin(mono, 0.1)
    pan = side * (0.9 - 0.4 * np.clip(t / sec, 0, 1))      # -1 左 … +1 右
    gl = np.sqrt((1 - pan) / 2)
    gr = np.sqrt((1 + pan) / 2)
    return np.stack([mono * gl, mono * gr], 1)


def debris_bump():
    """撞了一块小碎石：机壳闷闷地「咚」一下、轻轻一晃，几颗小砂子沙沙擦过去。不吓人。"""
    x = np.zeros(int(0.9 * SR))
    add(x, 0.0, thump(0.6, 90, 0.07, 151, 900) * 0.8)
    add(x, 0.0, modal([(310, 0.07, 0.2), (720, 0.03, 0.08)], 0.4))
    r = np.random.default_rng(152)
    for _ in range(6):
        add(x, float(r.uniform(0.05, 0.4)), burst(0.015, 0.003, 1000, 3000) * float(r.uniform(0.03, 0.07)))
    return cabin(band(x, 45, 2600), 0.14)


def airflow_loop():
    """平稳的气流（循环 6 秒）：低通的风声，慢慢起伏两次，很淡的一点高一些的气声；接缝交叉淡化。"""
    sec, xf = 6.0, 1.0
    n = int((sec + xf) * SR)
    t = np.arange(n) / SR
    swell = 1 + 0.25 * np.sin(2 * np.pi * t / 3.0) + 0.15 * unit(lp(nz(n, 161), 0.8))
    low = unit(band(nz(n, 162), 60, 500)) * 0.7
    mid = unit(band(nz(n, 163), 500, 1500)) * 0.15
    x = (low + mid) * swell
    y = loop_xfade(x, int(sec * SR), int(xf * SR))
    return rotate_to_zero(y)


# ================================================================== 通讯器
def phone_buzz():
    """通讯器轻震：两下短短的「嗡嗡」（低的马达抖动，隔着背包 / 衣服，很轻）。"""
    x = np.zeros(int(0.9 * SR))
    for at in (0.0, 0.32):
        tl = tt(0.2)
        m = np.sin(2 * np.pi * 160 * tl) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 40 * tl)))
        add(x, at, m * np.clip(tl / 0.01, 0, 1) * np.clip((0.2 - tl) / 0.02, 0, 1))
    return cabin(band(x, 90, 900), 0.06)


def phone_send():
    """发出一条消息：一声往上的轻「啾」+ 一点点纸一样的气声。"""
    t = tt(0.3)
    f = 700 + 500 * np.clip(t / 0.12, 0, 1)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.clip(t / 0.01, 0, 1) * np.exp(-t / 0.07)
    x += unit(band(nz(len(t), 171), 1500, 4000)) * np.exp(-t / 0.04) * 0.08
    return cabin(band(x, 300, 3500), 0.1)


# ================================================================== 写文件
JOBS = [
    ("alarm", alarm, 0.32),
    ("alarm_stop", alarm_stop, 0.3),
    ("book_close", book_close, 0.32),
    ("card_beep", card_beep, 0.22),
    ("converter_burn", converter_burn, 0.55),
    ("crate_bump", crate_bump, 0.5),
    ("crumbs", crumbs, 0.25),
    ("drop_in", drop_in, 0.42),
    ("engine_boost", engine_boost, 0.55),
    ("hiss_thin", hiss_thin, 0.16),
    ("nav_alert", nav_alert, 0.24),
    ("nav_beep", nav_beep, 0.22),
    ("pat", pat, 0.45),
    ("pen_tap", pen_tap, 0.26),
    ("splash", splash, 0.6),
    ("switch_off", switch_off, 0.3),
    ("thruster_off", thruster_off, 0.5),
    ("thud", thud, 0.65),
    ("valve_lock", valve_lock, 0.4),
    ("wire_scrape", wire_scrape, 0.38),
    ("wood_knock", wood_knock, 0.45),
    ("debris_pass_l", lambda: debris_pass(-1), 0.4),
    ("debris_pass_r", lambda: debris_pass(1), 0.4),
    ("debris_bump", debris_bump, 0.45),
    ("airflow_loop", airflow_loop, 0.2),
    ("phone_buzz", phone_buzz, 0.3),
    ("phone_send", phone_send, 0.22),
]
LOOPS = {"hiss_thin", "airflow_loop"}


def save(name, x, peak, loop=False):
    m = np.max(np.abs(x)) or 1.0
    x = x / m * peak
    st = x.ndim == 2
    if not loop:
        if st:
            x = np.stack([fades(x[:, 0]), fades(x[:, 1])], 1)
        else:
            x = fades(x)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT / (name + ".wav")), "wb") as w:
        w.setnchannels(2 if st else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    mono = pcm.astype(float).mean(1) / 32768 if st else pcm.astype(float) / 32768
    F.STATS.append((name, mono, loop))


def set_loop_imports():
    """循环的两个：.import 改成 loop_mode=2（forward）。没有 .import（还没导入过）就跳过，打印提示。"""
    for name in LOOPS:
        p = OUT / (name + ".wav.import")
        if not p.exists():
            print(f"  {p.name} 还没有：Godot 导入后再跑一次本脚本")
            continue
        s = p.read_text()
        s2 = re.sub(r"edit/loop_mode=\d", "edit/loop_mode=2", s)
        if s2 != s:
            p.write_text(s2)
            print(f"  {p.name}: loop_mode=2")


def main():
    for name, fn, pk in JOBS:
        save(name, fn(), pk, loop=name in LOOPS)
    F.report()
    set_loop_imports()


if __name__ == "__main__":
    main()
