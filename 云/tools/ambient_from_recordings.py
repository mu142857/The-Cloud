"""把下载的 CC0 录音（audio/ambient/candidates/，带 .gdignore，不进游戏包）做成游戏里用的无缝循环（11-04）。
  river  ← candidates/03_oga_park_river/park_ambience_river.wav（Thimras，CC0）：截 30 秒，高频轻轻压一点（3.5 kHz 以上约 -6 dB），
           调到 -21 dBFS（和原来的流水声差不多响），单声道 → audio/sfx/river_flow.wav（文件名不变，河流章 room.json 不用改）
  rain   ← candidates/02_oga_rain_gutter/rain-gutter-loop_0.mp3（Ogrebane，CC0）：截 30 秒 → audio/sfx/rain_loop.wav（城市、闪回用）
  循环：多截 2 秒，末尾这 2 秒和开头用等功率交叉淡化叠在一起，首尾接上不断。
用法：python3 tools/ambient_from_recordings.py river|rain 输出.wav [频谱图.png]
需要 ffmpeg（解 mp3 / 重采样）。
"""
import sys, subprocess, tempfile, os, math
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as sg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100
CFG = {
    "river": {"src": "audio/ambient/candidates/03_oga_park_river/park_ambience_river.wav", "start": 100.0, "sec": 30.0,
              "soften": 3500.0, "rms": -21.0},
    "rain": {"src": "audio/ambient/candidates/02_oga_rain_gutter/rain-gutter-loop_0.mp3", "start": 8.0, "sec": 30.0,
             "soften": 0.0, "rms": -20.0},
}
XF = 2.0


def read_mono(path):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "x.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), out], check=True)
        sr, x = wavfile.read(out)
    return x.astype(np.float64) / 32768.0


def main():
    kind, out = sys.argv[1], sys.argv[2]
    c = CFG[kind]
    x = read_mono(os.path.join(ROOT, c["src"]))
    a = int(c["start"] * SR)
    n = int(c["sec"] * SR)
    xf = int(XF * SR)
    seg = x[a:a + n + xf].copy()
    if c["soften"] > 0:
        b, aa = sg.butter(2, c["soften"], btype="low", fs=SR)
        lp = sg.filtfilt(b, aa, seg)
        seg = lp + 0.5 * (seg - lp)                        # 高频留一半（约 -6 dB），水声还在，不刺
    # 等功率交叉淡化：末尾多出来的 xf 叠到开头
    t = np.linspace(0, 1, xf)
    fin, fout = np.sin(t * np.pi / 2), np.cos(t * np.pi / 2)
    y = seg[:n].copy()
    y[:xf] = seg[:xf] * fin + seg[n:n + xf] * fout
    y -= np.mean(y)
    y *= (10 ** (c["rms"] / 20)) / np.sqrt(np.mean(y ** 2))
    if np.max(np.abs(y)) > 0.89:
        y *= 0.89 / np.max(np.abs(y))
    pcm = (y * 32767).astype(np.int16)
    wavfile.write(out, SR, pcm)
    f, P = sg.welch(pcm / 32768.0, SR, nperseg=4096)
    print("saved %s %.1fs rms=%.1f peak=%.2f hf>4k=%.3f seam=%.4f" % (out, n / SR, 20 * math.log10(np.sqrt(np.mean((pcm / 32768.0) ** 2))),
          np.max(np.abs(pcm)) / 32768, P[f > 4000].sum() / P.sum(), abs(pcm[-1] - pcm[0]) / 32768))
    if len(sys.argv) > 3:
        from PIL import Image
        ff, tt, S = sg.spectrogram(pcm / 32768.0, SR, nperseg=2048, noverlap=1024)
        S = 10 * np.log10(S + 1e-14)[ff <= 8000][::-1]
        Image.fromarray((np.clip((S + 110) / 70, 0, 1) * 255).astype(np.uint8)).resize((600, 200)).save(sys.argv[3])


main()
