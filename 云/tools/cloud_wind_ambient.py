"""云层上的风（11-06 开始界面的云层小镇、结局三云台的 cloud_wind）。合成，不是录音，没有授权问题。
40 秒无缝循环：频域整形的周期噪声（本来就首尾相接），只有 120~900 Hz 一个软鼓包，1.4 kHz 以上很快压下去，没有白噪音的沙沙
（作者嫌过森林的白噪音）；音量跟一条首尾接得上的慢包络走，偶尔来一阵。左右两路相关但不相同，听起来宽一点。
用法：python3 tools/cloud_wind_ambient.py 输出.wav，再 ffmpeg -i 输出.wav -c:a vorbis -strict -2 -q:a 3 audio/sfx/cloud_wind.ogg（这台机器的 ffmpeg 没有 libvorbis，用内置的）
"""
import sys
import numpy as np
import scipy.io.wavfile as wavfile

SR = 44100
SEC = 40
N = SR * SEC


def shaped_noise(seed):
    r = np.random.default_rng(seed)
    f = np.maximum(np.fft.rfftfreq(N, 1.0 / SR), 1.0)
    mag = (0.25 + np.exp(-((np.log(f) - np.log(320.0)) / 0.8) ** 2)) / np.sqrt(f)
    mag *= 1.0 / (1.0 + (70.0 / f) ** 4)                          # 太低的轰轰声去掉
    mag *= 1.0 / (1.0 + (f / 1100.0) ** 6)                        # 高的压掉
    spec = mag * np.exp(1j * r.uniform(0, 2 * np.pi, f.size))
    spec[0] = 0
    x = np.fft.irfft(spec, N)
    return x / np.max(np.abs(x))


rng = np.random.default_rng(20261106)
t = np.arange(N) / SR
gust = np.zeros(N)
for period, amp in zip((40, 20, 13.333, 8, 5), (0.5, 0.35, 0.22, 0.12, 0.06)):     # 周期都整除 40 秒：首尾接得上
    gust += amp * np.sin(2 * np.pi * t / period + rng.uniform(0, 2 * np.pi))
gust = 0.62 + 0.38 * np.tanh(gust * 1.5)
L = (shaped_noise(1) * 0.8 + shaped_noise(3) * 0.2) * gust
R = (shaped_noise(2) * 0.8 + shaped_noise(3) * 0.2) * gust
st = np.stack([L, R], 1)
st *= 10 ** (-20.0 / 20.0) / np.sqrt(np.mean(st ** 2))            # 响度 -20 dBFS（实际多响由播放时的 db 定）
st = np.clip(st, -1, 1)
wavfile.write(sys.argv[1], SR, (st * 32767).astype(np.int16))
print("peak", float(np.max(np.abs(st))), "seam", float(np.max(np.abs(st[0] - st[-1]))))
