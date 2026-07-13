import os
import csv
import io
import time
from datetime import datetime
import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd

# ==============================================================================
# 1. INITIALIZATION & CORE CONFIGURATIONS
# ==============================================================================

DATABASE_FILE = "Captura_Notas_Fiscais.csv"

if not os.path.exists(DATABASE_FILE) or os.path.getsize(DATABASE_FILE) == 0:
    with open(DATABASE_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "transaction_id", 
            "timestamp", 
            "employee_name",
            "file_path", 
            "user_description", 
            "headcount", 
            "extracted_emission_date", 
            "extracted_total_value",
            "fiscal_id"
        ])

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

CATEGORIES = [
    "ÁGUA", "ALMOÇO", "CAFÉ DA MANHÃ", "CARGA", "COMBUSTÍVEL", "CRÉDITO",
    "ENVIO DE MATERIAL", "ESTACIONAMENTO", "FARMÁCIA", "FERRAMENTAS",
    "HOTEL", "JANTA", "LAVAGEM CARRO", "LAVANDERIA",
    "MATERIAL DE ESCRITÓRIO", "MATERIAL OBRA", "MERCADO", "OUTROS",
    "PASSAGEM", "PEÇAS CARRO", "PEDÁGIO", "REEMBOLSO", "SAQUE",
    "TAXA DE SAQUE", "UBER"
]

st.set_page_config(
    page_title="Sistema Unificado - Controle de Despesas",
    page_icon="🧾",
    layout="wide"
)

aba_selecionada = st.tabs(["📲 Módulo do Funcionário (Captura)", "🔒 Painel Administrativo (Gerência)"])

# ==============================================================================
# TAB 1: MÓDULO DO FUNCIONÁRIO (CAPTURA)
# ==============================================================================
with aba_selecionada[0]:
    st.title("Sistema de Captura e Auditoria de Despesas")
    st.markdown("Use este espaço para digitalizar e enviar comprovantes fiscais em tempo real.")
    st.markdown("---")

    if "form_key" not in st.session_state:
        st.session_state.form_key = 0

    st.subheader("1. Informações Operacionais")

    with st.form(key=f"expense_form_{st.session_state.form_key}", clear_on_submit=True):
        employee_name = st.text_input("Nome do Funcionário", placeholder="Digite seu nome completo")
        user_description = st.selectbox("Finalidade do Gasto / Descrição", options=CATEGORIES, index=1)
        headcount = st.number_input("Quantidade de Beneficiários (Pessoas)", min_value=1, value=1, step=1)

        st.subheader("2. Digitalização do Comprovante")
        captured_file = st.file_uploader("Insira ou tire a foto do cupom fiscal", type=["png", "jpg", "jpeg"])

        submit_button = st.form_submit_button("Processar Documento e Sincronizar", type="primary")

    if submit_button:
        if not employee_name:
            st.error("Erro: O campo 'Nome do Funcionário' é obrigatório.")
        elif not captured_file:
            st.error("Erro: Nenhuma imagem detectada para processamento.")
        else:
            with st.spinner("Executando pipeline de extração por Visão Computacional..."):
                try:
                    img_payload = Image.open(captured_file)
                    current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    virtual_file_path = f"MEM_STREAM/rec_{current_timestamp}.png"

                    llm_engine = genai.GenerativeModel('gemini-2.5-flash')
                    
                    extraction_prompt = (
                        "Analyze the attached document. Extract the emission date, the final total value, "
                        "and any official Brazilian fiscal identification number such as NFC-e number, NFS-e number, "
                        "or Chave de Acesso. If no official fiscal identification sequence is found on the document, "
                        "return 'NONE' for FISCAL_ID.\n\n"
                        "Return the extracted information strictly in plain text formatting exactly as the template below, "
                        "with no markdown tags, no notes, and no additional text:\n"
                        "DATE: DD/MM/YYYY\n"
                        "VALUE: 00.00\n"
                        "FISCAL_ID: TEXT"
                    )

                    inference_response = llm_engine.generate_content([extraction_prompt, img_payload])
                    raw_output = inference_response.text
                    
                    extracted_date = "N/A"
                    extracted_value = "N/A"
                    fiscal_id = "NONE"
                    
                    for line in raw_output.split("\n"):
                        if "DATE:" in line:
                            extracted_date = line.replace("DATE:", "").strip()
                        if "VALUE:" in line:
                            extracted_value = line.replace("VALUE:", "").strip()
                        if "FISCAL_ID:" in line:
                            fiscal_id = line.replace("FISCAL_ID:", "").strip()

                    if fiscal_id.upper() == "NONE" or fiscal_id == "":
                        fiscal_display = "Sem Cupom Fiscal (Documento Não-Fiscal)"
                    else:
                        fiscal_display = fiscal_id

                    transaction_id = f"TX-{current_timestamp}"

                    with open(DATABASE_FILE, mode="a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            transaction_id,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            employee_name,
                            virtual_file_path,
                            user_description,
                            headcount,
                            extracted_date,
                            extracted_value,
                            fiscal_id
                        ])

                    st.balloons()
                    st.success("✅ CONCLUÍDO COM SUCESSO! A nota fiscal foi escaneada e sincronizada com a gerência.")
                    st.info(f"Código da Transação: {transaction_id} | Valor Identificado: R$ {extracted_value}")
                    
                    time.sleep(3)
                    
                    st.session_state.form_key += 1
                    st.rerun()

                except Exception as ex:
                    st.error(f"Falha na execução do pipeline: {str(ex)}")

# ==============================================================================
# TAB 2: PAINEL ADMINISTRATIVO (GERÊNCIA)
# ==============================================================================
with aba_selecionada[1]:
    st.title("🔒 Área Restrita - Controle Administrativo")
    st.markdown("Insira a credencial master para auditar as despesas consolidadas e exportar planilhas.")
    st.markdown("---")

    senha_inserida = st.text_input("Senha de Acesso Gerencial", type="password", placeholder="Digite a senha master")

    if senha_inserida == "caetevisual":
        st.success("Autenticação efetuada com sucesso! Exibindo banco de dados.")
        st.markdown("---")

        if os.path.exists(DATABASE_FILE) and os.path.getsize(DATABASE_FILE) > 100:
            df = pd.read_csv(DATABASE_FILE)
            
            df["transaction_id"] = df["transaction_id"].astype(str)
            df["fiscal_id"] = df["fiscal_id"].fillna("NONE").astype(str)
            df["extracted_total_value"] = df["extracted_total_value"].fillna("0.00").astype(str)

            rename_rules = {
                "transaction_id": "ID Transação",
                "timestamp": "Data/Hora Envio",
                "employee_name": "Funcionário",
                "file_path": "Caminho do Arquivo",
                "user_description": "Categoria da Despesa",
                "headcount": "Qtd Pessoas",
                "extracted_emission_date": "Data Emissão (IA)",
                "extracted_total_value": "Valor Total (IA)",
                "fiscal_id": "ID Fiscal / Autenticação"
            }
            
            df_display = df.rename(columns=rename_rules)
            final_order = [
                "ID Transação", "Data/Hora Envio", "Funcionário", "Caminho do Arquivo", 
                "Categoria da Despesa", "Qtd Pessoas", "Data Emissão (IA)", 
                "Valor Total (IA)", "ID Fiscal / Autenticação"
            ]
            df_display = df_display[final_order]

            col1, col2, col3 = st.columns(3)
            col1.metric("Total de Notas Capturadas", len(df))
            
            try:
                v_clean = df["extracted_total_value"].str.replace("R$", "", regex=False).str.strip()
                total_gasto = pd.to_numeric(v_clean, errors='coerce').sum()
                if pd.isna(total_gasto) or total_gasto > 100000000:
                    col2.metric("Volume Financeiro Auditado", "R$ 0.00")
                else:
                    col2.metric("Volume Financeiro Auditado", f"R$ {total_gasto:,.2f}")
            except Exception:
                col2.metric("Volume Financeiro Auditado", "R$ 0.00")
                
            non_fiscal_count = len(df[df["fiscal_id"].str.upper() == "NONE"])
            col3.metric("Documentos Não-Fiscais", non_fiscal_count)

            st.subheader("Registros Sincronizados no Sistema")
            st.dataframe(df_display, use_container_width=True)

            st.markdown("---")
            st.subheader("Exportação de Relatório Executivo")

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_display.to_excel(writer, index=False, sheet_name='Auditoria Despesas')
            
            st.download_button(
                label="📥 Baixar Planilha Oficial do Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Relatorio_Auditoria_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.info("Nenhum registro de despesa armazenado na base de dados até o momento.")
    elif senha_inserida != "":
        st.error("Senha incorreta. Acesso negado aos relatórios.")
    else:
        st.warning("Por razões de compliance e LGPD, insira a senha para desbloquear a visualização financeira.")
