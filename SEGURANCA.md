# Segurança — Clarisse

Metodologia: requisitos AppSec da Smart Compass (skill auditoria-seguranca).
Atualizado em: 28/09/2026

A Clarisse é uma aplicação local de um usuário só. Ela não tem banco, cadastro nem
login de pessoas, mas abre uma porta em `127.0.0.1` que **executa ações na
máquina**. O risco central é outro programa — em especial uma página aberta no
navegador — mandar pedidos para essa porta. Os itens abaixo foram lidos com isso
em mente.

| # | Requisito | Situação | Onde / motivo |
|---|-----------|----------|---------------|
| 1 | Esconder API Keys | pendente | |
| 2 | Limpar secrets do Git | pendente | |
| 3 | Public Key DB (chaves públicas vs. privadas de banco) | não se aplica | sem banco de dados |
| 4 | Ativar RLS (Row Level Security) | não se aplica | sem banco e sem múltiplos usuários |
| 5 | Criptografia de dados | pendente | |
| 6 | Auth server-side | pendente | |
| 7 | Restringir acessos (authorization / IDOR) | pendente | |
| 8 | Bloquear Mass Assignment | pendente | |
| 9 | Proteger Cookies | pendente | |
| 10 | Hash nas Senhas | não se aplica | a aplicação não guarda senha |
| 11 | Rate Limit | pendente | |
| 12 | Bot protection | pendente | |
| 13 | Queries parametrizadas | pendente | |
| 14 | Validação de inputs | pendente | |
| 15 | Vazar conteúdo (data leakage) | pendente | |
| 16 | Restringir uploads | pendente | |
| 17 | Trim respostas de API (over-fetching) | pendente | |
| 18 | Add security headers | pendente | |
| 19 | Forçar HTTPS | pendente | |
| 20 | Scan de dependências | pendente | |
| 21 | Código de origem open source (procedência e risco de supply chain) | pendente | |

## Código de terceiros copiado

| Componente | Origem | Versão | Licença | Modificado? |
|---|---|---|---|---|
