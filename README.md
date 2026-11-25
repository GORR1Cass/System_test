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

Third-person rooftop shooter prototype in plain HTML + JavaScript (Three.js from a CDN). Open `game/index.html` in a browser – no build step.

- **Mouse** aim · **Left click** shoot · **WASD** move · **Shift** run · **Space** jump / wall jump
- **Right click** or **E** bullet time (slows player, enemies and bullets; drains the meter)
- Run and jump along a wall to **wall run**, jump into a wall to **wall climb**, jump again to **wall jump** off it
- **R** restarts after you die or clear the level
- The level is one street with buildings on both sides (and behind the start). No stairs: wall-jump up the 3–3.5 m **alleys**
  between buildings, use the **orange billboards** on lower roofs to continue up to taller neighbours, and **wall-run** along the
  orange walls to cross the 12 m courtyards (the far east tower can only be reached that way)
- Guns have a limited range (player ~60 m, enemies engage within 50 m); the crosshair turns red on an enemy in range and shows
  "Out of range" beyond it
- Enemies fire 3-round bursts; standing still in the open gets you killed quickly
- Tuning values (speeds, damage, ranges, bullet time) are in the `CFG` object at the top of the script
