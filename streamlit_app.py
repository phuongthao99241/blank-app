import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Comparison Tool", layout="wide")
st.title("🔍 Vertrags-/Asset- & Report-Vergleich")

tab_de, tab_en = st.tabs(["🇩🇪 Deutsch", "🇬🇧 English"])

TOL = 1.0

# =========================
# 🔧 HELPERS
# =========================

def row_to_string(row):
    return " ".join(row.fillna("").astype(str).tolist()).lower()


def _try_parse_number(val):
    if pd.isna(val):
        return False, None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return True, float(val)

    s = str(val).strip()
    if s == "":
        return False, None

    s_clean = (
        s.replace("\xa0", "")
         .replace("€", "")
         .replace("%", "")
         .replace(" ", "")
         .replace("’", "")
         .replace("'", "")
    )

    try:
        return True, float(s_clean.replace(".", "").replace(",", "."))
    except:
        pass

    try:
        return True, float(s_clean.replace(",", ""))
    except:
        pass

    return False, None


def nearly_equal(a, b, tol=TOL):
    ok_a, fa = _try_parse_number(a)
    ok_b, fb = _try_parse_number(b)
    if ok_a and ok_b:
        return abs(fa - fb) < tol
    return False


# =========================
# 📊 CLOSING
# =========================

@st.cache_data
def clean_and_prepare(uploaded_file, id_col, asset_col):
    df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=None)

    header_1 = df_raw.iloc[1]
    header_2 = df_raw.iloc[2]
    header_3 = df_raw.iloc[3]

    header_1 = header_1.ffill()
    header_2 = header_2.ffill()

    df_data = df_raw.iloc[4:].copy().reset_index(drop=True)

    columns_combined = []
    for i in range(len(header_1)):
        if i < 9:
            columns_combined.append(header_1[i])
        else:
            beschreibung = re.sub(r"\s+", " ", str(header_1[i]).strip())
            konto_nr = str(header_2[i]).strip()
            soll_haben = str(header_3[i]).strip()
            columns_combined.append(f"{beschreibung} - {konto_nr}_IFRS16 - {soll_haben}")

    df_data.columns = columns_combined

    df_data[id_col] = df_data[id_col].fillna("").astype(str)
    df_data[asset_col] = df_data[asset_col].fillna("").astype(str)

    return df_data.set_index([id_col, asset_col])


def compare_closing(df_test, df_prod, id_col, asset_col):
    all_keys = sorted(set(df_test.index).union(set(df_prod.index)))
    common_cols = df_test.columns.intersection(df_prod.columns)

    results = []

    for (vertrag, asset) in all_keys:
        row = {id_col: vertrag, asset_col: asset}

        if (vertrag, asset) not in df_test.index:
            row["Differences"] = "Only in Prod"
        elif (vertrag, asset) not in df_prod.index:
            row["Differences"] = "Only in Test"
        else:
            diffs = []
            for col in common_cols:
                val_test = df_test.loc[(vertrag, asset), col]
                val_prod = df_prod.loc[(vertrag, asset), col]

                if isinstance(val_test, pd.Series): val_test = val_test.iloc[0]
                if isinstance(val_prod, pd.Series): val_prod = val_prod.iloc[0]

                if pd.isna(val_test) and pd.isna(val_prod):
                    continue

                if nearly_equal(val_test, val_prod):
                    continue

                if pd.isna(val_test) or pd.isna(val_prod) or val_test != val_prod:
                    diffs.append(f"{col}: Test={val_test} / Prod={val_prod}")

            row["Differences"] = "; ".join(diffs) if diffs else "None"

        results.append(row)

    df = pd.DataFrame(results)
    return df[df["Differences"] != "None"]


# =========================
# 📑 REPORT LOADING
# =========================

@st.cache_data
def load_report(file):
    if file.name.endswith(".csv"):
        try:
            df_raw = pd.read_csv(file, header=None, dtype=str, sep=None, engine="python", encoding="utf-8", on_bad_lines="skip")
        except:
            df_raw = pd.read_csv(file, header=None, dtype=str, sep=None, engine="python", encoding="latin1", on_bad_lines="skip")
    else:
        df_raw = pd.read_excel(file, header=None, dtype=str)

    # find header row
    header_row = None
    for i in range(len(df_raw)):
        if "system" in row_to_string(df_raw.iloc[i]):
            header_row = i
            break

    if header_row is None:
        st.error("❌ Header row not found")
        st.write(df_raw.head(20))
        st.stop()

    df = df_raw.iloc[header_row:].copy()
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    # remove total rows
    for i in range(len(df)):
        if "total" in row_to_string(df.iloc[i]):
            df = df.iloc[:i]
            break

    df.columns = [str(c).strip() for c in df.columns]

    return df


# =========================
# 🔍 ID DETECTION
# =========================

def find_id_columns(df):
    contract_col = None
    asset_col = None

    for c in df.columns:
        lc = str(c).lower().replace("-", " ").replace("_", " ").strip()

        if ("vertrag" in lc or "contract" in lc) and "id" in lc:
            contract_col = c

        if "asset" in lc and "id" in lc:
            asset_col = c

    # fallback
    if contract_col is None:
        for c in df.columns:
            if "vertrag" in str(c).lower() or "contract" in str(c).lower():
                contract_col = c
                break

    if asset_col is None:
        for c in df.columns:
            if "asset" in str(c).lower():
                asset_col = c
                break

    return contract_col, asset_col


# =========================
# 📊 REPORT COMPARISON
# =========================

def compare_reports(df_test, df_prod):

    id_test, asset_test = find_id_columns(df_test)
    id_prod, asset_prod = find_id_columns(df_prod)

    if not id_test or not asset_test:
        st.error("❌ Could not detect ID columns in TEST")
        st.write(df_test.columns.tolist())
        st.stop()

    if not id_prod or not asset_prod:
        st.error("❌ Could not detect ID columns in PROD")
        st.write(df_prod.columns.tolist())
        st.stop()

    df_test = df_test.rename(columns={id_test: "ID", asset_test: "ASSET"})
    df_prod = df_prod.rename(columns={id_prod: "ID", asset_prod: "ASSET"})

    df_test["ID"] = df_test["ID"].fillna("").astype(str)
    df_test["ASSET"] = df_test["ASSET"].fillna("").astype(str)

    df_prod["ID"] = df_prod["ID"].fillna("").astype(str)
    df_prod["ASSET"] = df_prod["ASSET"].fillna("").astype(str)

    df_test["KEY"] = df_test["ID"] + "||" + df_test["ASSET"]
    df_prod["KEY"] = df_prod["ID"] + "||" + df_prod["ASSET"]

    df_test = df_test.set_index("KEY")
    df_prod = df_prod.set_index("KEY")

    all_keys = sorted(set(df_test.index).union(set(df_prod.index)))

    def is_system_col(col):
        lc = col.lower()
        return "system" in lc and "id" in lc

    common_cols = [
        c for c in df_test.columns.intersection(df_prod.columns)
        if not is_system_col(c)
        and c not in ["ID", "ASSET"]
    ]

    results = []

    for key in all_keys:
        row_test = df_test.loc[key] if key in df_test.index else pd.Series()
        row_prod = df_prod.loc[key] if key in df_prod.index else pd.Series()

        contract = row_test.get("ID", row_prod.get("ID", ""))
        asset = row_test.get("ASSET", row_prod.get("ASSET", ""))

        row_result = {"ID": contract, "ASSET": asset}

        for col in common_cols:
            val_test = row_test.get(col, None)
            val_prod = row_prod.get(col, None)

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
    mode = st.radio("Vergleichstyp wählen", ["Closing", "Report"])

    file_test = st.file_uploader("Test-Datei", type=["xlsx", "csv"], key="de1")
    file_prod = st.file_uploader("Prod-Datei", type=["xlsx", "csv"], key="de2")

    if file_test and file_prod:

        if mode == "Closing":
            df_test = clean_and_prepare(file_test, "Vertrags-ID", "Asset-ID")
            df_prod = clean_and_prepare(file_prod, "Vertrags-ID", "Asset-ID")
            df_diff = compare_closing(df_test, df_prod, "Vertrags-ID", "Asset-ID")

        else:
            df_test = load_report(file_test)
            df_prod = load_report(file_prod)
            df_diff = compare_reports(df_test, df_prod)

        st.dataframe(df_diff, use_container_width=True)

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df_diff.to_excel(writer, index=False)

        st.download_button("📥 Ergebnis herunterladen", data=out.getvalue(), file_name="vergleich.xlsx")


# =========================
# 🇬🇧 UI
# =========================

with tab_en:
    mode = st.radio("Select Comparison Type", ["Closing", "Report"])

    file_test = st.file_uploader("Test File", type=["xlsx", "csv"], key="en1")
    file_prod = st.file_uploader("Prod File", type=["xlsx", "csv"], key="en2")

    if file_test and file_prod:

        if mode == "Closing":
            df_test = clean_and_prepare(file_test, "Contract ID", "Asset ID")
            df_prod = clean_and_prepare(file_prod, "Contract ID", "Asset ID")
            df_diff = compare_closing(df_test, df_prod, "Contract ID", "Asset ID")

        else:
            df_test = load_report(file_test)
            df_prod = load_report(file_prod)
            df_diff = compare_reports(df_test, df_prod)

        st.dataframe(df_diff, use_container_width=True)

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df_diff.to_excel(writer, index=False)

        st.download_button("📥 Download result", data=out.getvalue(), file_name="comparison.xlsx")
