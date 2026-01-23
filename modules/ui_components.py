
import streamlit as st

def apply_custom_styles():
    """
    Applies a custom CSS theme to the Streamlit app.
    Theme: Modern Financial Terminal (Dark Mode)
    """
    st.markdown("""
        <style>
        /* Import Google Fonts: Inter (UI) and JetBrains Mono (Code/Data) */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=JetBrains+Mono:wght@400;700&display=swap');

        /* --- Global Reset & Typography --- */
        .stApp {
            background-color: #0d1117; /* GitHub Dark Dimmed equivalent */
            font-family: 'Inter', sans-serif;
            color: #c9d1d9;
        }
        
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            letter-spacing: -0.5px;
            color: #f0f6fc;
        }

        code, .stDataFrame, .stTable {
            font-family: 'JetBrains Mono', monospace !important;
        }

        /* --- Sidebar Styling --- */
        [data-testid="stSidebar"] {
            background-color: #010409; /* Darker than main */
            border-right: 1px solid #30363d;
        }
        
        [data-testid="stSidebar"] h1 {
            font-size: 1.2rem;
            color: #58a6ff; /* Tech Blue */
        }

        /* --- Button Styling --- */
        /* Default Button (Secondary) */
        .stButton > button {
            background-color: #21262d;
            color: #c9d1d9;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .stButton > button:hover {
            background-color: #30363d;
            border-color: #8b949e;
            color: #ffffff;
        }

        /* Primary Button (Action) */
        .stButton > button[kind="primary"] {
            background-color: #238636;
            border-color: #238636;
            color: #ffffff;
            box-shadow: 0 0 10px rgba(35, 134, 54, 0.4);
        }

        .stButton > button[kind="primary"]:hover {
            background-color: #2ea043;
            border-color: #2ea043;
            box-shadow: 0 0 15px rgba(46, 160, 67, 0.6);
        }

        /* --- Data Display & Containers --- */
        /* Expander */
        .streamlit-expanderHeader {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #e6edf3;
        }
        
        /* Status Container */
        [data-testid="stStatusWidget"] {
            background-color: #161b22;
            border: 1px solid #30363d;
        }

        /* Dataframes */
        [data-testid="stDataFrame"] {
            border: 1px solid #30363d;
            border-radius: 0px; /* Sharp edges for terminal look */
        }

        /* Custom Dividers */
        hr {
            margin-top: 2rem;
            margin-bottom: 2rem;
            border: 0;
            border-top: 1px solid #30363d;
        }

        /* --- Custom Utility Classes (Use via st.markdown) --- */
        .bullish {
            color: #3fb950;
            font-weight: bold;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .bearish {
            color: #f85149;
            font-weight: bold;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .highlight {
            color: #58a6ff;
            font-weight: bold;
        }

        </style>
    """, unsafe_allow_html=True)

def render_header():
    """Renders the main header with a custom aesthetic."""
    st.markdown("""
        <div style="padding: 1rem 0; border-bottom: 2px solid #30363d; margin-bottom: 2rem;">
            <h1 style="margin: 0; font-size: 2.5rem; background: -webkit-linear-gradient(45deg, #58a6ff, #8b949e); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                ⚡ GapTrading <span style="font-weight:300; color: #8b949e; -webkit-text-fill-color: #8b949e;">Terminal</span>
            </h1>
            <p style="margin-top: 0.5rem; color: #8b949e; font-family: 'JetBrains Mono', monospace;">
                :: INTRA-DAY MOMENTUM SCANNER ::
            </p>
        </div>
    """, unsafe_allow_html=True)
