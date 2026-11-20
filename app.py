from pathlib import Path
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title='ObsEd RN — Observatório da Educação', page_icon='🐘', layout='wide')
BASE = Path(__file__).resolve().parent
ARQUIVOS_CENSO = {2024: BASE / 'dados' / 'brutos' / 'microdados_ed_basica_2024.csv', 2025: BASE / 'dados' / 'consolidados' / 'censo_escolar_rn_2025_integrado.csv'}
ARQUIVO_POP = BASE / 'dados' / 'ibge_populacao_municipios_rn_2022.csv'
ARQUIVO_IDEB = BASE / 'dados' / 'ideb' / 'ideb_rn_municipios_2005_2025.csv'
ARQUIVO_IDEB_ESTADO = BASE / 'dados' / 'ideb' / 'ideb_rn_estadual_2005_2025.csv'

@st.cache_data(show_spinner='Lendo os dados do Censo Escolar…')
def carregar(caminho, tamanho, modificacao, ano):
    df = pd.read_csv(caminho, sep=';', encoding='utf-8-sig' if ano == 2025 else 'latin1', low_memory=False)
    if not pd.to_numeric(df['NU_ANO_CENSO'], errors='coerce').eq(ano).all():
        raise ValueError('Ano divergente na base censitária.')
    if ano == 2025 and (df['CO_ENTIDADE'].isna().any() or df['CO_ENTIDADE'].duplicated().any()):
        raise ValueError('Códigos escolares ausentes ou duplicados na base integrada.')
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

st.title('ObsEd RN')
st.markdown('🎲🐘🎲')
st.markdown('### Observatório da Educação no Rio Grande do Norte')
st.markdown("""
<div style="font-size:clamp(0.9rem, 1.3vw, 1.1rem); font-weight:500;
            line-height:1.5; margin-top:-0.5rem; margin-bottom:0.5rem; color:inherit;">
Dados para entender. Conhecimento para debater. Educação para transformar.
</div>
""", unsafe_allow_html=True)
st.caption('Versão 10.14 em teste • Censo Escolar 2024 e 2025 (INEP) • IDEB 2005–2025 (INEP) • Censo Demográfico 2022 (IBGE)')
with st.sidebar:
    ano_censo = st.selectbox('Ano do Censo Escolar', [2025, 2024], key='ano_censo')
    st.caption('O ano selecionado não altera as séries históricas, o IDEB ou os anos financeiros do PNAE.')
ARQUIVO = ARQUIVOS_CENSO[ano_censo]
if not ARQUIVO.exists():
    st.error(f'Não encontrei a base do Censo {ano_censo}: {ARQUIVO.relative_to(BASE)}. Selecione outro ano ou confira o arquivo.')
    st.stop()
try:
    info = ARQUIVO.stat()
    df = carregar(str(ARQUIVO), info.st_size, info.st_mtime, ano_censo)
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

@st.cache_data(show_spinner=False)
def carregar_ideb_painel(caminho, tamanho, modificacao, estadual=False):
    base = pd.read_csv(caminho, sep=';' if estadual else ',', encoding='utf-8-sig')
    obrigatorias = {'etapa', 'rede', 'ano', 'ideb_observado'}
    if not obrigatorias.issubset(base.columns):
        raise ValueError('Faltam colunas no arquivo de IDEB.')
    base['ano'] = pd.to_numeric(base['ano'], errors='raise').astype(int)
    base['ideb_observado'] = pd.to_numeric(base['ideb_observado'], errors='coerce')
    if not base['ideb_observado'].dropna().between(0, 10).all():
        raise ValueError('O arquivo contém IDEB fora da escala 0–10.')
    chaves = ['etapa', 'rede', 'ano'] if estadual else ['etapa', 'rede', 'ano', 'codigo_municipio']
    if base.duplicated(chaves).any():
        raise ValueError('Há registros duplicados na série do IDEB.')
    if estadual and (len(base) != 121 or set(base['etapa']) != {'Anos iniciais', 'Anos finais', 'Ensino médio'}):
        raise ValueError('A série estadual não corresponde à extração oficial esperada.')
    if not estadual and base['codigo_municipio'].astype(str).nunique() != 167:
        raise ValueError('A base municipal não contempla os 167 municípios.')
    return base


# Menu principal em grade, sem rolagem horizontal das antigas guias.
MENU = [('geral', '📊 Visão geral'), ('escolas', '🏫 Escolas e fichas'), ('comparar', '⚖️ Comparar municípios'), ('panorama', '🗺️ Panorama municipal'), ('eja', '📚 EJA'), ('alimentacao', '🍽️ Alimentação escolar'), ('historica', '📈 Série histórica'), ('ideb', '📉 IDEB e aprendizagem'), ('superior', '🎓 Ensino superior'), ('fontes', '📖 Fontes e metodologia'), ('auditoria', '🔎 Auditoria dos dados'), ('questao', '💡 Educação em questão'), ('transparencia', '🏛️ Transparência Pública')]
if 'obsed_secao' not in st.session_state:
    st.session_state.obsed_secao = 'geral'

def selecionar_secao(secao):
    st.session_state.obsed_secao = secao

for inicio in range(0, len(MENU), 3):
    for coluna, (secao, rotulo) in zip(st.columns(3), MENU[inicio:inicio+3]):
        coluna.button(rotulo, key='nav_obsed_'+secao,
                      type='primary' if st.session_state.obsed_secao == secao else 'secondary',
                      use_container_width=True, on_click=selecionar_secao, args=(secao,))
st.divider()
if st.session_state.obsed_secao == 'geral':
    st.markdown("""
    <style>
    .st-key-obsed_ideb_destaque {
        outline: 2px solid #607986;
        outline-offset: -2px;
        border-radius: 0.6rem;
    }
    </style>
    """, unsafe_allow_html=True)
    with st.container(border=True, key='obsed_ideb_destaque'):
        st.subheader('📈 IDEB em destaque')
        st.caption('Últimos resultados oficiais disponíveis para a mesma etapa e rede. Fonte: INEP. Os anos podem diferir quando não há resultado publicado.')
        if ARQUIVO_IDEB_ESTADO.exists() and ARQUIVO_IDEB.exists():
            try:
                ei = ARQUIVO_IDEB_ESTADO.stat()
                mi = ARQUIVO_IDEB.stat()
                estado_ideb = carregar_ideb_painel(str(ARQUIVO_IDEB_ESTADO), ei.st_size, ei.st_mtime, True)
                mun_ideb = carregar_ideb_painel(str(ARQUIVO_IDEB), mi.st_size, mi.st_mtime, False)
                e_col, r_col = st.columns(2)
                etapa_painel = e_col.selectbox('Etapa — painel IDEB', ['Anos iniciais', 'Anos finais', 'Ensino médio'], key='etapa_painel_ideb')
                redes_estaduais = set(estado_ideb.loc[estado_ideb['etapa'].eq(etapa_painel), 'rede'].unique())
                redes_municipais = set(mun_ideb.loc[mun_ideb['etapa'].eq(etapa_painel), 'rede'].unique())
                redes_comparaveis = sorted(redes_estaduais & redes_municipais)
                if not redes_comparaveis:
                    raise ValueError('Não há redes equivalentes para esta etapa.')
                rede_padrao = 'Pública' if 'Pública' in redes_comparaveis else 'Estadual' if 'Estadual' in redes_comparaveis else redes_comparaveis[0]
                rede_painel = r_col.selectbox('Rede — painel IDEB', redes_comparaveis, index=redes_comparaveis.index(rede_padrao), key='rede_painel_ideb')
                if etapa_painel == 'Ensino médio':
                    st.caption('No ensino médio, a comparação utiliza a rede estadual: a série estadual não oferece a categoria Pública presente na base municipal.')
                serie_estado = estado_ideb.loc[estado_ideb['etapa'].eq(etapa_painel) & estado_ideb['rede'].eq(rede_painel)].dropna(subset=['ideb_observado']).sort_values('ano')
                municipio_painel = municipio if municipio != 'Todos os municípios' else st.selectbox('Escolha um município para comparar', sorted(mun_ideb['municipio'].dropna().unique()), index=sorted(mun_ideb['municipio'].dropna().unique()).index('Natal') if 'Natal' in set(mun_ideb['municipio']) else 0, key='mun_painel_ideb')
                st.caption(f'Município em análise: {municipio_painel}. O filtro lateral de município tem prioridade; sem filtro, você pode escolher aqui.')
                serie_mun = mun_ideb.loc[mun_ideb['municipio'].eq(municipio_painel) & mun_ideb['etapa'].eq(etapa_painel) & mun_ideb['rede'].eq(rede_painel)].dropna(subset=['ideb_observado']).sort_values('ano')
                def mostrar_nota(coluna, nome, serie):
                    if serie.empty:
                        coluna.metric(nome, 'Sem divulgação')
                    else:
                        ultimo = serie.iloc[-1]
                        coluna.metric(nome + ' (' + str(int(ultimo['ano'])) + ')', f"{ultimo['ideb_observado']:.1f}".replace('.', ','))
                card_rn, card_mun = st.columns(2)
                mostrar_nota(card_rn, 'Rio Grande do Norte', serie_estado)
                mostrar_nota(card_mun, municipio_painel, serie_mun)
                st.caption('Recorte: ' + etapa_painel + ' · Rede ' + rede_painel + '. Os filtros laterais de rede e localização não se aplicam a este quadro.')
                with st.expander('Ver gráficos históricos e comparação', expanded=False):
                    st.markdown('#### Rio Grande do Norte — série estadual oficial')
                    if serie_estado.empty:
                        st.info('Não há resultados estaduais publicados neste recorte.')
                    else:
                        st.altair_chart(alt.Chart(serie_estado).mark_line(point=True, strokeWidth=2.5).encode(
                            x=alt.X('ano:O', title='Ano'),
                            y=alt.Y('ideb_observado:Q', title='IDEB observado', scale=alt.Scale(domain=[0,10])),
                            tooltip=[alt.Tooltip('ano:O',title='Ano'),alt.Tooltip('ideb_observado:Q',title='IDEB',format='.1f')]
                        ).properties(height=250), use_container_width=True)
                        u=serie_estado.iloc[-1]
                        st.caption(f'Último resultado estadual publicado neste recorte: {u["ideb_observado"]:.1f} ({int(u["ano"])}).'.replace(f'{u["ideb_observado"]:.1f}',f'{u["ideb_observado"]:.1f}'.replace('.',',')))
                    st.markdown('#### Município — série oficial')
                    if serie_mun.empty:
                        st.info('Sem resultado municipal publicado para esta combinação de município, etapa e rede.')
                    else:
                        st.altair_chart(alt.Chart(serie_mun).mark_line(point=True, strokeWidth=2.5).encode(
                            x=alt.X('ano:O', title='Ano'),
                            y=alt.Y('ideb_observado:Q', title='IDEB observado', scale=alt.Scale(domain=[0,10])),
                            tooltip=[alt.Tooltip('ano:O',title='Ano'),alt.Tooltip('ideb_observado:Q',title='IDEB',format='.1f')]
                        ).properties(height=250), use_container_width=True)
                    if not serie_estado.empty and not serie_mun.empty:
                        comum = serie_estado[['ano','ideb_observado']].merge(serie_mun[['ano','ideb_observado']],on='ano',suffixes=('_estado','_municipio'))
                        if not comum.empty:
                            st.markdown('#### Comparação direta — mesmos anos, etapa e rede')
                            comp = comum.melt(id_vars='ano',value_vars=['ideb_observado_estado','ideb_observado_municipio'],var_name='Território',value_name='IDEB')
                            comp['Território'] = comp['Território'].map({'ideb_observado_estado':'Rio Grande do Norte','ideb_observado_municipio':municipio_painel})
                            st.altair_chart(alt.Chart(comp).mark_line(point=True).encode(x=alt.X('ano:O',title='Ano'),y=alt.Y('IDEB:Q',scale=alt.Scale(domain=[0,10])),color='Território:N',tooltip=['ano:O','Território:N',alt.Tooltip('IDEB:Q',format='.1f')]).properties(height=260),use_container_width=True)
                    st.caption('A comparação só reúne resultados com mesma etapa, rede e ano. Não se calculam médias de IDEB. O filtro lateral de localização não se aplica ao IDEB.')
            except (OSError, ValueError, KeyError, pd.errors.ParserError) as erro_painel:
                st.error(f'Não foi possível carregar o painel IDEB: {erro_painel}')
        else:
            st.info('Para ativar os gráficos estaduais e municipais, coloque os dois arquivos de IDEB na pasta dados/ideb/.')

        st.button('Abrir painel completo do IDEB', key='atalho_ideb_inicio', on_click=selecionar_secao, args=('ideb',))

    st.subheader(f'Indicadores de {ano_censo}')
    a,b,c = st.columns(3)
    a.metric('Escolas em atividade', numero(filtrado['CO_ENTIDADE'].nunique()))
    b.metric('Matrículas na educação básica', numero(pd.to_numeric(filtrado['QT_MAT_BAS'], errors='coerce').sum(min_count=1)))
    c.metric('Soma de docentes por escola', numero(pd.to_numeric(filtrado['QT_DOC_BAS'], errors='coerce').sum(min_count=1)))
    st.caption('Matrículas não são necessariamente estudantes distintos; a soma de docentes por escola não corresponde necessariamente a pessoas distintas.')

    if ano_censo == 2025:
        d,e = st.columns(2)
        d.metric('Turmas', numero(pd.to_numeric(filtrado['QT_TUR_BAS'], errors='coerce').sum(min_count=1)))
        e.metric('Soma de gestores por escola', numero(pd.to_numeric(filtrado['QT_GEST_BAS'], errors='coerce').sum(min_count=1)))
        st.caption('Escolas ativas sem valor informado no recorte: ' + ' · '.join(f'{rotulo}: {filtrado[col].isna().sum()}' for rotulo,col in [('Matrículas','QT_MAT_BAS'),('Docentes','QT_DOC_BAS'),('Turmas','QT_TUR_BAS'),('Gestores','QT_GEST_BAS')]) + '. Totais somam somente valores existentes; ausência não significa zero.')
    st.subheader('Matrículas por etapa de ensino')
    etapas = {'Educação infantil':'QT_MAT_INF', 'Ensino fundamental':'QT_MAT_FUND', 'Ensino médio':'QT_MAT_MED'}
    dados = {nome:pd.to_numeric(filtrado[col], errors='coerce').sum(min_count=1) for nome,col in etapas.items() if col in filtrado.columns}
    st.bar_chart(pd.DataFrame({'Matrículas':dados}))
    st.caption('As categorias exibidas não representam necessariamente uma decomposição exaustiva do total da educação básica.')
    st.subheader('Escolas por dependência administrativa')
    st.bar_chart(filtrado['TP_DEPENDENCIA'].map(dependencias).value_counts())

if st.session_state.obsed_secao == 'escolas':
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
    st.download_button('Baixar tabela filtrada (CSV)', tabela.to_csv(index=False, sep=';').encode('utf-8-sig'), f'escolas_rn_{ano_censo}.csv', 'text/csv')
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
        st.caption(f"Código INEP: {numero(codigo)} · {r['NO_MUNICIPIO']} · {dependencias(r['TP_DEPENDENCIA'])} · {localizacao(r['TP_LOCALIZACAO'])} · {ano_censo}")
        with st.container(border=True):
            st.markdown('#### Identificação')
            st.write(f"**Endereço informado:** {valor(r,'DS_ENDERECO')}, {numero(valor(r,'NU_ENDERECO'))} — {valor(r,'NO_BAIRRO')}")
            st.write(f"**Município:** {valor(r,'NO_MUNICIPIO')} | **Rede:** {dependencias(r['TP_DEPENDENCIA'])} | **Localização:** {localizacao(r['TP_LOCALIZACAO'])}")
        st.markdown('#### Matrículas, docentes e turmas')
        c1,c2,c3 = st.columns(3)
        c1.metric('Matrículas na educação básica', numero(valor(r,'QT_MAT_BAS')))
        c2.metric('Docentes vinculados à escola', numero(valor(r,'QT_DOC_BAS')))
        c3.metric('Turmas na educação básica', numero(valor(r,'QT_TUR_BAS')))
        st.caption(f'Contagens referentes a esta escola no Censo Escolar {ano_censo}. Não confundir matrículas com estudantes distintos.')
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
            'Ano': ano_censo, 'Código INEP': codigo, 'Escola': r['NO_ENTIDADE'],
            'Município': r['NO_MUNICIPIO'], 'Rede': dependencias(r['TP_DEPENDENCIA']),
            'Matrículas': valor(r, 'QT_MAT_BAS'),
            'Docentes por escola': valor(r, 'QT_DOC_BAS'),
            'Turmas': valor(r, 'QT_TUR_BAS')
        }])
        st.download_button('Baixar resumo da ficha (CSV)',
                           ficha.to_csv(index=False, sep=';').encode('utf-8-sig'),
                           f'ficha_escola_{int(codigo)}_{ano_censo}.csv', 'text/csv')
        linhas_exportacao = [
            {'Grupo': 'Matrículas', 'Indicador': item['Indicador'],
             'Valor informado': item['Matrículas'], 'Variável INEP': item['Variável INEP']}
            for item in linhas
        ] + detalhes_exportacao
        if linhas_exportacao:
            st.download_button('Baixar indicadores detalhados (CSV)',
                               pd.DataFrame(linhas_exportacao).to_csv(index=False, sep=';').encode('utf-8-sig'),
                               f'indicadores_escola_{int(codigo)}_{ano_censo}.csv', 'text/csv')


if st.session_state.obsed_secao == 'comparar':
    st.subheader(f'Comparação entre municípios — Censo Escolar {ano_censo}')
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
                'Matrículas na educação básica': pd.to_numeric(parte['QT_MAT_BAS'], errors='coerce').sum(min_count=1),
                'Soma de docentes por escola': pd.to_numeric(parte['QT_DOC_BAS'], errors='coerce').sum(min_count=1),
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
                               f'comparacao_municipios_infraestrutura_{ano_censo}.csv', 'text/csv')
        st.download_button('Baixar comparação geral (CSV)',
                           resumo_df.to_csv(index=False, sep=';').encode('utf-8-sig'),
                           f'comparacao_municipios_{ano_censo}.csv', 'text/csv')
        st.info('Comparações descritivas, não avaliações de qualidade. Diferenças entre municípios podem refletir composição das redes, etapas ofertadas e características territoriais.')

if st.session_state.obsed_secao == 'panorama':
    st.subheader(f'Panorama dos municípios do Rio Grande do Norte — {ano_censo}')
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
            'Matrículas': pd.to_numeric(parte['QT_MAT_BAS'], errors='coerce').sum(min_count=1),
            'Soma de docentes por escola': pd.to_numeric(parte['QT_DOC_BAS'], errors='coerce').sum(min_count=1),
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
                st.caption(f'População do Censo 2022, não de {ano_censo}. Municípios sem correspondência ficam sem população; faixas selecionadas os excluem.')
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
                           f'panorama_municipios_rn_{ano_censo}.csv', 'text/csv')
        st.caption('Percentual calculado somente entre escolas com resposta 0 ou 1. '
                   'Uma declaração censitária não equivale a verificação presencial. '
                   'O filtro por rede e localização altera o conjunto de escolas; municípios sem escolas nesse recorte não aparecem.')
        st.caption(f'Os dados escolares são de {ano_censo}; os dados populacionais, quando incluídos, são de 2022.')


# Painéis novos da versão 10: somente dados efetivamente presentes nos arquivos.
if st.session_state.obsed_secao == 'eja':
    st.subheader(f'Educação de Jovens e Adultos — Censo Escolar {ano_censo}')
    st.caption('Matrículas em EJA não medem diretamente alfabetização de adultos. Não representam pessoas distintas.')
    if 'QT_MAT_EJA' not in filtrado.columns:
        st.warning('A variável QT_MAT_EJA não está presente no arquivo importado.')
    else:
        eja = filtrado.copy()
        eja['matriculas_eja'] = pd.to_numeric(eja['QT_MAT_EJA'], errors='coerce')
        st.metric('Matrículas em EJA no recorte', numero(eja['matriculas_eja'].sum(min_count=1)))
        resumo_eja = eja.groupby('NO_MUNICIPIO', as_index=False)['matriculas_eja'].sum(min_count=1)
        resumo_eja = resumo_eja.rename(columns={'NO_MUNICIPIO':'Município','matriculas_eja':'Matrículas EJA'})
        st.dataframe(resumo_eja.sort_values('Matrículas EJA', ascending=False), hide_index=True, width='stretch')
        st.download_button('Baixar EJA por município (CSV)', resumo_eja.to_csv(index=False,sep=';').encode('utf-8-sig'), f'eja_municipios_{ano_censo}.csv', 'text/csv')
    st.info('Série histórica e indicadores de alfabetização do IBGE: aguardando importação e harmonização.')

if st.session_state.obsed_secao == 'alimentacao':
    st.subheader('Alimentação escolar — infraestrutura e financiamento')
    st.caption(f'Infraestrutura: Censo Escolar {ano_censo}. Dados financeiros abaixo permanecem nos anos identificados em cada painel.')
    st.caption('Cozinha e refeitório não comprovam oferta, regularidade ou qualidade das refeições.')
    indicadores = {'Cozinha':'IN_COZINHA', 'Refeitório':'IN_REFEITORIO', 'Alimentação escolar':'IN_ALIMENTACAO'}
    for rotulo, coluna in indicadores.items():
        if coluna in filtrado.columns:
            sim, validos, ausentes, percentual = indicador_municipal(filtrado, coluna)
            st.metric(f'Escolas com {rotulo.lower()} declarado', numero(sim))
            st.caption(f'{validos} respostas 0/1; {ausentes} sem resposta interpretável; {percentual}% entre respostas válidas.' if validos else 'Sem respostas interpretáveis.')
        else:
            st.info(f'Variável {coluna} não encontrada.')
    st.markdown('#### Previsão de repasses federais do PNAE — 2024')
    st.caption('Atenção: valores PREVISTOS pelo FNDE, não pagamentos confirmados, despesas executadas ou recursos próprios das administrações.')
    arquivo_prev = BASE / 'dados' / 'pnae' / 'pnae_rn_2024_previsao_detalhada.csv'
    if arquivo_prev.exists():
        try:
            prev = pd.read_csv(arquivo_prev, sep=';', encoding='utf-8-sig', dtype={'entidade_executora':str,'modalidade_pnae':str})
            necessarias = {'ano','uf','entidade_executora','modalidade_pnae','alunos_informados','valor_previsto_brl','natureza'}
            if not necessarias.issubset(prev.columns):
                raise ValueError('O arquivo não contém todas as colunas esperadas da base detalhada.')
            prev['valor_previsto_brl'] = pd.to_numeric(prev['valor_previsto_brl'], errors='coerce')
            prev['alunos_informados'] = pd.to_numeric(prev['alunos_informados'], errors='coerce')
            if prev['valor_previsto_brl'].isna().any() or (prev['valor_previsto_brl'] < 0).any():
                raise ValueError('Há valores previstos ausentes, inválidos ou negativos.')
            if not ((prev['uf'] == 'RN') & (pd.to_numeric(prev['ano'], errors='coerce') == 2024)).all():
                raise ValueError('Há registros fora do RN ou de 2024.')
            entidades = sorted(prev['entidade_executora'].dropna().unique().tolist())
            entidade = st.selectbox('Entidade executora — previsão FNDE', ['Todas as entidades'] + entidades, key='entidade_prev')
            modalidades = sorted(prev['modalidade_pnae'].dropna().unique().tolist())
            modalidade = st.selectbox('Modalidade de ensino — previsão FNDE', ['Todas as modalidades'] + modalidades, key='modalidade_prev')
            recorte = prev.copy()
            if entidade != 'Todas as entidades':
                recorte = recorte[recorte['entidade_executora'] == entidade]
            if modalidade != 'Todas as modalidades':
                recorte = recorte[recorte['modalidade_pnae'] == modalidade]
            st.metric('Valor federal previsto no recorte', f"R$ {recorte['valor_previsto_brl'].sum():,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
            st.caption('Os filtros acima são próprios da planilha do FNDE. O filtro municipal da barra lateral ainda não se aplica aos valores financeiros: a correspondência oficial das entidades com os municípios está pendente.')
            resumo = recorte.groupby('entidade_executora', as_index=False).agg(valor_previsto_brl=('valor_previsto_brl','sum'), modalidades=('modalidade_pnae','nunique'))
            st.dataframe(resumo.sort_values('valor_previsto_brl', ascending=False), hide_index=True, width='stretch')
            with st.expander('Ver registros detalhados por modalidade'):
                st.dataframe(recorte, hide_index=True, width='stretch')
            st.download_button('Baixar recorte da previsão (CSV)', recorte.to_csv(index=False, sep=';').encode('utf-8-sig'), 'pnae_rn_2024_previsao_recorte.csv', 'text/csv')
        except Exception as e:
            st.error(f'Não foi possível validar a base de previsão do PNAE: {e}')
    else:
        st.info('Coloque o arquivo pnae_rn_2024_previsao_detalhada.csv em dados/pnae para visualizar os valores previstos.')
    st.caption('Identificação histórica de governantes, transferências efetivamente pagas e despesas realizadas: ainda não integradas.')
    st.divider()
    st.markdown('#### Série histórica do financiamento federal do PNAE — 2010 a 2024')
    st.caption('2010–2023: valores identificados como pagos nos arquivos fornecidos. 2024: valores previstos, apresentados separadamente. Valores nominais, sem correção pela inflação. Não representam despesas municipais ou qualidade das refeições.')

    arquivos_hist = [
        ('2010–2021', BASE / 'dados' / 'pnae' / 'pnae_rn_2010_2021_valores_pagos_detalhado.csv'),
        ('2022', BASE / 'dados' / 'pnae' / 'pnae_rn_2022_valores_pagos_detalhado.csv'),
        ('2023', BASE / 'dados' / 'pnae' / 'pnae_rn_2023_valores_pagos_detalhado.csv'),
        ('2024', BASE / 'dados' / 'pnae' / 'pnae_rn_2024_previsao_detalhada.csv'),
    ]
    faltantes = [rotulo for rotulo, caminho in arquivos_hist if not caminho.exists()]
    if faltantes:
        st.warning('Arquivos ainda não encontrados em dados/pnae: ' + ', '.join(faltantes) + '. A série exibirá apenas os períodos disponíveis.')

    @st.cache_data(show_spinner=False)
    def ler_historico_pnae(caminho, tamanho, modificacao, periodo):
        raw = pd.read_csv(caminho, sep=';', encoding='utf-8-sig', dtype=str)
        if periodo == '2010–2021':
            mapa = {'ANO':'ano', 'UF':'uf', 'ENTIDADE_RESP':'entidade', 'ACAO':'acao', 'VALOR_PAGO':'valor'}
            natureza = 'Pago (conforme arquivo)'
            decimal_virgula = True
        elif periodo == '2022':
            mapa = {'ano':'ano', 'uf':'uf', 'entidade_responsavel':'entidade', 'acao':'acao', 'valor_pago_brl':'valor'}
            natureza = 'Pago (conforme arquivo)'
            decimal_virgula = False
        elif periodo == '2023':
            mapa = {'ano':'ano', 'uf':'uf', 'entidade_responsavel':'entidade', 'acao':'acao', 'valor_pago':'valor'}
            natureza = 'Pago (conforme arquivo)'
            decimal_virgula = False
        else:
            mapa = {'ano':'ano', 'uf':'uf', 'entidade_executora':'entidade', 'modalidade_pnae':'acao', 'valor_previsto_brl':'valor'}
            natureza = 'Previsto (não pago)'
            decimal_virgula = False
        ausentes = set(mapa) - set(raw.columns)
        if ausentes:
            raise ValueError(f'{periodo}: colunas ausentes: {sorted(ausentes)}')
        base_h = raw[list(mapa)].rename(columns=mapa).copy()
        base_h['ano'] = pd.to_numeric(base_h['ano'], errors='coerce')
        base_h['uf'] = base_h['uf'].str.strip().str.upper()
        base_h['entidade'] = base_h['entidade'].str.strip()
        base_h['acao'] = base_h['acao'].fillna('NÃO INFORMADA').str.strip()
        valores = base_h['valor'].str.strip()
        if decimal_virgula:
            valores = valores.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        base_h['valor'] = pd.to_numeric(valores, errors='coerce')
        if (base_h['uf'] != 'RN').any() or base_h['ano'].isna().any() or base_h['valor'].isna().any() or (base_h['valor'] < 0).any() or base_h['entidade'].isna().any():
            raise ValueError(f'{periodo}: há UF, ano, entidade ou valor inválido; nenhum registro foi descartado silenciosamente.')
        inicio, fim = (2010, 2021) if periodo == '2010–2021' else (int(periodo), int(periodo))
        if not base_h['ano'].between(inicio, fim).all():
            raise ValueError(f'{periodo}: há registros com ano fora do intervalo esperado.')
        base_h['ano'] = base_h['ano'].astype(int)
        base_h['natureza'] = natureza
        return base_h

    partes_h = []
    for rotulo_h, caminho_h in arquivos_hist:
        if caminho_h.exists():
            try:
                info_h = caminho_h.stat()
                partes_h.append(ler_historico_pnae(str(caminho_h), info_h.st_size, info_h.st_mtime, rotulo_h))
            except Exception as erro_h:
                st.error(f'Erro ao ler a base histórica {rotulo_h}: {erro_h}')
    if partes_h:
        historico = pd.concat(partes_h, ignore_index=True)
        anos_presentes = sorted(historico['ano'].unique().tolist())
        st.caption('Anos carregados: ' + ', '.join(map(str, anos_presentes)) + '.')
        entidades_h = sorted(historico['entidade'].dropna().unique().tolist())
        entidade_h = st.selectbox('Entidade executora — série histórica', ['Todas as entidades'] + entidades_h, key='entidade_historica')
        acoes_h = sorted(historico['acao'].dropna().unique().tolist())
        acao_h = st.selectbox('Código da modalidade/ação PNAE — série histórica', ['Todas as ações'] + acoes_h, key='acao_historica')
        recorte_h = historico.copy()
        if entidade_h != 'Todas as entidades':
            recorte_h = recorte_h[recorte_h['entidade'] == entidade_h]
        if acao_h != 'Todas as ações':
            recorte_h = recorte_h[recorte_h['acao'] == acao_h]
        resumo_h = recorte_h.groupby(['ano', 'natureza'], as_index=False)['valor'].sum().rename(columns={'valor':'Valor (R$)'})
        pagos_h = resumo_h[resumo_h['natureza'] == 'Pago (conforme arquivo)'].sort_values('ano')
        previstos_h = resumo_h[resumo_h['natureza'] == 'Previsto (não pago)'].sort_values('ano')
        if not pagos_h.empty:
            st.markdown('**Valores registrados como pagos — 2010 a 2023**')
            grafico_h = pagos_h[['ano', 'Valor (R$)']].copy()
            grafico_h['Ano'] = grafico_h['ano'].astype(str)
            grafico_h['Milhões de R$'] = grafico_h['Valor (R$)'] / 1_000_000
            ordem_anos = [str(ano) for ano in sorted(grafico_h['ano'].unique())]
            grafico = (
                alt.Chart(grafico_h)
                .mark_line(point=True, strokeWidth=2.5)
                .encode(
                    x=alt.X('Ano:N', sort=ordem_anos, title='Ano', axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('Milhões de R$:Q', title='Valor pago (milhões de R$)',
                            scale=alt.Scale(zero=False),
                            axis=alt.Axis(format='.0f')),
                    tooltip=[alt.Tooltip('Ano:N', title='Ano'),
                             alt.Tooltip('Valor (R$):Q', title='Valor pago (R$)', format=',.2f')]
                )
                .properties(height=350)
            )
            st.altair_chart(grafico, use_container_width=True)
            st.caption('Valores nominais, sem correção pela inflação. A escala vertical pode começar acima de zero para evidenciar variações; consulte a tabela para os valores completos.')
            # Correção pelo IPCA: média dos números-índices mensais de cada ano,
            # expressa em reais médios de 2023. Não altera os dados originais.
            caminho_ipca = BASE / 'dados' / 'ibge' / 'ipca_fatores_anuais_base_2023.csv'
            if caminho_ipca.exists():
                try:
                    fatores = pd.read_csv(caminho_ipca, encoding='utf-8-sig')
                    colunas_ipca = {'ano', 'ipca_indice_medio_anual', 'fator_para_reais_medios_2023'}
                    if not colunas_ipca.issubset(fatores.columns):
                        raise ValueError('Colunas esperadas ausentes no arquivo de fatores.')
                    fatores['ano'] = pd.to_numeric(fatores['ano'], errors='raise').astype(int)
                    fatores['fator_para_reais_medios_2023'] = pd.to_numeric(fatores['fator_para_reais_medios_2023'], errors='raise')
                    if fatores['ano'].duplicated().any() or (fatores['fator_para_reais_medios_2023'] <= 0).any():
                        raise ValueError('Anos duplicados ou fatores inválidos.')
                    corrigidos = pagos_h.merge(fatores[['ano', 'fator_para_reais_medios_2023']], on='ano', how='left', validate='many_to_one')
                    if corrigidos['fator_para_reais_medios_2023'].isna().any():
                        raise ValueError('Faltam fatores de correção para anos com pagamentos.')
                    corrigidos['Valor corrigido (R$ de 2023)'] = corrigidos['Valor (R$)'] * corrigidos['fator_para_reais_medios_2023']
                    corrigidos['Ano'] = corrigidos['ano'].astype(str)
                    corrigidos['Milhões de R$ de 2023'] = corrigidos['Valor corrigido (R$ de 2023)'] / 1_000_000
                    st.markdown('**Valores pagos corrigidos pelo IPCA — reais médios de 2023**')
                    grafico_real = (alt.Chart(corrigidos).mark_line(point=True, strokeWidth=2.5).encode(
                        x=alt.X('Ano:N', sort=[str(a) for a in sorted(corrigidos['ano'].unique())], title='Ano', axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('Milhões de R$ de 2023:Q', title='Valor pago (milhões de R$ de 2023)', scale=alt.Scale(zero=False), axis=alt.Axis(format='.0f')),
                        tooltip=[alt.Tooltip('Ano:N', title='Ano'), alt.Tooltip('Valor (R$):Q', title='Valor nominal (R$)', format=',.2f'), alt.Tooltip('Valor corrigido (R$ de 2023):Q', title='Valor corrigido (R$)', format=',.2f')]
                    ).properties(height=350))
                    st.altair_chart(grafico_real, use_container_width=True)
                    st.caption('Correção: IPCA nacional (IBGE/SIDRA, tabela 1737, variável 2266). Fator = média dos números-índices mensais de 2023 dividida pela média do ano de origem. Aproximação para fluxos anuais sem datas mensais; não mede especificamente o preço dos alimentos. A escala vertical pode começar acima de zero.')
                    tabela_corrigida = corrigidos[['ano', 'Valor (R$)', 'fator_para_reais_medios_2023', 'Valor corrigido (R$ de 2023)']].rename(columns={'Valor (R$)':'Valor nominal (R$)', 'fator_para_reais_medios_2023':'Fator IPCA'})
                    st.dataframe(tabela_corrigida, hide_index=True, width='stretch')
                    st.download_button('Baixar valores corrigidos pelo IPCA (CSV)', tabela_corrigida.to_csv(index=False, sep=';').encode('utf-8-sig'), 'pnae_rn_valores_corrigidos_ipca_base_2023.csv', 'text/csv', key='baixar_pnae_ipca')
                except (ValueError, KeyError, OSError) as erro_ipca:
                    st.warning(f'Não foi possível aplicar a correção pelo IPCA: {erro_ipca}')
            else:
                st.info('Para exibir a correção monetária, coloque ipca_fatores_anuais_base_2023.csv em dados/ibge/.')
        if not previstos_h.empty:
            st.markdown('**Previsão de repasse — 2024 (não comparável diretamente com os pagamentos)**')
            st.dataframe(previstos_h, hide_index=True, width='stretch')
        st.markdown('**Tabela histórica do recorte selecionado**')
        st.dataframe(resumo_h.sort_values('ano'), hide_index=True, width='stretch')
        st.download_button('Baixar tabela histórica (CSV)', resumo_h.sort_values('ano').to_csv(index=False, sep=';').encode('utf-8-sig'), 'pnae_rn_serie_historica_recorte.csv', 'text/csv', key='baixar_historico_pnae')
        st.caption('O filtro de município da barra lateral não se aplica a esta série. A seleção financeira é feita por entidade executora; nomes de entidades não foram equiparados automaticamente a municípios. Em 2010, a ação aparece como NAO_DISCRIMINADA. A comparação entre anos depende de validação das regras do FNDE e da correção monetária.')
    else:
        st.info('A série histórica estará disponível quando os arquivos CSV forem colocados em dados/pnae.')

    st.markdown('#### Qualidade da alimentação')
    st.info('Cardápios, execução das compras, agricultura familiar, pareceres dos conselhos e inspeções ainda não foram importados. Não atribuímos notas sem evidências.')
    st.markdown('[Repasses oficiais do FNDE](https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/programas/pnae/consultas/repasses-financeiros-por-entidade-executora) · [Resultados eleitorais do TSE](https://www.tse.jus.br/eleicoes/resultados-eleicoes)')

if st.session_state.obsed_secao == 'fontes':
    st.subheader('Fontes e metodologia')
    ficha_metodologica = BASE / 'FICHA_METODOLOGICA.md'
    if ficha_metodologica.exists():
        st.download_button('Baixar ficha metodológica completa (Markdown)', ficha_metodologica.read_bytes(),
                           'ficha_metodologica_observatorio_rn_v9.md', 'text/markdown')
    else:
        st.info('A ficha metodológica completa ainda não está disponível nesta pasta.')
    st.write('**PNAE histórico:** CSVs locais derivados das planilhas FNDE 2010–2024. Os valores de 2010–2023 são rotulados como pagos nos arquivos; 2024 apresenta previsão. Não são gastos das prefeituras nem recursos próprios. A interpretação temporal exige validação metodológica e correção monetária.')
    st.write('**População:** IBGE, Censo Demográfico 2022, tabela 4714, variável 93, municípios do RN. O número de habitantes é referente a 2022; sua associação é feita pelo código IBGE de sete dígitos.')
    st.write(f'**Fonte:** INEP, Censo Escolar {ano_censo}, arquivo {ARQUIVO.name}.')
    if ano_censo == 2025:
        st.write('**Integração 2025:** tabelas Escola, Matrícula, Docente, Turma e Gestor Escolar V2, cruzadas pelo código INEP da escola, com validação um a um. Ausências preservadas. Cursos técnicos não foram incorporados para evitar multiplicação de registros.')
    st.write('**Recorte:** SG_UF = RN e TP_SITUACAO_FUNCIONAMENTO = 1 (escolas em atividade).')
    st.write('**Unidade da ficha:** registro da escola identificado pelo código CO_ENTIDADE.')
    st.write('**Contagens:** somas das variáveis QT_MAT_BAS, QT_DOC_BAS e QT_TUR_BAS, conforme o caso. Docentes podem ser contabilizados em mais de uma escola.')
    st.write('**Limitações:** não são exibidos evasão ou direção escolar. O IDEB municipal está disponível em aba própria. A série histórica 2007–2024 é experimental. As categorias e codificações devem ser conferidas no dicionário oficial antes da divulgação científica definitiva.')
    st.write('**Interpretação:** indicadores com prefixo IN_ são tratados como presença (1), ausência (0) ou não informado; indicadores QT_ são quantidades. Campos não presentes no CSV não aparecem nas fichas.')
    st.write('**Validação pendente:** a nomenclatura de cada variável e suas regras de aplicabilidade precisam ser verificadas no dicionário oficial do ano selecionado antes da publicação pública definitiva.')
    st.write('**Comparações municipais:** percentuais de infraestrutura usam somente escolas com valor 0 ou 1 na variável consultada; respostas ausentes são informadas separadamente. Comparações não implicam causalidade.')
    st.write('**População:** Censo Demográfico IBGE 2022, tabela SIDRA 4714, variável 93, municípios do RN. A importação requer conferir 167 municípios e integridade dos códigos IBGE.')
    st.write('**Panorama municipal:** agrega os registros escolares por município e apresenta denominadores e ausências para cada indicador. O filtro populacional é opcional e requer CSV oficial do IBGE 2022, identificado por código municipal de sete dígitos.')
    st.write('**Privacidade:** a ficha exibe dados institucionais, não dados pessoais de estudantes.')


if st.session_state.obsed_secao == 'auditoria':
    st.subheader(f'Auditoria preliminar — Censo Escolar {ano_censo}')
    st.caption('Verificações automáticas de consistência interna. Não substituem a conferência com as publicações e os dicionários oficiais do INEP e IBGE.')
    st.markdown('#### Arquivo educacional e recorte')
    st.write(f'**Fonte local:** `{ARQUIVO.name}` · **Tamanho:** {ARQUIVO.stat().st_size / 1024**2:,.1f} MiB')
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
    for coluna in ['QT_MAT_BAS', 'QT_DOC_BAS', 'QT_TUR_BAS', 'QT_GEST_BAS']:
        if coluna in df.columns:
            numeros = pd.to_numeric(df[coluna], errors='coerce')
            registrar(f'{coluna}: valores negativos', (numeros < 0).sum(), 'Quantidades não negativas')
            registrar(f'{coluna}: valores ausentes ou não numéricos', numeros.isna().sum(),
                      'Avaliar preenchimento e regras de aplicabilidade no dicionário')
    if ano_censo == 2025:
        cols_a = ['QT_MAT_BAS','QT_DOC_BAS','QT_TUR_BAS','QT_GEST_BAS']
        aus = df.loc[df[cols_a].isna().any(axis=1), ['CO_ENTIDADE','NO_ENTIDADE','NO_MUNICIPIO']+cols_a]
        st.markdown('#### Escolas ativas com pelo menos uma contagem ausente')
        st.dataframe(aus, hide_index=True, width='stretch')
        st.caption('Ausência de informação não equivale a zero.')
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


if st.session_state.obsed_secao == 'historica':
    st.subheader('Série histórica da educação básica — Rio Grande do Norte, 2007–2024')
    st.warning('SÉRIE EXPERIMENTAL 2007–2024: totais estaduais de quatro indicadores de matrículas confrontados com as Sinopses do INEP apenas para 2007, 2011 e 2021. Demais anos e indicadores ainda não validados externamente; a comparabilidade temporal também exige exame.')
    pasta_previas = BASE / 'dados' / 'historico' / 'previas_auditoria'
    arquivos_previas = sorted(pasta_previas.glob('previa_municipal_2007_2021_*.csv'), reverse=True)
    if not arquivos_previas:
        st.info('Prévia municipal ainda não localizada em dados/historico/previas_auditoria. A versão 10.4 permanece disponível nas outras abas.')
    else:
        caminho_h = arquivos_previas[0]
        try:
            h = pd.read_csv(caminho_h, encoding='utf-8-sig', dtype={'co_municipio':str})
            campos = {'ano','co_municipio','escolas_codigo_1','QT_MAT_BAS_soma_previa','QT_MAT_INF_soma_previa','QT_MAT_FUND_soma_previa','QT_MAT_MED_soma_previa','QT_DOC_BAS_soma_previa'}
            if not campos.issubset(h.columns):
                raise ValueError('Colunas ausentes: ' + ', '.join(sorted(campos-set(h.columns))))
            if h.duplicated(['ano','co_municipio']).any():
                raise ValueError('Foram encontrados municípios repetidos no mesmo ano.')
            if h['ano'].nunique()!=15 or len(h)!=2505 or h.groupby('ano')['co_municipio'].nunique().ne(167).any():
                raise ValueError('A cobertura não corresponde a 15 anos × 167 municípios; interrompida a apresentação.')
            # 2022–2024: arquivo histórico já existente, sem reprocessar nem sobrescrever dados.
            caminho_recente = BASE / 'dados' / 'historico' / 'censo_rn_municipios_historico.csv'
            if not caminho_recente.exists():
                raise FileNotFoundError('Não encontrei dados/historico/censo_rn_municipios_historico.csv. Nenhum arquivo foi alterado.')
            recente = pd.read_csv(caminho_recente, sep=';', encoding='utf-8-sig', dtype={'codigo_municipio': str})
            mapa_colunas = {
                'codigo_municipio': 'co_municipio',
                'escolas_ativas_registros': 'escolas_codigo_1',
                'matriculas_basica': 'QT_MAT_BAS_soma_previa',
                'matriculas_infantil': 'QT_MAT_INF_soma_previa',
                'matriculas_fundamental': 'QT_MAT_FUND_soma_previa',
                'matriculas_medio': 'QT_MAT_MED_soma_previa',
                'docentes_basica_vinculos_escola': 'QT_DOC_BAS_soma_previa',
            }
            esperadas = {'ano', *mapa_colunas.keys()}
            if not esperadas.issubset(recente.columns):
                raise ValueError('Colunas ausentes no histórico 2022–2024: ' + ', '.join(sorted(esperadas-set(recente.columns))))
            recente = recente.rename(columns=mapa_colunas)
            colunas_comuns = ['ano', 'co_municipio', 'escolas_codigo_1', 'QT_MAT_BAS_soma_previa',
                              'QT_MAT_INF_soma_previa', 'QT_MAT_FUND_soma_previa',
                              'QT_MAT_MED_soma_previa', 'QT_DOC_BAS_soma_previa']
            recente = recente[colunas_comuns].copy()
            if (set(pd.to_numeric(recente['ano'], errors='coerce').dropna().astype(int)) != {2022, 2023, 2024}
                or len(recente) != 501 or recente.duplicated(['ano','co_municipio']).any()
                or recente.groupby('ano')['co_municipio'].nunique().ne(167).any()):
                raise ValueError('Histórico 2022–2024 não contém exatamente três anos × 167 municípios únicos.')
            if set(h['co_municipio'].astype(str)) != set(recente['co_municipio'].astype(str)):
                raise ValueError('Os códigos municipais das duas séries não coincidem.')
            h = pd.concat([h[colunas_comuns], recente], ignore_index=True)
            for coluna_numerica in ['ano', *colunas_comuns[2:]]:
                h[coluna_numerica] = pd.to_numeric(h[coluna_numerica], errors='raise')
            if (len(h) != 3006 or h['ano'].nunique() != 18
                or h.duplicated(['ano','co_municipio']).any()
                or h.groupby('ano')['co_municipio'].nunique().ne(167).any()
                or h[colunas_comuns[2:]].isna().any().any()
                or (h[colunas_comuns[2:]] < 0).any().any()):
                raise ValueError('A série unificada falhou na auditoria de cobertura e valores.')
            nomes = df[['CO_MUNICIPIO','NO_MUNICIPIO']].dropna().drop_duplicates('CO_MUNICIPIO').copy()
            nomes['co_municipio'] = pd.to_numeric(nomes['CO_MUNICIPIO'], errors='coerce').astype('Int64').astype(str)
            mapa_nomes = dict(zip(nomes['co_municipio'], nomes['NO_MUNICIPIO']))
            h['municipio'] = h['co_municipio'].map(mapa_nomes).fillna(h['co_municipio'])
            indicadores_h = {
                'Matrículas — educação básica':'QT_MAT_BAS_soma_previa',
                'Matrículas — educação infantil':'QT_MAT_INF_soma_previa',
                'Matrículas — ensino fundamental':'QT_MAT_FUND_soma_previa',
                'Matrículas — ensino médio':'QT_MAT_MED_soma_previa',
                'Escolas — situação de funcionamento 1':'escolas_codigo_1',
                'Docentes — soma de QT_DOC_BAS (conceito pendente)':'QT_DOC_BAS_soma_previa',
            }
            a_h,b_h = st.columns(2)
            indicador_escolhido = a_h.selectbox('Indicador histórico', list(indicadores_h), key='ind_hist_105')
            municipios_h = ['Todo o RN'] + sorted(h['municipio'].unique())
            municipio_escolhido = b_h.selectbox('Território', municipios_h, key='mun_hist_105')
            col_h = indicadores_h[indicador_escolhido]
            recorte_h = h if municipio_escolhido=='Todo o RN' else h[h['municipio']==municipio_escolhido]
            serie_h = recorte_h.groupby('ano', as_index=False)[col_h].sum()
            serie_h['ano'] = serie_h['ano'].astype(int)
            serie_h = serie_h.rename(columns={col_h:'valor'})
            # Anos são categorias temporais: não aplicar separador de milhares (2,012).
            serie_grafico = serie_h.copy()
            serie_grafico['Ano'] = serie_grafico['ano'].astype(str)
            grafico_serie = (
                alt.Chart(serie_grafico)
                .mark_line(point=True, strokeWidth=2.5)
                .encode(
                    x=alt.X('Ano:N', sort=[str(a) for a in sorted(serie_h['ano'].unique())],
                            title='Ano', axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('valor:Q', title=indicador_escolhido),
                    tooltip=[alt.Tooltip('Ano:N', title='Ano'),
                             alt.Tooltip('valor:Q', title=indicador_escolhido, format=',.0f')]
                )
                .properties(height=350)
            )
            st.altair_chart(grafico_serie, use_container_width=True)
            c1_h,c2_h,c3_h = st.columns(3)
            c1_h.metric('2007', numero(serie_h.loc[serie_h.ano==2007,'valor'].sum()))
            c2_h.metric('2024', numero(serie_h.loc[serie_h.ano==2024,'valor'].sum()))
            c3_h.metric('Municípios na base', numero(h['co_municipio'].nunique()))
            serie_h['Situação da conferência'] = serie_h['ano'].map(lambda y: 'Total estadual de matrículas confrontado com INEP' if municipio_escolhido=='Todo o RN' and col_h.startswith('QT_MAT_') and y in (2007,2011,2021) else 'Ainda não confrontado com Sinopse oficial')
            st.dataframe(serie_h.rename(columns={'ano':'Ano','valor':'Quantidade'}), hide_index=True, width='stretch')
            st.download_button('Baixar recorte histórico (CSV)', serie_h.to_csv(index=False,sep=';').encode('utf-8-sig'), 'observatorio_rn_serie_historica_2007_2024_experimental.csv', 'text/csv', key='baixar_hist_105')
            st.caption('Fontes locais: prévia municipal 2007–2021 e histórico municipal 2022–2024, provenientes de microdados do Censo Escolar/INEP. Conferência externa pontual dos totais estaduais de matrículas: 2007, 2011 e 2021. Escolas: situação 1. Matrículas não equivalem a pessoas distintas; docentes podem refletir vínculos escolares. Série não harmonizada para mudanças metodológicas.')
        except Exception as erro_h:
            st.error(f'Não foi possível carregar a série histórica com segurança: {erro_h}')


@st.cache_data(show_spinner='Carregando IDEB oficial…')
def carregar_ideb(caminho, tamanho, modificacao):
    base = pd.read_csv(caminho, encoding='utf-8-sig', dtype={'codigo_municipio': str})
    campos = {'etapa','codigo_municipio','municipio','rede','ano','ideb_observado','meta_ideb','situacao_valor'}
    if not campos.issubset(base.columns):
        raise ValueError('Colunas obrigatórias ausentes: ' + ', '.join(sorted(campos - set(base.columns))))
    if base.duplicated(['etapa','codigo_municipio','rede','ano']).any():
        raise ValueError('Há resultados repetidos para município, etapa, rede e ano.')
    if not base['codigo_municipio'].str.fullmatch(r'24\d{5}', na=False).all():
        raise ValueError('Há códigos municipais fora do Rio Grande do Norte.')
    base['ano'] = pd.to_numeric(base['ano'], errors='raise').astype(int)
    for col in ['ideb_observado','meta_ideb']:
        base[col] = pd.to_numeric(base[col], errors='coerce')
        if base[col].notna().any() and not base[col].dropna().between(0,10).all():
            raise ValueError(f'Notas inválidas na coluna {col}.')
    if base['codigo_municipio'].nunique() != 167:
        raise ValueError('A base não contempla exatamente os 167 municípios do RN.')
    return base

if st.session_state.obsed_secao == 'ideb':
    st.caption('A série estadual oficial e a série municipal também estão disponíveis no painel IDEB em destaque, na aba Visão geral.')
    st.subheader('IDEB — resultados municipais do Rio Grande do Norte')
    st.caption('Fonte: INEP, divulgação 2005–2025. Resultados por município, rede e etapa; não são notas individuais de estudantes nem médias calculadas pelo Observatório.')
    if not ARQUIVO_IDEB.exists():
        st.warning('Base do IDEB não encontrada. Coloque ideb_rn_municipios_2005_2025.csv em dados/ideb/.')
    else:
        try:
            info_ideb = ARQUIVO_IDEB.stat()
            ideb = carregar_ideb(str(ARQUIVO_IDEB), info_ideb.st_size, info_ideb.st_mtime)
            etapas_ideb = ['Anos iniciais', 'Anos finais', 'Ensino médio']
            c1, c2, c3 = st.columns(3)
            etapa_i = c1.selectbox('Etapa de ensino', etapas_ideb, key='ideb_etapa')
            redes_i = sorted(ideb.loc[ideb['etapa'].eq(etapa_i), 'rede'].unique())
            rede_i = c2.selectbox('Rede de ensino', redes_i, index=redes_i.index('Pública') if 'Pública' in redes_i else 0, key='ideb_rede')
            municipios_i = sorted(ideb['municipio'].unique())
            mun_i = c3.selectbox('Município', municipios_i, index=municipios_i.index('Natal') if 'Natal' in municipios_i else 0, key='ideb_municipio')
            rec_i = ideb.loc[ideb['etapa'].eq(etapa_i) & ideb['rede'].eq(rede_i) & ideb['municipio'].eq(mun_i)].sort_values('ano').copy()
            st.markdown('#### Evolução do IDEB observado')
            validos_i = rec_i.dropna(subset=['ideb_observado'])
            if validos_i.empty:
                st.info('Não há resultados publicados para este recorte.')
            else:
                graf_i = (alt.Chart(validos_i).mark_line(point=True, strokeWidth=2.5).encode(
                    x=alt.X('ano:O', title='Ano'),
                    y=alt.Y('ideb_observado:Q', title='IDEB observado', scale=alt.Scale(domain=[0,10])),
                    tooltip=[alt.Tooltip('ano:O',title='Ano'), alt.Tooltip('ideb_observado:Q',title='IDEB',format='.1f')]
                ).properties(height=330))
                st.altair_chart(graf_i, use_container_width=True)
                ultimo_i = validos_i.iloc[-1]
                st.metric('Último IDEB divulgado neste recorte', f"{ultimo_i['ideb_observado']:.1f}".replace('.', ','), help=f"Ano: {int(ultimo_i['ano'])}")
            st.dataframe(rec_i[['ano','ideb_observado','meta_ideb','situacao_valor']].rename(columns={
                'ano':'Ano','ideb_observado':'IDEB observado','meta_ideb':'Meta','situacao_valor':'Situação'}), hide_index=True, width='stretch')
            st.caption('Células vazias não equivalem a zero. Metas são apresentadas somente quando constam do arquivo oficial; não inferimos metas para anos posteriores.')
            st.divider()
            st.markdown('#### Comparar municípios no mesmo ano, rede e etapa')
            anos_i = sorted(ideb.loc[ideb['etapa'].eq(etapa_i) & ideb['rede'].eq(rede_i),'ano'].unique(), reverse=True)
            ano_i = st.selectbox('Ano de referência', anos_i, key='ideb_ano')
            comp_i = ideb.loc[ideb['etapa'].eq(etapa_i) & ideb['rede'].eq(rede_i) & ideb['ano'].eq(ano_i)].copy()
            comp_i = comp_i.sort_values(['ideb_observado','municipio'], ascending=[False,True], na_position='last')
            st.metric('Municípios com resultado publicado neste recorte', int(comp_i['ideb_observado'].notna().sum()))
            st.dataframe(comp_i[['municipio','ideb_observado','meta_ideb','situacao_valor']].rename(columns={
                'municipio':'Município','ideb_observado':'IDEB observado','meta_ideb':'Meta','situacao_valor':'Situação'}), hide_index=True, width='stretch')
            st.download_button('Baixar comparação IDEB (CSV)', comp_i.to_csv(index=False,sep=';').encode('utf-8-sig'),
                               f'ideb_rn_{ano_i}_comparacao.csv', 'text/csv', key='ideb_download')
            st.info('Comparações descritivas: resultados de diferentes redes, etapas e anos não devem ser somados. A rede Pública pode abranger resultados de outras dependências; não é uma categoria aditiva. O IDEB combina desempenho no Saeb e fluxo escolar.')
            st.markdown('[Fonte oficial: resultados do IDEB — INEP](https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados)')
        except (OSError, ValueError, KeyError, pd.errors.ParserError) as erro_i:
            st.error(f'Não foi possível validar ou carregar a base IDEB: {erro_i}')


if st.session_state.obsed_secao == 'superior':
    st.subheader('Ensino superior')
    st.info('Seção em construção. As bases oficiais do ensino superior ainda serão integradas e auditadas.')

if st.session_state.obsed_secao == 'questao':
    st.subheader('Educação em questão')
    st.write('Espaço dedicado a ensaios, análises críticas e debates sobre a educação potiguar.')
    st.info('Seção em construção. Os textos serão incorporados posteriormente.')


# RSIP — registro público, somente leitura. Atualização editorial via CSV local.
if st.session_state.obsed_secao == 'transparencia':
    from datetime import datetime
    from zoneinfo import ZoneInfo
    st.subheader('Transparência Pública')
    st.markdown('**Registro de Solicitações de Informação Pública — RSIP**')
    st.markdown('> A informação pública não é uma concessão do Estado. É um direito do cidadão.')
    st.caption('Registro independente dos filtros educacionais. Acompanhamento documental; não constitui avaliação antecipada dos órgãos públicos.')
    texto_oficio = 'ObsEd RN — Observatório da Educação no Rio Grande do Norte\nDados para entender. Conhecimento para debater. Educação para transformar.\n\nOFÍCIO Nº 001/2026 — ObsEd RN\nNatal, 18 de novembro de 2026.\n\nÀ Secretaria de Estado da Educação do Rio Grande do Norte\nA/C do setor responsável pelo Censo Escolar e pelas estatísticas educacionais\n\nAssunto: Pedido de acesso à informação — evolução das matrículas e metodologia do SIGEduc e do Censo Escolar\n\nPrezados(as) Senhores(as),\n\nO ObsEd RN, iniciativa independente de pesquisa sobre a educação potiguar, solicita, com fundamento na Lei Federal nº 12.527/2011, acesso a informações e documentos existentes sobre a evolução das matrículas na educação básica.\n\nNossas extrações dos microdados do INEP indicam 802.751 matrículas em 2022, 796.526 em 2023, 783.190 em 2024 e 756.434 em 2025, uma redução de 46.317 no período. Na rede estadual, os totais passaram de 196.764 para 182.461 entre 2024 e 2025; na EJA estadual, de 23.632 para 19.574; e na educação profissional estadual, de 12.986 para 26.135. As modalidades podem se sobrepor.\n\nEm consultas ao SIGEduc realizadas em 18/11/2026, observamos os seguintes quantitativos (2024 → 2025):\n• CEJA Professora Lia Campos (INEP 24056987): INEP 1.355 → 698; SIGEduc 1.976 → 1.929.\n• CEJA Professor Felipe Guerra (INEP 24056774): INEP 851 → 410; SIGEduc 1.222 → 920.\n• Escola Estadual Aldo Fernandes de Melo (INEP 24060020): INEP 727 → 192; SIGEduc 745 → 181.\n\nEssas diferenças não constituem, por si sós, evidência de erro, pois as fontes podem adotar critérios e datas de referência distintos. Para compreender tais diferenças, solicitamos:\n\n1. Notas técnicas, manuais e dicionários que descrevam a metodologia dos indicadores do SIGEduc, especialmente o conceito de matrícula, a data de referência, o tratamento de inscrições ao longo do ano, transferências, cancelamentos, duplicidades e particularidades da EJA; bem como os procedimentos de transmissão e validação junto ao INEP e eventuais alterações entre 2024 e 2025.\n\n2. Relatórios, diagnósticos e atos administrativos existentes relativos à redução de matrículas estaduais, à reorganização da EJA, à expansão da educação profissional e a eventuais inconsistências e retificações do Censo Escolar de 2025.\n\n3. Para as três instituições identificadas acima, registros e documentos existentes sobre alterações na oferta de vagas, turmas, turnos, etapas e modalidades, transferências coletivas de estudantes (com indicação das instituições de destino, quando registrada), reformas prediais e reorganizações administrativas entre 2024 e 2025.\n\n4. Bases estatísticas existentes do SIGEduc referentes a 2022–2025, por ano, município e estabelecimento (preferencialmente com código INEP), contendo matrículas por etapa e modalidade, aprovação, reprovação, abandono, docentes, turmas, situação de funcionamento e oferta educacional. Solicitamos, preferencialmente, formato digital aberto (CSV ou equivalente), acompanhado de documentação metodológica.\n\nCaso algum item não esteja disponível, solicitamos a indicação dessa circunstância e, se conhecido, do órgão que detém a informação. Não solicitamos a produção de estudos inéditos nem dados pessoais de estudantes, docentes ou gestores. O pedido tem finalidade científica e informativa e não pressupõe irregularidade.\n\nAgradecemos a atenção e a colaboração institucional.\n\nAtenciosamente,\nMonalisa Carrilho de Macedo\nProfessora da Universidade Federal do Rio Grande do Norte\nObsEd RN — Observatório da Educação no Rio Grande do Norte\n'
    campos = ['registro','orgao','assunto','elaboracao','protocolo','data_protocolo','prazo_resposta','data_resposta','resultado','observacoes']
    inicial = pd.DataFrame([['001/2026','Secretaria de Estado da Educação — RN','Matrículas e diferenças entre INEP e SIGEduc','2026-11-18','','','','','','Minuta elaborada; envio não confirmado.']], columns=campos)
    caminho_rsip = BASE / 'dados' / 'transparencia' / 'registro_solicitacoes.csv'
    registro = inicial.copy()
    if caminho_rsip.exists():
        try:
            registro = pd.read_csv(caminho_rsip, sep=';', encoding='utf-8-sig', dtype=str, keep_default_na=False)
            if not set(campos).issubset(registro.columns) or registro['registro'].duplicated().any() or registro['registro'].str.strip().eq('').any():
                raise ValueError('Colunas obrigatórias ou identificadores inválidos.')
            registro = registro[campos].copy()
        except Exception as erro:
            st.error(f'Não foi possível validar o registro: {erro}')
            st.stop()
    hoje = datetime.now(ZoneInfo('America/Fortaleza')).date()
    def data_rsip(v):
        return pd.to_datetime(v, format='%Y-%m-%d', errors='coerce')
    def situacao_rsip(r):
        if not r['protocolo'].strip() or pd.isna(data_rsip(r['data_protocolo'])):
            return 'Aguardando protocolo'
        if pd.notna(data_rsip(r['data_resposta'])):
            return 'Respondida'
        prazo = data_rsip(r['prazo_resposta'])
        if pd.isna(prazo):
            return 'Protocolada — prazo a confirmar'
        return 'Prazo vencido — sem resposta registrada' if hoje > prazo.date() else 'Aguardando resposta'
    registro['situacao'] = registro.apply(situacao_rsip, axis=1)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric('Elaboradas', len(registro))
    c2.metric('Protocoladas', int(registro['situacao'].ne('Aguardando protocolo').sum()))
    c3.metric('Respondidas', int(registro['situacao'].eq('Respondida').sum()))
    c4.metric('Prazo vencido', int(registro['situacao'].str.startswith('Prazo vencido').sum()))
    st.caption('Prazo conforme o protocolo oficial, inclusive eventual prorrogação. Ausência de resposta registrada não prova ausência de resposta do órgão.')
    st.dataframe(registro.rename(columns={'registro':'Registro','orgao':'Órgão','assunto':'Assunto','elaboracao':'Elaboração','protocolo':'Protocolo','data_protocolo':'Data do protocolo','prazo_resposta':'Prazo informado','data_resposta':'Data da resposta','resultado':'Resultado','observacoes':'Observações','situacao':'Situação'}), hide_index=True, width='stretch')
    st.download_button('Baixar registro (CSV)', registro[campos].to_csv(index=False,sep=';').encode('utf-8-sig'), 'registro_solicitacoes.csv', 'text/csv', key='rsip_csv')
    st.divider()
    st.markdown('#### Solicitação nº 001/2026 — SEEC/RN')
    st.caption('Texto elaborado em 18/11/2026. A publicação desta minuta não comprova seu envio.')
    with st.expander('Ler a íntegra do primeiro ofício', expanded=True):
        st.markdown(texto_oficio.replace("\n", "  \n"))
    st.download_button('Baixar ofício nº 001/2026 (TXT)', texto_oficio.encode('utf-8'), 'oficio_001_2026_obsed.txt', 'text/plain', key='rsip_oficio')
    st.markdown('[Lei de Acesso à Informação — Lei nº 12.527/2011](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm)')
    st.caption('Atualização editorial: dados/transparencia/registro_solicitacoes.csv. Não publicar dados pessoais, anexos sigilosos ou protocolos que concedam acesso a informações privadas.')
