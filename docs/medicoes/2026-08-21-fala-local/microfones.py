import sounddevice as sd

padrao = sd.default.device[0]
print("dispositivos de entrada disponiveis:\n")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        marca = "  <== PADRAO" if i == padrao else ""
        print(f"{i:3}  canais={d['max_input_channels']:2}  {d['name'][:55]}{marca}")
print(f"\ntaxa padrao: {sd.query_devices(padrao)['default_samplerate']:.0f} Hz")
