"""Gera uma cópia publicável da versão 9, sem alterar a instalação local."""
from pathlib import Path
import shutil, zipfile, sys
import pandas as pd

kit = Path(__file__).resolve().parent
projeto = kit.parent
original = projeto / 'dados' / 'brutos' / 'microdados_ed_basica_2024.csv'
populacao = projeto / 'dados' / 'ibge_populacao_municipios_rn_2022.csv'
destino = projeto / 'ELINFANTE_PRONTO_PARA_GITHUB'
if not original.is_file() or not populacao.is_file():
    sys.exit('ERRO: arquivos oficiais não encontrados. Verifique se o kit está dentro da pasta principal do Observatório.')
if destino.exists():
    sys.exit('A pasta ELINFANTE_PRONTO_PARA_GITHUB já existe. Para evitar substituições, interrompi a operação.')
destino.mkdir()
(destino / 'dados').mkdir()
print('Lendo o arquivo oficial. Aguarde...')
partes=[]
for bloco in pd.read_csv(original, sep=';', encoding='latin1', low_memory=False, chunksize=3000):
    selecao = bloco.loc[(bloco['SG_UF'].astype(str).str.strip() == 'RN') & (pd.to_numeric(bloco['TP_SITUACAO_FUNCIONAMENTO'], errors='coerce') == 1)]
    if not selecao.empty: partes.append(selecao)
if not partes: sys.exit('ERRO: nenhuma escola em atividade no RN encontrada. Não publique.')
df=pd.concat(partes,ignore_index=True)
if df['CO_ENTIDADE'].duplicated().any(): sys.exit('ERRO: códigos INEP duplicados. Não publique.')
if df['NO_MUNICIPIO'].nunique() != 167: print('ATENÇÃO: municípios encontrados:',df['NO_MUNICIPIO'].nunique())
saida=destino/'dados'/'escolas_rn_2024_publicacao.csv'
df.to_csv(saida,index=False,sep=';',encoding='utf-8-sig')
shutil.copy2(populacao,destino/'dados'/populacao.name)
for nome in ('app.py','requirements.txt','README.md','FICHA_METODOLOGICA.md'):
    shutil.copy2(kit/nome,destino/nome)
print('Escolas:',len(df),'| Municípios:',df['NO_MUNICIPIO'].nunique())
print('Matrículas:',int(pd.to_numeric(df['QT_MAT_BAS'],errors='coerce').sum()))
print('Docentes somados por escola:',int(pd.to_numeric(df['QT_DOC_BAS'],errors='coerce').sum()))
print('Arquivo reduzido: %.2f MiB'%(saida.stat().st_size/1024**2))
if saida.stat().st_size > 95*1024**2: sys.exit('ATENÇÃO: arquivo ainda grande demais para upload comum do GitHub.')
zip_path=projeto/'ELINFANTE_PRONTO_PARA_GITHUB.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for arq in destino.rglob('*'):
        if arq.is_file(): z.write(arq,arq.relative_to(destino))
print('PRONTO! Pasta:',destino)
print('ZIP:',zip_path)
print('NÃO ENVIE os microdados nacionais originais ao GitHub.')
