import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Comparison Tool", layout="wide")
st.title("🔍 Vertrags-/Asset- & Report-Vergleich")

tab_de, tab_en = st.tabs(["🇩🇪 Deutsch", "🇬🇧 English"])

# =========================
# 🔧 COMMON FUNCTIONS
# =========================

TOL = 1.0

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
# 📊 CLOSING LOGIC
# =========================

@st.cache_data
def clean_and_prepare(uploaded_file, id_col, asset_col):
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

    header_1 = df_raw.iloc[1]
    header_2 = df_raw.iloc[2]
    header_3 = df_raw.iloc[3]

    header_1 = header_1.ffill()
    header_2 = header_2.ffill()

    df_data = df_raw.iloc[4:].copy()
    df_data.reset_index(drop=True, inplace=True)

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
# 📑 REPORT LOGIC
# =========================

@st.cache_data
def load_report(file):
    if file.name.endswith(".csv"):
        df_raw = pd.read_csv(file, header=None, dtype=str)
    else:
        df_raw = pd.read_excel(file, header=None, dtype=str)

    header_row = None
    for i in range(len(df_raw)):
        row_str = " ".join(df_raw.iloc[i].astype(str)).lower()
        if "system id" in row_str or "system-id" in row_str:
            header_row = i
            break

    if header_row is None:
        raise ValueError("System ID header not found")

    df = df_raw.iloc[header_row:].copy()
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    # remove total rows
    for i in range(len(df)):
        if "total" in " ".join(df.iloc[i].astype(str)).lower():
            df = df.iloc[:i]
            break

    df.columns = [str(c).strip() for c in df.columns]

    system_id_col = None
    asset_id_col = None

    for c in df.columns:
        lc = c.lower()
        if "system id" in lc or "system-id" in lc:
            system_id_col = c
        if "asset" in lc and "system id" in lc:
            asset_id_col = c

    if not system_id_col or not asset_id_col:
        raise ValueError("ID columns not found")

    df[system_id_col] = df[system_id_col].fillna("").astype(str)
    df[asset_id_col] = df[asset_id_col].fillna("").astype(str)

    df["KEY"] = df[system_id_col] + "||" + df[asset_id_col]

    return df.set_index("KEY")


def compare_reports(df_test, df_prod):
    all_keys = sorted(set(df_test.index).union(set(df_prod.index)))
    common_cols = df_test.columns.intersection(df_prod.columns)

    results = []

    for key in all_keys:
        row = {"KEY": key}

        if key not in df_test.index:
            row["Status"] = "Only in Prod"
        elif key not in df_prod.index:
            row["Status"] = "Only in Test"
        else:
            row["Status"] = "OK"

            for col in common_cols:
                val_test = df_test.loc[key, col]
                val_prod = df_prod.loc[key, col]

                if isinstance(val_test, pd.Series): val_test = val_test.iloc[0]
                if isinstance(val_prod, pd.Series): val_prod = val_prod.iloc[0]

                ok_a, fa = _try_parse_number(val_test)
                ok_b, fb = _try_parse_number(val_prod)

                if ok_a and ok_b:
                    row[col] = fa - fb
                else:
                    row[col] = str(val_test) == str(val_prod)

        results.append(row)

    return pd.DataFrame(results)


# =========================
# 🇩🇪 GERMAN UI
# =========================

with tab_de:
    mode = st.radio("Vergleichstyp wählen", ["Closing", "Report"], key="mode_de")

    file_test = st.file_uploader("Test-Datei", type=["xlsx", "csv"], key="test_de")
    file_prod = st.file_uploader("Prod-Datei", type=["xlsx", "csv"], key="prod_de")

    if file_test and file_prod:

        if mode == "Closing":
            id_col = "Vertrags-ID"
            asset_col = "Asset-ID"

            df_test = clean_and_prepare(file_test, id_col, asset_col)
            df_prod = clean_and_prepare(file_prod, id_col, asset_col)

            df_diff = compare_closing(df_test, df_prod, id_col, asset_col)

        else:
            df_test = load_report(file_test)
            df_prod = load_report(file_prod)

            df_diff = compare_reports(df_test, df_prod)

        st.dataframe(df_diff, use_container_width=True)

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df_diff.to_excel(writer, index=False)

        st.download_button(
            "📥 Ergebnis herunterladen",
            data=out.getvalue(),
            file_name="vergleich.xlsx"
        )


# =========================
# 🇬🇧 ENGLISH UI
# =========================

with tab_en:
    mode = st.radio("Select Comparison Type", ["Closing", "Report"], key="mode_en")

    file_test = st.file_uploader("Test File", type=["xlsx", "csv"], key="test_en")
    file_prod = st.file_uploader("Prod File", type=["xlsx", "csv"], key="prod_en")

    if file_test and file_prod:

        if mode == "Closing":
            id_col = "Contract ID"
            asset_col = "Asset ID"

            df_test = clean_and_prepare(file_test, id_col, asset_col)
            df_prod = clean_and_prepare(file_prod, id_col, asset_col)

            df_diff = compare_closing(df_test, df_prod, id_col, asset_col)

        else:
            df_test = load_report(file_test)
            df_prod = load_report(file_prod)

            df_diff = compare_reports(df_test, df_prod)

        st.dataframe(df_diff, use_container_width=True)

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df_diff.to_excel(writer, index=False)

        st.download_button(
            "📥 Download result",
            data=out.getvalue(),
            file_name="comparison.xlsx"
        )
