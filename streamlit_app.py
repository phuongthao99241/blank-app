import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Comparison Tool", layout="wide")
st.title("🔍 Vertrags-/Asset- & Report-Vergleich")

tab_de, tab_en = st.tabs(["🇩🇪 Deutsch", "🇬🇧 English"])

# =========================
# 🔧 HELPERS
# =========================

def row_to_string(row):
    return " ".join(row.fillna("").astype(str)).lower()

def _try_parse_number(val):
    if pd.isna(val):
        return False, None
    try:
        return True, float(str(val).replace(",", "."))
    except:
        return False, None


# =========================
# 📑 REPORT LOADING (SIMPLIFIED)
# =========================

@st.cache_data
def load_report(file):

    # read raw (no header!)
    try:
        df_raw = pd.read_csv(
            file,
            header=None,
            dtype=str,
            sep=None,
            engine="python",
            encoding="utf-8",
            on_bad_lines="skip"
        )
    except:
        df_raw = pd.read_csv(
            file,
            header=None,
            dtype=str,
            sep=None,
            engine="python",
            encoding="latin1",
            on_bad_lines="skip"
        )

    # 🔍 find header row (FIRST COLUMN == "System ID")
    header_row = None

    for i in range(len(df_raw)):
        first_cell = str(df_raw.iloc[i, 0]).strip().lower()

        if "system id" in first_cell or "system-id" in first_cell:
            header_row = i
            break

    if header_row is None:
        st.error("❌ Could not find header row (System ID)")
        st.write(df_raw.head(20))
        st.stop()

    # 🎯 build dataframe from header
    df = df_raw.iloc[header_row:].copy()
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    # clean column names
    df.columns = [str(c).strip() for c in df.columns]

    # ❌ remove total rows
    df = df[~df.apply(lambda row: "total" in " ".join(row.fillna("").astype(str)).lower(), axis=1)]

    return df


# =========================
# 📊 REPORT COMPARISON
# =========================

def compare_reports(df_test, df_prod, id_col, asset_col):

    # ensure IDs exist
    if id_col not in df_test.columns or asset_col not in df_test.columns:
        st.error("❌ TEST: Required columns not found")
        st.write(df_test.columns.tolist())
        st.stop()

    if id_col not in df_prod.columns or asset_col not in df_prod.columns:
        st.error("❌ PROD: Required columns not found")
        st.write(df_prod.columns.tolist())
        st.stop()

    # normalize IDs
    df_test[id_col] = df_test[id_col].fillna("").astype(str)
    df_test[asset_col] = df_test[asset_col].fillna("").astype(str)

    df_prod[id_col] = df_prod[id_col].fillna("").astype(str)
    df_prod[asset_col] = df_prod[asset_col].fillna("").astype(str)

    # create key
    df_test["KEY"] = df_test[id_col] + "||" + df_test[asset_col]
    df_prod["KEY"] = df_prod[id_col] + "||" + df_prod[asset_col]

    df_test = df_test.set_index("KEY")
    df_prod = df_prod.set_index("KEY")

    all_keys = sorted(set(df_test.index).union(set(df_prod.index)))

    # ignore System ID columns
    def is_system_col(col):
        return "system" in col.lower() and "id" in col.lower()

    common_cols = [
        c for c in df_test.columns.intersection(df_prod.columns)
        if c not in [id_col, asset_col, "KEY"]
        and not is_system_col(c)
    ]

    results = []

    for key in all_keys:
        row_test = df_test.loc[key] if key in df_test.index else pd.Series()
        row_prod = df_prod.loc[key] if key in df_prod.index else pd.Series()

        contract = row_test.get(id_col, row_prod.get(id_col, ""))
        asset = row_test.get(asset_col, row_prod.get(asset_col, ""))

        row_result = {
            id_col: contract,
            asset_col: asset
        }

        for col in common_cols:
            val_test = row_test.get(col)
            val_prod = row_prod.get(col)

            ok_a, fa = _try_parse_number(val_test)
            ok_b, fb = _try_parse_number(val_prod)

            if ok_a and ok_b:
                row_result[col] = fa - fb
            else:
                row_result[col] = str(val_test) == str(val_prod)

        results.append(row_result)

    return pd.DataFrame(results)


# =========================
# 🇩🇪 UI
# =========================

with tab_de:
    st.subheader("Report Vergleich (CSV)")

    file_test = st.file_uploader("Test-Datei", type=["csv"], key="de_test")
    file_prod = st.file_uploader("Prod-Datei", type=["csv"], key="de_prod")

    if file_test and file_prod:
        df_test = load_report(file_test)
        df_prod = load_report(file_prod)

        df_diff = compare_reports(df_test, df_prod, "Vertrags-ID", "Asset-ID")

        st.dataframe(df_diff, use_container_width=True)

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df_diff.to_excel(writer, index=False)

        st.download_button("📥 Ergebnis herunterladen", data=out.getvalue(), file_name="vergleich.xlsx")


# =========================
# 🇬🇧 UI
# =========================

with tab_en:
    st.subheader("Report Comparison (CSV)")

    file_test = st.file_uploader("Test File", type=["csv"], key="en_test")
    file_prod = st.file_uploader("Prod File", type=["csv"], key="en_prod")

    if file_test and file_prod:
        df_test = load_report(file_test)
        df_prod = load_report(file_prod)

        df_diff = compare_reports(df_test, df_prod, "Contract ID", "Asset ID")

        st.dataframe(df_diff, use_container_width=True)

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df_diff.to_excel(writer, index=False)

        st.download_button("📥 Download result", data=out.getvalue(), file_name="comparison.xlsx")
