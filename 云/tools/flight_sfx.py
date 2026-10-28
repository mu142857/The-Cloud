"""飞行段的占位音效（全部程序生成，以后请换成正式的，文件名不变即可）。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/flight_sfx.py

输出 audio/sfx/flight_*.wav（44.1kHz 单声道 16 位）。方向和 level1_sfx.py 一样：柔和、偏低频、不刺耳。
引擎是 4 秒无缝循环（所有频率在 4 秒里都是整数个周期，噪声首尾交叉淡化）。
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "audio" / "sfx"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(23)


def lp(x, cutoff, n=1):
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    L = int(8 / (2 * np.pi * cutoff / SR)) + 1
    h = a * (1 - a) ** np.arange(L)
    for _ in range(n):
        N = 1 << (len(x) + L - 1).bit_length()
        x = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)[: len(x)]
    return x


def hp(x, cutoff):
    return x - lp(x, cutoff)


def save(name, x, peak=0.8):
    m = np.max(np.abs(x)) or 1.0
    x = x / m * peak
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(name, f"{len(x) / SR:.2f}s")


def tt(sec):
    return np.arange(int(sec * SR)) / SR


def engine(sec=4.0):
    """低低的嗡：55Hz 和几条泛音，一点慢慢起伏的气流噪声。"""
    t = tt(sec)
    x = 0.55 * np.sin(2 * np.pi * 55 * t) + 0.3 * np.sin(2 * np.pi * 110 * t + 0.4)
    x += 0.12 * np.sin(2 * np.pi * 165 * t + 1.1) + 0.06 * np.sin(2 * np.pi * 275 * t)
    x *= 1 + 0.12 * np.sin(2 * np.pi * 1.0 * t)           # 4 秒 4 个周期：无缝
    n = len(t)
    w = lp(hp(rng.standard_normal(n + SR), 120), 700, n=2)
    w = w / np.max(np.abs(w)) * 0.35
    head, tail = w[:SR], w[n:n + SR]
    f = np.linspace(0, 1, SR)
    w = w[:n].copy()
    w[:SR] = head * f + tail * (1 - f)
    return x + w * (1 + 0.3 * np.sin(2 * np.pi * 0.5 * t))


def bump():
    """撞到：一下闷的「咚」+ 一点金属轻响。"""
    t = tt(0.9)
    th = np.sin(2 * np.pi * (48 + 50 * np.exp(-t / 0.05)) * t) * np.exp(-t / 0.22)
    nz = lp(rng.standard_normal(len(t)), 900, n=2)
    nz = nz / np.max(np.abs(nz)) * 0.5 * np.exp(-t / 0.08)
    ring = 0.12 * np.sin(2 * np.pi * 640 * t) * np.exp(-t / 0.18) + 0.08 * np.sin(2 * np.pi * 1012 * t) * np.exp(-t / 0.12)
    return th + nz + ring


def drip():
    """漏油的一滴：短短往上滑的「啵」。"""
    t = tt(0.16)
    f = 520 + 900 * (t / 0.16)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.035) * np.clip(t / 0.003, 0, 1)


def mote():
    """拾到光点：两声很轻的铃（五度），尾巴一点亮晶晶。"""
    t = tt(1.3)
    x = np.zeros(len(t))
    for at, f, a in ((0.0, 988, 0.5), (0.07, 1480, 0.35)):
        u = np.clip(t - at, 0, None)
        on = t >= at
        x += on * a * np.sin(2 * np.pi * f * u) * np.exp(-u / 0.45) * np.clip(u / 0.004, 0, 1)
        x += on * a * 0.25 * np.sin(2 * np.pi * f * 3.0 * u) * np.exp(-u / 0.12)
    return x


def burn():
    """烧东西：一口气「呼」地着起来（噪声越来越亮再落下），里面几下噼啪，最后一声暖的低音。"""
    sec = 2.4
    t = tt(sec)
    n = len(t)
    w = rng.standard_normal(n)
    out = np.zeros(n)
    seg = 2048
    cut = 300 + 2200 * np.sin(np.pi * np.clip(t / 1.6, 0, 1)) ** 1.5
    for i in range(0, n, seg):
        blk = lp(w[max(0, i - 2048):i + seg], float(cut[min(i + seg // 2, n - 1)]), n=2)
        out[i:i + seg] = blk[-(min(seg, n - i)):]
    out = out / np.max(np.abs(out)) * np.clip(t / 0.25, 0, 1) * np.exp(-np.clip(t - 1.0, 0, None) / 0.5)
    crack = np.zeros(n)
    for _ in range(26):
        p = rng.integers(int(0.15 * SR), int(1.7 * SR))
        L = rng.integers(80, 500)
        crack[p:p + L] += rng.standard_normal(L) * np.exp(-np.arange(L) / (L / 4)) * rng.uniform(0.2, 0.7)
    crack = lp(crack, 3200)
    u = np.clip(t - 1.1, 0, None)
    warm = (t >= 1.1) * (0.35 * np.sin(2 * np.pi * 196 * u) + 0.2 * np.sin(2 * np.pi * 294 * u)) * np.exp(-u / 0.7) \
        * np.clip(u / 0.05, 0, 1)
    return out * 0.7 + crack * 0.6 + warm


def card():
    """决定卡出现：很轻的一口气 + 一声低的钟（不惊人，像翻开一页）。"""
    t = tt(2.2)
    breath = lp(hp(rng.standard_normal(len(t)), 300), 1800, n=2)
    breath = breath / np.max(np.abs(breath)) * 0.25 * np.sin(np.pi * np.clip(t / 0.6, 0, 1)) ** 2
    u = np.clip(t - 0.12, 0, None)
    bell = (t >= 0.12) * (0.4 * np.sin(2 * np.pi * 392 * u) + 0.22 * np.sin(2 * np.pi * 587 * u)
                          + 0.08 * np.sin(2 * np.pi * 1176 * u)) * np.exp(-u / 0.8) * np.clip(u / 0.02, 0, 1)
    return breath + bell


def cough():
    """引擎咳嗽：三下闷的「噗」，越来越弱。"""
    t = tt(1.2)
    x = np.zeros(len(t))
    for at, a in ((0.0, 1.0), (0.28, 0.7), (0.62, 0.45)):
        u = np.clip(t - at, 0, None)
        on = t >= at
        nz = lp(rng.standard_normal(len(t)), 380, n=2)
        nz = nz / np.max(np.abs(nz))
        x += on * a * (nz * 0.8 + np.sin(2 * np.pi * (70 + 40 * np.exp(-u / 0.03)) * u)) * np.exp(-u / 0.09)
    return x


def rumble():
    """颠簸：一阵低频抖动，中间两下「咚咚」（木头撞出舱门）。"""
    sec = 2.2
    t = tt(sec)
    n = len(t)
    nz = lp(rng.standard_normal(n), 120, n=3)
    nz = nz / np.max(np.abs(nz))
    e = np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 0.7 * (1 + 0.5 * np.sin(2 * np.pi * 7 * t))
    x = nz * e
    for at in (0.55, 0.8, 1.15):
        u = np.clip(t - at, 0, None)
        x += (t >= at) * 0.6 * np.sin(2 * np.pi * (90 + 60 * np.exp(-u / 0.03)) * u) * np.exp(-u / 0.12)
        x += (t >= at) * 0.12 * np.sin(2 * np.pi * 410 * u) * np.exp(-u / 0.08)
    return x


def repair():
    """漏油修好：两下小小的「叮」。"""
    t = tt(0.5)
    x = np.zeros(len(t))
    for at, f in ((0.0, 1318), (0.11, 1760)):
        u = np.clip(t - at, 0, None)
        x += (t >= at) * np.sin(2 * np.pi * f * u) * np.exp(-u / 0.07) * 0.5
    return x


def select():
    t = tt(0.07)
    return np.sin(2 * np.pi * 880 * t) * np.exp(-t / 0.015) * 0.6 + np.sin(2 * np.pi * 1760 * t) * np.exp(-t / 0.006) * 0.2


def arrive():
    """到达 / 结算：一个慢慢涨起来的暖和弦（D 大三和弦 + 九音），4 秒。"""
    sec = 4.5
    t = tt(sec)
    x = np.zeros(len(t))
    for f, a in ((147, 0.4), (220, 0.32), (294, 0.28), (370, 0.2), (440, 0.12), (659, 0.06)):
        x += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (1 + 0.05 * np.sin(2 * np.pi * 0.7 * t + f))
    return x * np.clip(t / 1.4, 0, 1) ** 1.5 * np.clip((sec - t) / 1.6, 0, 1) ** 1.5


def main():
    save("flight_engine_loop.wav", engine(), 0.55)
    save("flight_bump.wav", bump(), 0.8)
    save("flight_drip.wav", drip(), 0.35)
    save("flight_mote.wav", mote(), 0.45)
    save("flight_burn.wav", burn(), 0.7)
    save("flight_card.wav", card(), 0.5)
    save("flight_cough.wav", cough(), 0.7)
    save("flight_rumble.wav", rumble(), 0.8)
    save("flight_repair.wav", repair(), 0.35)
    save("flight_select.wav", select(), 0.3)
    save("flight_arrive.wav", arrive(), 0.5)


if __name__ == "__main__":
    main()
