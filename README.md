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
- Run and jump along a wall to **wall run** (it holds you level and never lifts you; you keep the speed you arrive with and slowly lose it; too slow and you slide off), jump into a wall to **wall climb**, jump again to **wall jump**
- **Steer wall jumps** with the movement keys: hold toward the wall to jump up it, away from it to leap out, along it (or nothing) for a balanced jump. One wall jump per wall until you land or touch another wall
- **Steer in the air** by holding a direction: your flight turns toward it (holding back brakes). Right after a wall jump the jump carries you for a quarter of a second first, and you never come out of a wall jump faster than you were running along the wall
- **R** restarts at any time · **M** turns sound on/off (all sounds are synthesized in the browser; they start after your first click)

**Goal:** reach the top of the red-tipped spire. Fighting is optional (kills refill health and bullet time); clearing every enemy does not end the level. The top-right panel shows the distance to the spire.

### Level design

One critical path from the start roof to the red-tipped spire, built on a few level-design principles:

| Principle | Where it shows up |
| --- | --- |
| Flow / momentum, colour-coded route (Mirror's Edge "runner vision") | Every traversal surface is orange; each move sets up the next |
| Teach → test → combine (Titanfall 2 enforces wall running early) | Sections 1–2 teach the wall run and the wall-jump corridor with no enemies; arenas test them under fire; later sections combine them |
| Combat arenas joined by traversal ("combat bowls", Gears of War / Ghostrunner) | Two arenas with enemies on floor, ledge and roof layers, hard-cornered cover, an overlook on entry, and a low (fight) and high (wall-run) route |
| Landmark / "weenie" | The spire's red mast is visible from the start, framed by the first corridor |
| Forgiving failure | Every gap drops to the ground floor with a climbable way back up |
| Push-forward combat (Doom), kill-refilled bullet time (Max Payne 2) | Each kill gives +20 health and +35 bullet time; bullet time never refills on its own |

Each section has its own look (sandstone old town, construction site, brick courtyard, slate industrial, glass plaza) and the sky shifts from hazy to deep blue toward the spire. The camera keeps to the open side in tight spaces and the player turns see-through if the camera gets very close.

Sections: start roof → wall-run channel (the only way across; the right side is a 12 m block) → enclosed climbing well (four platforms, closed sides) → arena 1 (courtyard) → zig-zag wall-run corridor → arena 2 (spire plaza) → **spire run**: wall-run out over the plaza, hop three rising platforms, wall-run toward the spire, then climb three stepped buttresses (or wall-run along the spire face between the last two) to the top. Falling into the plaza: a shaft leads back up to the start of the run.

- 14 enemies of three types at fixed posts: **riflemen** (keep their distance, 3-round bursts), **snipers** (darker, long barrel; a laser tracks you for ~1 s, locks, then one heavy shot — move when it locks), **rushers** (smaller, brighter; charge in and fire a close-range spread). Enemies steer around walls and cover and recover if they get stuck. Arena 1 has enemies on the floor, ledges and a roof; in the spire plaza every enemy holds a raised post (ledges at 6–24 m, a tower roof, the spire top) and none come down. Enemies are aggressive: fast, accurate bursts, quick reactions, and riflemen only back off when you get within 10 m; riflemen and rushers only fire when they are **on your screen** (with a short reaction delay); snipers can fire from off screen, since their laser and a rising tone warn you and the shot can be dodged, and are much less accurate against a wall-running player
- Enemies posted 7 m up or lower decide every second or two whether to hold their post or jump down to the floor: they drop to escape when you reach their level up close, or to hunt you when they lose sight of you on the floor. Higher posts always stay
- Guns have a limited range (player ~60 m, enemies 50 m); the crosshair shows "Out of range"
- Tuning values (speeds, damage, ranges, rewards, bullet time) are in the `CFG` object at the top of the script
