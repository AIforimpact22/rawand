import os
import pandas as pd
import streamlit as st

# =========================
# CONFIG
# =========================
DEFAULT_CSV_PATH = "/workspaces/rawand/database.csv"
NA_VALUES = ["", "NA", "NaN", "None", None]

st.set_page_config(page_title="CSV Wizard — Add Row", page_icon="🧭", layout="centered")


# =========================
# HELPERS
# =========================
def load_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        pd.DataFrame().to_csv(path, index=False)
        return pd.DataFrame()
    try:
        return pd.read_csv(path, na_values=NA_VALUES, keep_default_na=True)
    except Exception:
        return pd.DataFrame()

def save_csv_atomic(df: pd.DataFrame, path: str):
    tmp = f"{path}.tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)

def infer_input_type(series: pd.Series) -> str:
    if series.empty:
        return "text"
    if pd.api.types.is_bool_dtype(series):
        return "bool"
    if pd.api.types.is_integer_dtype(series):
        return "int"
    if pd.api.types.is_float_dtype(series):
        return "float"
    # try numeric
    try:
        pd.to_numeric(series.dropna())
        return "float"
    except Exception:
        return "text"

def parse_value(value: str, kind: str):
    if kind == "bool":
        return bool(value)
    if kind == "int":
        if value is None or str(value).strip() == "":
            return None
        try:
            return int(str(value).strip())
        except Exception:
            return None
    if kind == "float":
        if value is None or str(value).strip() == "":
            return None
        try:
            return float(str(value).strip())
        except Exception:
            return None
    return value if value is not None else ""


# =========================
# STATE
# =========================
if "csv_path" not in st.session_state:
    st.session_state.csv_path = DEFAULT_CSV_PATH

if "df" not in st.session_state:
    st.session_state.df = load_csv(st.session_state.csv_path)

# Wizard state
if "wizard_idx" not in st.session_state:
    st.session_state.wizard_idx = 0  # which column we're on

if "temp_row" not in st.session_state:
    # holds values keyed by column name while walking through wizard
    st.session_state.temp_row = {}

def reset_wizard(clear_values: bool = True):
    st.session_state.wizard_idx = 0
    if clear_values:
        st.session_state.temp_row = {}

# =========================
# UI: HEADER / PATH
# =========================
st.title("🧭 Add New Row — Step-by-Step")
st.caption(f"CSV path: {st.session_state.csv_path}")

df = st.session_state.df

# If CSV has no headers, ask for them first
if df.shape[1] == 0:
    st.info("Your CSV has no columns yet. Create headers to start the wizard.")
    cols_input = st.text_input(
        "Column names (comma-separated)",
        value="RespondentID,Country,YearsExperience,PrimaryDesignTool,AIUsageFrequency,AIApplications,PerceivedBenefits,MainConcerns,SatisfactionScore,WouldRecommendAI",
    )
    if st.button("Create headers"):
        cols = [c.strip() for c in cols_input.split(",") if c.strip()]
        if not cols:
            st.error("Please enter at least one column name.")
        else:
            st.session_state.df = pd.DataFrame(columns=cols)
            save_csv_atomic(st.session_state.df, st.session_state.csv_path)
            reset_wizard(clear_values=True)
            st.success("Headers created. Wizard is ready.")
            st.rerun()
else:
    cols = df.columns.tolist()
    kinds = {c: infer_input_type(df[c]) for c in cols}
    total = len(cols)
    idx = st.session_state.wizard_idx
    current_col = cols[idx]

    # Top status: total + position
    st.subheader(f"Field {idx + 1} of {total}  •  Total inputs: {total}")
    st.progress((idx + 1) / total)

    # Ensure prior value exists in temp_row
    if current_col not in st.session_state.temp_row:
        # sensible defaults
        if kinds[current_col] == "bool":
            st.session_state.temp_row[current_col] = False
        else:
            st.session_state.temp_row[current_col] = ""

    # ============ SINGLE FIELD FORM ============
    st.markdown("### Enter value")
    with st.form("step_form", clear_on_submit=False):
        kind = kinds[current_col]
        label = f"{current_col} ({kind})"

        if kind == "bool":
            val = st.checkbox(label, value=bool(st.session_state.temp_row[current_col]))
        elif kind == "int":
            # use text_input to allow blanks, parse later
            val = st.text_input(label, value=str(st.session_state.temp_row[current_col] or ""))
        elif kind == "float":
            val = st.text_input(label, value=str(st.session_state.temp_row[current_col] or ""))
        else:
            val = st.text_input(label, value=str(st.session_state.temp_row[current_col] or ""))

        col_a, col_b, col_c = st.columns([1,1,1])
        go_back = col_a.form_submit_button("⬅️ Back", disabled=(idx == 0))
        go_next = col_b.form_submit_button("Next ➡️", disabled=(idx < total - 1 and False) is False and False)  # no-op, we control below
        save_done = col_c.form_submit_button("✅ Save Row", disabled=(idx != total - 1))

        # Store current field value in temp storage
        st.session_state.temp_row[current_col] = val

    # Button logic outside the form (to avoid double submit issues)
    # Back
    if go_back and idx > 0:
        st.session_state.wizard_idx -= 1
        st.rerun()

    # Next (only if not last field)
    if go_next and idx < total - 1:
        st.session_state.wizard_idx += 1
        st.rerun()

    # Save Row at the end
    if save_done and idx == total - 1:
        # finalize values with parsing by kind
        final_row = {}
        for c in cols:
            final_row[c] = parse_value(st.session_state.temp_row.get(c, ""), kinds[c])

        new_df = pd.concat([df, pd.DataFrame([final_row])], ignore_index=True)
        save_csv_atomic(new_df, st.session_state.csv_path)
        st.session_state.df = new_df
        st.success("Row saved to CSV ✅")

        # reset for a new entry
        reset_wizard(clear_values=True)

        # Optionally show the new last row
        with st.expander("Preview last saved row", expanded=True):
            st.dataframe(pd.DataFrame([final_row]), hide_index=True, use_container_width=True)

    # Utility row under the form
    col1, col2, col3 = st.columns([1,1,1])
    if col1.button("Reset wizard"):
        reset_wizard(clear_values=True)
        st.rerun()
    if col2.button("Jump to first"):
        st.session_state.wizard_idx = 0
        st.rerun()
    if col3.button("Jump to last"):
        st.session_state.wizard_idx = total - 1
        st.rerun()

    # Optional context: show what you've entered so far
    with st.expander("Current values (unsaved draft)", expanded=False):
        preview = {c: st.session_state.temp_row.get(c, "") for c in cols}
        st.dataframe(pd.DataFrame([preview]), hide_index=True, use_container_width=True)
