"""A página de verdade (pasta web/): anel com a constelação de ferramentas, cartões e escrita opcional."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def _pagina():
    return (WEB / "index.html").read_text(encoding="utf-8")


def _scripts_da_pagina():
    return re.findall(r'<script src="/static/([^"]+)"', _pagina())


def test_pagina_carrega_nucleo_e_cartoes_antes_do_app_e_nada_do_rosto():
    scripts = _scripts_da_pagina()

    assert {"nucleo.js", "cartoes.js", "app.js"} <= set(scripts)
    assert scripts.index("nucleo.js") < scripts.index("app.js")
    assert scripts.index("cartoes.js") < scripts.index("app.js")
    assert not {"rosto.js", "malha-rosto.js", "enxame.js"} & set(scripts)
    assert not any((WEB / nome).exists() for nome in ("rosto.js", "malha-rosto.js", "enxame.js"))


def test_pagina_tem_o_canvas_do_nucleo_e_os_lugares_dos_cartoes():
    pagina = _pagina()

    assert '<canvas id="nucleo"' in pagina
    for id_ in ("palco-cartao", "fileira", "legenda", "voce", "estado"):
        assert f'id="{id_}"' in pagina


def test_escrever_e_opcional_e_o_chat_comeca_fechado():
    pagina = _pagina()

    assert re.search(r'<button[^>]+id="escrever"[^>]+aria-expanded="false"', pagina)
    assert re.search(r'<aside[^>]+id="chat"', pagina)
    assert "com-chat" not in re.search(r"<body[^>]*>", pagina).group(0)
    assert pagina.index('id="chat"') < pagina.index('id="formulario"') < pagina.index('id="texto"')


def test_confirmar_e_cancelar_ficam_dentro_do_chat():
    pagina = _pagina()
    chat = re.search(r'<aside[^>]+id="chat"[\s\S]*?</aside>', pagina).group(0)

    assert 'id="confirmar"' in chat and 'id="cancelar"' in chat


def test_nucleo_mostra_o_logo_da_smart_no_lugar_do_globo():
    nucleo = (WEB / "nucleo.js").read_text(encoding="utf-8")
    logo = WEB / "logo-smart.png"

    assert "/static/logo-smart.png" in nucleo
    assert "desenharGlobo" not in nucleo
    assert logo.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_cores_da_marca_na_pagina():
    css = (WEB / "estilo.css").read_text(encoding="utf-8").lower()

    assert "#0a0a0a" in css and "#c9a84c" in css
    assert "#15294a" not in css and "#0e1a2b" not in css


def test_scripts_so_procuram_elementos_que_existem_na_pagina():
    ids = set(re.findall(r'id="([^"]+)"', _pagina()))

    for script in _scripts_da_pagina():
        procurados = set(re.findall(r'getElementById\("([^"]+)"\)', (WEB / script).read_text(encoding="utf-8")))
        assert procurados <= ids, f"{script} procura {sorted(procurados - ids)}, que não existe na página"


def test_textos_de_fora_sao_criados_como_texto_e_nunca_como_html():
    for script in _scripts_da_pagina():
        codigo = (WEB / script).read_text(encoding="utf-8")
        assert "innerHTML" not in codigo, script
        assert "insertAdjacentHTML" not in codigo, script
    assert "textContent" in (WEB / "cartoes.js").read_text(encoding="utf-8")
