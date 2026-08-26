"""O servidor residente do Ouvinte: carrega o modelo uma vez e espera pedido.

Iniciar o Python a cada tecla custa 8,42 s fixos nesta maquina (0,13 s de
interpretador, 1,51 s de import, 6,78 s de carga do modelo), medido em
25/08/2026 contra um criterio de 0,5 s escrito antes. Dai o residente.

A conversa e por arquivo, como o resto do projeto ja faz: o atalho escreve o
comando, o servidor devolve o texto e so entao levanta o sinal. O sinal e
obrigatorio — arquivo ainda em escrita e lido pela metade, e isso ja custou caro
uma vez com o mp3.

Uma instancia por maquina, nao por sessao: sao ~10 sessoes do Claude Code
abertas, e dez modelos residentes seriam ~6 GB de RAM disputando o microfone.
"""

from __future__ import annotations

import ctypes
import gc
import time
from collections.abc import Callable
from pathlib import Path

PID = 'servidor.pid'
COMANDO = 'comando.txt'
TEXTO = 'texto.txt'
SINAL = 'pronto.flag'

DITAR = 'ditar'

OCIOSO_S = 15 * 60
INTERVALO_S = 0.12  # o mesmo passo com que o reprodutor le o controle da pausa

_ACESSO_CONSULTA = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
_AINDA_ATIVO = 259  # STILL_ACTIVE


def processo_vivo(pid: int) -> bool:
    """Diz se aquele PID e um processo que ainda roda.

    Nao usar `os.kill(pid, 0)` aqui: no Windows o CPython implementa `os.kill`
    abrindo o processo e chamando `TerminateProcess`, entao o teste de vida
    mataria o servidor que ele deveria apenas encontrar.

    Um processo que saiu com o codigo 259 aparece como vivo. E o preco de
    consultar por codigo de saida, e ele e pequeno perto de matar o processo.
    """
    kernel32 = ctypes.windll.kernel32
    alca = kernel32.OpenProcess(_ACESSO_CONSULTA, False, pid)
    if not alca:
        return False
    try:
        codigo = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(alca, ctypes.byref(codigo)):
            return False
        return codigo.value == _AINDA_ATIVO
    finally:
        kernel32.CloseHandle(alca)


def travar(
    pasta: Path,
    *,
    pid: int,
    vivo: Callable[[int], bool] = processo_vivo,
) -> bool:
    """Toma a trava da maquina para este PID, ou recusa se ja ha dono vivo.

    PID orfao de processo morto nao pode bloquear a subida do proximo: a maquina
    e desligada no botao com frequencia, e um arquivo esquecido deixaria o
    Ouvinte mudo ate alguem apagar na mao.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / PID

    dono = _pid_registrado(arquivo)
    if dono is not None and dono != pid and vivo(dono):
        return False

    arquivo.write_text(str(pid), encoding='utf-8')
    return True


def _pid_registrado(arquivo: Path) -> int | None:
    try:
        return int(arquivo.read_text(encoding='utf-8').strip())
    except (OSError, ValueError):
        return None


def escrever(caminho: Path, conteudo: str) -> None:
    caminho.write_text(conteudo, encoding='utf-8')


def registrar_no_log(pasta: Path, mensagem: str) -> None:
    """Anota no mesmo `clarisse.log` que o lado PowerShell ja escreve."""
    from datetime import datetime

    carimbo = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    try:
        with (Path(pasta).parent / 'clarisse.log').open('a', encoding='utf-8') as saida:
            saida.write(f'[{carimbo}] ouvinte: {mensagem}\n')
    except OSError:
        pass


class Servidor:
    """Atende um pedido por vez, guardando o motor entre pedidos.

    O motor abre no primeiro pedido, nao na construcao: subir junto com a sessao
    do Claude Code custaria 500 a 700 MB de RAM de quem talvez nunca aperte a
    tecla.
    """

    def __init__(
        self,
        pasta: Path,
        *,
        abrir_motor: Callable[[], object],
        ditar: Callable[[object], str],
        registrar: Callable[[str], None] | None = None,
        ocioso_s: float = OCIOSO_S,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._abrir_motor = abrir_motor
        self._ditar = ditar
        self._registrar = registrar or (lambda msg: registrar_no_log(self.pasta, msg))
        self._ocioso_s = ocioso_s
        self._relogio = relogio
        self._motor: object | None = None
        self._ultimo_uso = relogio()

    @property
    def motor_carregado(self) -> bool:
        return self._motor is not None

    def rodar(
        self,
        *,
        intervalo_s: float = INTERVALO_S,
        parar: Callable[[], bool] | None = None,
    ) -> None:
        """Atende ate mandarem parar.

        Sem `parar`, roda ate o processo ser encerrado — e o mesmo contrato do
        escutador de atalhos, que sai pelo `clarisse.ps1 -Mode atalhos-off`.
        """
        parar = parar or (lambda: False)
        while not parar():
            self.passo()
            time.sleep(intervalo_s)

    def passo(self) -> None:
        """Uma volta: le o pedido, se houver, e responde."""
        comando = self._pegar_comando()
        if comando is None:
            self._talvez_descarregar()
            return

        self._limpar_resposta()

        if comando != DITAR:
            self._registrar(f'comando desconhecido: {comando!r}')
            return

        try:
            texto = self._ditar(self._motor_pronto())
        except Exception as erro:  # fronteira: o servidor nao pode cair
            self._registrar(f'ditado falhou: {erro!r}')
            return
        finally:
            # O ocio conta do fim do trabalho: transcrever leva segundos, e
            # contar do inicio encurtaria a folga de quem acabou de ditar.
            self._ultimo_uso = self._relogio()

        if not texto:
            self._registrar('ditado sem texto - nada a digitar')
            return

        escrever(self.pasta / TEXTO, texto)
        escrever(self.pasta / SINAL, '')

    def _motor_pronto(self) -> object:
        if self._motor is None:
            self._motor = self._abrir_motor()
        self._ultimo_uso = self._relogio()
        return self._motor

    def _talvez_descarregar(self) -> None:
        """Solta o modelo depois de um tempo parado.

        Sao 500 a 700 MB de RAM parados numa maquina que ja segura dez sessoes
        do Claude Code. O proximo pedido paga a carga de novo, e tudo bem: quem
        ficou quinze minutos sem ditar nao esta cronometrando a proxima frase.
        """
        if self._motor is None:
            return
        if self._relogio() - self._ultimo_uso < self._ocioso_s:
            return

        self._motor = None
        gc.collect()
        self._registrar('motor descarregado por ocio')

    def _pegar_comando(self) -> str | None:
        """Le e apaga o pedido. Pedido lido duas vezes seria ditado duas vezes."""
        arquivo = self.pasta / COMANDO
        try:
            comando = arquivo.read_text(encoding='utf-8').strip()
        except OSError:
            return None
        arquivo.unlink(missing_ok=True)
        return comando

    def _limpar_resposta(self) -> None:
        """Derruba a resposta anterior antes de comecar.

        Sinal velho de pe faria o atalho digitar o texto da frase passada.
        """
        (self.pasta / SINAL).unlink(missing_ok=True)
        (self.pasta / TEXTO).unlink(missing_ok=True)
