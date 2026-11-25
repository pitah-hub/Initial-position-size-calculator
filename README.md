# Position Size Calculator

A Streamlit trading utility for calculating position size, risk, target allocations, margin, and estimated liquidation levels.

The calculation engine is isolated in `calculator_engine.py`; `app.py` is the presentation layer and calls the engine directly.

## Run locally

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Open the local address Streamlit displays, usually `http://localhost:8501`.

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. In Streamlit Community Cloud, select **Create app** and choose the repository and branch.
3. Set the main file path to `app.py`.
4. Deploy. Streamlit installs the dependency declared in `requirements.txt` automatically.

Do not commit `.streamlit/secrets.toml` if you create one; it is excluded by `.gitignore`.
