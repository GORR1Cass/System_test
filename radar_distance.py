#!/usr/bin/env python3
"""
Leitura em tempo real de distancias do radar TI xWR1843BOOST (demo mmWave SDK 3.x,
o mesmo firmware usado pelo mmWave Demo Visualizer 3.6.0).

Como funciona
-------------
1. Abre a porta CLI (Application/User UART, 115200) e envia o arquivo .cfg
   (equivale a clicar em "Send Config" no Visualizer).
2. Abre a porta de dados (Auxiliary Data Port, 921600) e le os frames binarios
   (cabecalho + TLVs). O TLV 1 traz os pontos detectados (x, y, z, velocidade)
   e o TLV 7 traz SNR/ruido de cada ponto.
3. Calcula a distancia (range) de cada ponto = sqrt(x^2 + y^2 + z^2), mostra o
   objeto mais proximo e opcionalmente grava tudo em CSV.

Exemplos
--------
    python radar_distance.py --list-ports
    python radar_distance.py --cli-port COM97 --data-port COM98
    python radar_distance.py --cli-port /dev/ttyACM0 --data-port /dev/ttyACM1
    python radar_distance.py --cli-port COM97 --data-port COM98 --csv medidas.csv
    python radar_distance.py --simulate            # sem hardware, para testar
    python radar_distance.py --simulate --no-plot  # so texto no terminal
"""

from __future__ import annotations

import argparse
import csv
import math
import queue
import struct
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07])
# magic(8) + version, totalPacketLen, platform, frameNumber, timeCpuCycles,
# numDetectedObj, numTLVs, subFrameNumber (8 x uint32)  -> 40 bytes (SDK 3.x)
HEADER = struct.Struct("<8s8I")
TLV_HEAD = struct.Struct("<II")
TLV_DETECTED_POINTS = 1
TLV_SIDE_INFO = 7
MAX_PACKET = 64 * 1024

DEFAULT_CFG = Path(__file__).with_name("xwr1843_distance.cfg")


# --------------------------------------------------------------------------- #
# Estruturas de dados e parser
# --------------------------------------------------------------------------- #
@dataclass
class Point:
    x: float
    y: float
    z: float
    velocity: float
    snr_db: float = 0.0

    @property
    def range_m(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    @property
    def azimuth_deg(self) -> float:
        return math.degrees(math.atan2(self.x, self.y))


@dataclass
class Frame:
    number: int
    points: list[Point] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class FrameParser:
    """Reconstroi frames a partir do fluxo de bytes da porta de dados."""

    def __init__(self) -> None:
        self.buf = bytearray()
        self.bad_packets = 0

    def feed(self, data: bytes) -> list[Frame]:
        self.buf += data
        frames: list[Frame] = []
        while True:
            i = self.buf.find(MAGIC)
            if i < 0:
                del self.buf[: max(0, len(self.buf) - (len(MAGIC) - 1))]
                break
            if i > 0:
                del self.buf[:i]
            if len(self.buf) < HEADER.size:
                break
            hdr = HEADER.unpack_from(self.buf)
            total_len = hdr[2]
            if total_len < HEADER.size or total_len > MAX_PACKET:
                self.bad_packets += 1
                del self.buf[: len(MAGIC)]
                continue
            if len(self.buf) < total_len:
                break
            frame = self._parse(bytes(self.buf[:total_len]), hdr)
            del self.buf[:total_len]
            if frame is not None:
                frames.append(frame)
        return frames

    def _parse(self, packet: bytes, hdr: tuple) -> Frame | None:
        frame_number, num_obj, num_tlvs = hdr[4], hdr[6], hdr[7]
        points: list[Point] = []
        snrs: list[float] = []
        offset = HEADER.size
        try:
            for _ in range(num_tlvs):
                tlv_type, tlv_len = TLV_HEAD.unpack_from(packet, offset)
                offset += TLV_HEAD.size
                if offset + tlv_len > len(packet):
                    raise struct.error("TLV maior que o pacote")
                if tlv_type == TLV_DETECTED_POINTS:
                    n = min(num_obj, tlv_len // 16)
                    for k in range(n):
                        x, y, z, v = struct.unpack_from("<4f", packet, offset + 16 * k)
                        points.append(Point(x, y, z, v))
                elif tlv_type == TLV_SIDE_INFO:
                    n = tlv_len // 4
                    for k in range(n):
                        snr, _noise = struct.unpack_from("<hh", packet, offset + 4 * k)
                        snrs.append(snr * 0.1)  # unidade: 0.1 dB
                offset += tlv_len
        except struct.error:
            self.bad_packets += 1
            return None
        for p, s in zip(points, snrs):
            p.snr_db = s
        return Frame(number=frame_number, points=points)


# --------------------------------------------------------------------------- #
# Comunicacao com o radar
# --------------------------------------------------------------------------- #
def list_ports() -> list:
    from serial.tools import list_ports as lp

    return sorted(lp.comports(), key=lambda p: p.device)


def autodetect_ports() -> tuple[str, str]:
    """Os dois COMs do XDS110: o primeiro e a CLI, o segundo e a porta de dados."""
    cands = [
        p for p in list_ports()
        if "XDS110" in (p.description or "") + (p.manufacturer or "")
        or (p.vid == 0x0451)
    ]
    cli = [p for p in cands if "Application" in (p.description or "")]
    data = [p for p in cands if "Auxiliary" in (p.description or "")]
    if cli and data:
        return cli[0].device, data[0].device
    if len(cands) >= 2:
        return cands[0].device, cands[1].device
    raise SystemExit(
        "Nao encontrei as duas portas do XDS110. Use --list-ports e passe "
        "--cli-port e --data-port manualmente."
    )


def send_config(cli, cfg_path: Path, verbose: bool = True) -> None:
    """Envia o .cfg linha a linha e espera 'Done' (ou 'Error') de cada comando."""
    lines = [
        l.strip() for l in cfg_path.read_text().splitlines()
        if l.strip() and not l.strip().startswith("%")
    ]
    cli.reset_input_buffer()
    for line in lines:
        cli.write((line + "\n").encode())
        reply = b""
        deadline = time.time() + 3.0
        while time.time() < deadline:
            reply += cli.read(cli.in_waiting or 1)
            if b"Done" in reply or b"Error" in reply or b"not recognized" in reply:
                break
        text = reply.decode(errors="replace").strip().replace("\r", "")
        ok = "Done" in text and "Error" not in text
        if verbose:
            print(f"  {'OK ' if ok else 'ERR'} {line}")
        if not ok and line != "sensorStop":
            print(f"      resposta: {text!r}")
            if "Error" in text or "not recognized" in text:
                raise SystemExit(f"O radar rejeitou o comando: {line}")


class SimulatedPort:
    """Porta falsa que gera frames reais do protocolo (para testar sem placa)."""

    def __init__(self, fps: float = 10.0) -> None:
        self.period = 1.0 / fps
        self.t0 = time.time()
        self.n = 0
        self.next_t = self.t0
        self.in_waiting = 0

    def read(self, _size: int = 1) -> bytes:
        now = time.time()
        if now < self.next_t:
            time.sleep(min(self.next_t - now, 0.05))
            return b""
        self.next_t += self.period
        self.n += 1
        t = now - self.t0
        # alvo 1 vai e vem entre 0.8 e 4 m; alvo 2 parado em 6 m, levemente a direita
        r1 = 2.4 + 1.6 * math.sin(t * 0.7)
        a1 = math.radians(20 * math.sin(t * 0.4))
        pts = [
            (r1 * math.sin(a1), r1 * math.cos(a1), 0.05, 0.4 * math.cos(t * 0.7), 28.0),
            (1.5, 5.8, 0.0, 0.0, 17.0),
        ]
        return build_packet(self.n, pts)

    def close(self) -> None:
        pass


def build_packet(frame_no: int, pts: list[tuple]) -> bytes:
    """Monta um pacote no formato do demo (usado pelo simulador e pelos testes)."""
    det = b"".join(struct.pack("<4f", *p[:4]) for p in pts)
    side = b"".join(struct.pack("<hh", int(p[4] * 10), 20) for p in pts)
    tlvs = (
        TLV_HEAD.pack(TLV_DETECTED_POINTS, len(det)) + det
        + TLV_HEAD.pack(TLV_SIDE_INFO, len(side)) + side
    )
    total = HEADER.size + len(tlvs)
    total += (-total) % 32  # o firmware preenche ate multiplo de 32 bytes
    header = HEADER.pack(MAGIC, 0x03060000, total, 0x1843, frame_no, 0, len(pts), 2, 0)
    return (header + tlvs).ljust(total, b"\x00")


def reader_thread(port, out: queue.Queue, stop: threading.Event) -> None:
    parser = FrameParser()
    while not stop.is_set():
        try:
            data = port.read(port.in_waiting or 1)
        except Exception as exc:  # porta desconectada, etc.
            print(f"[leitura] erro: {exc}", file=sys.stderr)
            stop.set()
            return
        if not data:
            continue
        for frame in parser.feed(data):
            if out.full():
                try:
                    out.get_nowait()  # descarta o mais antigo: priorizamos tempo real
                except queue.Empty:
                    pass
            out.put(frame)


# --------------------------------------------------------------------------- #
# Saida: nearest object, CSV, terminal e grafico
# --------------------------------------------------------------------------- #
def select_points(frame: Frame, args) -> list[Point]:
    return [
        p for p in frame.points
        if args.min_range <= p.range_m <= args.max_range and p.snr_db >= args.min_snr
    ]


def nearest(points: list[Point]) -> Point | None:
    return min(points, key=lambda p: p.range_m, default=None)


class CsvLogger:
    def __init__(self, path: str | None) -> None:
        self.f = None
        if path:
            self.f = open(path, "w", newline="")
            self.w = csv.writer(self.f)
            self.w.writerow(
                ["timestamp", "frame", "obj", "range_m", "x_m", "y_m", "z_m",
                 "velocity_mps", "azimuth_deg", "snr_db", "is_nearest"]
            )

    def log(self, frame: Frame, points: list[Point], near: Point | None) -> None:
        if not self.f:
            return
        for i, p in enumerate(points):
            self.w.writerow([
                f"{frame.timestamp:.3f}", frame.number, i, f"{p.range_m:.3f}",
                f"{p.x:.3f}", f"{p.y:.3f}", f"{p.z:.3f}", f"{p.velocity:.3f}",
                f"{p.azimuth_deg:.1f}", f"{p.snr_db:.1f}", int(p is near),
            ])
        self.f.flush()

    def close(self) -> None:
        if self.f:
            self.f.close()


def run_text(q: queue.Queue, stop: threading.Event, args, logger: CsvLogger) -> None:
    last = 0.0
    while not stop.is_set():
        try:
            frame = q.get(timeout=0.2)
        except queue.Empty:
            continue
        pts = select_points(frame, args)
        near = nearest(pts)
        logger.log(frame, pts, near)
        if time.time() - last < 1.0 / args.print_hz:
            continue
        last = time.time()
        if near:
            others = ", ".join(f"{p.range_m:.2f}" for p in sorted(pts, key=lambda p: p.range_m)[1:4])
            print(f"frame {frame.number:6d} | mais proximo: {near.range_m:6.2f} m "
                  f"({near.azimuth_deg:+5.1f} graus, v={near.velocity:+.2f} m/s, "
                  f"SNR {near.snr_db:.0f} dB) | {len(pts)} pts"
                  + (f" | outros: {others} m" if others else ""))
        else:
            print(f"frame {frame.number:6d} | nenhum objeto detectado")


def run_plot(q: queue.Queue, stop: threading.Event, args, logger: CsvLogger) -> None:
    import matplotlib

    if args.save_png:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.animation import FuncAnimation

    fig, (ax_map, ax_hist) = plt.subplots(
        1, 2, figsize=(12, 6), gridspec_kw={"width_ratios": [1.1, 1]}
    )
    fig.canvas.manager.set_window_title("xWR1843 - distancia em tempo real") if hasattr(
        fig.canvas, "manager") and fig.canvas.manager else None

    # Mapa "visto de cima": radar na origem, eixo y = frente
    rmax = args.max_range
    ax_map.set_aspect("equal")
    ax_map.set_xlim(-rmax, rmax)
    ax_map.set_ylim(0, rmax * 1.05)
    ax_map.set_xlabel("x lateral (m)")
    ax_map.set_ylabel("y frente (m)")
    ax_map.set_title("Vista superior")
    theta = np.linspace(-np.pi / 2, np.pi / 2, 200)
    for r in np.arange(1, rmax + 0.01, 1 if rmax <= 10 else 2):
        ax_map.plot(r * np.sin(theta), r * np.cos(theta), color="0.85", lw=0.8, zorder=0)
        ax_map.text(0.05, r, f"{r:g} m", color="0.5", fontsize=7, va="bottom")
    for ang in (-60, -30, 0, 30, 60):
        a = math.radians(ang)
        ax_map.plot([0, rmax * math.sin(a)], [0, rmax * math.cos(a)], color="0.9", lw=0.8, zorder=0)
    ax_map.plot(0, 0, "k^", ms=10)
    scat = ax_map.scatter([], [], c=[], cmap="viridis", vmin=0, vmax=40, s=60, zorder=3)
    near_dot, = ax_map.plot([], [], "o", mfc="none", mec="red", mew=2, ms=18, zorder=4)
    big = ax_map.text(0.5, 0.97, "-- m", transform=ax_map.transAxes, ha="center",
                      va="top", fontsize=26, fontweight="bold", color="crimson",
                      bbox=dict(fc="white", ec="0.8", alpha=0.9))

    # Historico da distancia ao objeto mais proximo
    window = args.history
    hist = deque()
    line_hist, = ax_hist.plot([], [], color="crimson", lw=1.8)
    ax_hist.set_xlim(-window, 0)
    ax_hist.set_ylim(0, rmax)
    ax_hist.set_xlabel("tempo (s)")
    ax_hist.set_ylabel("distancia ao mais proximo (m)")
    ax_hist.set_title(f"Ultimos {window:g} s")
    ax_hist.grid(alpha=0.3)
    status = ax_hist.text(0.02, 0.97, "", transform=ax_hist.transAxes, va="top", fontsize=9)
    fig.tight_layout()

    state = {"frames": 0, "t_fps": time.time(), "fps": 0.0}

    def update(_):
        latest = None
        while True:
            try:
                frame = q.get_nowait()
            except queue.Empty:
                break
            pts = select_points(frame, args)
            near = nearest(pts)
            logger.log(frame, pts, near)
            latest = (frame, pts, near)
            state["frames"] += 1
            hist.append((frame.timestamp, near.range_m if near else float("nan")))
        now = time.time()
        if now - state["t_fps"] >= 1.0:
            state["fps"] = state["frames"] / (now - state["t_fps"])
            state["frames"], state["t_fps"] = 0, now
        while hist and now - hist[0][0] > window:
            hist.popleft()
        if latest:
            _, pts, near = latest
            if pts:
                scat.set_offsets(np.c_[[p.x for p in pts], [p.y for p in pts]])
                scat.set_array(np.array([p.snr_db for p in pts]))
            else:
                scat.set_offsets(np.empty((0, 2)))
            if near:
                near_dot.set_data([near.x], [near.y])
                big.set_text(f"{near.range_m:.2f} m")
            else:
                near_dot.set_data([], [])
                big.set_text("-- m")
        if hist:
            ts = np.array([t - now for t, _ in hist])
            ds = np.array([d for _, d in hist])
            line_hist.set_data(ts, ds)
        status.set_text(f"{state['fps']:.1f} frames/s")
        if stop.is_set():
            plt.close(fig)
        return scat, near_dot, big, line_hist, status

    anim = FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)
    if args.save_png:
        t_end = time.time() + args.save_after
        while time.time() < t_end:
            update(None)
            time.sleep(0.05)
        fig.savefig(args.save_png, dpi=110)
        print(f"grafico salvo em {args.save_png}")
        stop.set()
        return
    try:
        plt.show()
    finally:
        stop.set()
        del anim


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-ports", action="store_true", help="lista as portas seriais e sai")
    ap.add_argument("--cli-port", help="porta CLI (XDS110 Application/User UART). Ex.: COM97, /dev/ttyACM0")
    ap.add_argument("--data-port", help="porta de dados (XDS110 Auxiliary Data Port). Ex.: COM98, /dev/ttyACM1")
    ap.add_argument("--cli-baud", type=int, default=115200)
    ap.add_argument("--data-baud", type=int, default=921600)
    ap.add_argument("--config", type=Path, default=DEFAULT_CFG, help="arquivo .cfg do demo")
    ap.add_argument("--no-config", action="store_true",
                    help="nao envia o .cfg (o radar ja foi configurado/esta transmitindo)")
    ap.add_argument("--csv", help="grava todos os pontos detectados neste arquivo CSV")
    ap.add_argument("--no-plot", action="store_true", help="apenas texto no terminal")
    ap.add_argument("--print-hz", type=float, default=5.0, help="taxa de impressao no modo texto")
    ap.add_argument("--min-range", type=float, default=0.2, help="ignora pontos mais perto que isso (m)")
    ap.add_argument("--max-range", type=float, default=9.0, help="ignora pontos mais longe que isso (m)")
    ap.add_argument("--min-snr", type=float, default=0.0, help="SNR minimo em dB")
    ap.add_argument("--history", type=float, default=30.0, help="janela do historico (s)")
    ap.add_argument("--simulate", action="store_true", help="gera dados falsos, sem hardware")
    ap.add_argument("--save-png", help="(teste) renderiza sem janela e salva o grafico neste PNG")
    ap.add_argument("--save-after", type=float, default=4.0, help="(teste) segundos antes de salvar o PNG")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if args.list_ports:
        for p in list_ports():
            print(f"{p.device:15s} {p.description}  [{p.hwid}]")
        return

    cli = None
    if args.simulate:
        data = SimulatedPort()
    else:
        import serial

        if not (args.cli_port and args.data_port):
            args.cli_port, args.data_port = autodetect_ports()
            print(f"Portas detectadas: CLI={args.cli_port}  DADOS={args.data_port}")
        try:
            data = serial.Serial(args.data_port, args.data_baud, timeout=0.05)
            if not args.no_config:
                cli = serial.Serial(args.cli_port, args.cli_baud, timeout=0.1)
        except serial.SerialException as exc:
            raise SystemExit(
                f"Nao consegui abrir a porta: {exc}\n"
                "Feche o mmWave Demo Visualizer / Radar Studio / terminal que esteja usando o COM."
            )
        if cli:
            print(f"Enviando configuracao {args.config} ...")
            send_config(cli, args.config)
        data.reset_input_buffer()

    q: queue.Queue = queue.Queue(maxsize=200)
    stop = threading.Event()
    t = threading.Thread(target=reader_thread, args=(data, q, stop), daemon=True)
    t.start()
    logger = CsvLogger(args.csv)
    print("Lendo dados do radar. Ctrl+C para sair.")
    try:
        if args.no_plot:
            run_text(q, stop, args, logger)
        else:
            run_plot(q, stop, args, logger)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        t.join(timeout=1)
        logger.close()
        if cli:
            try:
                cli.write(b"sensorStop\n")
                time.sleep(0.2)
            except Exception:
                pass
            cli.close()
        data.close()
        print("Encerrado.")


if __name__ == "__main__":
    main()
