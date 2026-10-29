# Observatório da Educação do Rio Grande do Norte
## Ficha metodológica — versão 9 (documento de trabalho)
**Data:** 29 de outubro de 2026  
**Situação:** protótipo local funcional; validação científica e publicação pública pendentes.

### 1. Finalidade e abrangência
O Observatório é uma iniciativa de interesse público e científico destinada a facilitar a consulta e a comparação crítica de informações educacionais do Rio Grande do Norte. A versão 9 abrange inicialmente a **educação básica**, com registros escolares do **Censo Escolar 2024**. Não constitui, ainda, série histórica desde 2000 nem inclui indicadores de evasão, IDEB, ENADE, ensino superior ou identificação de dirigentes escolares.

### 2. Fontes e referências temporais
- **INEP:** microdados do Censo Escolar da Educação Básica 2024, arquivo local `dados/brutos/microdados_ed_basica_2024.csv`.
- **IBGE:** Censo Demográfico 2022, tabela 4714, variável 93, população residente dos municípios do Rio Grande do Norte, consultada pela API oficial e armazenada em `dados/ibge_populacao_municipios_rn_2022.csv`.
- **Atenção:** os dados escolares referem-se a 2024, enquanto os populacionais se referem a 2022. Não se deve apresentá-los como observações simultâneas nem interpretar a relação entre matrículas e população total como taxa de escolarização.

**Consulta à API IBGE:** https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93?localidades=N6%5BN3%5B24%5D%5D

### 3. Universo e unidade de observação
O programa seleciona registros para os quais `SG_UF = 'RN'` e `TP_SITUACAO_FUNCIONAMENTO = 1` (em atividade). A unidade básica da ficha é a escola, identificada por `CO_ENTIDADE`. Os agrupamentos municipais utilizam `NO_MUNICIPIO`; a ligação com a população utiliza `CO_MUNICIPIO`, convertido em código IBGE de sete dígitos.

Os totais dependem dos filtros de município, dependência administrativa e localização. Quando um recorte não contém escolas de determinado município, esse município pode deixar de aparecer na tabela.

### 4. Indicadores educacionais
| Indicador exibido | Campo do arquivo | Regra empregada | Ressalva |
|---|---|---|---|
| Escolas em atividade | `CO_ENTIDADE` | Número de códigos escolares distintos no recorte | Não inclui escolas fora do filtro de funcionamento |
| Matrículas na educação básica | `QT_MAT_BAS` | Soma dos valores numéricos das escolas | Matrículas não equivalem necessariamente a pessoas distintas |
| Soma de docentes por escola | `QT_DOC_BAS` | Soma dos valores numéricos das escolas | Não corresponde necessariamente a docentes distintos no município |
| Turmas da escola | `QT_TUR_BAS` | Valor informado no registro escolar | Aplicabilidade conforme dicionário do INEP |
| Infraestrutura | Variáveis `IN_...` selecionadas | 1 = declaração de presença; 0 = declaração de ausência | Declaração censitária, não vistoria presencial |

**Percentual municipal de infraestrutura** = (número de escolas com resposta **1**) ÷ (número de escolas com resposta **0 ou 1**) × 100.  
Registros não interpretáveis como 0 ou 1 ficam **fora do denominador** e são apresentados separadamente. Se não houver respostas válidas, o percentual não é calculado.

As variáveis de quantidade (`QT_...`) não devem ser interpretadas como indicadores binários. As regras de aplicabilidade, códigos especiais e significados exatos de cada variável ainda precisam de conferência com o dicionário oficial do Censo Escolar 2024.

### 5. População municipal e integração
A população é importada em CSV com as colunas `codigo_ibge` e `populacao_2022`. O programa verifica o formato dos códigos, rejeita códigos duplicados e associa a população ao panorama escolar pelo código municipal. O resultado exibido no teste local foi de **167 correspondências para 167 municípios**.

A importação local informou **167 municípios e 3.302.729 habitantes**; a captura da versão 8 mostrou, entre outros exemplos, **Natal: 751.300 habitantes** e **Mossoró: 264.577 habitantes** (2022). Esses resultados são evidências do funcionamento da integração, **não substituem uma auditoria independente dos arquivos de origem**.

As faixas de população são calculadas com os valores de 2022. A população não muda quando se filtram redes escolares ou escolas urbanas/rurais: trata-se da população **total do município**, e não da população atendida pela rede selecionada.

### 6. Leitura responsável e limitações
- O Observatório oferece **descrições**, não rankings automáticos de qualidade educacional.
- Diferenças entre municípios podem refletir composição das redes, etapas ofertadas, porte populacional, território e condições socioeconômicas.
- A existência declarada de um recurso não comprova seu estado de conservação, acessibilidade efetiva ou qualidade de uso.
- Matrículas, docentes e escolas possuem unidades distintas; não devem ser confundidos nem somados entre si.
- A comparação direta de dados escolares de 2024 com população total de 2022 exige cautela metodológica.
- O aplicativo não exibe dados pessoais de estudantes; futuras expansões deverão manter controles de privacidade e verificar eventuais informações pessoais de profissionais.

### 7. Verificações antes da divulgação pública
1. Conferir a versão exata, a procedência e o dicionário de variáveis dos microdados INEP 2024.
2. Validar contagens estaduais e uma amostra de municípios e escolas contra tabulações oficiais do INEP.
3. Confrontar a população de Natal, Mossoró e municípios de diferentes portes com a tabela oficial do IBGE.
4. Verificar códigos, duplicações, valores ausentes e a regra de funcionamento das escolas.
5. Examinar os indicadores `IN_...` quanto a não resposta, não aplicabilidade e mudanças de definição.
6. Testar os filtros, o CSV exportado, a acessibilidade e a documentação de fontes e licenças.
7. Registrar data de atualização, versão do aplicativo e transformações realizadas.

### 8. Princípio orientador
**Dados para entender. Conhecimento para debater. Educação para transformar.**

A proposta é disponibilizar evidências para a investigação pública e o debate informado, sem transformar números isolados em julgamentos apressados sobre escolas, municípios ou profissionais.

*Epígrafe em discussão para a identidade institucional: “O que são dados senão memória?”*
