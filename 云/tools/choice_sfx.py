"""对话选项确认音 choice_ring.wav（程序生成，以后可以换正式素材，文件名不变即可）。

    python tools/choice_sfx.py

只用标准库（不需要 numpy）。输出 audio/sfx/choice_ring.wav（44.1kHz 单声道 16 位），打印时长 / 峰值 / RMS。

声音（11-08 作者「每次选择一个对话选项……音效应该就是很空灵的一个声音」）：
  两个很轻的玻璃钟音往上走一个五度（A5 → E6，隔 70ms），每个音是一对差 1.3Hz 的正弦（慢慢「呼吸」的颤），
  带一点点非整数泛音（像玻璃 / 风铃，不像钢琴）；底下垫一口很轻的高频气声（像吸了一口气）；
  最后过一个长尾巴的 Schroeder 混响（4 个梳状 + 2 个全通），湿声比较多，让它「飘」在空气里。
  峰值压在 -6 dBFS，播放时 story_dialogue 再给 -9 dB，不会盖过对话。
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "audio" / "sfx" / "choice_ring.wav"
LEN = 2.6
N = int(SR * LEN)
rnd = random.Random(1108)


def bell(buf, start, f0, amp, decay):
    """玻璃钟音：f0 一对微微失谐的正弦 + 两个非整数泛音，起音 6ms，指数衰减。"""
    s0 = int(start * SR)
    partials = [(1.0, 1.0, decay), (2.76, 0.16, decay * 0.45), (5.4, 0.05, decay * 0.25)]
    for i in range(s0, N):
        t = (i - s0) / SR
        att = min(1.0, t / 0.006)
        v = 0.0
        for ratio, a, d in partials:
            f = f0 * ratio
            env = math.exp(-t / d)
            if env < 1e-4:
                continue
            v += a * env * (math.sin(2 * math.pi * f * t) + math.sin(2 * math.pi * (f + 1.3) * t + 0.7)) * 0.5
        buf[i] += amp * att * v


def breath(buf, amp):
    """高频气声：白噪声 → 两级一阶高通 + 一级低通（约 2.5k~7k），0~0.5s 升起又落下。"""
    hp1 = hp2 = lp = 0.0
    prev = prev1 = 0.0
    a_hp = math.exp(-2 * math.pi * 2500 / SR)
    a_lp = 1 - math.exp(-2 * math.pi * 7000 / SR)
    for i in range(int(0.6 * SR)):
        t = i / SR
        x = rnd.uniform(-1, 1)
        hp1 = a_hp * (hp1 + x - prev)
        prev = x
        hp2 = a_hp * (hp2 + hp1 - prev1)
        prev1 = hp1
        lp += a_lp * (hp2 - lp)
        env = math.sin(math.pi * min(1.0, t / 0.5)) ** 2
        buf[i] += amp * env * lp


def comb(x, delay, fb, damp):
    y = [0.0] * len(x)
    line = [0.0] * delay
    k = 0
    store = 0.0
    for i, v in enumerate(x):
        out = line[k]
        store = out * (1 - damp) + store * damp
        line[k] = v + store * fb
        k = (k + 1) % delay
        y[i] = out
    return y


def allpass(x, delay, g):
    y = [0.0] * len(x)
    line = [0.0] * delay
    k = 0
    for i, v in enumerate(x):
        b = line[k]
        out = -v + b
        line[k] = v + b * g
        k = (k + 1) % delay
        y[i] = out
    return y


def reverb(x):
    combs = [(1557, 0.86), (1617, 0.85), (1491, 0.87), (1422, 0.86)]
    acc = [0.0] * len(x)
    for d, fb in combs:
        c = comb(x, d, fb, 0.35)
        for i in range(len(x)):
            acc[i] += c[i] * 0.25
    acc = allpass(acc, 225, 0.5)
    acc = allpass(acc, 556, 0.5)
    return acc


def main():
    dry = [0.0] * N
    bell(dry, 0.000, 880.0, 0.55, 0.55)        # A5
    bell(dry, 0.070, 1318.5, 0.45, 0.75)       # E6
    breath(dry, 0.05)
    wet = reverb(dry)
    out = [d * 0.55 + w * 0.9 for d, w in zip(dry, wet)]
    # 尾巴最后 0.4s 淡到 0，开头精确 0
    fade = int(0.4 * SR)
    for i in range(fade):
        out[N - fade + i] *= (1 - i / fade) ** 2
    peak = max(abs(v) for v in out) or 1.0
    g = 0.5 / peak                               # -6 dBFS
    out = [v * g for v in out]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32767)) for v in out))
    rms = math.sqrt(sum(v * v for v in out) / N)
    print(f"{OUT.name}: {LEN:.2f}s peak {20 * math.log10(max(abs(v) for v in out)):.1f} dBFS rms {20 * math.log10(rms):.1f} dBFS")


if __name__ == "__main__":
    main()
