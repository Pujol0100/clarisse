from clarisse.tecla import escutar_pela_tecla


async def test_cada_aperto_da_tecla_liga_ou_desliga_o_microfone():
    publicados = []

    async def publicar(evento):
        publicados.append(evento)

    async def dois_apertos():
        yield
        yield

    await escutar_pela_tecla(publicar, apertos=dois_apertos)

    assert publicados == [{"tipo": "escutar"}, {"tipo": "escutar"}]
