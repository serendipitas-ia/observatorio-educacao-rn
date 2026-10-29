from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Observatório da Educação do RN', page_icon='🐘', layout='wide')
BASE = Path(__file__).resolve().parent
ARQUIVO = BASE / 'dados' / 'escolas_rn_2024_publicacao.csv'
ARQUIVO_POP = BASE / 'dados' / 'ibge_populacao_municipios_rn_2022.csv'

@st.cache_data(show_spinner='Lendo os microdados oficiais de 2024…')
def carregar(caminho, tamanho, modificacao):
    df = pd.read_csv(caminho, sep=';', encoding='utf-8-sig', low_memory=False)
    df = df.loc[(df['SG_UF'].astype(str).str.strip() == 'RN') & (pd.to_numeric(df['TP_SITUACAO_FUNCIONAMENTO'], errors='coerce') == 1)].copy()
    return df

@st.cache_data(show_spinner=False)
def carregar_populacao(caminho, tamanho, modificacao):
    """Lê o CSV populacional oficial importado, sujeito a validação."""
    pop = pd.read_csv(caminho, sep=';', dtype={'codigo_ibge': str}, encoding='utf-8-sig')
    obrigatorias = {'codigo_ibge', 'populacao_2022'}
    if not obrigatorias.issubset(pop.columns):
        raise ValueError('CSV do IBGE precisa conter codigo_ibge e populacao_2022.')
    pop = pop[['codigo_ibge', 'populacao_2022']].copy()
    pop['codigo_ibge'] = pop['codigo_ibge'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    pop['populacao_2022'] = pd.to_numeric(pop['populacao_2022'], errors='coerce')
    pop = pop.dropna(subset=['populacao_2022'])
    pop = pop[pop['codigo_ibge'].str.fullmatch(r'\d{7}', na=False)]
    if pop['codigo_ibge'].duplicated().any():
        raise ValueError('Há códigos municipais repetidos no CSV do IBGE; verifique a fonte.')
    return pop

def indicador_municipal(parte, coluna):
    valores = pd.to_numeric(parte[coluna], errors='coerce')
    validos = valores.isin([0, 1])
    n = int(validos.sum())
    sim = int((valores == 1).sum())
    return sim, n, int(len(parte) - n), round(sim * 100 / n, 1) if n else float('nan')

def numero(v):
    if pd.isna(v): return 'Não informado'
    try: return f'{int(float(v)):,}'.replace(',', '.')
    except (ValueError, TypeError): return str(v)

def valor(row, col):
    if col not in row.index or pd.isna(row[col]): return 'Não informado'
    return row[col]

def sim_nao(row, col):
    v = valor(row, col)
    if str(v) in ('1', '1.0'): return 'Sim'
    if str(v) in ('0', '0.0'): return 'Não'
    return 'Não informado'

def dependencias(v):
    return {1:'Federal', 2:'Estadual', 3:'Municipal', 4:'Privada'}.get(pd.to_numeric(v, errors='coerce'), 'Não informada')

def localizacao(v):
    return {1:'Urbana', 2:'Rural'}.get(pd.to_numeric(v, errors='coerce'), 'Não informada')

st.title('🐘 Observatório da Educação do Rio Grande do Norte')
st.markdown("""
<div style="font-size:clamp(1.05rem, 2vw, 1.45rem); font-weight:650;
            line-height:1.5; margin-top:-0.5rem; margin-bottom:0.5rem; color:inherit;">
Dados para entender. Conhecimento para debater. Educação para transformar.
</div>
""", unsafe_allow_html=True)
st.caption('Protótipo público beta • Versão 9 • Censo Escolar 2024 (INEP) • Censo Demográfico 2022 (IBGE)')
if not ARQUIVO.exists():
    st.error('Arquivo de dados da publicação não encontrado: dados/escolas_rn_2024_publicacao.csv. Execute o preparador no Mac e envie os arquivos gerados.')
    st.stop()
try:
    info = ARQUIVO.stat()
    df = carregar(str(ARQUIVO), info.st_size, info.st_mtime)
except Exception as e:
    st.error(f'Não foi possível ler o arquivo do INEP: {e}')
    st.stop()

with st.sidebar:
    st.header('Filtros')
    municipio = st.selectbox('Município', ['Todos os municípios'] + sorted(df['NO_MUNICIPIO'].dropna().astype(str).unique().tolist()))
    rede = st.selectbox('Dependência administrativa', ['Todas as redes', 'Federal', 'Estadual', 'Municipal', 'Privada'])
    zona = st.selectbox('Localização', ['Todas as localizações', 'Urbana', 'Rural'])

filtrado = df.copy()
if municipio != 'Todos os municípios': filtrado = filtrado[filtrado['NO_MUNICIPIO'] == municipio]
if rede != 'Todas as redes': filtrado = filtrado[filtrado['TP_DEPENDENCIA'].map(dependencias) == rede]
if zona != 'Todas as localizações': filtrado = filtrado[filtrado['TP_LOCALIZACAO'].map(localizacao) == zona]

aba_geral, aba_escolas, aba_comparar, aba_panorama, aba_fontes, aba_auditoria = st.tabs(['📊 Visão geral', '🏫 Escolas e fichas', '⚖️ Comparar municípios', '🗺️ Panorama municipal', '📖 Fontes e metodologia', '🔎 Auditoria dos dados'])
with aba_geral:
    st.subheader('Indicadores de 2024')
    a,b,c = st.columns(3)
    a.metric('Escolas em atividade', numero(filtrado['CO_ENTIDADE'].nunique()))
    b.metric('Matrículas na educação básica', numero(pd.to_numeric(filtrado['QT_MAT_BAS'], errors='coerce').sum()))
    c.metric('Soma de docentes por escola', numero(pd.to_numeric(filtrado['QT_DOC_BAS'], errors='coerce').sum()))
    st.caption('Matrículas não são necessariamente estudantes distintos; a soma de docentes por escola não corresponde necessariamente a pessoas distintas.')
    st.subheader('Matrículas por etapa de ensino')
    etapas = {'Educação infantil':'QT_MAT_INF', 'Ensino fundamental':'QT_MAT_FUND', 'Ensino médio':'QT_MAT_MED'}
    dados = {nome:int(pd.to_numeric(filtrado[col], errors='coerce').sum()) for nome,col in etapas.items() if col in filtrado.columns}
    st.bar_chart(pd.DataFrame({'Matrículas':dados}))
    st.caption('As categorias exibidas não representam necessariamente uma decomposição exaustiva do total da educação básica.')
    st.subheader('Escolas por dependência administrativa')
    st.bar_chart(filtrado['TP_DEPENDENCIA'].map(dependencias).value_counts())

with aba_escolas:
    st.subheader('Consulta de escolas')
    busca = st.text_input('Buscar escola pelo nome', placeholder='Digite parte do nome da escola')
    escolas = filtrado.copy()
    if busca.strip(): escolas = escolas[escolas['NO_ENTIDADE'].astype(str).str.contains(busca.strip(), case=False, regex=False, na=False)]
    escolas = escolas.sort_values(['NO_ENTIDADE', 'CO_ENTIDADE'])
    st.write(f'**{len(escolas):,} escolas encontradas**'.replace(',', '.'))
    tabela = pd.DataFrame({
        'Código INEP': escolas['CO_ENTIDADE'].astype('Int64').astype(str),
        'Escola': escolas['NO_ENTIDADE'],
        'Município': escolas['NO_MUNICIPIO'],
        'Rede': escolas['TP_DEPENDENCIA'].map(dependencias),
        'Localização': escolas['TP_LOCALIZACAO'].map(localizacao),
    })
    st.dataframe(tabela, hide_index=True, width="stretch")
    st.download_button('Baixar tabela filtrada (CSV)', tabela.to_csv(index=False, sep=';').encode('utf-8-sig'), 'escolas_rn_2024.csv', 'text/csv')
    st.divider()
    st.subheader('Ficha individual da escola')
    if escolas.empty:
        st.info('Nenhuma escola corresponde aos filtros. Ajuste a pesquisa para abrir uma ficha.')
    else:
        opcoes = escolas.drop_duplicates(subset=['CO_ENTIDADE'])
        codigos = opcoes['CO_ENTIDADE'].tolist()
        rotulos = {r['CO_ENTIDADE']:f"{r['NO_ENTIDADE']} — {r['NO_MUNICIPIO']} (INEP {int(r['CO_ENTIDADE'])})" for _,r in opcoes.iterrows()}
        codigo = st.selectbox('Selecione uma escola para abrir sua ficha', codigos, format_func=lambda x:rotulos[x])
        r = opcoes.loc[opcoes['CO_ENTIDADE'] == codigo].iloc[0]
        st.markdown(f"### {r['NO_ENTIDADE']}")
        st.caption(f"Código INEP: {numero(codigo)} · {r['NO_MUNICIPIO']} · {dependencias(r['TP_DEPENDENCIA'])} · {localizacao(r['TP_LOCALIZACAO'])} · 2024")
        with st.container(border=True):
            st.markdown('#### Identificação')
            st.write(f"**Endereço informado:** {valor(r,'DS_ENDERECO')}, {numero(valor(r,'NU_ENDERECO'))} — {valor(r,'NO_BAIRRO')}")
            st.write(f"**Município:** {valor(r,'NO_MUNICIPIO')} | **Rede:** {dependencias(r['TP_DEPENDENCIA'])} | **Localização:** {localizacao(r['TP_LOCALIZACAO'])}")
        st.markdown('#### Matrículas, docentes e turmas')
        c1,c2,c3 = st.columns(3)
        c1.metric('Matrículas na educação básica', numero(valor(r,'QT_MAT_BAS')))
        c2.metric('Docentes vinculados à escola', numero(valor(r,'QT_DOC_BAS')))
        c3.metric('Turmas na educação básica', numero(valor(r,'QT_TUR_BAS')))
        st.caption('Contagens referentes a esta escola no Censo Escolar 2024. Não confundir matrículas com estudantes distintos.')
        st.markdown('#### Matrículas por etapa e modalidade')
        grupos_matriculas = {
            'Educação infantil': 'QT_MAT_INF',
            'Creche': 'QT_MAT_INF_CRE',
            'Pré-escola': 'QT_MAT_INF_PRE',
            'Ensino fundamental': 'QT_MAT_FUND',
            'Fundamental — anos iniciais': 'QT_MAT_FUND_AI',
            'Fundamental — anos finais': 'QT_MAT_FUND_AF',
            'Ensino médio': 'QT_MAT_MED',
            'Educação de jovens e adultos': 'QT_MAT_EJA',
            'Educação profissional': 'QT_MAT_PROF',
            'Educação especial': 'QT_MAT_ESP',
        }
        linhas = [{'Indicador': nome, 'Matrículas': numero(r[col]), 'Variável INEP': col}
                  for nome, col in grupos_matriculas.items() if col in r.index]
        if linhas:
            st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        else:
            st.info('Não foram encontradas variáveis de matrícula detalhada neste arquivo.')
        st.caption('Algumas categorias são subconjuntos de outras ou podem se sobrepor. Não some as linhas para obter o total.')

        grupos_recursos = {
            'Ambientes e espaços pedagógicos': {
                'Biblioteca': 'IN_BIBLIOTECA',
                'Sala de leitura': 'IN_SALA_LEITURA',
                'Laboratório de informática': 'IN_LABORATORIO_INFORMATICA',
                'Laboratório de ciências': 'IN_LABORATORIO_CIENCIAS',
                'Quadra de esportes': 'IN_QUADRA_ESPORTES',
                'Parque infantil': 'IN_PARQUE_INFANTIL',
                'Pátio coberto': 'IN_PATIO_COBERTO',
                'Pátio descoberto': 'IN_PATIO_DESCOBERTO',
                'Auditório': 'IN_AUDITORIO',
                'Sala de atendimento educacional especializado': 'IN_SALA_ATENDIMENTO_ESPECIAL',
            },
            'Água, saneamento e alimentação': {
                'Água potável': 'IN_AGUA_POTAVEL',
                'Abastecimento pela rede pública': 'IN_AGUA_REDE_PUBLICA',
                'Abastecimento por poço artesiano': 'IN_AGUA_POCO_ARTESIANO',
                'Esgoto pela rede pública': 'IN_ESGOTO_REDE_PUBLICA',
                'Fossa séptica': 'IN_ESGOTO_FOSSA_SEPTICA',
                'Energia elétrica pela rede pública': 'IN_ENERGIA_REDE_PUBLICA',
                'Cozinha': 'IN_COZINHA',
                'Refeitório': 'IN_REFEITORIO',
            },
            'Tecnologia e equipamentos': {
                'Internet': 'IN_INTERNET',
                'Banda larga': 'IN_BANDA_LARGA',
                'Computador': 'IN_COMPUTADOR',
                'Computador de mesa para alunos': 'QT_DESKTOP_ALUNO',
                'Computador portátil para alunos': 'QT_COMP_PORTATIL_ALUNO',
                'Tablet para alunos': 'QT_TABLET_ALUNO',
                'Projetor multimídia': 'QT_EQUIP_MULTIMIDIA',
            },
            'Acessibilidade': {
                'Banheiro acessível': 'IN_BANHEIRO_PNE',
                'Rampas': 'IN_ACESSIBILIDADE_RAMPAS',
                'Pisos táteis': 'IN_ACESSIBILIDADE_PISOS_TATEIS',
                'Corrimão e guarda-corpos': 'IN_ACESSIBILIDADE_CORRIMAO',
                'Portas com vão livre adequado': 'IN_ACESSIBILIDADE_VAO_LIVRE',
                'Sinalização visual': 'IN_ACESSIBILIDADE_SINAL_VISUAL',
                'Sinalização sonora': 'IN_ACESSIBILIDADE_SINAL_SONORO',
                'Sinalização tátil': 'IN_ACESSIBILIDADE_SINAL_TATIL',
            },
        }

        st.markdown('#### Infraestrutura, equipamentos e acessibilidade')
        detalhes_exportacao = []
        for grupo, indicadores in grupos_recursos.items():
            with st.expander(grupo, expanded=(grupo == 'Ambientes e espaços pedagógicos')):
                registros = []
                for nome, col in indicadores.items():
                    if col not in r.index:
                        continue
                    situacao = sim_nao(r, col) if col.startswith('IN_') else numero(r[col])
                    registros.append({'Indicador': nome, 'Valor informado': situacao, 'Variável INEP': col})
                    detalhes_exportacao.append({'Grupo': grupo, 'Indicador': nome,
                                                'Valor informado': situacao, 'Variável INEP': col})
                if registros:
                    st.dataframe(pd.DataFrame(registros), hide_index=True, width="stretch")
                else:
                    st.info('Este arquivo não contém as variáveis selecionadas para esta seção.')

        st.caption('“Não informado” não significa “Não”. Variáveis ausentes do arquivo são omitidas. '
                   'As denominações e os códigos deverão ser confrontados com o dicionário oficial do INEP.')

        st.markdown('#### Exportação da ficha')
        ficha = pd.DataFrame([{
            'Ano': 2024, 'Código INEP': codigo, 'Escola': r['NO_ENTIDADE'],
            'Município': r['NO_MUNICIPIO'], 'Rede': dependencias(r['TP_DEPENDENCIA']),
            'Matrículas': valor(r, 'QT_MAT_BAS'),
            'Docentes por escola': valor(r, 'QT_DOC_BAS'),
            'Turmas': valor(r, 'QT_TUR_BAS')
        }])
        st.download_button('Baixar resumo da ficha (CSV)',
                           ficha.to_csv(index=False, sep=';').encode('utf-8-sig'),
                           f'ficha_escola_{int(codigo)}_2024.csv', 'text/csv')
        linhas_exportacao = [
            {'Grupo': 'Matrículas', 'Indicador': item['Indicador'],
             'Valor informado': item['Matrículas'], 'Variável INEP': item['Variável INEP']}
            for item in linhas
        ] + detalhes_exportacao
        if linhas_exportacao:
            st.download_button('Baixar indicadores detalhados (CSV)',
                               pd.DataFrame(linhas_exportacao).to_csv(index=False, sep=';').encode('utf-8-sig'),
                               f'indicadores_escola_{int(codigo)}_2024.csv', 'text/csv')


with aba_comparar:
    st.subheader('Comparação entre municípios — Censo Escolar 2024')
    st.caption('Esta comparação considera todos os estabelecimentos em atividade no município, independentemente dos filtros laterais, para evitar comparações acidentais entre recortes diferentes.')
    municipios = sorted(df['NO_MUNICIPIO'].dropna().astype(str).unique().tolist())
    padrao = [m for m in ['Natal', 'Mossoró'] if m in municipios]
    if len(padrao) < 2:
        padrao = municipios[:2]
    selecionados = st.multiselect('Selecione de dois a cinco municípios', municipios, default=padrao, max_selections=5)
    if len(selecionados) < 2:
        st.info('Selecione pelo menos dois municípios para comparar.')
    else:
        comparado = df[df['NO_MUNICIPIO'].isin(selecionados)].copy()
        resumo = []
        for nome in selecionados:
            parte = comparado[comparado['NO_MUNICIPIO'] == nome]
            resumo.append({
                'Município': nome,
                'Escolas em atividade': int(parte['CO_ENTIDADE'].nunique()),
                'Matrículas na educação básica': int(pd.to_numeric(parte['QT_MAT_BAS'], errors='coerce').sum()),
                'Soma de docentes por escola': int(pd.to_numeric(parte['QT_DOC_BAS'], errors='coerce').sum()),
            })
        st.markdown('#### Dimensão das redes escolares')
        resumo_df = pd.DataFrame(resumo)
        st.dataframe(resumo_df, hide_index=True, width='stretch')
        st.bar_chart(resumo_df.set_index('Município')[['Escolas em atividade']])
        st.markdown('#### Infraestrutura: proporção de escolas com recurso declarado')
        indicadores_comparacao = {
            'Biblioteca': 'IN_BIBLIOTECA',
            'Sala de leitura': 'IN_SALA_LEITURA',
            'Laboratório de informática': 'IN_LABORATORIO_INFORMATICA',
            'Laboratório de ciências': 'IN_LABORATORIO_CIENCIAS',
            'Quadra de esportes': 'IN_QUADRA_ESPORTES',
            'Água potável': 'IN_AGUA_POTAVEL',
            'Internet': 'IN_INTERNET',
            'Banda larga': 'IN_BANDA_LARGA',
            'Banheiro acessível': 'IN_BANHEIRO_PNE',
            'Rampas': 'IN_ACESSIBILIDADE_RAMPAS',
            'Pisos táteis': 'IN_ACESSIBILIDADE_PISOS_TATEIS',
        }
        disponiveis = {rotulo: coluna for rotulo, coluna in indicadores_comparacao.items() if coluna in df.columns}
        if not disponiveis:
            st.warning('Não há colunas de infraestrutura disponíveis neste arquivo.')
        else:
            indicador = st.selectbox('Indicador a comparar', list(disponiveis))
            coluna = disponiveis[indicador]
            linhas_comparacao = []
            for nome in selecionados:
                parte = comparado[comparado['NO_MUNICIPIO'] == nome]
                valores = pd.to_numeric(parte[coluna], errors='coerce')
                validos = valores.isin([0, 1])
                n_validos = int(validos.sum())
                n_sim = int((valores == 1).sum())
                n_sem = int(len(parte) - n_validos)
                pct = round(n_sim / n_validos * 100, 1) if n_validos else None
                linhas_comparacao.append({
                    'Município': nome,
                    'Escolas com recurso': n_sim,
                    'Escolas com resposta 0 ou 1': n_validos,
                    'Sem resposta interpretável': n_sem,
                    'Percentual (%)': pct,
                })
            tabela_comparacao = pd.DataFrame(linhas_comparacao)
            st.dataframe(tabela_comparacao, hide_index=True, width='stretch')
            if tabela_comparacao['Percentual (%)'].notna().any():
                st.bar_chart(tabela_comparacao.set_index('Município')[['Percentual (%)']])
            st.caption('Denominador: escolas em atividade com resposta 0 ou 1 no indicador selecionado. Escolas sem resposta interpretável não entram no percentual e são exibidas separadamente. Uma resposta “Sim” representa declaração censitária, não verificação presencial.')
            st.download_button('Baixar comparação de infraestrutura (CSV)',
                               tabela_comparacao.to_csv(index=False, sep=';').encode('utf-8-sig'),
                               'comparacao_municipios_infraestrutura_2024.csv', 'text/csv')
        st.download_button('Baixar comparação geral (CSV)',
                           resumo_df.to_csv(index=False, sep=';').encode('utf-8-sig'),
                           'comparacao_municipios_2024.csv', 'text/csv')
        st.info('Comparações descritivas, não avaliações de qualidade. Diferenças entre municípios podem refletir composição das redes, etapas ofertadas e características territoriais.')

with aba_panorama:
    st.subheader('Panorama dos municípios do Rio Grande do Norte — 2024')
    st.caption('Tabela ordenável de todos os municípios presentes nos microdados, sem limitar a consulta a cinco municípios.')
    rede_p = st.selectbox('Rede administrativa no panorama', ['Todas as redes', 'Federal', 'Estadual', 'Municipal', 'Privada'], key='rede_panorama')
    zona_p = st.selectbox('Localização no panorama', ['Todas as localizações', 'Urbana', 'Rural'], key='zona_panorama')
    base_p = df.copy()
    if rede_p != 'Todas as redes':
        base_p = base_p[base_p['TP_DEPENDENCIA'].map(dependencias) == rede_p]
    if zona_p != 'Todas as localizações':
        base_p = base_p[base_p['TP_LOCALIZACAO'].map(localizacao) == zona_p]

    indicadores_p = {
        'Biblioteca': 'IN_BIBLIOTECA',
        'Internet': 'IN_INTERNET',
        'Quadra de esportes': 'IN_QUADRA_ESPORTES',
        'Laboratório de ciências': 'IN_LABORATORIO_CIENCIAS',
        'Banheiro acessível': 'IN_BANHEIRO_PNE',
        'Rampas': 'IN_ACESSIBILIDADE_RAMPAS',
        'Pisos táteis': 'IN_ACESSIBILIDADE_PISOS_TATEIS',
        'Água potável': 'IN_AGUA_POTAVEL',
    }
    indicadores_p = {k: v for k, v in indicadores_p.items() if v in base_p.columns}
    indicador_p = st.selectbox('Indicador de infraestrutura', list(indicadores_p), key='indicador_panorama')
    col_p = indicadores_p[indicador_p]
    cod_mun = 'CO_MUNICIPIO' if 'CO_MUNICIPIO' in df.columns else None

    linhas_p = []
    for nome, parte in base_p.groupby('NO_MUNICIPIO', dropna=True):
        sim, validos, sem, pct = indicador_municipal(parte, col_p)
        linha = {
            'Município': nome,
            'Escolas': int(parte['CO_ENTIDADE'].nunique()),
            'Matrículas': int(pd.to_numeric(parte['QT_MAT_BAS'], errors='coerce').sum()),
            'Soma de docentes por escola': int(pd.to_numeric(parte['QT_DOC_BAS'], errors='coerce').sum()),
            'Escolas com recurso': sim,
            'Escolas com resposta 0 ou 1': validos,
            'Sem resposta interpretável': sem,
            'Percentual (%)': pct,
        }
        if cod_mun:
            codigo_m = pd.to_numeric(parte[cod_mun], errors='coerce').dropna()
            linha['codigo_ibge'] = str(int(codigo_m.iloc[0])) if not codigo_m.empty else ''
        linhas_p.append(linha)

    panorama_df = pd.DataFrame(linhas_p)
    if panorama_df.empty:
        st.info('Nenhum município corresponde aos filtros.')
    else:
        st.markdown('#### Filtro por população municipal')
        if ARQUIVO_POP.exists() and cod_mun:
            try:
                stat_pop = ARQUIVO_POP.stat()
                pop_df = carregar_populacao(str(ARQUIVO_POP), stat_pop.st_size, stat_pop.st_mtime)
                panorama_df = panorama_df.merge(pop_df, on='codigo_ibge', how='left', validate='many_to_one')
                st.caption(f'População IBGE identificada em {panorama_df["populacao_2022"].notna().sum()} dos {len(panorama_df)} municípios deste recorte.')
                panorama_df = panorama_df.rename(columns={'populacao_2022': 'População (IBGE, 2022)'})
                faixas = [
                    ('Até 5 mil', 0, 5000),
                    ('De 5 mil a 10 mil', 5000, 10000),
                    ('De 10 mil a 20 mil', 10000, 20000),
                    ('De 20 mil a 50 mil', 20000, 50000),
                    ('De 50 mil a 100 mil', 50000, 100000),
                    ('Mais de 100 mil', 100000, float('inf')),
                ]
                escolhas = st.multiselect('Faixas de população — Censo IBGE 2022',
                                         [f[0] for f in faixas])
                if escolhas:
                    condicao = pd.Series(False, index=panorama_df.index)
                    for rotulo, minimo, maximo in faixas:
                        if rotulo in escolhas:
                            condicao |= ((panorama_df['População (IBGE, 2022)'] > minimo) &
                                         (panorama_df['População (IBGE, 2022)'] <= maximo))
                    panorama_df = panorama_df[condicao].copy()
                st.caption('População do Censo 2022, não de 2024. Municípios sem correspondência ficam sem população; faixas selecionadas os excluem.')
            except Exception as e:
                st.warning(f'Não foi possível utilizar o CSV de população: {e}')
        else:
            st.info('O filtro populacional estará disponível após acrescentarmos uma tabela oficial do IBGE 2022. '
                    'O panorama educacional já funciona sem ela; nenhum valor de população foi estimado.')
        if 'codigo_ibge' in panorama_df.columns:
            panorama_df = panorama_df.drop(columns=['codigo_ibge'])
        if 'População (IBGE, 2022)' in panorama_df.columns:
            ordem = list(panorama_df.columns)
            ordem.remove('População (IBGE, 2022)')
            ordem.insert(1, 'População (IBGE, 2022)')
            panorama_df = panorama_df[ordem]
        st.metric('Municípios exibidos', len(panorama_df))
        st.dataframe(panorama_df, hide_index=True, width='stretch',
                     column_config={'População (IBGE, 2022)': st.column_config.NumberColumn(
                         'População (IBGE, 2022)', format='%d')} if 'População (IBGE, 2022)' in panorama_df.columns else None)
        st.download_button('Baixar panorama municipal (CSV)',
                           panorama_df.to_csv(index=False, sep=';').encode('utf-8-sig'),
                           'panorama_municipios_rn_2024.csv', 'text/csv')
        st.caption('Percentual calculado somente entre escolas com resposta 0 ou 1. '
                   'Uma declaração censitária não equivale a verificação presencial. '
                   'O filtro por rede e localização altera o conjunto de escolas; municípios sem escolas nesse recorte não aparecem.')
        st.caption('Os dados escolares são de 2024; os dados populacionais, quando incluídos, são de 2022.')

with aba_fontes:
    st.subheader('Fontes e metodologia')
    st.warning('VERSÃO BETA: os resultados são preliminares. A validação externa dos indicadores e a investigação de 48 valores ausentes ainda estão pendentes.')
    st.download_button('Baixar ficha metodológica completa (Markdown)',
                       (BASE / 'FICHA_METODOLOGICA.md').read_bytes(),
                       'ficha_metodologica_observatorio_rn_v9.md', 'text/markdown')
    st.write('**População:** IBGE, Censo Demográfico 2022, tabela 4714, variável 93, municípios do RN. O número de habitantes não é referente a 2024; sua associação é feita pelo código IBGE de sete dígitos.')
    st.write('**Fonte:** Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira (INEP), microdados do Censo Escolar da Educação Básica 2024, arquivo microdados_ed_basica_2024.csv.')
    st.write('**Recorte:** SG_UF = RN e TP_SITUACAO_FUNCIONAMENTO = 1 (escolas em atividade).')
    st.write('**Unidade da ficha:** registro da escola identificado pelo código CO_ENTIDADE.')
    st.write('**Contagens:** somas das variáveis QT_MAT_BAS, QT_DOC_BAS e QT_TUR_BAS, conforme o caso. Docentes podem ser contabilizados em mais de uma escola.')
    st.write('**Limitações:** dados de 2024; não são exibidos IDEB, evasão, direção escolar nem série histórica nesta versão. As categorias e codificações devem ser conferidas no dicionário oficial antes da divulgação científica definitiva.')
    st.write('**Interpretação:** indicadores com prefixo IN_ são tratados como presença (1), ausência (0) ou não informado; indicadores QT_ são quantidades. Campos não presentes no CSV não aparecem nas fichas.')
    st.write('**Validação pendente:** a nomenclatura de cada variável e suas regras de aplicabilidade precisam ser verificadas no dicionário oficial de 2024 antes da publicação pública definitiva.')
    st.write('**Comparações municipais:** percentuais de infraestrutura usam somente escolas com valor 0 ou 1 na variável consultada; respostas ausentes são informadas separadamente. Comparações não implicam causalidade.')
    st.write('**População:** Censo Demográfico IBGE 2022, tabela SIDRA 4714, variável 93, municípios do RN. A importação requer conferir 167 municípios e integridade dos códigos IBGE.')
    st.write('**Panorama municipal:** agrega os registros escolares por município e apresenta denominadores e ausências para cada indicador. O filtro populacional é opcional e requer CSV oficial do IBGE 2022, identificado por código municipal de sete dígitos.')
    st.write('**Privacidade:** a ficha exibe dados institucionais, não dados pessoais de estudantes.')


with aba_auditoria:
    st.subheader('Auditoria preliminar das bases — versão 9')
    st.caption('Verificações automáticas de consistência interna. Não substituem a conferência com as publicações e os dicionários oficiais do INEP e IBGE.')
    st.markdown('#### Arquivo educacional e recorte')
    st.write(f'**Base pública derivada:** `{ARQUIVO.name}` · **Tamanho:** {ARQUIVO.stat().st_size / 1024**2:,.1f} MiB')
    st.write('**Filtro:** escolas no RN e situação de funcionamento igual a 1 (atividade).')
    st.metric('Registros escolares no recorte', numero(len(df)))
    st.metric('Escolas distintas (código INEP)', numero(df['CO_ENTIDADE'].nunique()))
    st.metric('Municípios distintos (nome)', numero(df['NO_MUNICIPIO'].nunique()))

    verificacoes = []
    def registrar(teste, quantidade, criterio):
        verificacoes.append({'Verificação':teste, 'Ocorrências':int(quantidade), 'Critério':criterio,
                             'Situação':'Verificar' if quantidade else 'Sem ocorrência'})
    registrar('Códigos INEP duplicados', df['CO_ENTIDADE'].duplicated().sum(),
              'Um registro por código escolar no recorte selecionado')
    registrar('Código INEP ausente', df['CO_ENTIDADE'].isna().sum(), 'Identificador escolar obrigatório')
    registrar('Nome de município ausente', df['NO_MUNICIPIO'].isna().sum(), 'Identificação municipal esperada')
    if 'CO_MUNICIPIO' in df.columns:
        codigos = pd.to_numeric(df['CO_MUNICIPIO'], errors='coerce')
        registrar('Código municipal inválido ou ausente',
                  (codigos.isna() | ~codigos.astype('Int64').astype(str).str.fullmatch(r'\d{7}', na=False)).sum(),
                  'Código IBGE com sete algarismos')
        cod_por_nome = df[['NO_MUNICIPIO','CO_MUNICIPIO']].dropna().drop_duplicates().groupby('NO_MUNICIPIO')['CO_MUNICIPIO'].nunique()
        registrar('Nomes de município associados a mais de um código', (cod_por_nome > 1).sum(),
                  'Um código municipal por nome no recorte do RN')
    for coluna in ['QT_MAT_BAS', 'QT_DOC_BAS']:
        if coluna in df.columns:
            numeros = pd.to_numeric(df[coluna], errors='coerce')
            registrar(f'{coluna}: valores negativos', (numeros < 0).sum(), 'Quantidades não negativas')
            registrar(f'{coluna}: valores ausentes ou não numéricos', numeros.isna().sum(),
                      'Avaliar preenchimento e regras de aplicabilidade no dicionário')
    st.markdown('#### Verificações automáticas')
    verificacoes_df = pd.DataFrame(verificacoes)
    st.dataframe(verificacoes_df, hide_index=True, width='stretch')
    st.download_button('Baixar verificações (CSV)',
                       verificacoes_df.to_csv(index=False, sep=';').encode('utf-8-sig'),
                       'auditoria_preliminar_rn_v9.csv', 'text/csv')

    st.markdown('#### Conferência da população IBGE 2022')
    if ARQUIVO_POP.exists() and 'CO_MUNICIPIO' in df.columns:
        try:
            pop_stat = ARQUIVO_POP.stat()
            p_aud = carregar_populacao(str(ARQUIVO_POP), pop_stat.st_size, pop_stat.st_mtime)
            cod_rn = set(pd.to_numeric(df['CO_MUNICIPIO'], errors='coerce').dropna().astype('int64').astype(str))
            cod_pop = set(p_aud['codigo_ibge'])
            a,b,c = st.columns(3)
            a.metric('Municípios no CSV IBGE', numero(len(p_aud)))
            b.metric('Códigos INEP sem população', numero(len(cod_rn - cod_pop)))
            c.metric('População total do CSV (2022)', numero(p_aud['populacao_2022'].sum()))
            if len(cod_rn - cod_pop):
                st.warning('Existem códigos municipais sem correspondência. Confira os arquivos antes de divulgar resultados.')
                st.dataframe(pd.DataFrame({'Código IBGE sem correspondência': sorted(cod_rn - cod_pop)}),hide_index=True)
            else:
                st.success('Todos os códigos municipais presentes no recorte educacional foram encontrados no CSV populacional.')
            if len(p_aud) != 167:
                st.warning('O arquivo populacional não contém exatamente 167 municípios. Verifique a consulta oficial.')
            if (p_aud['populacao_2022'] <= 0).any():
                st.warning('Há valores populacionais nulos ou negativos; confira a fonte.')
        except Exception as e:
            st.error(f'Não foi possível auditar o CSV populacional: {e}')
    else:
        st.info('Arquivo populacional ou código municipal não disponível para esta auditoria.')
    st.info('Estes testes verificam consistência técnica; não demonstram, por si só, que todos os totais e conceitos estão corretos. A comparação com as tabelas oficiais permanece pendente.')
