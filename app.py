# app.py
import io
import streamlit as st
import pandas as pd

from gcp_scan import run_all

# Tenta usar AG Grid (mais “bonito” e com filtros). Se não tiver, cai em st.dataframe.
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
    AGGRID_AVAILABLE = True
except Exception:
    AGGRID_AVAILABLE = False


st.set_page_config(page_title="GCP FinOps Scanner", layout="wide")

st.title("GCP FinOps Scanner (Local)")
st.caption("Pré-requisito: rode `gcloud auth application-default login` (ADC) e depois use essa UI.")


def render_table(df: pd.DataFrame, height: int = 420):
    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return

    if AGGRID_AVAILABLE:
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_default_column(sortable=True, filter=True, resizable=True)
        gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=25)
        gb.configure_side_bar()  # painel de filtros/colunas
        grid_options = gb.build()

        AgGrid(
            df,
            gridOptions=grid_options,
            height=height,
            update_mode=GridUpdateMode.NO_UPDATE,
            fit_columns_on_grid_load=True,
        )
    else:
        st.dataframe(df, use_container_width=True, height=height)


def to_excel_bytes(dfs: dict[str, pd.DataFrame]) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        for sheet, df in dfs.items():
            safe_sheet = sheet[:31]  # limite do Excel
            (df if df is not None else pd.DataFrame()).to_excel(writer, sheet_name=safe_sheet, index=False)
    bio.seek(0)
    return bio.read()


with st.sidebar:
    st.header("Config")
    project_id = st.text_input("Project ID", placeholder="meu-projeto-gcp")
    lookback_days = st.number_input("Lookback (dias)", min_value=1, max_value=30, value=7)
    vm_cpu_th = st.slider("VM CPU média < (%)", min_value=1, max_value=50, value=10) / 100.0
    sql_cpu_th = st.slider("Cloud SQL CPU média < (%)", min_value=1, max_value=50, value=10) / 100.0

    run_btn = st.button("Rodar análise", type="primary")

    st.divider()
    st.subheader("Status UI")
    st.write(f"AG Grid: {'✅' if AGGRID_AVAILABLE else '❌ (usando st.dataframe)'}")


if run_btn:
    if not project_id:
        st.error("Preencha o Project ID.")
        st.stop()

    with st.spinner("Coletando dados (Compute + Monitoring + SQL Admin)..."):
        try:
            dfs = run_all(project_id, int(lookback_days), float(vm_cpu_th), float(sql_cpu_th))
        except Exception as e:
            st.error(f"Erro ao rodar: {e}")
            st.stop()

    st.success("Concluído!")

    # Download do Excel
    xlsx_bytes = to_excel_bytes(dfs)
    st.download_button(
        label="⬇️ Baixar Excel (.xlsx)",
        data=xlsx_bytes,
        file_name=f"gcp_finops_report_{project_id}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()

    # Tabs por “aba do Excel”
    tab_names = list(dfs.keys())
    tabs = st.tabs(tab_names)

    for t, name in zip(tabs, tab_names):
        with t:
            df = dfs.get(name)
            st.subheader(name)
            st.caption(f"Linhas: {len(df) if df is not None else 0}")
            render_table(df)
else:
    st.info("Preencha o Project ID na barra lateral e clique em **Rodar análise**.")
