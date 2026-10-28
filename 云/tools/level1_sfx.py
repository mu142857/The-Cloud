"""第一关的占位音效（全部是程序生成的占位，以后请作曲 / 音效换掉，文件名保持不变即可）。

跑法：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/level1_sfx.py
输出 audio/sfx/*.wav（44.1kHz 单声道 16 位；雨声是 20 秒无缝循环）。

方向：ASMR，柔和、偏低频，不刺耳。雷声没有尖锐的「咔」，近雷也只是一个闷一点的炸开。
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "audio" / "sfx"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(11)


def lp_fast(x, cutoff, n=1):
    """固定截止频率的一阶低通（用截断的指数冲激响应做卷积），n = 叠几次。"""
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    # 用 FFT 做 IIR 的冲激响应卷积（截断到 8 个时间常数）
    L = int(8 / (2 * np.pi * cutoff / SR)) + 1
    h = a * (1 - a) ** np.arange(L)
    for _ in range(n):
        x = np.convolve(x, h)[: len(x)] if L < 4000 else _fftconv(x, h)
    return x


def _fftconv(x, h):
    n = len(x) + len(h)
    N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)[: len(x)]


def hp_fast(x, cutoff):
    return x - lp_fast(x, cutoff)


def norm(x, peak=0.8):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def save(name, x, peak=0.8):
    x = norm(x, peak)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(name, f"{len(x) / SR:.2f}s")


def env(n, attack, release, curve=2.0):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    r = np.clip((n / SR - t) / max(release, 1e-4), 0, 1) ** curve
    return a * r


# ------------------------------------------------------------------ 雨（循环）
def rain(sec=20.0):
    n = int(sec * SR)
    # 底层：粉红一点的噪声，低通到 3k、高通 200，慢慢起伏
    w = rng.standard_normal(n + SR)
    base = lp_fast(hp_fast(w, 180), 2600, n=2)
    slow = 0.85 + 0.15 * np.sin(np.linspace(0, 2 * np.pi * 3, n + SR) + 0.7)
    base *= slow
    # 雨滴：很多很短的小「嗒」，打在叶子上（带一点音高）
    drops = np.zeros(n + SR)
    k = int(sec * 90)
    for _ in range(k):
        p = rng.integers(0, n + SR - 2000)
        L = rng.integers(200, 900)
        f = rng.uniform(1800, 4200)
        t = np.arange(L) / SR
        d = np.sin(2 * np.pi * f * t) * np.exp(-t * rng.uniform(250, 600)) * rng.uniform(0.02, 0.09)
        drops[p:p + L] += d
    drops = lp_fast(drops, 5000)
    x = base * 0.9 + drops
    # 无缝：尾巴最后 1 秒和开头交叉淡化
    head, tail = x[:SR], x[n:n + SR]
    fade = np.linspace(0, 1, SR)
    x = x[:n].copy()
    x[:SR] = head * fade + tail * (1 - fade)
    return x


# ------------------------------------------------------------------ 雷
def rumble(sec, bumps, cutoff=140, seed=0):
    r = np.random.default_rng(seed)
    n = int(sec * SR)
    w = r.standard_normal(n)
    x = lp_fast(w, cutoff, n=3)
    e = np.zeros(n)
    t = np.arange(n) / SR
    for (at, amp, width) in bumps:
        e += amp * np.exp(-((t - at) / width) ** 2) * (t > at - width * 0.6)
        e += amp * 0.6 * np.exp(-np.clip(t - at, 0, None) / (width * 2.5)) * (t > at)
    return x * e * env(n, 0.05, 1.2)


def thunder_far(seed, sec=6.0):
    r = np.random.default_rng(seed)
    bumps = [(0.5 + r.uniform(0, 0.4), 1.0, 0.45)]
    for _ in range(3):
        bumps.append((r.uniform(1.0, 4.0), r.uniform(0.3, 0.7), r.uniform(0.3, 0.8)))
    return rumble(sec, bumps, cutoff=110, seed=seed)


def thunder_near(seed):
    r = np.random.default_rng(seed)
    sec = 4.5
    n = int(sec * SR)
    # 炸开：比远雷亮一点的噪声（低通 900），快起、半秒落下去
    burst = lp_fast(r.standard_normal(n), 900, n=2) * np.exp(-np.arange(n) / SR / 0.35) * (np.arange(n) > int(0.02 * SR))
    body = rumble(sec, [(0.15, 1.0, 0.25), (0.7, 0.7, 0.5), (1.6, 0.45, 0.7)], cutoff=170, seed=seed + 50)
    return burst * 0.55 / (np.max(np.abs(burst)) or 1) * np.max(np.abs(body)) * 1.6 + body


# ------------------------------------------------------------------ 飞船
def whoosh():
    sec = 2.6
    n = int(sec * SR)
    t = np.arange(n) / SR
    # 越来越近：音量上去，噪声的「亮度」先升后降（多普勒感），加一条往下滑的低音
    cut = 400 + 2600 * np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 2
    w = rng.standard_normal(n)
    # 随时间变的低通：分段做
    out = np.zeros(n)
    seg = 2048
    for i in range(0, n, seg):
        c = float(cut[min(i + seg // 2, n - 1)])
        blk = lp_fast(w[max(0, i - 2048):i + seg], c, n=2)
        out[i:i + seg] = blk[-(min(seg, n - i)):]
    tone_f = 220 * (1 - 0.55 * t / sec)
    tone = np.sin(2 * np.pi * np.cumsum(tone_f) / SR) * 0.25
    tone += np.sin(2 * np.pi * np.cumsum(tone_f * 1.5) / SR) * 0.1
    e = (t / sec) ** 1.6
    e *= np.clip((sec - t) / 0.05, 0, 1)
    return (norm(out) + tone) * e


def impact():
    sec = 3.0
    n = int(sec * SR)
    t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * (52 + 40 * np.exp(-t / 0.08)) * t) * np.exp(-t / 0.35)
    crunch = lp_fast(rng.standard_normal(n), 1400, n=2) * np.exp(-t / 0.22)
    crunch = norm(crunch) * 0.6
    dirt = lp_fast(rng.standard_normal(n), 500, n=2)
    dirt = norm(dirt) * 0.35 * np.exp(-t / 0.9)
    # 几下零碎的金属轻响（很闷）
    bits = np.zeros(n)
    for at in (0.25, 0.42, 0.7, 1.05):
        p = int(at * SR)
        L = int(0.25 * SR)
        tt = np.arange(L) / SR
        f = rng.uniform(500, 900)
        bits[p:p + L] += np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.06) * 0.12
    return thump * 1.0 + crunch + dirt + lp_fast(bits, 2500)


# ------------------------------------------------------------------ 小音效
def pickup():
    sec = 1.2
    n = int(sec * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for (at, f, amp) in ((0.0, 784, 0.5), (0.09, 1175, 0.4), (0.18, 1568, 0.25)):
        tt = np.clip(t - at, 0, None)
        on = t >= at
        x += on * amp * np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.35) * np.clip(tt / 0.004, 0, 1)
        x += on * amp * 0.3 * np.sin(2 * np.pi * f * 2.01 * tt) * np.exp(-tt / 0.15)
    return x


def tick():
    sec = 0.05
    n = int(sec * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * 1900 * t) * np.exp(-t / 0.008) + 0.3 * np.sin(2 * np.pi * 3800 * t) * np.exp(-t / 0.004)


def ui_click():
    sec = 0.08
    n = int(sec * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * 1200 * t) * np.exp(-t / 0.012) * 0.8 + np.sin(2 * np.pi * 600 * t) * np.exp(-t / 0.02) * 0.4


def burn_ding():
    """燃烧值滚完的那一下：暖一点的低音 + 一点亮。"""
    sec = 1.4
    n = int(sec * SR)
    t = np.arange(n) / SR
    x = 0.5 * np.sin(2 * np.pi * 523 * t) * np.exp(-t / 0.5)
    x += 0.35 * np.sin(2 * np.pi * 784 * t) * np.exp(-t / 0.4)
    x += 0.2 * np.sin(2 * np.pi * 1046 * t) * np.exp(-t / 0.3)
    return x * np.clip(t / 0.006, 0, 1)


def fire_crackle(sec=8.0):
    """坠毁的飞船冒烟时很轻的噼啪（循环）。"""
    n = int(sec * SR)
    x = lp_fast(rng.standard_normal(n + SR), 300, n=2) * 0.4
    for _ in range(int(sec * 14)):
        p = rng.integers(0, n + SR - 600)
        L = rng.integers(60, 400)
        x[p:p + L] += rng.standard_normal(L) * np.exp(-np.arange(L) / (L / 4)) * rng.uniform(0.3, 1.0)
    x = lp_fast(x, 3000)
    head, tail = x[:SR], x[n:n + SR]
    fade = np.linspace(0, 1, SR)
    x = x[:n].copy()
    x[:SR] = head * fade + tail * (1 - fade)
    return x


def main():
    save("rain_loop.wav", rain(), 0.7)
    save("thunder_far_1.wav", thunder_far(1), 0.75)
    save("thunder_far_2.wav", thunder_far(2), 0.7)
    save("thunder_far_3.wav", thunder_far(3, 7.0), 0.7)
    save("thunder_near_1.wav", thunder_near(4), 0.85)
    save("thunder_near_2.wav", thunder_near(5), 0.8)
    save("thunder_near_3.wav", thunder_near(6), 0.9)
    save("ship_whoosh.wav", whoosh(), 0.75)
    save("ship_impact.wav", impact(), 0.9)
    save("pickup.wav", pickup(), 0.6)
    save("tick.wav", tick(), 0.35)
    save("burn_ding.wav", burn_ding(), 0.55)
    save("ui_click.wav", ui_click(), 0.4)
    save("fire_crackle_loop.wav", fire_crackle(), 0.5)


if __name__ == "__main__":
    main()
