# System_test – distância em tempo real com o xWR1843BOOST

Substitui o mmWave Demo Visualizer: configura o radar, lê os pontos detectados e mostra/grava a distância.

```bash
pip install -r requirements.txt
python radar_distance.py --list-ports
python radar_distance.py --cli-port COM97 --data-port COM98 --csv medidas.csv
python radar_distance.py --simulate        # testa sem hardware
```

- **CLI port** = "XDS110 Class Application/User UART" (115200 baud)
- **Data port** = "XDS110 Class Auxiliary Data Port" (921600 baud)
- Placa em modo funcional (S1: SOP0=ON, SOP1=OFF, SOP2=OFF), com o demo *out-of-box* gravado e 5 V ligada. Aperte NRST (SW2) após ligar.
- Feche o Visualizer/navegador antes: só um programa pode usar o COM.
- Ajuste o alcance/resolução em `xwr1843_distance.cfg` (ou use o .cfg exportado do Visualizer).

## Game prototype – Cube Rooftops (`game/`)

Third-person parkour shooter prototype in plain HTML + JavaScript (Three.js from a CDN). Open `game/index.html` in a browser – no build step. The level is built only from boxes.

- **Mouse** aim · **Left click** shoot · **WASD** move · **Shift** run · **Space** jump / wall jump
- **Right click** or **E** bullet time (slows player, enemies and bullets; drains the meter)
- Run and jump along a wall to **wall run** (faster than running), jump into a wall to **wall climb**, jump again to **wall jump**
- **R** restarts at any time

### Level design

One critical path from the start roof to the red-tipped spire, built on a few level-design principles:

| Principle | Where it shows up |
| --- | --- |
| Flow / momentum, colour-coded route (Mirror's Edge "runner vision") | Every traversal surface is orange; each move sets up the next |
| Teach → test → combine (Titanfall 2 enforces wall running early) | Sections 1–2 teach the wall run and the wall-jump corridor with no enemies; arenas test them under fire; later sections combine them |
| Combat arenas joined by traversal ("combat bowls", Gears of War / Ghostrunner) | Two arenas with enemies on floor, ledge and roof layers, hard-cornered cover, an overlook on entry, and a low (fight) and high (wall-run) route |
| Landmark / "weenie" | The spire's red mast is visible from the start, framed by the first corridor |
| Forgiving failure | Every gap drops to the ground floor with a climbable way back up |
| Push-forward combat (Doom), kill-refilled bullet time (Max Payne 2) | Each kill gives +20 health and +35 bullet time |

Sections: start roof → wall-run gap → wall-jump corridor → arena 1 (courtyard) → zig-zag wall-run corridor → arena 2 (spire plaza) → spire top.

- 16 enemies at fixed posts; they fire 3-round bursts, only when they are **on your screen** (with a short reaction delay), and are much less accurate against a wall-running player
- Guns have a limited range (player ~60 m, enemies 50 m); the crosshair shows "Out of range"
- Tuning values (speeds, damage, ranges, rewards, bullet time) are in the `CFG` object at the top of the script
