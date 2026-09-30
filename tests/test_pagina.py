"""A página de verdade (pasta web/): rosto holográfico, drones e o que ela precisa carregar."""
import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def _scripts_da_pagina():
    return re.findall(r'<script src="/static/([^"]+)"', (WEB / "index.html").read_text(encoding="utf-8"))


def test_pagina_carrega_a_malha_antes_do_rosto_e_o_rosto_antes_do_app():
    scripts = _scripts_da_pagina()

    assert {"malha-rosto.js", "rosto.js", "enxame.js", "app.js"} <= set(scripts)
    assert scripts.index("malha-rosto.js") < scripts.index("rosto.js") < scripts.index("app.js")
    assert scripts.index("enxame.js") < scripts.index("app.js")


def test_pagina_tem_onde_desenhar_o_rosto():
    assert '<canvas id="rosto"' in (WEB / "index.html").read_text(encoding="utf-8")


def test_malha_do_rosto_esta_completa():
    texto = (WEB / "malha-rosto.js").read_text(encoding="utf-8")
    malha = json.loads(re.search(r"const MALHA_DO_ROSTO = (\{.*\});", texto, re.S).group(1))

    assert len(malha["v"]) == 468
    assert len(malha["f"]) == 898
    assert all(0 <= k < 468 for triangulo in malha["f"] for k in triangulo)


def test_licenca_do_mediapipe_acompanha_a_malha():
    texto = (WEB / "malha-rosto.js").read_text(encoding="utf-8")
    licenca = WEB / "licencas" / "mediapipe-LICENSE.txt"

    assert "Apache" in texto and "licencas/mediapipe-LICENSE.txt" in texto
    assert "Apache License" in licenca.read_text(encoding="utf-8")


def test_cores_da_marca_na_pagina():
    css = (WEB / "estilo.css").read_text(encoding="utf-8").lower()

    assert "#0a0a0a" in css and "#c9a84c" in css
    assert "#15294a" not in css and "#0e1a2b" not in css


def test_scripts_so_procuram_elementos_que_existem_na_pagina():
    pagina = (WEB / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', pagina))

    for script in _scripts_da_pagina():
        procurados = set(re.findall(r'getElementById\("([^"]+)"\)', (WEB / script).read_text(encoding="utf-8")))
        assert procurados <= ids, f"{script} procura {sorted(procurados - ids)}, que não existe na página"


def test_conversa_fica_num_painel_ao_lado_da_clarisse_como_historico():
    pagina = (WEB / "index.html").read_text(encoding="utf-8")

    assert re.search(r'<main class="palco">[\s\S]*</main>\s*<aside class="painel"', pagina)
    assert re.search(r'<section class="conversa" id="conversa" role="log"', pagina)
    assert pagina.index('id="conversa"') < pagina.index('id="formulario"')


def test_mensagens_do_chat_sao_criadas_como_texto_e_nunca_como_html():
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "innerHTML" not in app
    assert "textContent" in app
