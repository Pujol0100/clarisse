from clarisse.leitora.segredo import contem_segredo, mascarar


def test_mascara_valor_de_senha_em_atribuicao():
    texto = 'conectei com password=Trocar123! e deu certo'
    assert mascarar(texto) == 'conectei com password=[oculto] e deu certo'


def test_mascara_chave_da_anthropic():
    texto = 'usei a chave sk-ant-api03-abc123DEF456 no teste'
    assert mascarar(texto) == 'usei a chave [oculto] no teste'


def test_mascara_cabecalho_bearer():
    texto = 'mandei Authorization: Bearer eyJhbGciOiJIUzI1NiJ9 no header'
    assert mascarar(texto) == 'mandei Authorization: Bearer [oculto] no header'


def test_bearer_nao_deixa_o_token_sobrar_atras_da_palavra_mascarada():
    # A palavra Authorization casa com o padrao de atribuicao, e a palavra
    # Bearer parece o valor. Mascarar Bearer e deixar o token e o modo de
    # falhar que engana: [oculto] aparece e o segredo sobrevive.
    saida = mascarar('Authorization: Bearer eyJhbGciOiJIUzI1NiJ9')
    assert 'eyJhbGciOiJIUzI1NiJ9' not in saida


def test_mascara_chave_de_acesso_da_aws():
    texto = 'a conta usa AKIAIOSFODNN7EXAMPLE hoje'
    assert mascarar(texto) == 'a conta usa [oculto] hoje'


def test_nao_mascara_a_palavra_senha_sem_valor():
    texto = 'o usuario esqueceu a senha e pediu para redefinir'
    assert mascarar(texto) == texto
    assert contem_segredo(texto) is False


def test_contem_segredo_acusa_quando_mascarou():
    assert contem_segredo('token: abc123xyz789') is True


def test_texto_vazio_nao_quebra():
    assert mascarar('') == ''
    assert contem_segredo('') is False
