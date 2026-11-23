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
