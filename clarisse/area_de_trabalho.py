"""Fronteira com a área de trabalho do Windows: volume, janelas, área de transferência e teclas."""
from pycaw.pycaw import AudioUtilities


def definir_volume(nivel: int) -> None:
    AudioUtilities.GetSpeakers().EndpointVolume.SetMasterVolumeLevelScalar(nivel / 100, None)
