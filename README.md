# 🐘 Observatório da Educação do Rio Grande do Norte

**Dados para entender. Conhecimento para debater. Educação para transformar.**

Protótipo público beta (versão 9) de observatório científico e gratuito da educação básica do Rio Grande do Norte.

## Fontes
- INEP — Censo Escolar da Educação Básica, 2024 (escolas em atividade no RN).
- IBGE — Censo Demográfico 2022, tabela 4714, variável 93 (população municipal).

## Limitações
Os dados escolares são de 2024 e a população de 2022. Matrículas não equivalem necessariamente a estudantes distintos; a soma de docentes por escola não é contagem de pessoas distintas. Os indicadores de infraestrutura são declaratórios. Auditoria técnica preliminar não substitui validação independente. Os 48 registros com valores ausentes nas quantidades de matrículas e docentes requerem investigação.

## Execução
`pip install -r requirements.txt` e `streamlit run app.py`.

## Preparação dos dados
O arquivo `dados/escolas_rn_2024_publicacao.csv` é um **recorte derivado** dos microdados oficiais, apenas escolas em atividade no RN. O arquivo original completo não deve ser enviado ao GitHub. Veja `INSTRUCOES_PUBLICACAO.txt` no pacote preparador.

Consulte também `FICHA_METODOLOGICA.md`.
